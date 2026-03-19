---
name: django-admin-customization
description: Build and maintain Django admin tools for shop operations. Use this skill when customizing the Django admin for products, orders, stock, promotions, refunds, or any admin-facing functionality.
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
  - Glob
  - Grep
---

# Django Admin Customization

## Role of Django admin in this project

Django admin is **first-class** for this project. It is the primary interface for shop operators to manage:

- Products, descriptions, media, stock levels
- Variants (material × color combinations)
- Discounts, promo codes, gift cards, bundles
- Orders, payments, refunds
- Reviews and moderation
- Sales analytics

## Principles

1. **Practical over decorative.** Focus on operations that staff actually need. Do not add admin features for aesthetics.
2. **Standard Django admin is sufficient** for most needs. Do not build custom admin UX (React/Vue dashboards) unless standard admin cannot handle the requirement.
3. **Keep admin changes coherent.** Admin customizations for a model should live in the same app as the model.
4. **Admin is staff-only.** All admin views require authentication. Do not expose admin endpoints publicly.

## Implementation patterns

### Model registration
- Register models in `<app>/admin.py`.
- Use `@admin.register(Model)` decorator pattern.

### List views
- Configure `list_display` for useful columns.
- Add `list_filter` and `search_fields` for findability.
- Use `list_editable` sparingly — only for fields that make sense to bulk-edit.

### Detail views
- Use `fieldsets` to organize form sections logically.
- Use `readonly_fields` for computed or system-managed fields.
- Use `inlines` for related objects (e.g., OrderLines on an Order, Variants on a Product).

### Actions
- Add custom admin actions for common operations (e.g., "Mark as shipped", "Approve refund").
- Actions must be safe: confirm destructive operations, enforce business rules.

### Media and images
- Support image upload in product admin.
- Use thumbnail previews in list views where practical.

### i18n in admin
- If using `django-modeltranslation`, admin forms should show fields for all four languages (NL, EN, DE, FR).
- Use tabbed or grouped display to keep forms manageable.

## Scope boundaries

- Admin customization is backend work. Do not modify frontend code in this skill.
- Payment operations in admin must follow `PAYMENTS.md` rules (use the `mollie-payments-contract` skill).
- Keep admin code in `<app>/admin.py` files, not in separate admin apps unless complexity demands it.

## Verification

1. Run `cd backend && poetry run python manage.py check` — no errors.
2. Start the dev server and access `/admin/` — verify the customized views load correctly.
3. Test CRUD operations for the customized models through the admin interface.
4. Confirm staff-only access is enforced.
