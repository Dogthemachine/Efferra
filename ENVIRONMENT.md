# ENVIRONMENT.md — Deployment & Runtime Environment

## Overview

Single-VM deployment. No managed cloud services unless explicitly added later.

| Component | Technology | Notes |
|---|---|---|
| Reverse proxy | Nginx | Routes www and api subdomains |
| Backend app server | Gunicorn (Django) | API + admin |
| Frontend | Nuxt static build | Pre-rendered HTML/CSS/JS, served by Nginx |
| Database | PostgreSQL | On the same VM |
| Background jobs | Celery + Redis | Both on the same VM |

API-first split: Nuxt calls Django API. Nuxt never accesses the database directly.

---

## Domain routing

| Host | Destination |
|---|---|
| `www.<domain>` | Nuxt static site (served by Nginx) |
| `api.<domain>` | Django API (proxied to Gunicorn) |
| `api.<domain>/admin/` | Django admin (staff only) |

Nginx serves `/static/` and `/media/` directly — Django is not involved in static/media serving in production.

---

## Services (run as systemd units)

| Service | Unit name | Notes |
|---|---|---|
| Nginx | `nginx` | |
| PostgreSQL | `postgresql` | |
| Redis | `redis` | |
| Django API | `webshop-backend` | Gunicorn process |
| Celery worker | `webshop-worker` | Processes async jobs (webhook processing, emails) |
| Celery beat | `webshop-beat` | Scheduled jobs, if needed |

Nuxt does **not** run as a service. It is a static build served directly by Nginx.

---

## Static and media files

- Django static files are collected to `/static/` via `manage.py collectstatic`.
- Media uploads (product images) stored in `/media/`.
- Nginx serves both directly; Django is bypassed for these paths in production.

---

## Background jobs (Celery)

Celery + Redis are required for:

- Payment webhook processing pipeline (validate → dedup → enqueue → worker applies state)
- Transactional email dispatch (order confirmation, shipping updates, refund notices)
- Any long-running admin operations

**Redis is not required for local development at the current stage.** No Celery tasks exist yet. Redis becomes required when Phase 3 (payments) is implemented.

---

## Configuration and secrets

- Backend: `backend/.env` (not committed — `backend/.env.example` is the template)
- Frontend: `frontend/.env` (not committed — `frontend/.env.example` is the template)
- Never commit `.env` files to git.
- Never print secrets to logs.
- Full variable lists are in the respective `.env.example` files.

Key backend variables:
- `SECRET_KEY` — Django secret key
- `DEBUG` — set to `False` in production
- `ALLOWED_HOSTS` — production domain(s)
- `DATABASE_URL` — PostgreSQL connection string
- `REDIS_URL` — Redis connection string (required from Phase 3 onward)
- `MOLLIE_API_KEY`, `MOLLIE_WEBHOOK_SECRET`, `PUBLIC_BASE_URL` — payment integration (Phase 3)

---

## Local development

| Service | Default URL |
|---|---|
| Django backend | `http://localhost:8000` |
| Nuxt frontend | `http://localhost:3000` |

- PostgreSQL and Redis run locally (native install or Docker — implementation choice).
- Nuxt dev server proxies `/api/*` to the Django backend via Nitro `devProxy`.
- Use `make dev-backend` and `make dev-frontend` in separate terminals.
- `make setup` installs all dependencies and creates `.env` files from `.env.example`.
