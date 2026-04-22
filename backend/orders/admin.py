from django.contrib import admin

from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = (
        "product_name",
        "variant_sku",
        "variant_material",
        "variant_color",
        "variant_finish",
        "variant_description",
        "unit_price",
        "quantity",
        "line_total",
        "product_ref",
        "variant_ref",
    )
    fields = (
        "product_name",
        "variant_description",
        "variant_sku",
        "unit_price",
        "quantity",
        "line_total",
        "product_ref",
        "variant_ref",
    )
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_number",
        "email",
        "full_name",
        "status",
        "grand_total",
        "currency",
        "placed_at",
    )
    list_filter = ("status", "currency", "shipping_country", "placed_at")
    search_fields = ("order_number", "email", "first_name", "last_name")
    readonly_fields = (
        "order_number",
        "reference",
        "placed_at",
        "updated_at",
        "subtotal",
        "shipping_total",
        "grand_total",
    )
    inlines = [OrderItemInline]
    fieldsets = (
        (
            "Order",
            {
                "fields": (
                    "order_number",
                    "reference",
                    "status",
                    "currency",
                    "placed_at",
                    "updated_at",
                )
            },
        ),
        (
            "Customer",
            {
                "fields": (
                    "email",
                    "first_name",
                    "last_name",
                    "phone",
                    "company_name",
                )
            },
        ),
        (
            "Shipping address",
            {
                "fields": (
                    "shipping_full_name",
                    "shipping_address_line_1",
                    "shipping_address_line_2",
                    "shipping_postal_code",
                    "shipping_city",
                    "shipping_region",
                    "shipping_country",
                    "shipping_phone",
                )
            },
        ),
        (
            "Billing address",
            {
                "fields": (
                    "billing_same_as_shipping",
                    "billing_full_name",
                    "billing_address_line_1",
                    "billing_address_line_2",
                    "billing_postal_code",
                    "billing_city",
                    "billing_region",
                    "billing_country",
                )
            },
        ),
        (
            "Totals",
            {
                "fields": (
                    "subtotal",
                    "shipping_total",
                    "grand_total",
                )
            },
        ),
        (
            "Notes",
            {
                "fields": ("customer_note",),
                "classes": ("collapse",),
            },
        ),
    )

    def full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"
    full_name.short_description = "Name"
