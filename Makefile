.PHONY: setup setup-backend setup-frontend setup-env dev dev-backend dev-frontend \
       test test-backend test-frontend build build-frontend \
       migrate check

# ── Full-stack ────────────────────────────────────────────────

## Install all dependencies and prepare local env files.
setup: setup-backend setup-frontend setup-env

## Print instructions for starting both dev servers.
dev:
	@echo ""
	@echo "Start backend and frontend in separate terminals:"
	@echo ""
	@echo "  Terminal 1:  make dev-backend     (Django on localhost:8000)"
	@echo "  Terminal 2:  make dev-frontend     (Nuxt on localhost:3000)"
	@echo ""
	@echo "The frontend proxies /api/* requests to the backend automatically."
	@echo ""

## Run checks/tests for both backend and frontend.
test: test-backend test-frontend

## Build artifacts for both backend and frontend.
build: check build-frontend

# ── Backend ───────────────────────────────────────────────────

## Install backend Python dependencies via Poetry.
setup-backend:
	cd backend && poetry install

## Run Django development server on localhost:8000.
dev-backend:
	cd backend && poetry run python manage.py runserver

## Run Django test suite.
test-backend:
	cd backend && poetry run python manage.py test

## Run Django database migrations.
migrate:
	cd backend && poetry run python manage.py migrate

## Run Django system checks (validates settings, models, etc.).
check:
	cd backend && poetry run python manage.py check

# ── Frontend ──────────────────────────────────────────────────

## Install frontend Node dependencies via pnpm.
setup-frontend:
	cd frontend && pnpm install

## Run Nuxt development server on localhost:3000.
dev-frontend:
	cd frontend && pnpm dev

## Build Nuxt (includes TypeScript type-checking).
test-frontend:
	cd frontend && pnpm build

## Generate static Nuxt site to frontend/.output/public/.
build-frontend:
	cd frontend && pnpm generate

# ── Helpers ───────────────────────────────────────────────────

## Copy .env.example to .env for backend/frontend if .env does not exist yet.
setup-env:
	@if [ -f backend/.env ]; then echo "backend/.env already exists — skipping"; else cp backend/.env.example backend/.env && echo "Created backend/.env from .env.example"; fi
	@if [ -f frontend/.env ]; then echo "frontend/.env already exists — skipping"; else cp frontend/.env.example frontend/.env && echo "Created frontend/.env from .env.example"; fi
