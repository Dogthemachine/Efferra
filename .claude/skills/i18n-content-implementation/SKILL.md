---
name: i18n-content-implementation
description: Implement multilingual behavior correctly for the 4 launch languages (NL, EN, DE, FR). Use this skill when adding or modifying translated content, locale files, or i18n routing.
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
  - Glob
  - Grep
---

# i18n Content Implementation

## Launch languages

- **Dutch (NL)** — primary market
- **English (EN)**
- **German (DE)**
- **French (FR)**

All four languages must be supported at launch. Do not add languages beyond these unless explicitly requested.

## Two domains of translation

### 1. Frontend UI strings
- Static text in the Nuxt frontend (buttons, labels, navigation, error messages).
- Stored in frontend locale files (e.g., `frontend/locales/nl.json`, `frontend/locales/en.json`, etc.).
- Managed by the Nuxt i18n module.

### 2. Backend content translations
- Dynamic content created by admins (product names, descriptions, material names, etc.).
- Stored in the database via Django's translation framework (e.g., `django-modeltranslation` or similar).
- Served through the API with language-specific fields or content negotiation.

## Rules

1. **Do not invent translations.** If a translation is missing, leave it empty or use a clear placeholder (e.g., `[TODO: NL translation]`). Do not generate machine translations silently.
2. **Keep the two domains separate.** Frontend locale files handle UI strings. Backend handles content. Do not mix them.
3. **All four locales must be present** in any i18n-related change. If you add a new UI string key, add it to all four locale files (even if some are placeholders).
4. **Fallback behavior**: document the fallback strategy when implementing. Common approach: fall back to English if a translation is missing, then to the default language.
5. **i18n routing**: Nuxt routes should include locale prefixes (`/nl/`, `/en/`, `/de/`, `/fr/`). Follow the routing pattern established in the project.
6. **API language**: the API should accept a language parameter or header to return content in the requested language.

## When adding a new translatable field (backend)

1. Add the field to the model with translation support.
2. Create and run migrations.
3. Update the Django admin to show all language variants of the field.
4. Update the API serializer to include translated fields.
5. Test that the API returns correct content per language.

## When adding new UI strings (frontend)

1. Add the key and value to all four locale files.
2. Use the i18n helper (e.g., `$t('key')`) in templates — never hardcode user-visible text.
3. Verify the string renders correctly in at least two languages.

## Verification

1. Check that all locale files have the same set of keys (no missing keys in any language).
2. Test language switching in the frontend (if dev server is available).
3. Test API content in multiple languages (if applicable).
4. Confirm no hardcoded user-visible strings in templates or components.
