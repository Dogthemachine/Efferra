from decimal import Decimal

from django.db import IntegrityError
from django.test import TestCase

from catalog.models import Collection, Product, ProductVariant

from .models import Cart, CartItem


def make_variant(sku="TEST-001", price="25.00", stock=10):
    collection = Collection.objects.get_or_create(name="Test", slug="test")[0]
    product = Product.objects.get_or_create(
        slug="test-product",
        defaults={"name": "Test Product", "collection": collection},
    )[0]
    return ProductVariant.objects.create(
        product=product,
        sku=sku,
        material="Soy",
        color="White",
        price=Decimal(price),
        stock=stock,
    )


class CartModelTests(TestCase):
    def test_cart_token_is_uuid_and_unique(self):
        c1 = Cart.objects.create()
        c2 = Cart.objects.create()
        self.assertIsNotNone(c1.token)
        self.assertNotEqual(c1.token, c2.token)

    def test_cart_str(self):
        cart = Cart.objects.create()
        self.assertIn("Cart", str(cart))

    def test_item_count_empty_cart(self):
        cart = Cart.objects.create()
        self.assertEqual(cart.item_count, 0)

    def test_item_count_with_items(self):
        cart = Cart.objects.create()
        v = make_variant()
        CartItem.objects.create(cart=cart, variant=v, quantity=3)
        self.assertEqual(cart.item_count, 3)


class CartItemModelTests(TestCase):
    def setUp(self):
        self.cart = Cart.objects.create()
        self.variant = make_variant()

    def test_cart_item_str(self):
        item = CartItem.objects.create(cart=self.cart, variant=self.variant, quantity=2)
        self.assertIn("2×", str(item))

    def test_unique_constraint_per_variant(self):
        CartItem.objects.create(cart=self.cart, variant=self.variant, quantity=1)
        with self.assertRaises(IntegrityError):
            CartItem.objects.create(cart=self.cart, variant=self.variant, quantity=1)

    def test_different_carts_same_variant_allowed(self):
        cart2 = Cart.objects.create()
        CartItem.objects.create(cart=self.cart, variant=self.variant, quantity=1)
        # No error expected for a different cart with the same variant.
        item = CartItem.objects.create(cart=cart2, variant=self.variant, quantity=1)
        self.assertIsNotNone(item.pk)
