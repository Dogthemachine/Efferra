---
name: docs-sync
description: Keep project documentation truthful and synchronized with actual repo state. Use this skill when updating README.md, CLAUDE.md, ENVIRONMENT.md, PAYMENTS.md, or other project docs to ensure accuracy.
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - Grep
---

# Documentation Synchronization

## Core principle

**Only document what is already true.** Never write future plans as present facts. Never describe features that do not yet exist as if they are implemented.

## When to update each document

### `README.md`
- When a new developer-facing command is added (Makefile target, endpoint, setup step).
- When the repo structure changes meaningfully (new top-level directory, new app).
- When the project status changes (e.g., a phase is completed).
- Remove or update entries that describe things no longer true.

### `CLAUDE.md`
- When a project constraint or decision changes.
- When a new hard constraint is established.
- Do **not** update `CLAUDE.md` for routine implementation changes.
- `CLAUDE.md` is a contract document, not a changelog.

### `ENVIRONMENT.md`
- When deployment architecture decisions change.
- When new services or infrastructure components are added.
- Do not update for code-level changes that do not affect deployment.

### `PAYMENTS.md`
- When payment integration rules or data model requirements change.
- When new payment methods or flows are added.
- This is an authoritative contract — changes require careful review.

### `PLAN.md`
- When phase scope or sequencing changes.
- When new cards are added or existing cards are completed.
- Keep the plan aligned with actual progress.

## Rules

1. Read the document before editing it. Understand its current state.
2. Do not add aspirational content. If a feature is planned but not built, say "planned" or "not yet implemented" — do not describe it as working.
3. Keep documentation concise. Remove redundant explanations.
4. When removing a feature or changing behavior, update all affected docs — not just one.
5. Project-level skills (`.claude/skills/`) are part of the repo. If a skill references a workflow that changes, update the skill too.
6. Docs in the private repo (`CLAUDE.md`, `ENVIRONMENT.md`, `PAYMENTS.md`, `PLAN.md`) are excluded from the public mirror. `README.md` appears in both repos — ensure it makes sense without the private docs.

## Verification

After updating documentation:

1. Read the updated document end-to-end. Check for contradictions.
2. Verify any commands or paths mentioned actually exist and work.
3. Confirm no secrets or private values appear in the document.
