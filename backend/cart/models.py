"""
Cart domain models for Efferra.

A Cart is temporary working state — it represents an in-progress shopping
session before checkout converts it into an Order.

Cart → CartItem → ProductVariant (live pointer, no snapshot here)

Key rules:
- Cart is identified by a UUID token (session/anonymous ownership).
- CartItem points to the live ProductVariant; snapshot happens at order creation.
- Totals are not stored on Cart — they are always derived from live variant prices.
- A Cart has no billing/shipping data; that belongs to checkout and Order.
"""

import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _


class Cart(models.Model):
    """
    Represents an active shopping basket before an order is placed.

    Identified by a UUID token exchanged with the frontend via API.
    No user account link is required — carts are anonymous by default.
    """

    token = models.UUIDField(
        _("token"),
        default=uuid.uuid4,
        unique=True,
        editable=False,
        help_text=_("Opaque identifier sent to the frontend to claim this cart."),
    )
    # Shipping country is captured early to allow shipping cost preview.
    # ISO 3166-1 alpha-2, e.g. "NL", "DE". Blank until user selects country.
    shipping_country = models.CharField(
        _("shipping country"),
        max_length=2,
        blank=True,
        help_text=_("ISO 3166-1 alpha-2. Used for shipping cost preview before checkout."),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("cart")
        verbose_name_plural = _("carts")

    def __str__(self) -> str:
        return f"Cart {self.token}"

    @property
    def item_count(self) -> int:
        return sum(item.quantity for item in self.items.all())


class CartItem(models.Model):
    """
    One selected ProductVariant inside a Cart with a quantity.

    Points to the live ProductVariant — no price snapshot here.
    Snapshot happens when an Order is created from this cart.
    """

    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name=_("cart"),
    )
    variant = models.ForeignKey(
        "catalog.ProductVariant",
        on_delete=models.PROTECT,
        related_name="cart_items",
        verbose_name=_("product variant"),
    )
    quantity = models.PositiveIntegerField(_("quantity"), default=1)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("cart item")
        verbose_name_plural = _("cart items")
        # One row per variant per cart.
        constraints = [
            models.UniqueConstraint(fields=["cart", "variant"], name="unique_cart_variant")
        ]

    def __str__(self) -> str:
        return f"{self.quantity}× {self.variant} in {self.cart}"
