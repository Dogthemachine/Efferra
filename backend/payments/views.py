# Payments HTTP views are intentionally not implemented in this card.
#
# The minimal MVP API contract — pay/, status/, retry-payment/, webhook/ —
# is documented in PAYMENTS.md. Wiring it up requires DRF (still an open
# Phase 1/2 card) and the real Mollie integration (later in Phase 3), so
# the contract layer in this app is deliberately model-only for now.
