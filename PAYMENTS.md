# PAYMENTS.md — Mollie Payments Contract (Webshop)

Purpose
This file is the operational contract for payments integration only.
Out of scope: VAT/OSS/tax rules, invoicing format rules, shipping rules, frontend tech choice.

Status
The MVP payment-flow contract layer is implemented in the `payments` Django
app: `Payment`, `Refund`, `WebhookEvent` models, plus the reservation
lifecycle and idempotent state-transition helpers on `Order`. HTTP endpoints,
the real Mollie API client, and Celery worker wiring are still pending and
will land in subsequent Phase 3 cards.

Primary PSP
Mollie is the primary PSP. Notes may misspell it as “Morley”; treat as Mollie.

Quick facts
Currency: EUR.
Customer type: B2C.
Checkout: guest checkout is required; optional social login may exist but is not required for payment.
Required methods via Mollie (one integration approach):
- iDEAL with iDEAL → iDEAL | Wero → Wero transition handled without rewrites
- Cards (Apple Pay / Google Pay via card rails)
- PayPal
- SEPA bank transfer (asynchronous)
- Klarna (BNPL)

--------------------------------------------------------------------------------

HARD CONSTRAINTS (MUST / MUST NOT)

MUST
- Use Mollie hosted checkout or official Mollie components whenever possible.
- Treat Mollie webhooks as the source of truth for payment/refund state.
- Implement idempotency for create-payment and create-refund calls.
- Deduplicate webhook deliveries and process events idempotently.
- Persist provider references (payment_id, refund_id) for reconciliation and audit.
- Keep the integration safe to re-run (CI and agents retry work).

MUST NOT
- Must not hardcode payment method names, logos, or ordering anywhere (frontend or backend).
  Reason: iDEAL branding and method evolution (iDEAL → iDEAL | Wero → Wero) must not require code/UI rewrites.
- Must not mark an order as paid based only on return_url/redirect completion.
- Must not store, process, or log card data on our servers. No custom card forms.
- Must not log secrets (API keys, webhook secrets) or commit them to git.

--------------------------------------------------------------------------------

INTEGRATION OVERVIEW (HOSTED CHECKOUT)

Create-payment flow (backend)
1) Ensure Order exists and is eligible to pay.
2) Create Mollie payment/session with:
   - amount (EUR)
   - description (include local order number)
   - redirectUrl (return URL for UX)
   - webhookUrl (server-to-server)
   - metadata/reference containing local order_id (required)
3) Persist provider_payment_id and checkout_url.
4) Return checkout_url to frontend.

Customer flow (frontend)
- Redirect customer to Mollie hosted checkout URL.
- Do not implement payment method UI manually.
- Do not hardcode method display assets.

Confirmation flow (backend)
- Webhook processing fetches the authoritative payment status from Mollie.
- Order transitions to paid only through webhook-confirmed state.

--------------------------------------------------------------------------------

STATE MACHINE (PAYMENTS-RELEVANT)

Rule
Only webhooks may transition an Order into paid/refunded states.

Order statuses used by payments (implemented in orders.models.Order.Status)
pending          -- order created, stock reserved, no payment session yet
pending_payment  -- payment session open, awaiting webhook
paid             -- confirmed paid via webhook
fulfilled        -- shipped (post-paid business state)
payment_failed   -- terminal failure of the last attempt; reserved stock released
expired          -- reservation deadline passed; reserved stock released
cancelled        -- customer/admin cancel before payment; reserved stock released
refunded         -- full refund completed (admin-triggered)

Normalized Payment statuses (implemented in payments.models.Payment.Status)
created          -- local row exists, no PSP session opened yet
pending          -- PSP session opened, awaiting customer
paid             -- confirmed paid via webhook
failed           -- terminal failure
cancelled        -- explicit cancel
expired          -- PSP session expired
refunded         -- money returned (full refund, MVP)

Refund statuses (admin-triggered, full refunds only for MVP)
requested
processing
succeeded
failed
cancelled

MVP scope note
- `partially_refunded` is intentionally NOT a status on Order or Payment.
  Partial refunds are out of scope for MVP and will be added later.
- Spelling: `cancelled` (UK English) is used throughout the codebase to
  match the existing `Order.Status` field.

--------------------------------------------------------------------------------

DATA MODEL REQUIREMENTS (IMPLEMENTED)

The implemented schema lives in `backend/payments/models.py` and
`backend/orders/models.py`. The fields below match the actual code; see
`DOMAIN.md` for full per-field tables.

Order (extended for payments)
- existing fields: order_number, reference, totals, addresses, etc.
- status enum (see state machine above)
- reservation_expires_at (DateTimeField, nullable)
  -- set at order creation to now + Order.RESERVATION_TIMEOUT (30 min)
  -- cleared when the order reaches a terminal state
- helper methods (idempotent, raise InvalidOrderTransition on illegal moves):
  - mark_pending_payment(), mark_paid(), mark_payment_failed(),
    mark_cancelled(), mark_expired(), mark_fulfilled(), mark_refunded()
  - release_stock_reservation()
  - active_payment()

Payment (one row per payment attempt against an Order)
- id (UUID, pk)
- order (FK, PROTECT)
- provider (default "mollie")
- provider_payment_id (CharField, blank initially; unique per provider when set)
- checkout_url (URLField, blank; UX only)
- amount_cents (PositiveIntegerField; EUR cents)
- currency (default "EUR")
- status (enum: see state machine above)
- idempotency_key (CharField, blank)
- raw_provider_payload_last (JSONField, default {})
- created_at, updated_at
- helper methods: get_or_create_active(order), mark_pending(...),
  mark_paid(), mark_failed(), mark_cancelled(), mark_expired(),
  mark_refunded()
- rule: only one Payment with status in {created, pending} per Order at a
  time; enforced by get_or_create_active.

Refund (admin-triggered, full refunds only for MVP)
- id (UUID, pk)
- order (FK, PROTECT)
- payment (FK, PROTECT)
- provider_refund_id (CharField, blank initially; unique per payment when set)
- amount_cents (PositiveIntegerField; MUST equal order.grand_total in cents)
- currency (default "EUR")
- status (enum: see state machine above)
- idempotency_key (CharField, blank)
- created_by (FK auth.User, SET_NULL)
- raw_provider_payload_last (JSONField, default {})
- created_at, updated_at
- helper methods: request_full_refund(order, created_by=...),
  mark_processing(...), mark_succeeded(), mark_failed(), mark_cancelled()
- rule: request_full_refund rejects unpaid orders, orders with no paid
  payment, and orders that already have an active refund in flight.

WebhookEvent (dedup + audit)
- id (UUID, pk)
- provider (default "mollie")
- provider_event_key (CharField; UNIQUE together with provider)
- payload (JSONField, default {})
- received_at, processed_at (nullable)
- processing_status (enum: pending / success / failed)
- processing_error (text, blank)
- helper methods: record_delivery(...), mark_processed_success(),
  mark_processed_failed(error_message)
- rule: record_delivery is idempotent — duplicate deliveries return
  (existing_event, created=False) and MUST NOT trigger side effects again.

--------------------------------------------------------------------------------

MINIMAL API CONTRACT (MVP, GUEST-FIRST)

This is the locked direction for the public payment-flow API. HTTP wiring
is not yet implemented (DRF is still pending in Phase 1/2 follow-up
cards), but every endpoint below has a corresponding model-level helper
already in place so the contract is binding.

Endpoints (kept intentionally small — do not add more without justification):

1) POST /api/checkout/submit
   Purpose
   - Validate cart.
   - Create or reuse an Order for this checkout.
   - Reserve stock at order creation (decrement ProductVariant.stock).
   - Create or reuse the active Payment via Payment.get_or_create_active.
   - Return order/payment status + Mollie checkout_url.
   Rules
   - Repeated submission of the same cart MUST NOT create duplicate open
     orders unnecessarily; reuse the existing pending order while it is
     still within reservation window.

2) GET /api/orders/{token}/status
   Purpose
   - Frontend reads server truth after the customer returns from the
     PSP. Also usable for short polling.
   - `token` is the Order.reference UUID, not the sequential id.
   Rules
   - Reflects DB state. Never derives "paid" from the return URL.

3) POST /api/orders/{token}/retry-payment
   Purpose
   - Create a new Payment for an Order whose previous attempt is
     terminal (failed / cancelled / expired).
   Rules
   - If an active Payment exists, the response should reuse it instead
     of creating a new one (Payment.get_or_create_active).
   - The Order must still be in pending / pending_payment.

4) POST /api/payments/webhook/mollie
   Purpose
   - Webhook-driven payment synchronization and order finalization.
   Rules
   - Verify authenticity.
   - Persist via WebhookEvent.record_delivery (dedup by provider_event_key).
   - Enqueue background processing (Celery, once wired). Heavy work MUST
     NOT happen inline in the HTTP handler.

Admin endpoint (staff-only, full-refund-only for MVP)

5) POST /api/admin/orders/{token}/refund
   Purpose
   - Staff-triggered full refund after inspection.
   Rules
   - Staff-only.
   - Preconditions enforced by Refund.request_full_refund:
     order must be paid, must have a paid Payment, no active refund.
   - amount_cents MUST equal order.grand_total in cents.
   - Uses idempotency_key on the PSP refund call.
   - Final refund state confirmed via webhook or provider fetch
     (Refund.mark_succeeded then flips Payment and Order to refunded).

--------------------------------------------------------------------------------

WEBHOOK PROCESSING (REQUIRED BEHAVIOR)

Webhook handler (HTTP endpoint)
- Verify authenticity.
- Persist WebhookEvent (or compute provider_event_key) and deduplicate.
- Enqueue a job with provider_payment_id (and/or refund id).

Webhook worker job
1) Fetch payment state from Mollie using provider_payment_id.
2) Apply idempotent update:
   - If the same terminal state already applied: no-op.
   - Else update Payment row and corresponding Order state.
3) Emit side effects only on state transitions:
   - Send transactional email only when Order transitions into paid.
   - Avoid duplicate emails by transition guards.

Idempotency requirements
- Use idempotency keys for create-payment and create-refund.
- Store the idempotency key with the Payment/Refund record.
- Webhooks may be retried and delivered out of order; processing must be safe.

--------------------------------------------------------------------------------

SPECIAL CASES (METHOD BEHAVIOR)

SEPA bank transfer
- Asynchronous.
- Order can remain pending_payment for longer than the default 30-minute
  reservation window. Treatment of long-pending SEPA orders is a parking-lot
  item -- options include extending reservation_expires_at on
  mark_pending_payment for SEPA-method payments, or releasing stock and
  re-checking on webhook arrival. Decide before launching SEPA in production.

Klarna (BNPL)
- Treat as potentially asynchronous/conditional.
- Do not build method-specific UI branches; keep behavior provider-driven via Mollie.

iDEAL → iDEAL | Wero → Wero
- Never embed local iDEAL/Wero assets.
- Never depend on method display name in business logic.
- Hosted checkout/components must handle method presentation.

--------------------------------------------------------------------------------

REFUNDS (BUSINESS POLICY MAPPING)

Business policy
- Products are fragile and expensive.
- Returns are rare.
- Customer likely pays return shipping.
- Refund happens after staff inspection.

System mapping
1) Return request captured (outside payments scope).
2) Item received and inspected.
3) Admin triggers refund.
4) Backend calls Mollie refund API with idempotency.
5) Webhook/provider fetch confirms result.
6) Order transitions to refunded or partially_refunded.

--------------------------------------------------------------------------------

VERIFICATION CONTRACT (PAYMENTS ONLY)

Required scenarios — payments
- Card success
- iDEAL success
- PayPal success
- Klarna success
- Bank transfer pending → paid
- Payment failed
- Payment canceled
- Payment expired

Required scenarios — refunds (MVP: full refunds only)
- Full refund (admin-triggered)
- Double-click admin refund action must not double-refund
  (Refund.request_full_refund rejects duplicate active refunds)
- Webhook retry after refund must be idempotent
  (Refund.mark_succeeded is a no-op when already succeeded)

Required scenarios — security
- Webhook verification enforced
- Admin refund endpoint authorization enforced
- No secrets printed in logs during tests

Commands (adapt paths to repo)
pytest -q
pytest -q -k "payment"

Acceptance criteria
- Order becomes paid only via webhook-confirmed processing.
- Refund is created exactly once even with retries/double clicks.
- No payment method names/logos are hardcoded anywhere.
- Hosted checkout is used; card details never touch our server.
- Tests pass.

--------------------------------------------------------------------------------

IMPLEMENTATION SLICES

Slice 1 — MVP payment-flow contract (DONE)
- Payment, Refund, WebhookEvent models in `backend/payments/`.
- Order extended with `reservation_expires_at` and idempotent
  `mark_*` / `release_stock_reservation` / `active_payment` helpers.
- 30-minute reservation timeout (`Order.RESERVATION_TIMEOUT`).
- Full-refund-only enforcement on `Refund.request_full_refund`.
- Tests for the model-level state machine, dedup, and reservation
  release behavior.

Slice 2 — HTTP wiring (pending)
- Add DRF (or equivalent) to backend dependencies.
- Implement the five endpoints listed above.
- Wire Celery + Redis and add the webhook worker job that calls
  `Payment.mark_paid` / `Order.mark_paid` based on PSP fetch.
- Add real Mollie API client integration.

Slice 3 — End-to-end verification (pending)
- Run the full verification contract above against Mollie sandbox.

Report format after work
- Files changed
- Commands run
- Results
- Remaining blockers

--------------------------------------------------------------------------------

ENVIRONMENT VARIABLES (PLACEHOLDERS)

MOLLIE_API_KEY
MOLLIE_WEBHOOK_SECRET (or equivalent webhook verification config)
PUBLIC_BASE_URL (build redirectUrl and webhookUrl)

--------------------------------------------------------------------------------

PARKING LOT (NON-BLOCKING QUESTIONS)

- Whether Mollie method identifiers change in NL during Wero migration.
- Whether Mollie hosted checkout automatically updates iDEAL | Wero branding.
- Klarna availability across EU destinations under one Mollie contract.
- Bank transfer matching details (structured reference and/or virtual IBAN options).