---
name: no-prior-conftest
description: Spendly has no tests/conftest.py as of 2026-06-29 — keep test fixtures local to each test file.
metadata:
  type: project
---

As of 2026-06-29, `tests/conftest.py` does not exist in the Spendly codebase and there are no test files. The test-writer must not create or modify `tests/conftest.py`; keep all fixtures (app, client, temp_db_path, logged_in_client) local to each new `tests/test_<feature>.py` file.

**Why:** per the task contract for this project, conftest.py is treated as out-of-scope. Adding fixtures there could create order-dependent test interactions as more features are added.

**How to apply:** if a future task explicitly asks for shared conftest fixtures, ask for confirmation first. Otherwise, duplicate the local fixture block across test files (small duplication, no coupling).

Related: [[spendly-test-patterns]]
