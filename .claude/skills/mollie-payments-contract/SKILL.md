---
name: mollie-payments-contract
description: Enforce payment integration rules from PAYMENTS.md when implementing or modifying payment-related code. Use this skill for any work touching payments, refunds, webhooks, or Mollie integration.
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
  - Glob
  - Grep
---

# Mollie Payments Contract

## Before any payment work

**Read `PAYMENTS.md` first.** It is the authoritative specification for all payment integration decisions. This skill summarizes the key rules but `PAYMENTS.md` is the source of truth.

> Note: `PAYMENTS.md` exists in the private development repo. It is excluded from the public mirror.

## Hard rules (non-negotiable)

### Hosted checkout only
- Use Mollie hosted checkout or official Mollie components.
- Never build custom card entry forms.
- Never process, store, or log card data on our servers.

### Webhook is source of truth
- Order transitions to `paid` only via webhook-confirmed processing.
- Never mark an order as paid based on redirect/return URL alone.
- Return/redirect URLs are UX convenience only.

### Idempotency
- Create-payment and create-refund calls must use idempotency keys.
- Webhook processing must be idempotent and deduplicated.
- Store idempotency keys with Payment/Refund records.
- Webhooks may arrive out of order or be retried — processing must be safe.

### No hardcoded payment method display
- Never hardcode payment method names, logos, or ordering in frontend or backend.
- The iDEAL → iDEAL | Wero → Wero branding transition must not require code changes.
- Mollie hosted checkout handles method presentation.

### Refunds
- Refunds happen only after admin inspection and approval.
- Admin triggers refund through the backend; backend calls Mollie refund API.
- Final refund state is confirmed via webhook or provider fetch.
- Double-click on refund action must not cause double refund (idempotency).

## Data model (minimum from PAYMENTS.md)

- **Payment**: one row per payment attempt, linked to Order. Stores `provider_payment_id`, normalized status, amount.
- **Refund**: admin-triggered, linked to Order and Payment. Stores `provider_refund_id`, status, amount.
- **WebhookEvent**: deduplication and audit trail. Stores `provider_event_key` (unique), processing result.

## Webhook processing pattern

1. HTTP endpoint receives webhook.
2. Verify authenticity.
3. Persist/deduplicate WebhookEvent.
4. Enqueue background job (Celery) with provider payment/refund ID.
5. Worker fetches current state from Mollie API.
6. Idempotent update to Payment and Order records.
7. Side effects (emails) only on state transitions, guarded against duplicates.

## Environment variables (placeholders only)

- `MOLLIE_API_KEY` — never commit real values.
- `MOLLIE_WEBHOOK_SECRET` — never commit real values.
- `PUBLIC_BASE_URL` — used to build redirect and webhook URLs.

## Verification checklist

- [ ] Order becomes `paid` only via webhook processing.
- [ ] Refund is created exactly once even with retries.
- [ ] No payment method names/logos hardcoded anywhere.
- [ ] No card data logged or stored.
- [ ] Webhook authentication enforced.
- [ ] Admin refund endpoint requires staff authorization.
- [ ] Tests cover success, failure, cancel, expire, and retry scenarios.
