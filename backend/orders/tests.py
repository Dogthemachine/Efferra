from decimal import Decimal

from django.test import TestCase

from catalog.models import Collection, Product, ProductVariant

from .models import Order, OrderItem


def make_variant(sku="ORD-TEST-001"):
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
        price=Decimal("25.00"),
        stock=10,
    )


def make_order(**kwargs):
    defaults = dict(
        order_number="EFF-20240001",
        email="guest@example.com",
        first_name="Jan",
        last_name="Jansen",
        shipping_full_name="Jan Jansen",
        shipping_address_line_1="Keizersgracht 1",
        shipping_postal_code="1015CJ",
        shipping_city="Amsterdam",
        shipping_country="NL",
        subtotal=Decimal("50.00"),
        shipping_total=Decimal("5.95"),
        grand_total=Decimal("55.95"),
    )
    defaults.update(kwargs)
    return Order.objects.create(**defaults)


class OrderModelTests(TestCase):
    def test_order_str(self):
        order = make_order()
        self.assertIn("EFF-20240001", str(order))
        self.assertIn("Pending", str(order))

    def test_order_reference_is_unique_uuid(self):
        o1 = make_order(order_number="EFF-001")
        o2 = make_order(order_number="EFF-002")
        self.assertNotEqual(o1.reference, o2.reference)

    def test_default_status_is_pending(self):
        order = make_order()
        self.assertEqual(order.status, Order.Status.PENDING)

    def test_status_choices_available(self):
        statuses = [s[0] for s in Order.Status.choices]
        self.assertIn("pending", statuses)
        self.assertIn("pending_payment", statuses)
        self.assertIn("paid", statuses)
        self.assertIn("fulfilled", statuses)
        self.assertIn("cancelled", statuses)
        self.assertIn("refunded", statuses)

    def test_billing_same_as_shipping_default(self):
        order = make_order()
        self.assertTrue(order.billing_same_as_shipping)

    def test_billing_address_display_same_as_shipping(self):
        order = make_order()
        billing = order.billing_address_display
        self.assertEqual(billing["city"], "Amsterdam")
        self.assertEqual(billing["country"], "NL")

    def test_billing_address_display_separate(self):
        order = make_order(
            billing_same_as_shipping=False,
            billing_full_name="B. Betalaar",
            billing_address_line_1="Billing Street 5",
            billing_postal_code="2000AB",
            billing_city="Rotterdam",
            billing_country="NL",
        )
        billing = order.billing_address_display
        self.assertEqual(billing["city"], "Rotterdam")
        self.assertEqual(billing["full_name"], "B. Betalaar")

    def test_order_default_currency_eur(self):
        order = make_order()
        self.assertEqual(order.currency, "EUR")


class OrderItemModelTests(TestCase):
    def setUp(self):
        self.order = make_order()
        self.variant = make_variant()

    def test_order_item_str(self):
        item = OrderItem.objects.create(
            order=self.order,
            product_name="Test Product",
            variant_sku="ORD-TEST-001",
            variant_material="Soy",
            variant_color="White",
            variant_finish="",
            variant_description="Test Product / Soy / White",
            unit_price=Decimal("25.00"),
            quantity=2,
            line_total=Decimal("50.00"),
        )
        self.assertIn("2×", str(item))
        self.assertIn("Test Product", str(item))

    def test_order_item_snapshot_survives_without_variant_ref(self):
        item = OrderItem.objects.create(
            order=self.order,
            product_ref=None,
            variant_ref=None,
            product_name="Deleted Product",
            variant_sku="OLD-SKU",
            variant_material="Beeswax",
            variant_color="Natural",
            variant_finish="",
            variant_description="Deleted Product / Beeswax / Natural",
            unit_price=Decimal("30.00"),
            quantity=1,
            line_total=Decimal("30.00"),
        )
        # Snapshot data must be intact regardless of FK nullability.
        self.assertEqual(item.product_name, "Deleted Product")
        self.assertEqual(item.variant_sku, "OLD-SKU")
        self.assertIsNone(item.product_ref)
        self.assertIsNone(item.variant_ref)

    def test_order_item_with_variant_ref(self):
        item = OrderItem.objects.create(
            order=self.order,
            product_ref=self.variant.product,
            variant_ref=self.variant,
            product_name="Test Product",
            variant_sku="ORD-TEST-001",
            variant_material="Soy",
            variant_color="White",
            variant_finish="",
            variant_description="Test Product / Soy / White",
            unit_price=Decimal("25.00"),
            quantity=1,
            line_total=Decimal("25.00"),
        )
        self.assertEqual(item.variant_ref, self.variant)
