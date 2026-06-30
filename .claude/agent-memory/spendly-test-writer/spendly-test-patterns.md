---
name: spendly-test-patterns
description: How to write isolated, spec-anchored pytest tests for Spendly without conftest.py and without touching the real spendly.db.
metadata:
  type: project
---

Spendly has no `tests/conftest.py` and no existing test files as of 2026-06-29. The test-writer must keep fixtures local to each new `tests/test_<feature>.py` file.

**How to apply:** when writing tests for a new Spendly feature, follow these patterns.

## DB isolation without mocking

The project's `database/db.py` exposes a module-level `DB_PATH` (default `<project_root>/spendly.db`) and `get_db()` reads that attribute on every call. To run tests against a temp DB:

1. Patch `database.db.DB_PATH` to a `tempfile.mkstemp` path *before* importing the `app` module — the app's startup calls `init_db()` and `seed_db()` at import time and will write wherever `DB_PATH` is currently bound.
2. Re-import / `importlib.reload` the `app` module after patching, so its top-level `init_db()` and `seed_db()` go to the temp file.
3. Re-confirm `_db_module.DB_PATH = temp_db_path` after the import, defensively, in case of import-ordering surprises.
4. The seeded demo user is `demo@spendly.com` / `demo123` (created idempotently by `seed_db()`). Login via POST `/login` with those credentials to get a `session["user_id"]`.

## Module-scope vs function-scope fixtures

- The `temp_db_path` and `app` fixtures should be `scope="module"` so the seeded data persists across tests in a module (cheap, fast).
- The `client` fixture should be `scope="function"` so cookies / sessions don't bleed between tests.
- The `logged_in_client` fixture POSTs to `/login` with demo creds and asserts a 302/303 redirect before returning the client.

## Things to test on the `/profile` date-filter feature

- The active-filter pill is gated on `filter.active`; in the template it is wrapped in `{% if filter.active %}` and contains the literal text "Showing expenses from" and a `.active-filter-clear` anchor with `href="/profile"`.
- The "Clear" link inside the form has `class="btn-ghost"` and `href="/profile"` (no query string).
- The pill's date chips render `…` (U+2026 horizontal ellipsis) when a bound is missing or invalid.
- Empty-state copy: transactions table has "No expenses yet", category breakdown has "No spending yet".

## Why these patterns

- Why patch DB_PATH before import: the app module runs `init_db()`/`seed_db()` at import time against whatever `DB_PATH` is bound then. Patching after import would leave the real `spendly.db` mutated.
- Why module-scope temp_db_path: spinning up a fresh temp DB per test is slow and unnecessary — SQLite handles concurrent reads fine within one process.
- Why local fixtures, not conftest: project convention is per-file fixtures (see also [[no-prior-conftest]]).

Related: [[no-prior-conftest]]
