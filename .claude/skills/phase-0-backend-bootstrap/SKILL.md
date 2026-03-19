---
name: phase-0-backend-bootstrap
description: Support backend foundation tasks during Phase 0 scaffolding. Use this skill when working on Django project setup, initial app creation, settings configuration, or health endpoint work in the early bootstrap stage.
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
  - Glob
  - Grep
---

# Phase 0 Backend Bootstrap

## Working directory

All backend work happens in `backend/`. Do not create Django files outside this directory.

## Dependency management

- Use **Poetry only**. Run `poetry add <package>` to add dependencies.
- Never create `requirements.txt` or use `pip install` directly.
- Always update `poetry.lock` when dependencies change: `poetry lock` or `poetry add`.
- The `pyproject.toml` in `backend/` is the source of truth for Python dependencies.

## Environment configuration

- Use `backend/.env.example` as the template for environment variables.
- `.env.example` must contain **only safe placeholder values** (no real keys, no real database passwords).
- Real `.env` files are gitignored and never committed.
- When adding a new environment variable, update `.env.example` with a placeholder.

## Django conventions for this project

- Project settings live in `backend/config/settings.py`.
- URL configuration root is `backend/config/urls.py`.
- Each Django app lives directly under `backend/` (e.g., `backend/core/`, `backend/catalog/`).
- App names match the module names defined in `PLAN.md` Section B.

## Bootstrap patterns

- Health endpoint: `GET /api/health/` returning JSON with service status.
- Use Django's `INSTALLED_APPS` for app registration.
- Keep settings env-driven using `os.environ.get()` or a config library.
- SQLite is acceptable during bootstrap; PostgreSQL is the target for later phases.

## Makefile integration

- Backend commands exposed through the root `Makefile` must use Poetry:
  ```makefile
  setup:
  	cd backend && poetry install
  dev:
  	cd backend && poetry run python manage.py runserver
  ```
- When adding new backend workflow commands, update the Makefile. Use the `makefile-maintainer` skill for guidance.

## Verification

Before finishing any bootstrap task:

1. Run `cd backend && poetry run python manage.py check` — must pass with no errors.
2. Run `cd backend && poetry run python manage.py migrate` — must complete without errors.
3. If tests exist: `cd backend && poetry run pytest -q`.
4. Verify `make setup` works from the repo root.

## Documentation

- Update `README.md` only with information that is **currently true**.
- Do not document features, endpoints, or commands that do not yet exist.
- If you add a new Makefile target or endpoint, add it to the README.
