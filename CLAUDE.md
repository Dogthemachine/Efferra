# CLAUDE.md — Webshop Project Contract (Local Development)

## Purpose
This repository builds a small, neat luxury webshop for artistic candles.

- Market: NL-first, EU-wide shipping
- Expected traffic: low
- Launch style: full feature set from day one 

## Scope
This file contains **decided facts** and **non-negotiable constraints**.
It avoids unresolved questions and avoids prescribing internal implementation details where the agent can decide.

---

## Hard constraints (MUST / MUST NOT)

### MUST
- Backend is built in **Django**.
- Frontend is built in **Nuxt**.
- Backend and frontend are fully separated (**API-first**). Frontend consumes the backend API.
- Database is **PostgreSQL**.
- Support **guest checkout**.
- Support **4 languages at launch**: Dutch, English, German, French.
- Support promotions: **promo codes**, **gift cards**, **bundles**, **discounts**.
- Provide admin operations via **Django admin** with full control over shop data.
- Implement **GDPR compliance**, including **cookie consent** and **GDPR-compliant analytics**.
- Payments use **Mollie** (see **PAYMENTS.md**).
- Hosting targets a **simple VM** setup and should remain operationally minimal.

### MUST NOT
- Must not require user accounts to purchase (accounts are optional).
- Must not overbuild infrastructure for low traffic (avoid unnecessary managed services).
- Must not hardcode payment method names/logos in the frontend (provider-driven display; see **PAYMENTS.md**).

---

## Workstyle contract (how to work in this repo)
- Read `CLAUDE.md` and `PAYMENTS.md` before making payment-related changes.
- Prefer small, reviewable diffs.
- Keep decisions reversible unless explicitly required by constraints.
- Do not add new infrastructure components unless explicitly asked.
- Do not commit/push unless explicitly asked.
- Do not expose secrets (`.env` values, API keys) in logs, output, or commits.

---

## Product and positioning

### Product
Luxury artistic candles made by experienced artists.

- Premium materials
- Premium packaging
- Premium pricing
- Niche positioning (not mass market)

### Personalization
- No personalization.

### Inventory
- Fixed stock (not made-to-order).


## Customer support (decided)
- Customer support is required.
- Support channels:
  - Contact form on the website
  - Email support (support mailbox)

### Catalog scope at launch
- ~5–6 product families
- ~30–40 sellable stock positions (SKUs)
- Variants: specific allowed combinations of **material** and **color** (not a full matrix)
- Limited editions: supported
- No explicit per-customer limits or special quantity-cap system required at this stage

### Media and presentation
- Product photos are required.
- Product presentation should be rich enough to reduce misunderstandings.

### Brand/content pages
- Story / artist / materials pages are required.

---

## Markets, language, currency
- Customer type: B2C
- Currency: EUR
- Shipping coverage: Netherlands + EU-wide
- Languages at launch: Dutch, English, German, French

---

## Checkout, identity, reviews

### Cart
- Multi-item, multi-product cart.

### Checkout
- Guest checkout is required.

### Optional login
- Optional social login is supported for convenience and/or reviews.
- Providers: Google and Facebook.

### Reviews and comments
- Reviews/comments are open (any user can leave a comment under a product).
- Moderation is admin-managed (admins can manage/delete reviews).

---

## Promotions and pricing features
- Promo codes: required.
- Discount engine: required backend model to apply discounts to pricing.
- Gift cards: required.
  - Digital codes
  - Expiration rules supported
- Bundles: required.
  - Example mechanic: choose 3 items, pay for 2
- Shipping promotions: supported.
  - Free shipping above a purchase threshold is allowed by design

---

## Payments (decided)

### Primary PSP
- Mollie (NL-first; some notes may misspell as “Morley”; treat as Mollie).

### Required methods via Mollie
- iDEAL with iDEAL → iDEAL | Wero → Wero transition handled without rewrites
- Cards including Apple Pay and Google Pay via card rails
- PayPal
- SEPA bank transfer (asynchronous)
- Klarna (BNPL)
- Refunds supported as a first-class flow

### Payments integration rules (non-negotiable)
- Payment method names, logos, and ordering must never be hardcoded.
- Hosted checkout or official Mollie components are preferred to minimize PCI scope.
- Order/payment state must be webhook-driven; return/redirect URLs are UX only.
- Money-moving operations must be idempotent; webhook processing must be idempotent and deduplicated.
- Card details must never be stored, processed, or logged by our servers.

### Authoritative payment specification
- `PAYMENTS.md` is authoritative for payment implementation details.

---

## Shipping (decided)
- Shipping fee model: flat fee.
- Shipping zones: Netherlands and EU.
- Carrier intent: PostNL, DHL, and similar common EU carriers.
- Shipping pricing implementation: a simple price matrix for NL and EU, compatible with discounts and free-shipping promotions.

---

## Returns and refunds (decided)
- Returns expectation: low.
- Return flow: customer requests return, item is returned, staff inspects the product (fragile/expensive), refund is approved after inspection.
- Return shipping: customer pays (current policy).
- Return labels: generated on the website by user request (no pre-included labels).
- Refund timing rules: aligned with applicable law.
- Refund execution: admin-triggered refund through the PSP integration after inspection approval.

---

## Invoicing and email communication (decided)
- Invoices: required.
- Invoice format: PDF.
- Invoice delivery: emailed to the customer for every purchase.
- Transactional emails:
  - Order confirmation and shipping updates are required.
  - Refund-related messaging is supported.

---

## Admin and internal operations (decided)

### Admin system
- Django admin is required and must be customized for the webshop.

### Admin scope
Full control under login for:
- products, descriptions, media, stock
- discounts, gift cards, bundles
- orders, payments, refunds

### Sales analysis
- Internal sales analytics tools are required (admin-side).

---

## Tech architecture (decided, but implementation-choice friendly)

### Backend
- Django application exposing shop capabilities through an HTTP API.
- Concrete API toolkit (e.g., DRF vs other) is an implementation choice; keep the API stable and documented.

### Frontend
- Nuxt application consuming the Django API.
- Rendering mode (SSR/static/hybrid) and i18n implementation details are implementation choices; prioritize simplicity and maintainability for a low-traffic shop.

### API contract philosophy
- Backend is the source of truth for orders, payments, stock, promotions, and admin actions.
- Frontend is responsible for UX, content presentation, and calling backend endpoints.
- Payment flow follows `PAYMENTS.md` (create session → redirect; webhook confirms).

### Database
- PostgreSQL.

---

## Hosting and storage (decided)
- Hosting model: simple VM deployment with basic routing.
- Cloud components: keep minimal; avoid unnecessary managed services.
- Media storage: store media on the same VM (no external object storage by default).

---

## Privacy and compliance (decided)
- GDPR: required.
- Cookie consent: required.
- Analytics: required and implemented in a GDPR-compliant way.

--- 

## Dependency management (decided)

- **Backend (Django/Python):** `pyproject.toml` + `poetry.lock` (Poetry is the source of truth for Python deps).
- **Frontend (Nuxt/Node):** `pnpm` + `pnpm-lock.yaml` (pnpm is the source of truth for Node deps).
- **Repo orchestration:** root-level `Makefile` provides common commands (`make setup`, `make dev`, `make test`, `make build`, etc.) and should be kept up to date with the backend/frontend workflows.

Rules:
- Do not mix package managers (no npm/yarn alongside pnpm; no pip requirements files alongside Poetry unless explicitly requested).
- Always update lock files when dependencies change.