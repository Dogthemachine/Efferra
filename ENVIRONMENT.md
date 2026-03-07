ENVIRONMENT.md — Deployment/Runtime Environment Contract (VM)

High-level architecture 
* Reverse proxy: Nginx
* Backend app server: Gunicorn (Django)
* Frontend: Nuxt built as static output (served as static files; no Node SSR server for now, pre-render as static HTML)
* Database: PostgreSQL on the same VM
* Background jobs: Celery + Redis (Redis on the same VM)
* Backend/Frontend separation: API-first (Nuxt calls Django API)
* Hosting model: single VM.

Domains and routing (recommended default)
* www.<domain> → Nuxt static site
* api.<domain> → Django API
* api.<domain>/admin/ → Django admin (staff only)
Nginx routes:
* www serves Nuxt static assets
* api proxies to Gunicorn
* /static/ and /media/ served directly by Nginx (no Django for static/media)

Services on the VM 
Run as system services (e.g., systemd):
* nginx
* postgresql
* redis
* webshop-backend (Gunicorn)
* webshop-worker (Celery worker)
* webshop-beat (Celery beat, if scheduled jobs are needed)
Nuxt does not run as a service in production (static build served by Nginx).


Static + media handling 
* Django static is collected to /static/
* Media uploads stored in /media/
* Nginx serves both directly:
    * /static/ → shared static directory
    * /media/ → shared media directory

Background jobs 
* Use Celery + Redis for asynchronous processing.
* Typical tasks include:
    * payment webhook processing pipeline (validate → enqueue → worker applies state)
    * email sending (if implemented asynchronously)
    * any long-running admin operations

Configuration and secrets 
* Use separate environment files per app (paths are conventional; exact names can vary):
    * backend env file (Django)
    * frontend env file (Nuxt)
Rules:
* Do not commit env and md files to git.
* Do not print secrets to logs.
Note:
* Exact environment variable names and full config lists are intentionally left for implementation.

Local development (expected shape)
* Django runs locally (e.g., localhost:8000)
* Nuxt dev server runs locally (e.g., localhost:3000)
* Postgres + Redis run locally (native or via Docker)
