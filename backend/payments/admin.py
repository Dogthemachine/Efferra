"""
Admin registration for payments-app models.

These admins are intentionally read-only on transactional fields. The state
machine should be driven by webhooks and explicit transition methods, not by
manual edits in the Django admin. Refunds will get a richer admin in a later
card alongside the staff-only refund endpoint.
"""

from django.contrib import admin

from .models import Payment, Refund, WebhookEvent


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "order",
        "provider",
        "status",
        "amount_cents",
        "currency",
        "created_at",
    )
    list_filter = ("provider", "status", "currency")
    search_fields = ("provider_payment_id", "order__order_number", "order__email")
    readonly_fields = (
        "id",
        "order",
        "provider",
        "provider_payment_id",
        "checkout_url",
        "amount_cents",
        "currency",
        "status",
        "idempotency_key",
        "raw_provider_payload_last",
        "created_at",
        "updated_at",
    )
    ordering = ("-created_at",)


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "order",
        "payment",
        "status",
        "amount_cents",
        "currency",
        "created_by",
        "created_at",
    )
    list_filter = ("status", "currency")
    search_fields = ("provider_refund_id", "order__order_number", "order__email")
    readonly_fields = (
        "id",
        "order",
        "payment",
        "provider_refund_id",
        "amount_cents",
        "currency",
        "status",
        "idempotency_key",
        "created_by",
        "raw_provider_payload_last",
        "created_at",
        "updated_at",
    )
    ordering = ("-created_at",)


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = (
        "provider",
        "provider_event_key",
        "processing_status",
        "received_at",
        "processed_at",
    )
    list_filter = ("provider", "processing_status")
    search_fields = ("provider_event_key",)
    readonly_fields = (
        "id",
        "provider",
        "provider_event_key",
        "payload",
        "received_at",
        "processed_at",
        "processing_status",
        "processing_error",
    )
    ordering = ("-received_at",)
