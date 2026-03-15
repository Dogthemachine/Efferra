# Efferra

Luxury artistic candle webshop. NL-first, EU-wide shipping.

## Current status

**Phase 0 — Backend bootstrap complete.**

- Django backend initialized in `backend/`.
- Frontend (Nuxt) is not yet initialized.
- No production deployment configuration exists yet.

## Stack

| Layer    | Technology           | Status      |
|----------|----------------------|-------------|
| Backend  | Django 5.2 / Python  | Initialized |
| Frontend | Nuxt                 | Not started |
| Database | PostgreSQL (target)  | SQLite used for bootstrap |
| Payments | Mollie               | Not started |

## Repository structure

```
Efferra/
├── backend/                # Django backend (Poetry-managed)
│   ├── config/             # Django project settings, URLs, WSGI/ASGI
│   ├── core/               # Bootstrap app (health endpoint)
│   ├── manage.py
│   ├── pyproject.toml      # Python dependencies (Poetry)
│   ├── poetry.lock         # Locked dependency versions
│   └── .env.example        # Environment variable template
├── CLAUDE.md               # Project contract and constraints
├── ENVIRONMENT.md           # Deployment environment specification
├── PAYMENTS.md              # Payment integration specification
├── PLAN.md                  # Development plan
├── Makefile                 # Repository-level commands
└── README.md                # This file
```

## Backend setup

### Prerequisites

- **Python 3.10+** — Django 5.2 requires Python 3.10 or later.
- **Poetry 2.x** — Python dependency manager.

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

### Environment configuration

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` with your local settings. The defaults work for basic local development (SQLite database, debug mode on).

**Real `.env` files are never committed to git.** Only `.env.example` (with safe placeholder values) belongs in version control.

### Running the development server

```bash
cd backend
poetry run python manage.py migrate
poetry run python manage.py runserver
```

The server starts at `http://localhost:8000/`.

### Available endpoints

| Endpoint          | Description           |
|-------------------|-----------------------|
| `/api/health/`    | Health check (JSON)   |
| `/admin/`         | Django admin          |

### Using the Makefile

From the repository root:

```bash
make setup        # Install backend dependencies
make dev          # Run Django dev server
make migrate      # Run database migrations
make check        # Run Django system checks
```

## What is intentionally not done yet

- Nuxt frontend initialization
- PostgreSQL database wiring (SQLite used for bootstrap)
- Redis / Celery setup
- Mollie payment integration
- Product/catalog models
- Django admin customization
- User authentication / social login
- Production deployment configuration
- Docker / containerization

## Python version

Python 3.10+ is required. Django 5.2 (LTS) supports Python 3.10–3.13. The project uses `^3.10` in `pyproject.toml` to support any compatible Python 3.10+ version available on the developer's machine.
