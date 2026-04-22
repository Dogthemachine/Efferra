# Efferra

Luxury artistic candle webshop. NL-first, EU-wide shipping.

## Current status

**Phase 0 complete. Phase 1 catalog domain and Phase 2 cart/order domain models implemented.**

- Django backend initialized in `backend/`.
- Nuxt frontend initialized in `frontend/` with i18n skeleton (4 locales).
- Frontend-to-backend API bridge established via Nuxt dev proxy.
- Catalog domain models in place: `Collection`, `Product`, `ProductVariant`, `ProductImage`.
- Cart domain models in place: `Cart`, `CartItem` (session-based, token-identified).
- Order domain models in place: `Order`, `OrderItem` (guest checkout, full purchase snapshot).
- No production deployment configuration exists yet.

## Stack

| Layer    | Technology           | Status      |
|----------|----------------------|-------------|
| Backend  | Django 5.2 / Python  | Domain models active (catalog, cart, orders) |
| Frontend | Nuxt 3.x / pnpm     | Initialized |
| Database | PostgreSQL           | Configured for local dev  |
| Payments | Mollie               | Not started |

## Repository structure

```
Efferra/
├── backend/                # Django backend (Poetry-managed)
│   ├── config/             # Django project settings, URLs, WSGI/ASGI
│   ├── core/               # Bootstrap app (health endpoint)
│   ├── catalog/            # Catalog domain: Collection, Product, ProductVariant, ProductImage
│   ├── cart/               # Cart domain: Cart, CartItem (session-based, token-identified)
│   ├── orders/             # Order domain: Order, OrderItem (guest checkout, purchase snapshot)
│   ├── manage.py
│   ├── pyproject.toml      # Python dependencies (Poetry)
│   ├── poetry.lock         # Locked dependency versions
│   └── .env.example        # Environment variable template
├── frontend/               # Nuxt frontend (pnpm-managed)
│   ├── app.vue             # Root Vue component
│   ├── pages/              # Nuxt file-based routing
│   │   └── index.vue       # Home page (with i18n demo)
│   ├── i18n/
│   │   └── locales/        # Locale JSON files
│   │       ├── nl.json     # Dutch (default locale)
│   │       ├── en.json     # English
│   │       ├── de.json     # German
│   │       └── fr.json     # French
│   ├── nuxt.config.ts      # Nuxt configuration (i18n module configured)
│   ├── package.json        # Node dependencies (pnpm)
│   ├── pnpm-lock.yaml      # Locked dependency versions
│   ├── .node-version       # Node version hint (24)
│   └── .env.example        # Environment variable template
├── .claude/skills/         # Project-level Claude Code skills
├── CLAUDE.md               # Project contract and constraints
├── ENVIRONMENT.md          # Deployment environment specification
├── PAYMENTS.md             # Payment integration specification
├── PLAN.md                 # Development plan
├── Makefile                # Repository-level commands
└── README.md               # This file
```

## Prerequisites

### Backend

- **Python 3.10+** — Django 5.2 requires Python 3.10 or later.
- **Poetry 2.x** — Python dependency manager.
- **PostgreSQL** — A running local PostgreSQL server. Install however preferred (Homebrew, system package, Postgres.app, etc.).

### Frontend

- **Node.js 24.x** — The project uses Node 24. A `.node-version` file is provided in `frontend/` for version managers (nvm, fnm, etc.).
- **pnpm** — Node dependency manager. Installed via corepack (ships with Node.js).

## Installing pnpm

pnpm is activated through Node.js corepack:

```bash
corepack enable
corepack prepare pnpm@latest --activate
```

Verify installation:

```bash
pnpm --version
```

**Do not use npm or yarn for frontend dependencies.** pnpm is the only authorized Node package manager for this project.

## Backend setup

### Installing Poetry

If Poetry is not already installed:

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

Verify installation:

```bash
poetry --version
```

### Installing backend dependencies

```bash
cd backend
poetry install
```

This creates a virtual environment and installs all dependencies from `poetry.lock`.

### Using the Poetry environment

Run any command inside the Poetry-managed virtualenv:

```bash
poetry run python manage.py <command>
```

Or activate the shell:

```bash
poetry shell
```

### PostgreSQL setup

The backend requires a local PostgreSQL database. Install PostgreSQL however suits our platform (Homebrew, system package, Postgres.app, etc.) and ensure the server is running.

**Create the database and role:**

```bash
createuser efferra
createdb -O efferra efferra
```

Verify the connection:

```bash
psql -U efferra -d efferra -c "SELECT 1;"
```

The default `DATABASE_URL` in `.env.example` uses a passwordless local connection (`postgres://efferra@localhost:5432/efferra`). This works if the local PostgreSQL authentication configuration allows passwordless access for that role. If the setup requires a password, set one on the role and update `DATABASE_URL` in the local `.env`.

### Backend environment configuration

Copy the example environment file:

```bash
cd backend
cp .env.example .env
```

Edit `.env` with local settings. The `DATABASE_URL` must point to the local PostgreSQL instance. See `.env.example` for the expected format.

### Running the backend

```bash
cd backend
poetry run python manage.py migrate
poetry run python manage.py runserver
```

The server starts at `http://localhost:8000/`.

### Available backend endpoints

| Endpoint          | Description           |
|-------------------|-----------------------|
| `/api/health/`    | Health check (JSON)   |
| `/admin/`         | Django admin          |

## Frontend setup

### Installing frontend dependencies

```bash
cd frontend
pnpm install
```

### Frontend environment configuration

```bash
cd frontend
cp .env.example .env
```

### Running the Nuxt development server

```bash
cd frontend
pnpm dev
```

The dev server starts at `http://localhost:3000/`.

Routes are prefixed by locale: `/nl/`, `/en/`, `/de/`, `/fr/`. The default locale is Dutch (`nl`).

### Building the static site

```bash
cd frontend
pnpm generate
```

Output is written to `frontend/.output/public/` and can be served by any static file server.

## Using the Makefile

All developer workflow commands run from the repository root via `make`.

### Primary targets

```bash
make setup    # Install backend + frontend deps, create .env files from .env.example if missing
make dev      # Print instructions for starting dev servers (see below)
make test     # Sanity checks: backend test runner + frontend build validation
make build    # Run Django system checks + generate static Nuxt site
```

### Dev servers

`make dev` prints how to start both servers. They run in separate terminals:

```bash
# Terminal 1
make dev-backend      # Django dev server on localhost:8000

# Terminal 2
make dev-frontend     # Nuxt dev server on localhost:3000
```

The frontend dev server proxies `/api/*` requests to the backend automatically.

### Helper targets

```bash
make setup-backend    # Install backend dependencies only (Poetry)
make setup-frontend   # Install frontend dependencies only (pnpm)
make migrate          # Run Django database migrations
make check            # Run Django system checks
make build-frontend   # Generate static Nuxt site only
```

### What `make test` actually does today

- **Backend** (`test-backend`): runs `python manage.py test` — the Django test runner discovers and executes all tests. Tests exist for `cart` and `orders` domain models (18 tests). The `catalog` app has tests stubs ready but no written tests yet.
- **Frontend** (`test-frontend`): runs `pnpm build` — a full Nuxt production build that validates TypeScript types and module resolution. No dedicated test runner (e.g., Vitest) is configured yet.

### What the build target produces

- **Backend**: runs `manage.py check` to validate Django configuration. No collectstatic or packaging step exists yet.
- **Frontend**: runs `pnpm generate` to produce a static site in `frontend/.output/public/`.

## i18n setup

The frontend uses `@nuxtjs/i18n` with 4 locales configured:

| Code | Language | Route prefix |
|------|----------|-------------|
| `nl` | Dutch (default) | `/nl/` |
| `en` | English | `/en/` |
| `de` | German | `/de/` |
| `fr` | French | `/fr/` |

Locale files are in `frontend/i18n/locales/`. Currently they contain placeholder UI strings only. Real translations and product content are not implemented yet.

The i18n strategy is `prefix` — all routes include a locale prefix. The default locale is `nl` (Netherlands-first).

## Environment files

Real `.env` files are **never committed to git.** Only `.env.example` files (with safe placeholder values) belong in version control. The `.gitignore` enforces this.

## Python version

Python 3.10+ is required. Django 5.2 (LTS) supports Python 3.10–3.13. The project uses `^3.10` in `pyproject.toml` to support any compatible Python 3.10+ version available on the developer's machine.

## Local API bridge

During local development, the Nuxt dev server proxies all `/api/*` requests to the Django backend. This is configured via Nitro's `devProxy` in `nuxt.config.ts`.

- **Frontend**: `http://localhost:3000` (Nuxt dev server)
- **Backend**: `http://localhost:8000` (Django runserver)
- **Proxy rule**: `GET http://localhost:3000/api/health/` → `GET http://localhost:8000/api/health/`

The proxy target is controlled by the `NUXT_PUBLIC_API_BASE_URL` environment variable (default: `http://localhost:8000`). See `frontend/.env.example`.

To verify the bridge works:

1. Start both servers (`make dev-backend` and `make dev-frontend` in separate terminals).
2. Visit `http://localhost:3000/nl/` — the page should show "Backend status" with "Status: ok".
3. Or: `curl http://localhost:3000/api/health/` — should return `{"status": "ok"}`.

## Redis (planned, not yet wired)

Redis is part of the agreed architecture for background job processing (Celery task queue). It will be used for:

- Payment webhook processing (enqueue webhook events for async worker processing)
- Asynchronous email sending
- Any long-running admin operations

**Redis is not required to run the backend at the current stage.** No Celery tasks or Redis-dependent code exists yet.

When Redis is needed (Phase 3 — Payments), a local Redis server will be required:

**macOS (Homebrew):**

```bash
brew install redis
brew services start redis
```

**Linux:**

```bash
sudo apt install redis-server
sudo systemctl start redis
```

A `REDIS_URL` placeholder is included (commented out) in `backend/.env.example` for when it becomes needed.

## What is intentionally not done yet

- REST API endpoints for catalog, cart, and orders
- Redis / Celery wiring (documented above; will be implemented when needed)
- Mollie payment integration
- Django admin customization beyond basic model registration
- Shipping fee engine
- Promotions engine (promo codes, gift cards, bundles)
- User authentication / social login
- Production deployment configuration
- Docker / containerization
- Full i18n content translation for product content
- Analytics / GDPR compliance tools
