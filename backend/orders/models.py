"""
Order domain models for Efferra.

An Order is the final business record created from a Cart at checkout.

Structure:
    Order
    ├── shipping_address (embedded snapshot fields)
    ├── billing_address  (embedded snapshot fields, or "same as shipping" flag)
    ├── guest customer fields (email, name)
    └── OrderItem (one per line, full purchase snapshot)

Key rules:
- Order stores independent snapshots of everything needed to remain correct
  if catalog data is later changed or deleted.
- OrderItem is a historical record, not a live catalog pointer (though it
  keeps nullable FK references for traceability as long as the variant exists).
- Totals (subtotal, shipping, grand_total) are stored on Order to freeze the
  business record at time of purchase.
- Stock is reserved at order creation. The order itself is the reservation
  record: each OrderItem.quantity is decremented from ProductVariant.stock
  when the order is created, and restored if the payment flow ends in
  payment_failed / cancelled / expired. mark_paid commits the sale (no
  stock change). The reservation timeout is 30 minutes, controlled by
  Order.RESERVATION_TIMEOUT.
- Webhook is the source of truth for paid/refunded transitions. The
  helper methods in this module encode the legal transitions and are
  written to be idempotent so duplicate webhook deliveries are safe.
- Guest checkout requires no user account.
"""

import uuid
from datetime import timedelta

from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class InvalidOrderTransition(Exception):
    """Raised when an order transition is not allowed from the current status."""


class Order(models.Model):
    """
    The placed order as the central business record.

    Contains:
    - Public order number for customer communication.
    - Guest customer identity (no user account required).
    - Shipping and billing address snapshots.
    - Frozen totals at time of purchase.
    - Lifecycle status.
    """

    class Status(models.TextChoices):
        # Order placed; stock reserved; no payment session opened yet.
        PENDING = "pending", _("Pending")
        # Payment session opened; awaiting webhook confirmation.
        PENDING_PAYMENT = "pending_payment", _("Pending payment")
        # Confirmed paid via webhook. Stock is committed.
        PAID = "paid", _("Paid")
        # Shipped / dispatched (post-paid business state).
        FULFILLED = "fulfilled", _("Fulfilled / Shipped")
        # Last payment attempt failed terminally; reserved stock has been released.
        PAYMENT_FAILED = "payment_failed", _("Payment failed")
        # Reservation expired before any successful payment; reserved stock released.
        EXPIRED = "expired", _("Expired")
        # Customer or admin cancelled before payment; reserved stock released.
        CANCELLED = "cancelled", _("Cancelled")
        # Full refund completed (admin-triggered, MVP).
        REFUNDED = "refunded", _("Refunded")

    #: Statuses where the order is still working toward a successful payment.
    PRE_PAID_STATUSES = frozenset({"pending", "pending_payment"})

    #: Statuses where reserved stock should be considered released.
    RESERVATION_RELEASED_STATUSES = frozenset(
        {"payment_failed", "expired", "cancelled"}
    )

    #: Default reservation lifetime; see PAYMENTS.md and CLAUDE.md.
    RESERVATION_TIMEOUT = timedelta(minutes=30)

    # Public reference shown to the customer (e.g., in confirmation emails).
    order_number = models.CharField(
        _("order number"),
        max_length=32,
        unique=True,
        editable=False,
        help_text=_("Human-readable public identifier, e.g. EFF-20240001."),
    )

    # Internal UUID for safe API exposure without leaking sequential IDs.
    reference = models.UUIDField(
        _("reference"),
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )

    # --- Guest customer identity ---
    email = models.EmailField(_("email"))
    first_name = models.CharField(_("first name"), max_length=100)
    last_name = models.CharField(_("last name"), max_length=100)
    phone = models.CharField(_("phone"), max_length=30, blank=True)
    company_name = models.CharField(
        _("company name"),
        max_length=200,
        blank=True,
        help_text=_("Optional. For B2B or gift orders."),
    )

    # --- Shipping address snapshot ---
    shipping_full_name = models.CharField(_("shipping full name"), max_length=200)
    shipping_address_line_1 = models.CharField(_("shipping address line 1"), max_length=200)
    shipping_address_line_2 = models.CharField(
        _("shipping address line 2"), max_length=200, blank=True
    )
    shipping_postal_code = models.CharField(_("shipping postal code"), max_length=20)
    shipping_city = models.CharField(_("shipping city"), max_length=100)
    shipping_region = models.CharField(
        _("shipping region / state"),
        max_length=100,
        blank=True,
        help_text=_("Province or state. Optional for most EU addresses."),
    )
    shipping_country = models.CharField(
        _("shipping country"),
        max_length=2,
        help_text=_("ISO 3166-1 alpha-2 country code."),
    )
    shipping_phone = models.CharField(_("shipping phone"), max_length=30, blank=True)

    # --- Billing address snapshot ---
    # When billing_same_as_shipping is True, the billing_* fields are left blank
    # and the shipping address is treated as billing. Application layer enforces this.
    billing_same_as_shipping = models.BooleanField(
        _("billing same as shipping"),
        default=True,
    )
    billing_full_name = models.CharField(_("billing full name"), max_length=200, blank=True)
    billing_address_line_1 = models.CharField(
        _("billing address line 1"), max_length=200, blank=True
    )
    billing_address_line_2 = models.CharField(
        _("billing address line 2"), max_length=200, blank=True
    )
    billing_postal_code = models.CharField(_("billing postal code"), max_length=20, blank=True)
    billing_city = models.CharField(_("billing city"), max_length=100, blank=True)
    billing_region = models.CharField(_("billing region / state"), max_length=100, blank=True)
    billing_country = models.CharField(_("billing country"), max_length=2, blank=True)

    # --- Currency ---
    currency = models.CharField(
        _("currency"),
        max_length=3,
        default="EUR",
        help_text=_("ISO 4217. EUR only at launch."),
    )

    # --- Frozen totals (stored, not recalculated from live catalog) ---
    subtotal = models.DecimalField(
        _("subtotal"),
        max_digits=10,
        decimal_places=2,
        help_text=_("Sum of order item line totals before shipping."),
    )
    shipping_total = models.DecimalField(
        _("shipping total"),
        max_digits=8,
        decimal_places=2,
        help_text=_("Flat shipping fee applied at time of order."),
    )
    grand_total = models.DecimalField(
        _("grand total"),
        max_digits=10,
        decimal_places=2,
        help_text=_("subtotal + shipping_total. Frozen at time of order."),
    )

    # --- Status ---
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    # --- Optional notes ---
    customer_note = models.TextField(
        _("customer note"),
        blank=True,
        help_text=_("Optional note from the customer at checkout."),
    )

    # --- Stock reservation timing ---
    # Set when the order is created (with the reserved stock). Cleared when
    # the order moves to a terminal state (paid, payment_failed, expired,
    # cancelled, refunded). Compared against `timezone.now()` by the
    # reservation-sweeper (a Celery beat job, wired in a later phase) to
    # detect orders whose reservation has lapsed.
    reservation_expires_at = models.DateTimeField(
        _("reservation expires at"),
        null=True,
        blank=True,
        help_text=_(
            "When the stock reservation for this order lapses if no successful "
            "payment is recorded. Cleared once the order reaches a terminal state."
        ),
    )

    placed_at = models.DateTimeField(_("placed at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("order")
        verbose_name_plural = _("orders")
        ordering = ["-placed_at"]

    def __str__(self) -> str:
        return f"Order {self.order_number} ({self.get_status_display()})"

    @property
    def billing_address_display(self) -> dict:
        """
        Returns the effective billing address.
        If billing_same_as_shipping, returns shipping address fields.
        """
        if self.billing_same_as_shipping:
            return {
                "full_name": self.shipping_full_name,
                "address_line_1": self.shipping_address_line_1,
                "address_line_2": self.shipping_address_line_2,
                "postal_code": self.shipping_postal_code,
                "city": self.shipping_city,
                "region": self.shipping_region,
                "country": self.shipping_country,
            }
        return {
            "full_name": self.billing_full_name,
            "address_line_1": self.billing_address_line_1,
            "address_line_2": self.billing_address_line_2,
            "postal_code": self.billing_postal_code,
            "city": self.billing_city,
            "region": self.billing_region,
            "country": self.billing_country,
        }

    # ------------------------------------------------------------------
    # Reservation lifecycle
    # ------------------------------------------------------------------

    @classmethod
    def compute_reservation_expiry(cls, *, now=None):
        """Return the timestamp at which a fresh reservation should expire."""
        return (now or timezone.now()) + cls.RESERVATION_TIMEOUT

    @property
    def has_active_reservation(self) -> bool:
        """True iff the order is still holding reserved stock that is not yet expired."""
        if self.status not in self.PRE_PAID_STATUSES:
            return False
        if self.reservation_expires_at is None:
            return False
        return timezone.now() < self.reservation_expires_at

    @property
    def is_reservation_expired(self) -> bool:
        """True iff the reservation deadline has passed and stock has not yet been released."""
        if self.status not in self.PRE_PAID_STATUSES:
            return False
        if self.reservation_expires_at is None:
            return False
        return timezone.now() >= self.reservation_expires_at

    @transaction.atomic
    def release_stock_reservation(self) -> bool:
        """Restore previously-reserved stock to inventory.

        Idempotent: if there is no live reservation (``reservation_expires_at``
        is None), this is a no-op. Does not change order ``status`` — the
        caller is responsible for the status transition. Use ``mark_*`` helpers
        for combined transition + release behavior.

        Returns ``True`` if a release happened, ``False`` if it was a no-op.
        """
        if self.reservation_expires_at is None:
            return False
        # Local import avoids a hard cross-app cycle at module load time.
        from catalog.models import ProductVariant

        for item in self.items.select_related("variant_ref"):
            if item.variant_ref_id is not None:
                ProductVariant.objects.filter(pk=item.variant_ref_id).update(
                    stock=models.F("stock") + item.quantity
                )
        self.reservation_expires_at = None
        self.save(update_fields=["reservation_expires_at", "updated_at"])
        return True

    # ------------------------------------------------------------------
    # Status transitions (idempotent; webhook is the source of truth)
    # ------------------------------------------------------------------

    def _assert_transition(self, new_status: "Order.Status", *, allowed_from) -> None:
        if self.status not in allowed_from:
            raise InvalidOrderTransition(
                f"Cannot move order {self.pk} from {self.status} to {new_status}"
            )

    @transaction.atomic
    def mark_pending_payment(self) -> bool:
        """Transition to pending_payment when a payment session is opened.

        Idempotent: returns False if already in pending_payment.
        """
        if self.status == self.Status.PENDING_PAYMENT:
            return False
        self._assert_transition(
            self.Status.PENDING_PAYMENT, allowed_from={self.Status.PENDING}
        )
        self.status = self.Status.PENDING_PAYMENT
        self.save(update_fields=["status", "updated_at"])
        return True

    @transaction.atomic
    def mark_paid(self) -> bool:
        """Confirm payment success (must originate from a webhook).

        Idempotent: no-op when already paid. Stock was decremented at order
        creation, so this method commits the sale by clearing the reservation
        timer; it does not change ``ProductVariant.stock``.
        """
        if self.status == self.Status.PAID:
            return False
        self._assert_transition(
            self.Status.PAID,
            allowed_from={self.Status.PENDING, self.Status.PENDING_PAYMENT},
        )
        self.status = self.Status.PAID
        self.reservation_expires_at = None
        self.save(update_fields=["status", "reservation_expires_at", "updated_at"])
        return True

    @transaction.atomic
    def mark_payment_failed(self) -> bool:
        """Move to payment_failed and release reserved stock. Idempotent."""
        return self._terminal_pre_paid_release(self.Status.PAYMENT_FAILED)

    @transaction.atomic
    def mark_cancelled(self) -> bool:
        """Customer/admin cancelled before payment. Releases reserved stock. Idempotent."""
        return self._terminal_pre_paid_release(self.Status.CANCELLED)

    @transaction.atomic
    def mark_expired(self) -> bool:
        """Reservation deadline passed. Releases reserved stock. Idempotent."""
        return self._terminal_pre_paid_release(self.Status.EXPIRED)

    def _terminal_pre_paid_release(self, target: "Order.Status") -> bool:
        if self.status == target:
            return False
        self._assert_transition(
            target,
            allowed_from={self.Status.PENDING, self.Status.PENDING_PAYMENT},
        )
        self.release_stock_reservation()
        self.status = target
        self.save(update_fields=["status", "updated_at"])
        return True

    @transaction.atomic
    def mark_fulfilled(self) -> bool:
        """Mark a paid order as shipped/fulfilled."""
        if self.status == self.Status.FULFILLED:
            return False
        self._assert_transition(self.Status.FULFILLED, allowed_from={self.Status.PAID})
        self.status = self.Status.FULFILLED
        self.save(update_fields=["status", "updated_at"])
        return True

    @transaction.atomic
    def mark_refunded(self) -> bool:
        """Mark order as fully refunded (called by Refund.mark_succeeded)."""
        if self.status == self.Status.REFUNDED:
            return False
        self._assert_transition(
            self.Status.REFUNDED,
            allowed_from={self.Status.PAID, self.Status.FULFILLED},
        )
        self.status = self.Status.REFUNDED
        self.save(update_fields=["status", "updated_at"])
        return True

    # ------------------------------------------------------------------
    # Payment helpers
    # ------------------------------------------------------------------

    def active_payment(self):
        """Return the most recent active (non-terminal) payment, or None.

        MVP rule: at most one active payment exists per order at any time.
        Use ``Payment.get_or_create_active`` to honor this on creation.
        """
        from payments.models import Payment

        return (
            self.payments.filter(status__in=Payment.ACTIVE_STATUSES)
            .order_by("-created_at")
            .first()
        )


class OrderItem(models.Model):
    """
    One purchased line item within an Order.

    This is a historical snapshot — it stores all purchase data independently
    so the record remains correct even if catalog data is later changed or removed.

    Nullable FK references to Product/ProductVariant are kept for traceability
    but must never be relied on as authoritative (they can be NULL if deleted).
    """

    order = models.ForeignKey(
        Order,
        on_delete=models.PROTECT,
        related_name="items",
        verbose_name=_("order"),
    )

    # Nullable references for traceability — not authoritative.
    product_ref = models.ForeignKey(
        "catalog.Product",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_items",
        verbose_name=_("product (ref)"),
        help_text=_("Nullable FK for traceability. Do not use as authoritative — use snapshot fields."),
    )
    variant_ref = models.ForeignKey(
        "catalog.ProductVariant",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_items",
        verbose_name=_("variant (ref)"),
        help_text=_("Nullable FK for traceability. Do not use as authoritative — use snapshot fields."),
    )

    # --- Purchase snapshot (authoritative) ---
    product_name = models.CharField(
        _("product name"),
        max_length=200,
        help_text=_("Snapshot of product name at time of purchase."),
    )
    variant_sku = models.CharField(
        _("SKU"),
        max_length=100,
        help_text=_("Snapshot of variant SKU at time of purchase."),
    )
    variant_material = models.CharField(
        _("material"),
        max_length=100,
        help_text=_("Snapshot of variant material at time of purchase."),
    )
    variant_color = models.CharField(
        _("color"),
        max_length=100,
        help_text=_("Snapshot of variant color at time of purchase."),
    )
    variant_finish = models.CharField(
        _("finish"),
        max_length=100,
        blank=True,
        help_text=_("Snapshot of variant finish at time of purchase."),
    )

    # Full human-readable descriptor for display (e.g. "Branch No. 1 / Soy Wax / White").
    variant_description = models.CharField(
        _("variant description"),
        max_length=500,
        help_text=_("Snapshot of full variant display string at time of purchase."),
    )

    # --- Pricing snapshot ---
    unit_price = models.DecimalField(
        _("unit price"),
        max_digits=8,
        decimal_places=2,
        help_text=_("Price per unit at time of purchase, in order currency."),
    )
    quantity = models.PositiveIntegerField(_("quantity"))
    line_total = models.DecimalField(
        _("line total"),
        max_digits=10,
        decimal_places=2,
        help_text=_("unit_price × quantity. Stored, not recalculated."),
    )

    class Meta:
        verbose_name = _("order item")
        verbose_name_plural = _("order items")
        ordering = ["pk"]

    def __str__(self) -> str:
        return f"{self.quantity}× {self.product_name} ({self.variant_sku}) in {self.order}"
