"""
Tests for the MVP payment-flow contract.

These tests cover the model-level state machine, idempotency rules,
reservation lifecycle, and full-refund-only refund behavior. They do
not exercise HTTP endpoints — those are deliberately out of scope for
the contract card (no DRF wired yet).
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from catalog.models import Collection, Product, ProductVariant
from orders.models import InvalidOrderTransition, Order, OrderItem

from .models import (
    InvalidPaymentTransition,
    InvalidRefundOperation,
    Payment,
    Refund,
    WebhookEvent,
)


def _make_variant(*, sku="PMT-TEST-001", price="25.00", stock=10):
    collection, _ = Collection.objects.get_or_create(name="Test", slug="test")
    product, _ = Product.objects.get_or_create(
        slug="test-product",
        defaults={"name": "Test Product", "collection": collection},
    )
    return ProductVariant.objects.create(
        product=product,
        sku=sku,
        material="Soy",
        color="White",
        price=Decimal(price),
        stock=stock,
    )


def _make_order(*, status=Order.Status.PENDING, with_reservation=True, **overrides):
    """Create an Order with one OrderItem (variant_ref set) and a 30-min reservation."""
    variant = overrides.pop("variant", None) or _make_variant(
        sku=overrides.pop("variant_sku", "PMT-TEST-001"),
        stock=overrides.pop("variant_stock", 10),
    )
    quantity = overrides.pop("quantity", 2)
    unit_price = variant.price
    line_total = unit_price * quantity

    defaults = dict(
        order_number=overrides.pop("order_number", "EFF-PMT-001"),
        email="guest@example.com",
        first_name="Jan",
        last_name="Jansen",
        shipping_full_name="Jan Jansen",
        shipping_address_line_1="Keizersgracht 1",
        shipping_postal_code="1015CJ",
        shipping_city="Amsterdam",
        shipping_country="NL",
        subtotal=line_total,
        shipping_total=Decimal("5.95"),
        grand_total=line_total + Decimal("5.95"),
        status=status,
    )
    defaults.update(overrides)
    if with_reservation and status in Order.PRE_PAID_STATUSES:
        defaults["reservation_expires_at"] = Order.compute_reservation_expiry()
    order = Order.objects.create(**defaults)
    OrderItem.objects.create(
        order=order,
        product_ref=variant.product,
        variant_ref=variant,
        product_name=variant.product.name,
        variant_sku=variant.sku,
        variant_material=variant.material,
        variant_color=variant.color,
        variant_finish=variant.finish,
        variant_description=f"{variant.product.name} / {variant.material} / {variant.color}",
        unit_price=unit_price,
        quantity=quantity,
        line_total=line_total,
    )
    # Mimic stock reservation at order-creation time (the create-order API,
    # which is a separate card, will encapsulate this; the model-level tests
    # need the post-reservation state to exercise release behavior).
    if with_reservation and status in Order.PRE_PAID_STATUSES:
        ProductVariant.objects.filter(pk=variant.pk).update(
            stock=variant.stock - quantity
        )
        variant.refresh_from_db()
    return order, variant


# ---------------------------------------------------------------------------
# Order reservation lifecycle
# ---------------------------------------------------------------------------


class OrderReservationTests(TestCase):
    def test_compute_reservation_expiry_is_30_minutes(self):
        before = timezone.now()
        expiry = Order.compute_reservation_expiry()
        delta = expiry - before
        # Allow a small wallclock delta but assert it's the 30-min window.
        self.assertGreaterEqual(delta, timedelta(minutes=29, seconds=59))
        self.assertLessEqual(delta, timedelta(minutes=30, seconds=1))

    def test_reservation_active_for_pending_order(self):
        order, _ = _make_order()
        self.assertTrue(order.has_active_reservation)
        self.assertFalse(order.is_reservation_expired)

    def test_reservation_expired_when_deadline_passed(self):
        order, _ = _make_order()
        order.reservation_expires_at = timezone.now() - timedelta(minutes=1)
        order.save(update_fields=["reservation_expires_at"])
        self.assertFalse(order.has_active_reservation)
        self.assertTrue(order.is_reservation_expired)

    def test_release_stock_reservation_restores_inventory(self):
        order, variant = _make_order(variant_stock=10, quantity=3)
        # Stock decremented to 7 by _make_order.
        self.assertEqual(variant.stock, 7)
        order.release_stock_reservation()
        variant.refresh_from_db()
        self.assertEqual(variant.stock, 10)
        order.refresh_from_db()
        self.assertIsNone(order.reservation_expires_at)

    def test_release_stock_reservation_is_idempotent(self):
        order, variant = _make_order(variant_stock=10, quantity=3)
        first = order.release_stock_reservation()
        second = order.release_stock_reservation()
        self.assertTrue(first)
        self.assertFalse(second)
        variant.refresh_from_db()
        self.assertEqual(variant.stock, 10)


# ---------------------------------------------------------------------------
# Order status transitions
# ---------------------------------------------------------------------------


class OrderTransitionTests(TestCase):
    def test_mark_pending_payment_from_pending(self):
        order, _ = _make_order()
        self.assertTrue(order.mark_pending_payment())
        self.assertEqual(order.status, Order.Status.PENDING_PAYMENT)

    def test_mark_pending_payment_idempotent(self):
        order, _ = _make_order(status=Order.Status.PENDING_PAYMENT)
        self.assertFalse(order.mark_pending_payment())

    def test_mark_paid_clears_reservation_no_stock_change(self):
        order, variant = _make_order(variant_stock=10, quantity=4)
        # stock was 10, decremented to 6 at reservation
        self.assertEqual(variant.stock, 6)
        order.mark_pending_payment()
        order.mark_paid()
        order.refresh_from_db()
        variant.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)
        # Stock stays at 6 — sale is committed.
        self.assertEqual(variant.stock, 6)
        self.assertIsNone(order.reservation_expires_at)

    def test_mark_paid_idempotent(self):
        order, _ = _make_order()
        order.mark_paid()
        # second call is a no-op
        self.assertFalse(order.mark_paid())

    def test_mark_payment_failed_releases_stock(self):
        order, variant = _make_order(variant_stock=10, quantity=2)
        self.assertEqual(variant.stock, 8)
        order.mark_pending_payment()
        order.mark_payment_failed()
        order.refresh_from_db()
        variant.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAYMENT_FAILED)
        self.assertEqual(variant.stock, 10)
        self.assertIsNone(order.reservation_expires_at)

    def test_mark_payment_failed_idempotent(self):
        order, _ = _make_order()
        order.mark_payment_failed()
        self.assertFalse(order.mark_payment_failed())

    def test_mark_cancelled_releases_stock(self):
        order, variant = _make_order(variant_stock=5, quantity=2)
        self.assertEqual(variant.stock, 3)
        order.mark_cancelled()
        variant.refresh_from_db()
        self.assertEqual(variant.stock, 5)

    def test_mark_expired_releases_stock(self):
        order, variant = _make_order(variant_stock=5, quantity=1)
        self.assertEqual(variant.stock, 4)
        order.mark_expired()
        variant.refresh_from_db()
        self.assertEqual(variant.stock, 5)

    def test_cannot_mark_paid_from_cancelled(self):
        order, _ = _make_order()
        order.mark_cancelled()
        with self.assertRaises(InvalidOrderTransition):
            order.mark_paid()

    def test_mark_refunded_only_from_paid_or_fulfilled(self):
        order, _ = _make_order()
        with self.assertRaises(InvalidOrderTransition):
            order.mark_refunded()
        order.mark_paid()
        self.assertTrue(order.mark_refunded())
        # Idempotent.
        self.assertFalse(order.mark_refunded())


# ---------------------------------------------------------------------------
# Payment model
# ---------------------------------------------------------------------------


class PaymentModelTests(TestCase):
    def test_get_or_create_active_creates_first_payment(self):
        order, _ = _make_order()
        payment, created = Payment.get_or_create_active(order)
        self.assertTrue(created)
        self.assertEqual(payment.status, Payment.Status.CREATED)
        self.assertEqual(payment.amount_cents, int((order.grand_total * 100).to_integral_value()))
        self.assertEqual(payment.currency, "EUR")

    def test_get_or_create_active_reuses_existing_pending(self):
        order, _ = _make_order()
        first, _ = Payment.get_or_create_active(order)
        first.mark_pending(provider_payment_id="tr_abc", checkout_url="https://example/checkout")
        second, created_again = Payment.get_or_create_active(order)
        self.assertFalse(created_again)
        self.assertEqual(first.pk, second.pk)

    def test_get_or_create_active_creates_new_when_previous_terminal(self):
        order, _ = _make_order()
        first, _ = Payment.get_or_create_active(order)
        first.mark_failed()
        second, created_again = Payment.get_or_create_active(order)
        self.assertTrue(created_again)
        self.assertNotEqual(first.pk, second.pk)

    def test_mark_pending_sets_provider_fields(self):
        order, _ = _make_order()
        payment, _ = Payment.get_or_create_active(order)
        payment.mark_pending(provider_payment_id="tr_xyz", checkout_url="https://example/co")
        self.assertEqual(payment.status, Payment.Status.PENDING)
        self.assertEqual(payment.provider_payment_id, "tr_xyz")
        self.assertEqual(payment.checkout_url, "https://example/co")

    def test_mark_paid_then_refunded_path(self):
        order, _ = _make_order()
        payment, _ = Payment.get_or_create_active(order)
        payment.mark_pending(provider_payment_id="tr_1")
        self.assertTrue(payment.mark_paid())
        self.assertTrue(payment.mark_refunded())
        self.assertEqual(payment.status, Payment.Status.REFUNDED)

    def test_mark_paid_idempotent(self):
        order, _ = _make_order()
        payment, _ = Payment.get_or_create_active(order)
        payment.mark_paid()
        self.assertFalse(payment.mark_paid())

    def test_cannot_mark_paid_from_failed(self):
        order, _ = _make_order()
        payment, _ = Payment.get_or_create_active(order)
        payment.mark_failed()
        with self.assertRaises(InvalidPaymentTransition):
            payment.mark_paid()

    def test_unique_provider_payment_id_per_provider(self):
        order, _ = _make_order()
        p1, _ = Payment.get_or_create_active(order)
        p1.mark_pending(provider_payment_id="tr_dup")
        # A second order's payment cannot reuse the same provider_payment_id.
        order2, _ = _make_order(order_number="EFF-PMT-002", variant_sku="PMT-TEST-002")
        p2, _ = Payment.get_or_create_active(order2)
        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            p2.mark_pending(provider_payment_id="tr_dup")


# ---------------------------------------------------------------------------
# WebhookEvent dedup
# ---------------------------------------------------------------------------


class WebhookEventTests(TestCase):
    def test_record_delivery_creates_first_then_dedups(self):
        ev, created = WebhookEvent.record_delivery(
            provider="mollie", provider_event_key="tr_abc", payload={"id": "tr_abc"}
        )
        self.assertTrue(created)
        ev2, created_again = WebhookEvent.record_delivery(
            provider="mollie", provider_event_key="tr_abc", payload={"id": "tr_abc"}
        )
        self.assertFalse(created_again)
        self.assertEqual(ev.pk, ev2.pk)

    def test_mark_processed_success_sets_timestamp(self):
        ev, _ = WebhookEvent.record_delivery(
            provider="mollie", provider_event_key="tr_xyz"
        )
        self.assertIsNone(ev.processed_at)
        ev.mark_processed_success()
        self.assertIsNotNone(ev.processed_at)
        self.assertEqual(ev.processing_status, WebhookEvent.ProcessingStatus.SUCCESS)

    def test_mark_processed_failed_records_error(self):
        ev, _ = WebhookEvent.record_delivery(
            provider="mollie", provider_event_key="tr_err"
        )
        ev.mark_processed_failed("boom")
        self.assertEqual(ev.processing_status, WebhookEvent.ProcessingStatus.FAILED)
        self.assertIn("boom", ev.processing_error)


# ---------------------------------------------------------------------------
# Refund (full-refund-only MVP)
# ---------------------------------------------------------------------------


class RefundTests(TestCase):
    def _make_paid_order(self):
        order, variant = _make_order()
        payment, _ = Payment.get_or_create_active(order)
        payment.mark_pending(provider_payment_id="tr_paid")
        payment.mark_paid()
        order.mark_paid()
        return order, payment, variant

    def test_request_full_refund_succeeds_for_paid_order(self):
        order, payment, _ = self._make_paid_order()
        admin_user = get_user_model().objects.create_user(
            username="admin", password="x", is_staff=True
        )
        refund = Refund.request_full_refund(order, created_by=admin_user)
        self.assertEqual(refund.status, Refund.Status.REQUESTED)
        self.assertEqual(refund.amount_cents, int((order.grand_total * 100).to_integral_value()))
        self.assertEqual(refund.payment, payment)

    def test_request_full_refund_rejected_for_unpaid_order(self):
        order, _ = _make_order()
        with self.assertRaises(InvalidRefundOperation):
            Refund.request_full_refund(order)

    def test_request_full_refund_rejected_when_already_in_flight(self):
        order, _, _ = self._make_paid_order()
        Refund.request_full_refund(order)
        with self.assertRaises(InvalidRefundOperation):
            Refund.request_full_refund(order)

    def test_mark_succeeded_transitions_payment_and_order(self):
        order, payment, _ = self._make_paid_order()
        refund = Refund.request_full_refund(order)
        refund.mark_processing(provider_refund_id="re_1")
        refund.mark_succeeded()
        order.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(refund.status, Refund.Status.SUCCEEDED)
        self.assertEqual(payment.status, Payment.Status.REFUNDED)
        self.assertEqual(order.status, Order.Status.REFUNDED)

    def test_mark_succeeded_idempotent(self):
        order, _, _ = self._make_paid_order()
        refund = Refund.request_full_refund(order)
        self.assertTrue(refund.mark_succeeded())
        self.assertFalse(refund.mark_succeeded())

    def test_mark_failed_does_not_change_order(self):
        order, payment, _ = self._make_paid_order()
        refund = Refund.request_full_refund(order)
        refund.mark_failed()
        order.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(refund.status, Refund.Status.FAILED)
        # Order remains paid; payment remains paid. Failed refund does not undo
        # the paid state.
        self.assertEqual(order.status, Order.Status.PAID)
        self.assertEqual(payment.status, Payment.Status.PAID)


# ---------------------------------------------------------------------------
# Webhook-driven happy path (model-level rehearsal of the contract)
# ---------------------------------------------------------------------------


class WebhookDrivenContractTests(TestCase):
    """
    End-to-end model-level rehearsal:
    - order created with reservation
    - payment created and moved to pending
    - webhook event arrives twice (duplicate delivery)
    - second delivery is a dedup no-op; payment + order end up in paid exactly once
    """

    def test_duplicate_webhook_does_not_double_apply(self):
        order, variant = _make_order(variant_stock=10, quantity=3)
        payment, _ = Payment.get_or_create_active(order)
        payment.mark_pending(provider_payment_id="tr_double")
        order.mark_pending_payment()

        # First delivery
        ev1, created1 = WebhookEvent.record_delivery(
            provider="mollie",
            provider_event_key="tr_double",
            payload={"id": "tr_double", "status": "paid"},
        )
        self.assertTrue(created1)
        # Worker applies state: payment paid, order paid.
        payment.mark_paid()
        order.mark_paid()
        ev1.mark_processed_success()

        # Second (duplicate) delivery
        ev2, created2 = WebhookEvent.record_delivery(
            provider="mollie",
            provider_event_key="tr_double",
            payload={"id": "tr_double", "status": "paid"},
        )
        self.assertFalse(created2)
        # Re-applying transitions on already-terminal records is a no-op.
        self.assertFalse(payment.mark_paid())
        self.assertFalse(order.mark_paid())

        # Stock unchanged after both deliveries (sale committed once at first paid).
        variant.refresh_from_db()
        self.assertEqual(variant.stock, 7)
