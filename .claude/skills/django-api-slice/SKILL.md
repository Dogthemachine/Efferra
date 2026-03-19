---
name: django-api-slice
description: Create or modify one backend API slice (model, view, URL, serializer, tests) safely within the Django project. Use this skill when implementing a new API endpoint or modifying an existing one.
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
  - Glob
  - Grep
---

# Django API Slice

## Scope discipline

One API slice = one cohesive unit of backend functionality. Typically includes:

1. **Model(s)** — database schema for the feature.
2. **Serializer(s)** — input validation and output formatting.
3. **View(s)** — request handling and business logic.
4. **URL(s)** — route registration.
5. **Tests** — at minimum, model validation and API response tests.

Do not implement frontend changes in the same slice. The API is the boundary.

## Working directory

All backend code lives in `backend/`. Each Django app is a direct subdirectory of `backend/`.

## Implementation steps

1. **Read existing code** in the target app before writing. Understand current models, views, and URL patterns.
2. **Add or modify models** in `<app>/models.py`. Create migrations: `poetry run python manage.py makemigrations`.
3. **Add serializers** in `<app>/serializers.py` (or equivalent). Validate input strictly.
4. **Add views** in `<app>/views.py`. Keep business logic in the view or a service layer — not in serializers.
5. **Register URLs** in `<app>/urls.py` and include them in `config/urls.py` if not already included.
6. **Write tests** in `<app>/tests.py` or `<app>/tests/`. Cover success paths, validation errors, and edge cases.

## Conventions

- Use Django's standard app structure. Do not invent custom layouts.
- Follow the API toolkit already in use (DRF if present, or whatever is established).
- Keep endpoints RESTful and predictable.
- Avoid adding packages unless clearly necessary. Check `pyproject.toml` for what is already available.
- Use Poetry for any new dependency: `cd backend && poetry add <package>`.

## Architecture boundaries

- Backend is the source of truth for data and business logic.
- Frontend consumes the API — it does not access the database.
- Payment-related slices must follow `PAYMENTS.md` rules (read `PAYMENTS.md` first).
- Admin-related changes follow the `django-admin-customization` skill.

## Verification

1. Run migrations: `cd backend && poetry run python manage.py migrate`.
2. Run checks: `cd backend && poetry run python manage.py check`.
3. Run tests: `cd backend && poetry run pytest -q` (or `pytest -q -k "<feature>"`).
4. Confirm no secrets in the diff.

## Documentation

Update `README.md` only if the new slice changes the developer workflow (e.g., new required setup step, new Makefile target). Do not document every endpoint in the README — API documentation belongs in API docs or tests.
