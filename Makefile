.PHONY: setup setup-backend setup-frontend dev dev-backend dev-frontend \
       migrate check test build-frontend

# ── Full-stack ────────────────────────────────────────────────
setup: setup-backend setup-frontend

dev:
	@echo "Start backend and frontend dev servers in separate terminals:"
	@echo "  make dev-backend"
	@echo "  make dev-frontend"

# ── Backend ───────────────────────────────────────────────────
setup-backend:
	cd backend && poetry install

dev-backend:
	cd backend && poetry run python manage.py runserver

migrate:
	cd backend && poetry run python manage.py migrate

check:
	cd backend && poetry run python manage.py check

# ── Frontend ──────────────────────────────────────────────────
setup-frontend:
	cd frontend && pnpm install

dev-frontend:
	cd frontend && pnpm dev

build-frontend:
	cd frontend && pnpm generate
