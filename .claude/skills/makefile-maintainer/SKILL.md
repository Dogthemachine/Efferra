---
name: makefile-maintainer
description: Maintain the root Makefile as the repo orchestration entrypoint. Use this skill when adding, modifying, or reviewing Makefile targets to ensure they work correctly and honestly.
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
---

# Makefile Maintainer

## Role of the Makefile

The root `Makefile` provides common developer commands for both backend and frontend. It is the single entrypoint for repo-level operations.

## Package manager rules

- **Backend targets** must use Poetry:
  ```makefile
  setup:
  	cd backend && poetry install
  dev:
  	cd backend && poetry run python manage.py runserver
  ```
- **Frontend targets** must use pnpm:
  ```makefile
  frontend-setup:
  	cd frontend && pnpm install
  frontend-dev:
  	cd frontend && pnpm run dev
  ```
- Never use `pip`, `npm`, or `yarn` in Makefile targets.

## Rules

1. **Keep targets simple and honest.** Each target should do one clear thing.
2. **Do not hide destructive actions.** If a target drops a database or deletes files, name it clearly (e.g., `reset-db`) and consider adding a confirmation prompt.
3. **Every target must work.** Do not add speculative targets for features that do not exist yet. If the frontend is not initialized, do not add frontend targets.
4. **Match actual repo behavior.** Test targets after adding or modifying them.
5. **Use `.PHONY`** for all non-file targets.
6. **Use tab indentation** (required by Make).

## Standard target naming

Follow these conventions for consistency:

| Target | Purpose |
|--------|---------|
| `setup` | Install all dependencies |
| `dev` | Start development servers |
| `test` | Run all test suites |
| `build` | Build for production |
| `migrate` | Run database migrations |
| `check` | Run framework checks |
| `lint` | Run linters |
| `clean` | Remove build artifacts |

Prefix with `backend-` or `frontend-` when disambiguation is needed (e.g., `backend-test`, `frontend-build`).

## When to update the Makefile

- When a new developer workflow command is added.
- When an existing command changes (different flags, different directory).
- When a new app (backend or frontend) is initialized.
- Remove targets that no longer work.

## Verification

1. Run each modified target and confirm it succeeds.
2. Run `make` with no arguments — confirm it does not run destructive operations (or add a default help target).
3. Update `README.md` if Makefile changes affect documented developer workflow.
