---
name: private-public-mirror-safety
description: Protect the two-repo (private source-of-truth + public sanitized mirror) workflow. Use this skill when making changes that could affect what appears in the public repo, or when reviewing for accidental secret exposure.
allowed-tools:
  - Bash
  - Read
  - Grep
---

# Private/Public Mirror Safety

## Repo topology

- **Private repo** (origin): source of truth for all development. Contains project docs (`CLAUDE.md`, `ENVIRONMENT.md`, `PAYMENTS.md`, `PLAN.md`), code, and skills.
- **Public repo**: sanitized mirror updated by GitHub Actions on push to `main`.

## What the mirror workflow does

The GitHub Actions workflow (`.github/workflows/publish-public.yml`) runs on push to `main` and:

1. Checks out the private repo.
2. Removes internal docs: `CLAUDE.md`, `ENVIRONMENT.md`, `PAYMENTS.md`, `PLAN.md`.
3. Removes any `.env` files that might exist.
4. Force-pushes the sanitized result to the public repo.

## What is safe in the public mirror

- All application code (`backend/`, `frontend/`, etc.).
- `.claude/skills/` directory and all skill files (committed intentionally; must remain secret-free).
- `README.md`, `Makefile`, `.gitignore`, `.github/workflows/`.
- `.env.example` files (safe placeholder values only).

## What is excluded from the public mirror

- `CLAUDE.md`, `ENVIRONMENT.md`, `PAYMENTS.md`, `PLAN.md` (removed by the mirror workflow).
- Any `.env` files (removed by the mirror workflow).

## Rules

1. **Never commit secrets** to any branch. Not to private, not to public. Check before every commit:
   - No API keys, tokens, passwords, or private keys in any file.
   - No real credentials in `.env.example` files — only safe placeholders.
2. **Skills must be secret-free** because they appear in the public mirror.
3. **Skills may reference project docs** (`CLAUDE.md`, `PAYMENTS.md`, etc.) in their instructions, but these docs only exist in the private repo. Skills should not break if those docs are absent — they should note that the referenced doc is required context available in the development repo.
4. **Review changes for accidental secrets** before pushing:
   ```
   git diff --cached | grep -iE '(api.key|secret|token|password|private.key)'
   ```
5. **The mirror workflow itself must not leak secrets.** GitHub Actions secrets (`PUBLIC_REPO_DEPLOY_KEY`, `PUBLIC_REPO_SSH_URL`) are stored in GitHub and never printed to logs.
6. **Do not modify the mirror workflow** unless explicitly asked. Changes to `.github/workflows/publish-public.yml` affect what appears publicly.

## When adding new files to the repo

Ask: "Should this appear in the public mirror?"

- If **yes**: commit normally. The mirror includes everything not explicitly removed.
- If **no**: add a removal step to the mirror workflow, or place the file in a directory that is already excluded.

Currently, only the four named doc files are removed. If a new category of private content is added, the mirror workflow must be updated.

## Key nuance

These project skills are designed for the private development workflow. The public mirror is not the operational development workspace. Skills referencing source-of-truth docs will work in the private repo context but those docs will not be present in the public mirror.
