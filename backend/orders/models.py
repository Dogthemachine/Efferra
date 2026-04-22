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
- Status transitions are kept simple for MVP; no full workflow engine yet.
- Guest checkout requires no user account.
"""

import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _


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
        PENDING = "pending", _("Pending")
        # Order placed and awaiting payment confirmation via webhook.
        PENDING_PAYMENT = "pending_payment", _("Pending payment")
        PAID = "paid", _("Paid")
        FULFILLED = "fulfilled", _("Fulfilled / Shipped")
        CANCELLED = "cancelled", _("Cancelled")
        REFUNDED = "refunded", _("Refunded")

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
