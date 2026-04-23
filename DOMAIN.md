# DOMAIN.md — Domain Model Reference

This file documents the implemented domain models, their key fields, and the decisions behind them.
It is intended as a stable reference for agents and developers working on this codebase.

**Current status:** Catalog, Cart, and Order domain models are implemented and migrated.
API endpoints, admin customization, and frontend pages are not yet built.

---

## Catalog domain (`backend/catalog/models.py`)

### Hierarchy

```
Collection
  └── Product (one candle shape/design family)
        ├── ProductVariant (the sellable unit: material × color × finish)
        └── ProductImage (attached to Product, optionally to a specific Variant)
```

### Collection

Artistic grouping for navigation and storytelling (e.g. Forest, Faces, Branches).

| Field | Type | Notes |
|---|---|---|
| `name` | CharField(100) | |
| `slug` | SlugField(120) | unique |
| `description` | TextField | blank OK |
| `is_active` | BooleanField | default True |
| `sort_order` | PositiveSmallIntegerField | default 0 |

### Product

One candle shape/design family. **Not the sellable unit.**

| Field | Type | Notes |
|---|---|---|
| `collection` | FK → Collection | PROTECT |
| `name` | CharField(200) | |
| `slug` | SlugField(220) | unique |
| `description` | TextField | blank OK |
| `is_active` | BooleanField | default True |
| `is_limited_edition` | BooleanField | applies to whole design; variants can also be flagged independently |
| `dimensions_note` | CharField(200) | free-text physical notes (e.g. "approx. 18cm tall") |
| `sort_order` | PositiveSmallIntegerField | default 0 |
| `created_at`, `updated_at` | DateTimeField | auto |

**Derived property:** `display_price` → minimum price across active variants, or `None` if no active variant. Used for "from €X" cards.

### ProductVariant

The actual purchasable unit. **Commerce truth lives here.**

| Field | Type | Notes |
|---|---|---|
| `product` | FK → Product | PROTECT |
| `sku` | CharField(100) | unique |
| `material` | CharField(100) | e.g. Soy Wax, Beeswax, Paraffin |
| `color` | CharField(100) | e.g. White, Natural, Black |
| `finish` | CharField(100) | optional; e.g. hand-painted, natural, raw |
| `is_hand_painted` | BooleanField | explicit flag for hand-painted; kept separate for filtering |
| `price` | DecimalField(8,2) | EUR; the purchase price |
| `stock` | PositiveIntegerField | current stock count |
| `is_active` | BooleanField | only active variants are purchasable and shown |
| `is_limited_edition` | BooleanField | variant-level limited edition flag |
| `weight_grams` | PositiveIntegerField | nullable; for shipping calculation later |
| `created_at`, `updated_at` | DateTimeField | auto |

**Derived property:** `in_stock` → `stock > 0`.

### ProductImage

Visual assets. Always belongs to a Product; optionally linked to a specific Variant.

| Field | Type | Notes |
|---|---|---|
| `product` | FK → Product | CASCADE |
| `variant` | FK → ProductVariant | SET_NULL, nullable — None means general product image |
| `image` | ImageField | upload_to='catalog/' |
| `alt_text` | CharField(200) | blank OK |
| `sort_order` | PositiveSmallIntegerField | default 0 |
| `is_active` | BooleanField | default True |

---

## Cart domain (`backend/cart/models.py`)

### Cart

Anonymous shopping session before checkout.

| Field | Type | Notes |
|---|---|---|
| `token` | UUIDField | unique; exchanged with frontend as opaque cart identifier |
| `shipping_country` | CharField(2) | ISO 3166-1 alpha-2; blank until user selects country; for shipping cost preview |
| `created_at`, `updated_at` | DateTimeField | auto |

**Derived property:** `item_count` → sum of all CartItem quantities.

**Rules:**
- Cart is anonymous by default. No user account link.
- Totals are not stored. They are always derived from live variant prices.
- Billing/shipping address does not belong to Cart — it belongs to Order.

### CartItem

One selected variant in a Cart.

| Field | Type | Notes |
|---|---|---|
| `cart` | FK → Cart | CASCADE |
| `variant` | FK → ProductVariant | PROTECT; live pointer, no price snapshot |
| `quantity` | PositiveIntegerField | default 1 |
| `created_at`, `updated_at` | DateTimeField | auto |

**Constraint:** unique per (cart, variant) — one row per variant per cart.

**Rule:** Price snapshot does NOT happen on CartItem. It happens at order creation time.

---

## Order domain (`backend/orders/models.py`)

### Order

The central business record created from a Cart at checkout.

#### Status values

| Value | Meaning |
|---|---|
| `pending` | Default; order created, not yet submitted for payment |
| `pending_payment` | Payment session created; awaiting webhook confirmation |
| `paid` | Confirmed via Mollie webhook |
| `fulfilled` | Shipped / dispatched |
| `cancelled` | Cancelled |
| `refunded` | Refunded (full) |

Note: `partially_refunded` is defined in PAYMENTS.md but is not yet a status value in the Order model. This will need to be added in Phase 3.

#### Key fields

| Group | Fields |
|---|---|
| Public reference | `order_number` (CharField, unique, human-readable e.g. EFF-20240001) |
| Internal reference | `reference` (UUID, unique; used in API URLs to avoid leaking sequential IDs) |
| Guest identity | `email`, `first_name`, `last_name`, `phone`, `company_name` |
| Shipping snapshot | `shipping_full_name`, `shipping_address_line_1`, `shipping_address_line_2`, `shipping_postal_code`, `shipping_city`, `shipping_region`, `shipping_country`, `shipping_phone` |
| Billing snapshot | `billing_same_as_shipping` (default True) + `billing_full_name`, `billing_address_line_1`, etc. |
| Frozen totals | `subtotal`, `shipping_total`, `grand_total` (DecimalField) |
| Currency | `currency` (default EUR) |
| Status | `status` (TextChoices, default `pending`) |
| Notes | `customer_note` (optional) |
| Timestamps | `placed_at` (auto_now_add), `updated_at` (auto_now) |

**Derived property:** `billing_address_display` → returns effective billing address dict, using shipping fields when `billing_same_as_shipping=True`.

### OrderItem

One purchased line. A historical snapshot record, not a live catalog pointer.

| Field | Type | Notes |
|---|---|---|
| `order` | FK → Order | PROTECT |
| `product_ref` | FK → Product | SET_NULL, nullable — traceability only, not authoritative |
| `variant_ref` | FK → ProductVariant | SET_NULL, nullable — traceability only, not authoritative |
| `product_name` | CharField(200) | snapshot |
| `variant_sku` | CharField(100) | snapshot |
| `variant_material` | CharField(100) | snapshot |
| `variant_color` | CharField(100) | snapshot |
| `variant_finish` | CharField(100) | snapshot, blank OK |
| `variant_description` | CharField(500) | full display string snapshot, e.g. "Branch No. 1 / Soy Wax / White" |
| `unit_price` | DecimalField(8,2) | price at time of purchase |
| `quantity` | PositiveIntegerField | |
| `line_total` | DecimalField(10,2) | unit_price × quantity, stored not recalculated |

**Rule:** Snapshot fields are authoritative. FK references (`product_ref`, `variant_ref`) may become NULL if catalog records are deleted — do not rely on them for business logic.

---

## Decision log

Key decisions made during domain modeling. Preserved here so future agents/developers understand the rationale.

| Decision | What was decided | Why |
|---|---|---|
| Product is shape/design family, not the sellable unit | `Product` represents the design (e.g. "Branch Candle No. 1"). `ProductVariant` is what you actually buy. | Artistic candles come in multiple material/color combinations under one design identity. Flat product model would require duplication or awkward workarounds. |
| Variant is the sellable unit | Price, stock, SKU, and active status all live on `ProductVariant` | This is where commerce truth belongs. Separates design identity from purchase availability. |
| Explicit variant fields over generic attribute engine | `material`, `color`, `finish`, `is_hand_painted` are explicit fields on `ProductVariant` | MVP-appropriate. Generic attribute engines add complexity and querying difficulty for no benefit at this scale (~30-40 SKUs). Explicit fields allow typed queries, clean admin, and simpler serialization. Can be extended later if needed. |
| No production mold modeling | Mold/production-level data is out of scope in the webshop domain | The webshop represents what customers see and buy, not internal production tooling. |
| `display_price` as derived property | Product cards show "from €X" derived from the cheapest active variant | Correct UX for shape-driven catalog. Frontend should never independently compute this; the property lives on the model. |
| Product images: single model, optional variant link | `ProductImage` always belongs to a Product; `variant` FK is optional | Avoids over-engineering image hierarchy at MVP. A single model handles both general product shots and variant-specific imagery. |
| Cart is anonymous/token-based | `Cart` has a UUID token, no user FK | Guest-first checkout is a hard requirement. Token is exchanged via API and stored client-side. |
| No price snapshot in Cart | Cart items point to live `ProductVariant` price | Snapshot happens at order creation, not earlier. This keeps cart logic simple and ensures the final order price is accurate at the moment of purchase. |
| Order stores address snapshots | Shipping and billing addresses are embedded snapshot fields, not FK to an address table | Orders must remain correct even if customer changes their address later or if address records are deleted. Historical immutability of the order record. |
| Order totals are frozen | `subtotal`, `shipping_total`, `grand_total` are stored at creation, never recalculated | Prices can change. The order must reflect what the customer actually paid. |
| OrderItem snapshot pattern | All purchase data (name, SKU, material, color, price, quantity, line_total) is stored on OrderItem | Same reason as frozen totals — the record must survive catalog changes. Nullable FKs exist for traceability but the snapshot fields are authoritative. |
| Guest-first checkout | No user account required to place an order | Mandatory per CLAUDE.md. Accounts are optional/additive. |
| Order.reference as UUID | Public-facing order identifier in API URLs is a UUID, not sequential PK | Avoids leaking order volume and prevents enumeration attacks. `order_number` (e.g. EFF-20240001) is the human-readable identifier for customer communication. |
| Status `partially_refunded` missing from Order.Status | Not yet added to the Order model | An oversight to address in Phase 3 alongside the full payments implementation. PAYMENTS.md specifies it as a required state. |
