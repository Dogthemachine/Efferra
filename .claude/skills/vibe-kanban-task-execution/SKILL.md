---
name: vibe-kanban-task-execution
description: Execute one Vibe Kanban card safely and consistently. Use this skill when starting work on any task card to ensure the correct workflow, scope discipline, and verification steps.
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
  - Glob
  - Grep
  - Task
---

# Execute a Vibe Kanban Task Card

## Before starting

1. Read `CLAUDE.md` and `PAYMENTS.md` (if payment-related).
2. Read `PLAN.md` to understand the current phase and card dependencies.
3. Identify the exact card scope. Do not solve tasks from future phases unless explicitly requested.

## Execution rules

1. Work only within the scope defined by the card. If the card says "catalog models," do not also build API endpoints unless the card includes them.
2. Keep diffs small and reviewable. Prefer multiple small commits over one large diff.
3. Use the correct package managers:
   - Backend (Python): **Poetry only**. No `pip install`, no `requirements.txt`.
   - Frontend (Node): **pnpm only**. No `npm`, no `yarn`.
4. Follow existing project conventions found in the codebase. Do not introduce new patterns without justification.
5. Do not add infrastructure components (Docker, managed services, new databases) unless the card explicitly requires them.
6. Do not commit secrets, `.env` files, or real credentials.
7. Do not modify `CLAUDE.md`, `PAYMENTS.md`, or `ENVIRONMENT.md` unless the card scope includes documentation updates. Use the `docs-sync` skill for doc changes.

## Verification before claiming done

1. Run relevant checks:
   - Backend: `cd backend && poetry run python manage.py check`
   - Backend tests: `cd backend && poetry run pytest -q` (if tests exist)
   - Frontend: `cd frontend && pnpm run build` or `pnpm run typecheck` (if frontend exists)
2. Confirm no secrets are present in changed files.
3. Confirm the diff matches the card scope — nothing more, nothing less.

## Completion summary

After finishing, provide:

- **Files changed**: list of files created, modified, or deleted.
- **Commands run**: key commands executed during the task.
- **Verification result**: pass/fail for each check run.
- **Follow-ups**: any discovered work that belongs to a separate card.

## Branch and PR workflow

Branch creation, PR opening, and closeout belong to the `branch-pr-review-closeout` skill. Do not open PRs or merge branches as part of task execution unless explicitly asked.
