# Project-Level Claude Code Skills

This directory contains project-level Claude Code skills committed to the repository. They provide reusable workflow instructions for common development tasks in this project.

## Why these are committed

- Skills travel with the repo so any developer (or Claude Code session) can use them.
- They appear in both the private development repo and the public mirror.
- **They must never contain secrets, credentials, or private keys.**

## Skill inventory

| Skill | Purpose |
|-------|---------|
| `vibe-kanban-task-execution` | Execute one Vibe Kanban card safely |
| `branch-pr-review-closeout` | Finish-a-task workflow: PR, merge, cleanup |
| `private-public-mirror-safety` | Protect the two-repo workflow |
| `phase-0-backend-bootstrap` | Backend foundation tasks (Phase 0) |
| `docs-sync` | Keep documentation truthful and synchronized |
| `django-api-slice` | Create one backend API slice |
| `nuxt-page-slice` | Create or modify one frontend page/component |
| `i18n-content-implementation` | Implement multilingual behavior (NL/EN/DE/FR) |
| `mollie-payments-contract` | Enforce payment integration rules |
| `django-admin-customization` | Build admin tools for shop operations |
| `makefile-maintainer` | Maintain root Makefile targets |
| `phase-planning-card-breakdown` | Convert plan phases into Kanban cards |

## Structure

Each skill lives in its own folder with a `SKILL.md` file:

```
.claude/skills/<skill-name>/SKILL.md
```

Some skills may include companion files (`reference.md`, `checklist.md`) for extended content that would bloat the main skill file.

## Notes

- Some skills reference project docs (`CLAUDE.md`, `PAYMENTS.md`, `PLAN.md`, `ENVIRONMENT.md`) that exist only in the private repo and are excluded from the public mirror.
- Skills are designed for the private development workflow. The public mirror is not the operational development workspace.
