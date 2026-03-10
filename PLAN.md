# Efferra Webshop — Development Strategy & Phased Plan (v0.1)

---

## Section A: Repo Decisions Snapshot

**Product:** Luxury artistic candles, B2C, NL-first with EU-wide shipping. ~5-6 product families, ~30-40 SKUs. Fixed stock, no personalization, limited editions supported. Premium positioning and pricing.

**Stack (locked):**

| Layer | Technology |
|---|---|
| Backend | Django, PostgreSQL, Celery + Redis |
| Frontend | Nuxt (static build, no SSR in prod) |
| Payments | Mollie (hosted checkout) |
| Deps | Poetry (Python), pnpm (Node), Makefile (orchestration) |

**Deployment (locked):**
- Single VM: Nginx → Gunicorn (Django API) + static Nuxt
- `www.<domain>` → Nuxt static, `api.<domain>` → Django, `api.<domain>/admin/` → Django admin
- Nginx serves `/static/` and `/media/` directly
- Celery worker + beat as systemd services, Redis + PostgreSQL on same VM

**Key constraints:**
- API-first separation — Nuxt never touches DB directly
- Guest checkout required; accounts optional (Google/Facebook social login)
- 4 languages at launch: NL, EN, DE, FR
- EUR only
- Mollie webhooks are source of truth for payment state (never trust redirect)
- No hardcoded payment method names/logos anywhere
- No card data touches our servers
- GDPR compliance + cookie consent + compliant analytics
- Flat-rate shipping (NL + EU zones), free-shipping-above-threshold supported
- Returns: customer-initiated, customer-pays-return-shipping, refund after admin inspection
- PDF invoices emailed per purchase
- Django admin fully customized for shop operations

**Repo state:** Zero code. Only `.gitignore` and local-only doc files exist.

---

## Section B: Architecture Boundaries

### Backend modules (Django apps)

| Module | Responsibility |
|---|---|
| **`core`** | Base settings, shared utilities, Makefile targets, env config |
| **`catalog`** | Products, families, variants (material × color), media, limited editions, i18n content |
| **`cart`** | Session-based cart (multi-item), cart ↔ stock validation |
| **`orders`** | Order creation (guest + logged-in), order state machine, order history |
| **`payments`** | Mollie integration: Payment/Refund/WebhookEvent models, create-payment, webhook handler, worker jobs (as specified in PAYMENTS.md) |
| **`promotions`** | Promo codes, discounts, gift cards (digital, expiration), bundles ("choose 3 pay 2"), free-shipping threshold |
| **`shipping`** | Flat-fee price matrix (NL/EU zones), carrier metadata, return-label generation |
| **`accounts`** | Optional social login (Google/Facebook), minimal profile, session management |
| **`reviews`** | Product reviews/comments, admin moderation |
| **`invoicing`** | PDF invoice generation, transactional email dispatch (order confirmation, shipping update, refund notice) |
| **`analytics`** | Internal sales analytics (admin-side dashboards/reports) |
| **`compliance`** | GDPR data export/deletion hooks, cookie consent API endpoint |

### Frontend (Nuxt pages/components)

| Area | Responsibility |
|---|---|
| **Layout / i18n** | Multi-language shell (NL/EN/DE/FR), cookie consent banner |
| **Catalog pages** | Product listing, product detail (rich media), product families |
| **Cart** | Cart drawer/page, quantity controls, promo code input |
| **Checkout** | Guest checkout form (address, shipping zone), redirect to Mollie hosted checkout, order confirmation/status page |
| **Content pages** | Story / artist / materials brand pages, contact form |
| **Account (optional)** | Social login, order history, review submission |
| **Legal pages** | Privacy policy, terms, return policy, cookie policy |

### API boundary (Django ↔ Nuxt)

- Nuxt calls Django REST API for all data and mutations
- Nuxt **never** renders payment method UI — redirect to Mollie hosted checkout
- i18n content comes from backend (translated product content) + frontend (UI strings)
- Cart can be session-based (anonymous) with a cart token exchanged via API
- Static generation means Nuxt pre-renders catalog pages at build time; dynamic data (cart, checkout, order status) fetched client-side

---

## Section C: Phased Plan (v0.1)

### Phase 0 — Scaffolding & Dev Environment
**Goal:** Both apps run locally, talk to each other, CI-ready structure.

**Deliverables:**
- Django project + initial app structure (core, catalog stubs)
- Nuxt project with pnpm, i18n skeleton (4 locales)
- PostgreSQL + Redis local setup docs
- Makefile with `make setup`, `make dev`, `make test`, `make build`
- `.env.example` files for both apps
- API health-check endpoint (`GET /api/health/`)
- Nuxt dev proxy to Django API

**Acceptance criteria:**
- `make setup && make dev` starts both apps
- `make test` runs (empty) test suites for both
- Nuxt can fetch `/api/health/` and render the result
- No secrets in repo; `.env` files gitignored

---

### Phase 1 — Catalog & Admin Foundation
**Goal:** Products exist in DB, manageable via Django admin, browsable on frontend.

**Deliverables:**
- `catalog` app: Product, ProductFamily, Variant, ProductImage models
- i18n for product content (django-modeltranslation or similar)
- Django admin: product CRUD with image upload, variant management
- REST API: product list, product detail, product family endpoints
- Nuxt: catalog listing page, product detail page with images
- Nuxt: i18n routing (`/nl/`, `/en/`, `/de/`, `/fr/`)
- Media serving via Django dev server (Nginx in prod)

**Acceptance criteria:**
- Admin can create a product with variants, images, and translations in 4 languages
- Frontend renders product listing and detail in all 4 languages
- API returns structured product data with variant info
- Tests cover model validation and API serialization

---

### Phase 2 — Cart & Guest Checkout (pre-payment)
**Goal:** Customer can browse, add to cart, enter shipping info, and reach the point of payment.

**Deliverables:**
- `cart` app: session-based cart with cart-token API
- `orders` app: Order, OrderLine models, order creation from cart
- `shipping` app: flat-fee matrix (NL / EU), shipping zone resolution
- Cart API: add/remove/update items, apply promo code placeholder
- Checkout API: create order from cart + shipping details
- Nuxt: cart page/drawer, checkout flow (address form, shipping cost display, order summary)
- Stock validation at cart-add and order-creation time

**Acceptance criteria:**
- Guest user can add items, see cart, fill address, and create an order
- Shipping fee calculated correctly for NL and EU addresses
- Order is created with status `pending_payment`
- Out-of-stock items rejected at checkout
- Tests cover cart operations, order creation, and shipping calculation

---

### Phase 3 — Payments (Mollie Integration)
**Goal:** Full payment lifecycle as specified in PAYMENTS.md.

**Deliverables:**
- `payments` app: Payment, Refund, WebhookEvent models (exact schema from PAYMENTS.md)
- `POST /api/orders/{id}/pay/` — creates Mollie payment, returns checkout_url
- `POST /api/payments/mollie/webhook/` — verify, dedup, enqueue
- Celery worker: fetch Mollie state, idempotent Payment + Order update, transition-guarded side effects
- `POST /api/admin/orders/{id}/refund/` — staff-only, idempotent refund
- Nuxt: redirect to Mollie, return/confirmation page, order status polling
- Stock reservation with TTL for async methods (SEPA bank transfer)

**Acceptance criteria:**
- All PAYMENTS.md verification scenarios pass (card, iDEAL, PayPal, Klarna, bank transfer, fail, cancel, expire)
- Refund: full + partial, double-click safe, webhook-retry safe
- Order transitions to `paid` only via webhook
- No hardcoded method names/logos
- No card data logged or stored
- Webhook auth enforced, admin endpoint auth enforced
- Tests cover entire verification contract

---

### Phase 4 — Promotions & Gift Cards
**Goal:** All promotional mechanics operational.

**Deliverables:**
- `promotions` app: PromoCode, Discount, GiftCard, Bundle models
- Discount engine: applies discounts to cart/order totals
- Promo code validation + redemption API
- Gift card: purchase, digital code delivery, redemption as payment method
- Bundles: "choose N pay M" mechanic
- Free-shipping-above-threshold rule
- Django admin: full promo management
- Nuxt: promo code input in cart, gift card purchase page, bundle display

**Acceptance criteria:**
- Promo code applies correct discount
- Gift card can be purchased, emailed, and redeemed
- Bundle pricing computed correctly
- Free-shipping threshold works with shipping calculation
- Promotions stack/conflict rules are defined and tested

---

### Phase 5 — Invoicing, Emails & Returns
**Goal:** Transactional communications and return flow complete.

**Deliverables:**
- `invoicing` app: PDF invoice generation (per order)
- Email dispatch: order confirmation, shipping update, refund notice (Celery tasks)
- Invoice emailed on order paid
- `shipping` app extension: return label generation endpoint
- Admin: return request tracking, inspection status, refund trigger
- Nuxt: return request page (customer-facing)

**Acceptance criteria:**
- PDF invoice generated and emailed on every purchase
- Order confirmation email sent on payment success
- Return label downloadable by customer
- Admin can track return → inspect → trigger refund (connects to Phase 3 refund flow)
- No duplicate emails on webhook retries

---

### Phase 6 — Accounts, Reviews & Content Pages
**Goal:** Optional accounts, reviews, and brand content.

**Deliverables:**
- `accounts` app: Google + Facebook social login (django-allauth or similar)
- Optional account linking for order history
- `reviews` app: product reviews/comments, admin moderation
- Nuxt: login/register, order history, review form
- Nuxt: brand pages (story, artist, materials), contact form
- Contact form → email to support mailbox

**Acceptance criteria:**
- Social login works for Google and Facebook
- Logged-in user sees order history
- Reviews appear on product detail, admin can moderate/delete
- Contact form delivers to support email
- Brand pages render with translated content

---

### Phase 7 — Analytics, Compliance & Hardening
**Goal:** GDPR compliance, analytics, and production readiness.

**Deliverables:**
- `compliance` app: cookie consent API, consent storage, GDPR data export/deletion
- Nuxt: cookie consent banner (respects consent state)
- GDPR-compliant analytics integration (e.g., Plausible, Matomo, or server-side)
- `analytics` app: internal sales dashboards in Django admin
- Security hardening: CSRF, CORS, rate limiting, input validation audit
- Performance: static generation build pipeline, image optimization

**Acceptance criteria:**
- Cookie consent banner shows, respects choice, blocks tracking until consent
- Analytics only fire with consent
- Admin sees sales reports (orders, revenue, top products)
- GDPR: user can request data export and deletion
- Security headers set, no OWASP top-10 vulnerabilities

---

### Phase 8 — Deployment & Launch Prep
**Goal:** Production deployment on VM, launch checklist complete.

**Deliverables:**
- Nginx config (www + api subdomains, static/media serving)
- systemd unit files (gunicorn, celery worker, celery beat)
- `make deploy` / deployment script (or documented manual steps)
- SSL/TLS setup (Let's Encrypt)
- Backup strategy for PostgreSQL
- Monitoring: basic health checks, error logging
- Smoke test suite for production
- Launch checklist document

**Acceptance criteria:**
- Site accessible on production domain with SSL
- All features functional end-to-end in production
- Mollie webhooks reachable from Mollie servers
- Backups running
- Admin accessible at `api.<domain>/admin/`
- Smoke tests pass against production

---

## Section D: Kanban-Ready Task List (Next 20 Cards)

These cover **Phase 0 + Phase 1** — the immediate work to start implementation.

### Phase 0 — Scaffolding

| # | Card Title | Tags |
|---|---|---|
| 1 | Init Django project with Poetry + pyproject.toml | `scaffolding`, `backend` |
| 2 | Create initial Django apps: core, catalog | `scaffolding`, `backend` |
| 3 | Configure Django settings (PostgreSQL, Redis, env-based config) | `scaffolding`, `backend`, `config` |
| 4 | Add health-check endpoint GET /api/health/ | `scaffolding`, `backend`, `api` |
| 5 | Init Nuxt project with pnpm | `scaffolding`, `frontend` |
| 6 | Configure Nuxt i18n with 4 locale stubs (NL/EN/DE/FR) | `scaffolding`, `frontend`, `i18n` |
| 7 | Set up Nuxt dev proxy to Django API | `scaffolding`, `frontend`, `config` |
| 8 | Create root Makefile (setup, dev, test, build) | `scaffolding`, `dx` |
| 9 | Add .env.example for backend and frontend | `scaffolding`, `config` |
| 10 | Verify end-to-end: Nuxt fetches /api/health/ | `scaffolding`, `verification` |

### Phase 1 — Catalog & Admin

| # | Card Title | Tags |
|---|---|---|
| 11 | Design catalog models (Product, ProductFamily, Variant, ProductImage) | `catalog`, `backend`, `models` |
| 12 | Add i18n support for product content fields | `catalog`, `backend`, `i18n` |
| 13 | Customize Django admin for catalog CRUD + image upload | `catalog`, `backend`, `admin` |
| 14 | Build catalog API: product list + detail endpoints | `catalog`, `backend`, `api` |
| 15 | Build product family API endpoint | `catalog`, `backend`, `api` |
| 16 | Create Nuxt catalog listing page | `catalog`, `frontend`, `pages` |
| 17 | Create Nuxt product detail page with image gallery | `catalog`, `frontend`, `pages` |
| 18 | Implement i18n routing (/nl/, /en/, /de/, /fr/) | `frontend`, `i18n`, `routing` |
| 19 | Configure media upload + serving in dev | `catalog`, `backend`, `media` |
| 20 | Write tests for catalog models + API serialization | `catalog`, `backend`, `testing` |

---

## Section E: Risks / Assumptions (Implied by Docs)

| # | Item | Type | Notes |
|---|---|---|---|
| 1 | Mollie sandbox availability | Risk | Payment testing requires Mollie test API keys. Must be obtained before Phase 3. |
| 2 | iDEAL → Wero branding transition | Assumption | Docs assume Mollie hosted checkout handles this automatically. Parking-lot item in PAYMENTS.md. |
| 3 | Static Nuxt + dynamic checkout | Risk | Static pre-rendering works for catalog but cart/checkout/order-status require client-side fetches. Must validate hydration strategy early. |
| 4 | i18n content volume | Assumption | All 4 languages need translated product descriptions. Assumes content will be provided — not auto-translated. |
| 5 | Social login OAuth credentials | Risk | Google + Facebook OAuth app setup required before Phase 6. |
| 6 | Gift card as payment method | Risk | Gift cards need to integrate with the payment flow (partial payment: gift card + Mollie for remainder). This interaction needs careful design in Phase 4. |
| 7 | PDF invoice legal compliance | Assumption | Invoice must meet NL/EU requirements (VAT number, sequential numbering, etc.). Tax/VAT rules are out of scope per PAYMENTS.md but invoicing still needs them. |
| 8 | Single-VM performance ceiling | Assumption | Docs specify low traffic. If traffic spikes, the single-VM model has no horizontal scaling. Acceptable per constraints. |
| 9 | Email deliverability | Risk | Transactional emails require a reliable sender (SMTP service or transactional email provider). Not decided in docs — implementation choice. |
| 10 | Stock reservation TTL for async payments | Risk | SEPA bank transfer can pend for days. Stock reservation TTL policy needs a business decision (how long to hold stock). |

---

## Sequencing Rationale

- **Phase 0 first** because every subsequent phase needs running apps with a working API bridge.
- **Catalog before Cart** because cart depends on product models, and catalog is the simplest way to validate the full Django↔Nuxt data flow + i18n early.
- **Cart before Payments** because Mollie integration needs an Order to attach to — you can't test payments without a checkout flow.
- **Payments before Promotions** because a working baseline payment flow is needed before introducing discount/gift-card complexity that modifies totals.
- **Invoicing/Emails after Payments** because invoices trigger on payment success.
- **Accounts/Reviews late** because they're optional features that don't block the core purchase flow.
- **Compliance/Analytics near the end** because they wrap around existing features rather than building new ones.
- **Deployment last** because it's configuration, not application logic, and benefits from a complete feature set to smoke-test.
