---
name: nuxt-page-slice
description: Create or modify one Nuxt frontend page or component properly. Use this skill when building or updating pages, components, or layouts in the Nuxt frontend.
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
  - Glob
  - Grep
---

# Nuxt Page Slice

## Working directory

All frontend work happens in `frontend/`. Do not create frontend files outside this directory.

## Package manager

- Use **pnpm only**. No `npm`, no `yarn`.
- Add dependencies: `cd frontend && pnpm add <package>`.
- Add dev dependencies: `cd frontend && pnpm add -D <package>`.

## Nuxt conventions

- Pages live in `frontend/pages/` and follow Nuxt file-based routing.
- Components live in `frontend/components/`.
- Layouts live in `frontend/layouts/`.
- Composables live in `frontend/composables/`.
- Follow existing patterns in the codebase. Do not introduce new structural conventions without justification.

## Architecture boundaries

- **Business logic belongs in the backend.** The frontend calls the Django API for data and mutations.
- **Do not access the database** from the frontend. All data comes through API calls.
- **Payment method UI** is never rendered by the frontend. Redirect to Mollie hosted checkout instead.
- **Static build model**: Nuxt generates static HTML for catalog/content pages at build time. Dynamic data (cart, checkout, order status) is fetched client-side at runtime.

## API interaction

- Use Nuxt's `useFetch` or `$fetch` for API calls.
- Configure the API base URL via environment/runtime config, not hardcoded strings.
- Handle loading states and errors in the UI.

## i18n

- Launch languages: NL, EN, DE, FR.
- UI strings belong in frontend locale files.
- Product content translations come from the backend API.
- Follow the i18n setup established in the project. See the `i18n-content-implementation` skill for detailed i18n guidance.

## Verification

1. Build check: `cd frontend && pnpm run build` (if build target exists).
2. Type check: `cd frontend && pnpm run typecheck` (if configured).
3. Lint: `cd frontend && pnpm run lint` (if configured).
4. Manual verification: start dev server with `cd frontend && pnpm run dev` and check the page renders correctly.
5. Confirm no secrets in the diff.

## Documentation

Update `README.md` only if the change affects developer setup or workflow (e.g., new environment variable, new build step). Do not document individual pages in the README.
