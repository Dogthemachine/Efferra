# DOMAIN.md — Domain Model Reference

This file documents the implemented domain models, their key fields, and the decisions behind them.
It is intended as a stable reference for agents and developers working on this codebase.

**Current status:** Catalog, Cart, Order, and the MVP **Payments contract layer**
(Payment, Refund, WebhookEvent + Order reservation/transition helpers) are
implemented and migrated. HTTP endpoints, admin customization beyond default
registration, frontend pages, and the real Mollie integration are not yet
built.

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
| `pending` | Default; order created with stock reserved; no payment session opened yet |
| `pending_payment` | Payment session opened; awaiting webhook confirmation |
| `paid` | Confirmed via Mollie webhook; sale committed |
| `fulfilled` | Shipped / dispatched |
| `payment_failed` | Last payment attempt terminally failed; reserved stock has been released |
| `expired` | Reservation deadline passed before any successful payment; reserved stock released |
| `cancelled` | Customer or admin cancelled before payment; reserved stock released |
| `refunded` | Full refund completed (admin-triggered, MVP) |

Partial refunds are out of scope for the MVP. `partially_refunded` is intentionally
not a status value; full refunds only.

#### Stock reservation lifecycle

- Stock is reserved at order creation by decrementing `ProductVariant.stock`
  by each `OrderItem.quantity`. The order itself is the reservation record.
- `Order.reservation_expires_at` is set 30 minutes after creation
  (`Order.RESERVATION_TIMEOUT`).
- Helper methods on `Order`:
  - `Order.compute_reservation_expiry()` — returns `now + RESERVATION_TIMEOUT`.
  - `Order.has_active_reservation` — true while pre-paid and not yet expired.
  - `Order.is_reservation_expired` — true once the deadline has passed.
  - `Order.release_stock_reservation()` — restores reserved stock; idempotent.
  - `Order.mark_pending_payment()` / `mark_paid()` / `mark_payment_failed()` /
    `mark_cancelled()` / `mark_expired()` / `mark_fulfilled()` /
    `mark_refunded()` — idempotent state transitions. The terminal
    pre-paid transitions (`payment_failed`, `cancelled`, `expired`)
    release reserved stock automatically; `mark_paid` clears the
    reservation timer without changing stock (sale committed).
  - `Order.active_payment()` — returns the current non-terminal payment, or `None`.

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
| Reservation | `reservation_expires_at` (DateTimeField, nullable; set at creation, cleared on terminal state) |
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

## Payments domain (`backend/payments/models.py`)

The payments app implements the MVP payment-flow contract: state machines
for `Payment` and `Refund`, plus a `WebhookEvent` row for inbound webhook
deduplication. PSP integration (Mollie API calls, HTTP endpoints, Celery
worker) is wired in a later card; this app currently provides the
domain/contract layer only.

```
Order ─┬─< Payment   (one row per payment attempt; UUID pk)
       └─< Refund    (one row per admin-triggered refund; UUID pk; FK to Payment)

WebhookEvent (provider, provider_event_key uniquely; UUID pk)
```

### Payment

One payment attempt against a single Order. An Order may have multiple
Payment rows over its lifetime, but at most one is allowed to be in a
non-terminal status at any time.

| Field | Type | Notes |
|---|---|---|
| `id` | UUIDField (pk) | |
| `order` | FK → Order | PROTECT |
| `provider` | CharField(32) | default `mollie` |
| `provider_payment_id` | CharField(128) | blank initially; set after PSP call. Unique per provider when set. |
| `checkout_url` | URLField | UX only; never used as truth |
| `amount_cents` | PositiveIntegerField | EUR for MVP |
| `currency` | CharField(3) | default `EUR` |
| `status` | TextChoices | `created` / `pending` / `paid` / `failed` / `cancelled` / `expired` / `refunded` |
| `idempotency_key` | CharField(64) | passed to PSP create-payment so retries do not duplicate |
| `raw_provider_payload_last` | JSONField | last raw provider payload, for audit/debug |
| `created_at`, `updated_at` | DateTimeField | auto |

**Active vs terminal:** `Payment.ACTIVE_STATUSES = {created, pending}`.
Everything else is terminal.

**Helper methods:**
- `Payment.get_or_create_active(order)` — returns the current payable
  payment for an order, creating one if none exists. Honors the
  "one active payment per order" rule.
- `mark_pending(provider_payment_id, checkout_url)` — open the PSP session.
- `mark_paid()` / `mark_failed()` / `mark_cancelled()` / `mark_expired()` /
  `mark_refunded()` — idempotent transitions; raise `InvalidPaymentTransition`
  on illegal moves.

### Refund

Admin-triggered full refund. **MVP scope: full refunds only.**
`amount_cents` must equal the parent order's `grand_total` (in cents).

| Field | Type | Notes |
|---|---|---|
| `id` | UUIDField (pk) | |
| `order` | FK → Order | PROTECT |
| `payment` | FK → Payment | PROTECT |
| `provider_refund_id` | CharField(128) | blank initially. Unique per payment when set. |
| `amount_cents` | PositiveIntegerField | must equal order grand_total in cents (full refund) |
| `currency` | CharField(3) | default `EUR` |
| `status` | TextChoices | `requested` / `processing` / `succeeded` / `failed` / `cancelled` |
| `idempotency_key` | CharField(64) | passed to PSP refund call |
| `created_by` | FK → auth.User | SET_NULL; staff user who triggered |
| `raw_provider_payload_last` | JSONField | last raw provider payload |
| `created_at`, `updated_at` | DateTimeField | auto |

**Helper methods:**
- `Refund.request_full_refund(order, created_by=...)` — preconditions
  enforced: order must be `paid`, must have a `paid` Payment, must not
  already have an active refund in flight.
- `mark_processing(provider_refund_id)` / `mark_failed()` / `mark_cancelled()` —
  status-only transitions.
- `mark_succeeded()` — atomic terminal success; also flips Payment to
  `refunded` and Order to `refunded`.

### WebhookEvent

Durable record of one inbound provider webhook delivery, used for
deduplication and audit. The HTTP webhook handler must call
`WebhookEvent.record_delivery(...)` first; if `created=False`, the
delivery is a duplicate and must not produce side effects again.

| Field | Type | Notes |
|---|---|---|
| `id` | UUIDField (pk) | |
| `provider` | CharField(32) | default `mollie` |
| `provider_event_key` | CharField(255) | unique together with provider; for Mollie this is typically the provider payment id |
| `payload` | JSONField | raw inbound payload |
| `received_at` | DateTimeField | auto_now_add |
| `processed_at` | DateTimeField | nullable; set when worker finishes |
| `processing_status` | TextChoices | `pending` / `success` / `failed` |
| `processing_error` | TextField | populated when processing failed |

**Constraint:** unique `(provider, provider_event_key)` — guarantees
deduplication.

**Helper methods:**
- `WebhookEvent.record_delivery(provider, provider_event_key, payload)`
  — `(event, created)` tuple; idempotent.
- `mark_processed_success()` / `mark_processed_failed(error)`.

### MVP payment-flow rules (enforced in code)

- **Webhook is the source of truth.** `Order.mark_paid` and
  `Payment.mark_paid` are intended to be triggered only by confirmed-paid
  signal (typically a webhook). The frontend never marks an order paid.
- **Reservation timeout is 30 minutes** (`Order.RESERVATION_TIMEOUT`).
- **One active payment per order** at a time
  (`Payment.get_or_create_active`).
- **Idempotency:** every transition helper is a no-op when already in
  the target state; `WebhookEvent.record_delivery` deduplicates by
  `provider_event_key`; `Payment` and `Refund` carry `idempotency_key`
  for outbound PSP calls.
- **Full refunds only** for MVP. `Refund.request_full_refund` rejects
  any operation that would create or imply a partial refund.

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
| Full refunds only for MVP | `Refund.request_full_refund` enforces `amount_cents == order.grand_total`; no `partially_refunded` status on Order | The shop is low-traffic luxury with rare returns and per-order admin inspection. Partial refund logic adds substantial complexity (line-level accounting, multiple Refund rows per order, separate webhook flows) that is not justified at MVP scale. Partial refunds are explicitly deferred. |
| Order is the reservation record | Stock decrements at order creation; `Order.reservation_expires_at` carries the 30-minute deadline; OrderItem quantities drive release | A separate Reservation table would add a join and an extra lifecycle to keep in sync with Order for no MVP benefit. The order already has the items and quantities; making it the reservation record keeps the model graph minimal. |
| Separate Order and Payment status fields | Order tracks the business state; Payment tracks the per-attempt PSP state. They are not unified into one shared field. | The card spec explicitly allows distinct status fields when it keeps the implementation cleaner. Order outlives any single payment attempt (multiple retries are common); Payment carries provider-specific terminal states (`expired`, etc.) that have no direct business meaning on the Order. |
| Webhook-first truth, frontend never marks paid | `Order.mark_paid`/`Payment.mark_paid` are intended to fire only from webhook processing; the redirect/return URL is UX-only | Mandatory per CLAUDE.md and PAYMENTS.md. Trusting the redirect makes the system race-prone and trivially spoofable. |
| Idempotency built into transitions | All `mark_*` helpers are no-ops when already in the target state; `WebhookEvent` deduplicates deliveries by `provider_event_key` | Webhooks are retried by providers and may arrive out of order; double-clicks happen in admin UIs. Idempotent transitions and dedup are cheaper than recovery-from-corruption. |
