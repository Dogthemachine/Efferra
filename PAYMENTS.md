# PAYMENTS.md — Mollie Payments Contract (Webshop)

Purpose
This file is the operational contract for payments integration only.
Out of scope: VAT/OSS/tax rules, invoicing format rules, shipping rules, frontend tech choice.

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

Minimum Order statuses used by payments
pending_payment
paid
payment_failed
canceled
refund_pending
refunded
partially_refunded

Normalized Payment statuses (store provider status + normalize)
created
pending
paid
failed
canceled
expired
refunded
partially_refunded

Refund statuses (admin-triggered)
requested
processing
succeeded
failed
canceled

--------------------------------------------------------------------------------

DATA MODEL REQUIREMENTS (MINIMUM)

Order prerequisites
Payments attach to an existing Order.
Order must have:
- stable order_id
- total amount in cents
- currency (EUR)

Payment entity (one row per payment attempt)
Fields
id (UUID)
order_id (FK)
provider = "mollie"
provider_payment_id (string)
checkout_url (string, optional)
status (enum, normalized)
amount_cents (int)
currency = "EUR"
created_at, updated_at
raw_provider_payload_last (JSON, optional)

Refund entity (admin-triggered after inspection)
Fields
id (UUID)
order_id (FK)
payment_id (FK)
provider_refund_id (string)
amount_cents (int)
status (enum)
created_by_admin (FK/user id)
created_at, updated_at

WebhookEvent entity (dedup + audit)
Fields
id (UUID)
provider = "mollie"
provider_event_key (unique per delivery; design must guarantee uniqueness)
received_at
processed_at
processing_result (success/failure + message)

--------------------------------------------------------------------------------

API CONTRACT (DJANGO BACKEND, FRONTEND SEPARATE)

Public endpoints
POST /api/orders/
Creates an order (guest or logged-in).

POST /api/orders/{order_id}/pay/
Creates Mollie payment/session.
Returns checkout_url.

GET /api/orders/{order_id}/status/
Optional polling endpoint for UX.
Must reflect server-truth (DB state), not return_url assumptions.

Webhook endpoint (server-to-server)
POST /api/payments/mollie/webhook/
Rules
- Verify authenticity.
- Persist/deduplicate delivery.
- Enqueue background processing.
- Heavy work must not happen inline.

Admin endpoint
POST /api/admin/orders/{order_id}/refund/
Rules
- Staff-only.
- Preconditions enforced (return received + inspected + approved; order eligible).
- Uses idempotency key.
- Creates Mollie refund and persists provider_refund_id.
- Final refund state confirmed via webhook or provider fetch.

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
- Order can remain pending_payment for longer.
- Stock reservation policy must exist (TTL-based reserve; release on expiry/cancel).

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

Required scenarios — refunds
- Full refund
- Partial refund (if supported/needed)
- Double-click admin refund action must not double-refund
- Webhook retry after refund must be idempotent

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

FIRST IMPLEMENTATION SLICE (CLOUD CODE TASK)

Scope: payments only. Do not implement VAT/OSS/tax here.

Deliverables
1) Models: Payment, Refund, WebhookEvent (plus minimal Order fields if missing).
2) Endpoint: POST /api/orders/{order_id}/pay/ (creates Mollie payment, returns checkout_url).
3) Endpoint: POST /api/payments/mollie/webhook/ (verify, dedup, enqueue).
4) Worker: fetch Mollie payment state and idempotently update Payment + Order.
5) Endpoint: POST /api/admin/orders/{order_id}/refund/ (inspection-approved refund, idempotent).
6) Tests for the verification contract.

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