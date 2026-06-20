# TODO

- [ ] Implement Registration feature per `.claude/specs/02-registration.md`
  - [x] Set `app.secret_key` (if missing) and update `/register` route to handle GET + POST with validation + flash
  - [x] Add `create_user()` helper to `database/db.py`
  - [x] Update `templates/register.html` form (POST to `url_for('register')`, fields, confirm_password) and flash rendering
  - [x] Run app sanity check (start server, validate route wiring)
  - [x] Verify password stored as hash in `spendly.db`

  - [x] Run tests (pytest) if available


