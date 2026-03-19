---
name: phase-planning-card-breakdown
description: Convert PLAN.md phases into well-structured Vibe Kanban cards. Use this skill when breaking down a development phase into actionable task cards.
allowed-tools:
  - Read
  - Write
  - Glob
  - Grep
---

# Phase Planning and Card Breakdown

## Before starting

1. **Read `PLAN.md`** to understand the full phase plan, dependencies, and sequencing rationale.
2. Read `CLAUDE.md` for project constraints that affect card scope.
3. Check the current repo state to understand what already exists.

> Note: `PLAN.md` and `CLAUDE.md` exist in the private development repo. They are excluded from the public mirror.

## Card structure

Each card must include:

- **Title**: short, specific, action-oriented (e.g., "Add catalog product models" not "Do catalog stuff").
- **Scope**: exactly what this card delivers. Be specific about files, endpoints, models, or pages.
- **Constraints**: relevant project rules that apply to this card (from `CLAUDE.md`, `PAYMENTS.md`, etc.).
- **Acceptance criteria**: concrete, testable conditions that define "done."
- **Out of scope**: explicitly state what this card does NOT include to prevent scope creep.
- **Verification**: specific commands or checks to run before marking the card complete.

## Rules for good cards

1. **Small and testable.** Each card should be completable in a single focused session. If a card feels like it needs multiple days, split it.
2. **Preserve dependency order.** Cards within a phase should be ordered so each card's dependencies are met by previous cards.
3. **No giant implementation cards.** "Implement the entire catalog" is not a card. "Add Product and ProductFamily models" is a card.
4. **Match current repo state.** Do not create cards that assume code from future phases exists. Ground card scope in what the repo contains now.
5. **Keep future cards aligned with phase order.** Phase 2 cards should not assume Phase 3 is done.
6. **Include tags** for categorization (e.g., `backend`, `frontend`, `api`, `admin`, `i18n`).

## Phase breakdown workflow

1. Read the phase description and deliverables in `PLAN.md`.
2. Identify the natural work units (models, endpoints, pages, config changes).
3. Order them by dependency: foundational work first, then features that build on it.
4. Write each card with the full structure above.
5. Review: can each card be verified independently? If not, adjust boundaries.

## Example card format

```
Title: Add Product and ProductFamily models
Tags: catalog, backend, models

Scope:
- Create Product, ProductFamily, Variant, and ProductImage models in backend/catalog/models.py.
- Create and run migrations.
- Register models in Django admin with basic list views.

Constraints:
- Variants are specific allowed combinations of material and color (not a full matrix).
- Limited editions must be supported as a product flag.

Acceptance criteria:
- Models exist and migrations apply cleanly.
- Admin can create products with variants and images.
- poetry run python manage.py check passes.

Out of scope:
- API endpoints (separate card).
- i18n for product content (separate card).
- Frontend pages (separate card).

Verification:
- cd backend && poetry run python manage.py migrate
- cd backend && poetry run python manage.py check
- cd backend && poetry run pytest -q -k "catalog"
```

## Cross-phase awareness

When creating cards for a phase, note dependencies on previous phases and flag any risks from `PLAN.md` Section E that affect the current phase.
