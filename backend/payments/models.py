"""
Payment domain models for Efferra.

Scope of this module
--------------------
This file defines the *contract layer* for the MVP payment flow described in
PAYMENTS.md and the locked-direction notes for the MVP payment-flow card:

- ``Payment``       — one row per payment attempt against an Order.
- ``Refund``        — admin-triggered, full-refund-only for MVP.
- ``WebhookEvent``  — durable record of inbound provider webhook deliveries
                      so duplicate deliveries can be detected and skipped.

What this module deliberately does NOT do
------------------------------------------
- It does not talk to the Mollie API. PSP integration is a later card.
- It does not expose HTTP endpoints. The minimal API contract (see
  ``PAYMENTS.md``) will be wired up once DRF is added to the project.
- It does not enforce a state machine via DB triggers. Transitions are
  represented as small helper methods so they remain easy to reason about.

Key MVP rules baked into this module
------------------------------------
- Webhook is the source of truth: ``Order.mark_paid`` and ``Payment.mark_paid``
  are written so they only flip on confirmed-paid signal (typically a webhook).
- Idempotency: every transition helper is a no-op when already in the target
  terminal state, and ``WebhookEvent.record_delivery`` deduplicates by
  ``provider_event_key``.
- One active payment per order at a time: ``Payment.get_or_create_active``
  reuses any existing non-terminal payment instead of creating duplicates.
- Full refunds only for MVP: ``Refund`` requires ``amount_cents`` to equal
  the parent order's ``grand_total`` (in cents). Partial refunds are
  explicitly rejected.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


PROVIDER_MOLLIE = "mollie"


class InvalidPaymentTransition(Exception):
    """Raised when a payment transition is not allowed from the current status."""


class InvalidRefundOperation(Exception):
    """Raised when a refund cannot be created or transitioned given current state."""


class Payment(models.Model):
    """
    One payment attempt against a single Order.

    A given Order may have multiple Payment rows over its lifetime (e.g. user
    abandoned the first attempt and started a new one), but only one Payment
    is allowed to be in a non-terminal status at any time. Use
    :meth:`get_or_create_active` to obtain the current payable payment.
    """

    class Status(models.TextChoices):
        # Payment row exists locally but no provider session has been opened yet.
        CREATED = "created", _("Created")
        # Provider session/payment created. Customer has not yet completed flow.
        PENDING = "pending", _("Pending")
        # Confirmed paid via webhook. Money has been captured by the PSP.
        PAID = "paid", _("Paid")
        # Provider returned a terminal failure (e.g. card declined).
        FAILED = "failed", _("Failed")
        # User or system explicitly cancelled the payment attempt.
        CANCELLED = "cancelled", _("Cancelled")
        # Provider session expired before completion.
        EXPIRED = "expired", _("Expired")
        # Money has been returned to the customer (full refund for MVP).
        REFUNDED = "refunded", _("Refunded")

    #: Statuses that mean the payment is still capable of completing.
    ACTIVE_STATUSES = frozenset({Status.CREATED, Status.PENDING})

    #: Terminal failure-side statuses that should release reserved stock.
    TERMINAL_RELEASE_STATUSES = frozenset(
        {Status.FAILED, Status.CANCELLED, Status.EXPIRED}
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.PROTECT,
        related_name="payments",
        verbose_name=_("order"),
    )

    provider = models.CharField(
        _("provider"),
        max_length=32,
        default=PROVIDER_MOLLIE,
        help_text=_("PSP identifier. MVP only uses 'mollie'."),
    )
    provider_payment_id = models.CharField(
        _("provider payment id"),
        max_length=128,
        blank=True,
        help_text=_("Reference returned by the PSP after creating the payment."),
    )
    checkout_url = models.URLField(
        _("checkout URL"),
        max_length=500,
        blank=True,
        help_text=_("Hosted checkout URL returned by the PSP. UX-only; never used as truth."),
    )

    amount_cents = models.PositiveIntegerField(
        _("amount in cents"),
        help_text=_("Integer cents to avoid floating-point issues. EUR for MVP."),
    )
    currency = models.CharField(
        _("currency"),
        max_length=3,
        default="EUR",
        help_text=_("ISO 4217. EUR only at launch."),
    )

    status = models.CharField(
        _("status"),
        max_length=16,
        choices=Status.choices,
        default=Status.CREATED,
    )

    idempotency_key = models.CharField(
        _("idempotency key"),
        max_length=64,
        blank=True,
        help_text=_("Sent to the PSP's create-payment call so retries do not duplicate."),
    )

    raw_provider_payload_last = models.JSONField(
        _("raw provider payload (last)"),
        default=dict,
        blank=True,
        help_text=_("Last raw provider payload observed for this payment, for audit/debug."),
    )

    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("payment")
        verbose_name_plural = _("payments")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["provider", "provider_payment_id"]),
            models.Index(fields=["order", "status"]),
        ]
        constraints = [
            # provider_payment_id is optional at create-time but must be unique
            # per provider when set.
            models.UniqueConstraint(
                fields=["provider", "provider_payment_id"],
                name="unique_provider_payment_id",
                condition=~models.Q(provider_payment_id=""),
            ),
        ]

    def __str__(self) -> str:
        return f"Payment {self.id} for order {self.order_id} ({self.get_status_display()})"

    # ------------------------------------------------------------------
    # Status helpers
    # ------------------------------------------------------------------

    @property
    def is_active(self) -> bool:
        return self.status in self.ACTIVE_STATUSES

    @property
    def is_terminal(self) -> bool:
        return not self.is_active

    @property
    def amount_decimal(self) -> Decimal:
        return (Decimal(self.amount_cents) / Decimal(100)).quantize(Decimal("0.01"))

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def get_or_create_active(
        cls,
        order,
        *,
        provider: str = PROVIDER_MOLLIE,
        idempotency_key: str = "",
    ) -> tuple["Payment", bool]:
        """Return the current payable payment for ``order``, creating one if needed.

        Reuses the most recent active (non-terminal) payment when one exists.
        This is the helper that backend code should use to honor the
        "one active payment per order" rule and to make repeated checkout
        submissions idempotent.

        Returns ``(payment, created)``.
        """
        existing = order.active_payment()
        if existing is not None:
            return existing, False
        amount_cents = int((order.grand_total * 100).to_integral_value())
        payment = cls.objects.create(
            order=order,
            provider=provider,
            amount_cents=amount_cents,
            currency=order.currency,
            idempotency_key=idempotency_key,
        )
        return payment, True

    # ------------------------------------------------------------------
    # Transitions (idempotent, raise on illegal moves)
    # ------------------------------------------------------------------

    def _transition(self, new_status: "Payment.Status", *, allowed_from) -> bool:
        """Apply ``new_status``. Returns True if a save happened, False if no-op."""
        if self.status == new_status:
            return False
        if self.status not in allowed_from:
            raise InvalidPaymentTransition(
                f"Cannot move payment {self.pk} from {self.status} to {new_status}"
            )
        self.status = new_status
        self.save(update_fields=["status", "updated_at"])
        return True

    def mark_pending(self, *, provider_payment_id: str = "", checkout_url: str = "") -> bool:
        update_fields = ["status", "updated_at"]
        if provider_payment_id and provider_payment_id != self.provider_payment_id:
            self.provider_payment_id = provider_payment_id
            update_fields.append("provider_payment_id")
        if checkout_url and checkout_url != self.checkout_url:
            self.checkout_url = checkout_url
            update_fields.append("checkout_url")
        if self.status == self.Status.PENDING:
            if len(update_fields) > 2:  # provider_payment_id/checkout_url changed
                self.save(update_fields=update_fields)
                return True
            return False
        if self.status not in {self.Status.CREATED, self.Status.PENDING}:
            raise InvalidPaymentTransition(
                f"Cannot move payment {self.pk} from {self.status} to pending"
            )
        self.status = self.Status.PENDING
        self.save(update_fields=update_fields)
        return True

    def mark_paid(self) -> bool:
        return self._transition(
            self.Status.PAID,
            allowed_from={self.Status.CREATED, self.Status.PENDING},
        )

    def mark_failed(self) -> bool:
        return self._transition(
            self.Status.FAILED,
            allowed_from={self.Status.CREATED, self.Status.PENDING},
        )

    def mark_cancelled(self) -> bool:
        return self._transition(
            self.Status.CANCELLED,
            allowed_from={self.Status.CREATED, self.Status.PENDING},
        )

    def mark_expired(self) -> bool:
        return self._transition(
            self.Status.EXPIRED,
            allowed_from={self.Status.CREATED, self.Status.PENDING},
        )

    def mark_refunded(self) -> bool:
        return self._transition(
            self.Status.REFUNDED,
            allowed_from={self.Status.PAID},
        )


class Refund(models.Model):
    """
    Admin-triggered full refund of a paid order.

    MVP scope: only full refunds. ``amount_cents`` must equal the parent
    order's ``grand_total`` in cents. Partial refunds are explicitly
    rejected and will be added in a later phase.
    """

    class Status(models.TextChoices):
        REQUESTED = "requested", _("Requested")
        PROCESSING = "processing", _("Processing")
        SUCCEEDED = "succeeded", _("Succeeded")
        FAILED = "failed", _("Failed")
        CANCELLED = "cancelled", _("Cancelled")

    ACTIVE_STATUSES = frozenset({Status.REQUESTED, Status.PROCESSING})

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.PROTECT,
        related_name="refunds",
        verbose_name=_("order"),
    )
    payment = models.ForeignKey(
        Payment,
        on_delete=models.PROTECT,
        related_name="refunds",
        verbose_name=_("payment"),
    )

    provider_refund_id = models.CharField(
        _("provider refund id"),
        max_length=128,
        blank=True,
        help_text=_("Reference returned by the PSP after creating the refund."),
    )

    amount_cents = models.PositiveIntegerField(
        _("amount in cents"),
        help_text=_("Must equal order.grand_total (in cents) for MVP — full refund only."),
    )
    currency = models.CharField(
        _("currency"),
        max_length=3,
        default="EUR",
    )

    status = models.CharField(
        _("status"),
        max_length=16,
        choices=Status.choices,
        default=Status.REQUESTED,
    )

    idempotency_key = models.CharField(
        _("idempotency key"),
        max_length=64,
        blank=True,
        help_text=_("Sent to the PSP's refund call so retries do not duplicate."),
    )

    created_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_refunds",
        verbose_name=_("created by"),
        help_text=_("Staff user who triggered the refund."),
    )

    raw_provider_payload_last = models.JSONField(
        _("raw provider payload (last)"),
        default=dict,
        blank=True,
    )

    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("refund")
        verbose_name_plural = _("refunds")
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["payment", "provider_refund_id"],
                name="unique_payment_provider_refund_id",
                condition=~models.Q(provider_refund_id=""),
            ),
        ]

    def __str__(self) -> str:
        return f"Refund {self.id} for order {self.order_id} ({self.get_status_display()})"

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    @transaction.atomic
    def request_full_refund(
        cls,
        order,
        *,
        created_by=None,
        idempotency_key: str = "",
    ) -> "Refund":
        """Create a full-refund request for ``order``.

        MVP rules enforced here:
        - The order must be in ``paid`` status.
        - The order must have a ``paid`` Payment to refund against.
        - There must be no other active refund already in flight.
        - ``amount_cents`` is set to the order's grand total — partial
          refunds are not allowed.
        """
        from orders.models import Order as OrderModel  # local import avoids cycles

        if order.status != OrderModel.Status.PAID:
            raise InvalidRefundOperation(
                f"Order {order.pk} cannot be refunded from status {order.status}; must be paid."
            )

        paid_payment = order.payments.filter(status=Payment.Status.PAID).order_by("-created_at").first()
        if paid_payment is None:
            raise InvalidRefundOperation(
                f"Order {order.pk} has no paid payment to refund against."
            )

        active_refund_exists = order.refunds.filter(status__in=cls.ACTIVE_STATUSES).exists()
        if active_refund_exists:
            raise InvalidRefundOperation(
                f"Order {order.pk} already has an active refund in flight."
            )

        amount_cents = int((order.grand_total * 100).to_integral_value())
        return cls.objects.create(
            order=order,
            payment=paid_payment,
            amount_cents=amount_cents,
            currency=order.currency,
            created_by=created_by,
            idempotency_key=idempotency_key,
        )

    # ------------------------------------------------------------------
    # Status helpers
    # ------------------------------------------------------------------

    @property
    def is_active(self) -> bool:
        return self.status in self.ACTIVE_STATUSES

    @property
    def is_terminal(self) -> bool:
        return not self.is_active

    def _transition(self, new_status: "Refund.Status", *, allowed_from) -> bool:
        if self.status == new_status:
            return False
        if self.status not in allowed_from:
            raise InvalidRefundOperation(
                f"Cannot move refund {self.pk} from {self.status} to {new_status}"
            )
        self.status = new_status
        self.save(update_fields=["status", "updated_at"])
        return True

    def mark_processing(self, *, provider_refund_id: str = "") -> bool:
        update_fields = ["status", "updated_at"]
        if provider_refund_id and provider_refund_id != self.provider_refund_id:
            self.provider_refund_id = provider_refund_id
            update_fields.append("provider_refund_id")
        if self.status == self.Status.PROCESSING:
            if len(update_fields) > 2:
                self.save(update_fields=update_fields)
                return True
            return False
        if self.status not in {self.Status.REQUESTED, self.Status.PROCESSING}:
            raise InvalidRefundOperation(
                f"Cannot move refund {self.pk} from {self.status} to processing"
            )
        self.status = self.Status.PROCESSING
        self.save(update_fields=update_fields)
        return True

    @transaction.atomic
    def mark_succeeded(self) -> bool:
        if self.status == self.Status.SUCCEEDED:
            return False
        moved = self._transition(
            self.Status.SUCCEEDED,
            allowed_from={self.Status.REQUESTED, self.Status.PROCESSING},
        )
        if moved:
            self.payment.mark_refunded()
            self.order.mark_refunded()
        return moved

    def mark_failed(self) -> bool:
        return self._transition(
            self.Status.FAILED,
            allowed_from={self.Status.REQUESTED, self.Status.PROCESSING},
        )

    def mark_cancelled(self) -> bool:
        return self._transition(
            self.Status.CANCELLED,
            allowed_from={self.Status.REQUESTED, self.Status.PROCESSING},
        )


class WebhookEvent(models.Model):
    """
    Durable record of one inbound provider webhook delivery.

    The HTTP webhook handler must call :meth:`record_delivery` first.
    If ``created`` is ``False`` the delivery is a duplicate and must
    not produce side effects again.

    The actual fetch-and-apply work happens in a worker job (Celery
    once wired) keyed by ``provider_payment_id``; this row exists
    purely to deduplicate deliveries and to provide an audit trail.
    """

    class ProcessingStatus(models.TextChoices):
        PENDING = "pending", _("Pending")
        SUCCESS = "success", _("Success")
        FAILED = "failed", _("Failed")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    provider = models.CharField(
        _("provider"),
        max_length=32,
        default=PROVIDER_MOLLIE,
    )
    provider_event_key = models.CharField(
        _("provider event key"),
        max_length=255,
        help_text=_(
            "Unique key per delivery used for dedup. For Mollie this is typically "
            "the provider payment id reported in the webhook body."
        ),
    )
    payload = models.JSONField(
        _("payload"),
        default=dict,
        blank=True,
        help_text=_("Raw inbound payload as received."),
    )

    received_at = models.DateTimeField(_("received at"), auto_now_add=True)
    processed_at = models.DateTimeField(_("processed at"), null=True, blank=True)

    processing_status = models.CharField(
        _("processing status"),
        max_length=16,
        choices=ProcessingStatus.choices,
        default=ProcessingStatus.PENDING,
    )
    processing_error = models.TextField(
        _("processing error"),
        blank=True,
        help_text=_("Error message if processing_status is failed."),
    )

    class Meta:
        verbose_name = _("webhook event")
        verbose_name_plural = _("webhook events")
        ordering = ["-received_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "provider_event_key"],
                name="unique_provider_event_key",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"WebhookEvent {self.provider}/{self.provider_event_key} "
            f"({self.get_processing_status_display()})"
        )

    @classmethod
    def record_delivery(
        cls,
        *,
        provider: str,
        provider_event_key: str,
        payload: dict | None = None,
    ) -> tuple["WebhookEvent", bool]:
        """Record an inbound webhook delivery idempotently.

        Returns ``(event, created)``. When ``created`` is ``False`` the caller
        has received a duplicate delivery and MUST NOT trigger side effects
        again — it should still acknowledge the delivery to the provider.
        """
        return cls.objects.get_or_create(
            provider=provider,
            provider_event_key=provider_event_key,
            defaults={"payload": payload or {}},
        )

    def mark_processed_success(self) -> None:
        self.processing_status = self.ProcessingStatus.SUCCESS
        self.processing_error = ""
        self.processed_at = timezone.now()
        self.save(update_fields=["processing_status", "processing_error", "processed_at"])

    def mark_processed_failed(self, error_message: str) -> None:
        self.processing_status = self.ProcessingStatus.FAILED
        self.processing_error = error_message[:5000]
        self.processed_at = timezone.now()
        self.save(update_fields=["processing_status", "processing_error", "processed_at"])
