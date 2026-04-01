"""
Catalog domain models for Efferra.

Domain hierarchy:
    Collection → Product → ProductVariant
    ProductImage attaches to Product (and optionally to a specific Variant)

Commerce truth lives on ProductVariant:
    - price  (Decimal, EUR)
    - stock  (integer quantity)
    - active (controls purchase availability)

Public product cards derive a display price as the minimum active variant price.
"""

from decimal import Decimal

from django.db import models
from django.utils.translation import gettext_lazy as _


class Collection(models.Model):
    """
    Artistic series / family grouping.

    Examples: Forest, Faces, Branches.
    Groups products for navigation, storytelling, and merchandising.
    """

    name = models.CharField(_("name"), max_length=100)
    slug = models.SlugField(_("slug"), max_length=120, unique=True)
    description = models.TextField(_("description"), blank=True)
    is_active = models.BooleanField(_("active"), default=True)
    sort_order = models.PositiveSmallIntegerField(_("sort order"), default=0)

    class Meta:
        verbose_name = _("collection")
        verbose_name_plural = _("collections")
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return self.name


class Product(models.Model):
    """
    One candle shape / design family.

    Examples: Branch Candle No. 1, Face Candle No. 2.

    This is NOT the sellable unit — it is the common design identity shared by
    its variants.  Price and stock live on ProductVariant.
    """

    collection = models.ForeignKey(
        Collection,
        on_delete=models.PROTECT,
        related_name="products",
        verbose_name=_("collection"),
    )
    name = models.CharField(_("name"), max_length=200)
    slug = models.SlugField(_("slug"), max_length=220, unique=True)
    description = models.TextField(_("description"), blank=True)
    is_active = models.BooleanField(_("active"), default=True)
    is_limited_edition = models.BooleanField(
        _("limited edition"),
        default=False,
        help_text=_(
            "True when the limited-edition status applies to the whole design. "
            "Individual variants can also be marked limited edition independently."
        ),
    )
    # Physical notes common to all variants of this design (e.g. approximate height).
    # Free-text at MVP; can be structured later if needed.
    dimensions_note = models.CharField(_("dimensions note"), max_length=200, blank=True)
    sort_order = models.PositiveSmallIntegerField(_("sort order"), default=0)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("product")
        verbose_name_plural = _("products")
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return self.name

    @property
    def display_price(self) -> Decimal | None:
        """
        Minimum price across active variants.

        Returns None when no active variant exists.
        Used for 'from €X' display on product cards.
        """
        prices = list(
            self.variants.filter(is_active=True).values_list("price", flat=True)
        )
        return min(prices) if prices else None


class ProductVariant(models.Model):
    """
    The actual purchasable version of a product.

    Examples:
        Branch No. 1 / Soy Wax / White
        Branch No. 1 / Beeswax / Natural
        Face No. 2 / Paraffin / Black / Hand-painted

    This is where commerce truth lives: price, stock, purchase availability.
    """

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="variants",
        verbose_name=_("product"),
    )
    sku = models.CharField(_("SKU"), max_length=100, unique=True)

    # --- Material / color / finish ---
    material = models.CharField(_("material"), max_length=100)
    color = models.CharField(_("color"), max_length=100)
    finish = models.CharField(
        _("finish"),
        max_length=100,
        blank=True,
        help_text=_("E.g. painted, hand-painted, natural finish, raw."),
    )
    is_hand_painted = models.BooleanField(
        _("hand-painted"),
        default=False,
        help_text=_(
            "Explicit flag for hand-painted finish. "
            "Kept separate to allow easy filtering and display."
        ),
    )

    # --- Commerce ---
    price = models.DecimalField(_("price"), max_digits=8, decimal_places=2)
    stock = models.PositiveIntegerField(_("stock"), default=0)
    is_active = models.BooleanField(
        _("active"),
        default=True,
        help_text=_("Only active variants are purchasable and shown on the storefront."),
    )
    is_limited_edition = models.BooleanField(
        _("limited edition"),
        default=False,
        help_text=_("True when limited-edition status is specific to this variant."),
    )

    # Weight in grams; optional at MVP, useful for shipping calculation later.
    weight_grams = models.PositiveIntegerField(_("weight (grams)"), null=True, blank=True)

    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("product variant")
        verbose_name_plural = _("product variants")
        ordering = ["product", "material", "color"]

    def __str__(self) -> str:
        parts = [str(self.product), self.material, self.color]
        if self.finish:
            parts.append(self.finish)
        return " / ".join(parts)

    @property
    def in_stock(self) -> bool:
        return self.stock > 0


class ProductImage(models.Model):
    """
    Visual assets for products and variants.

    An image always belongs to a Product.
    If variant is set, the image is specific to that variant's appearance.
    If variant is None, the image represents the general product/design.

    Single model approach avoids over-complicating the image strategy at MVP.
    """

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="images",
        verbose_name=_("product"),
    )
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.SET_NULL,
        related_name="images",
        null=True,
        blank=True,
        verbose_name=_("variant"),
        help_text=_(
            "Leave blank for general product imagery. "
            "Set to link this image to a specific variant."
        ),
    )
    image = models.ImageField(_("image"), upload_to="catalog/")
    alt_text = models.CharField(_("alt text"), max_length=200, blank=True)
    sort_order = models.PositiveSmallIntegerField(_("sort order"), default=0)
    is_active = models.BooleanField(_("active"), default=True)

    class Meta:
        verbose_name = _("product image")
        verbose_name_plural = _("product images")
        ordering = ["sort_order"]

    def __str__(self) -> str:
        if self.variant:
            return f"{self.product} — {self.variant} (image {self.pk})"
        return f"{self.product} (image {self.pk})"
