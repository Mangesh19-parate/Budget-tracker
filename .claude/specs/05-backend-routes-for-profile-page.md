# Spec: Backend Routes For Profile Page

## Overview
Step 5 replaces the hardcoded data on `/profile` with real queries against the existing `users` and `expenses` tables. The Step 4 template stays unchanged — every variable it consumes (`user`, `summary`, `transactions`, `categories`) continues to be passed by name. New DB helpers in `database/db.py` fetch the logged-in user's record, their recent expenses, and per-category totals; the `/profile` route in `app.py` becomes a thin assembler that calls those helpers and renders the template. This step finalises the read path for the dashboard so that Step 7+ (add/edit/delete) can extend it without further template work.

## Depends on
- Step 1: Database setup (`users` and `expenses` tables must exist)
- Step 2: Registration (user accounts must exist)
- Step 3: Login + Logout (`session["user_id"]` must be set)
- Step 4: Profile Page (the `profile.html` template must exist and declare the variables consumed here)

## Routes
No new routes. The existing `GET /profile` route is modified:

- `GET /profile` — render the profile page with real DB data — logged-in only (redirect to `/login` if `session["user_id"]` is missing)

## Database changes
No database changes. The existing `users` and `expenses` tables (see `database/db.py:43–60`) are sufficient.

## Templates
- **Modify:** `templates/profile.html` — no structural changes required. Two small text edits:
  1. Remove the "Based on hardcoded sample" sub-label under "Top category" (line 47) — replace with neutral copy such as "Most-used category this account".
  2. Replace the "What's next?" placeholder card (lines 107–113) with an actionable empty/CTA card, e.g. a single primary button linking to `url_for('add_expense')` once Step 7 lands. For Step 5 the button may link to `/` (landing) — Step 7 will retarget it.
  3. Optional: update the empty-state copy when a brand-new user has zero expenses (handled by the route, not the template).

## Files to change
- `app.py` — replace the four hardcoded dicts in the `/profile` route with calls to new helpers in `database/db.py`. Add the imports for the new helpers. Keep the route function single-responsibility: fetch → render.
- `database/db.py` — add the following helpers (see Rules for signatures and contracts):
  - `get_user_by_id(user_id: int) -> sqlite3.Row | None`
  - `list_recent_expenses_for_user(user_id: int, limit: int = 5) -> list[sqlite3.Row]`
  - `summarise_expenses_for_user(user_id: int) -> dict`
  - `list_category_totals_for_user(user_id: int, limit: int = 4) -> list[sqlite3.Row]`
- `templates/profile.html` — minor copy edits as listed under Templates above.

## Files to create
None.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — use raw `sqlite3` via `get_db()` only
- Parameterised queries only — never f-strings in SQL
- Passwords hashed with werkzeug (no auth changes this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline styles
- No DB logic inside route functions — every query lives in `database/db.py`
- Every helper in `database/db.py` must open and close its own connection via `get_db()` (pattern already used by `create_user`, `get_user_by_email`)
- `get_user_by_id` must return `None` (not raise) when the row is missing — the route must then `abort(401)` or `redirect(url_for("login"))`
- `list_recent_expenses_for_user` must `ORDER BY date DESC, id DESC` and apply a `LIMIT` clause
- `summarise_expenses_for_user` must return at minimum: `total_spent` (float, raw — formatting belongs in the route), `transaction_count` (int), `top_category` (str or `None` when no expenses exist)
- `list_category_totals_for_user` must `GROUP BY category` and `ORDER BY total DESC LIMIT ?` — return rows with `category` and `total` columns
- Formatting rules for the route:
  - Currency rendering (`₹ 1,23,456` style with Indian comma grouping) must happen in `app.py`, not in the helpers or the template — add a small private helper `_format_inr(amount: float) -> str` in `app.py`
  - Initials for the avatar must be derived in the route from `user["name"]` (first letter of first two words, uppercased) — never persisted in the DB
  - `member_since` must be derived in the route by parsing `user["created_at"]` (e.g. `datetime.strptime(...).strftime("%b %Y")`)
  - Badge classes must be derived from the category name (e.g. slug → `badge-food`, `badge-travel`, `badge-bills`, default `badge-other`) in the route, not stored in the DB
- When a user has zero expenses, `top_category` must be `"—"`, `total_spent` must be `"₹ 0"`, and the transactions / categories tables must render an empty-state row instead of crashing
- Follow existing PEP 8 style: snake_case, type hints on new helpers, docstrings on public helpers

## Definition of done
- [ ] `git status` is clean apart from files touched by this step
- [ ] `app.py` imports the four new helpers from `database/db.py`
- [ ] `database/db.py` exports `get_user_by_id`, `list_recent_expenses_for_user`, `summarise_expenses_for_user`, `list_category_totals_for_user`, each with a docstring
- [ ] Visiting `/profile` while logged out still redirects to `/login` (HTTP 302 → 200)
- [ ] Visiting `/profile` as `demo@spendly.com` shows the demo user's real name and email, not "Aarav Mehta" / "aarav.mehta@example.com"
- [ ] Total spent, transaction count, and top category reflect the seeded expenses for that user (or `0` / `—` for a brand-new account)
- [ ] Recent-expenses table shows at most 5 rows ordered newest-first, with Indian-formatted `₹` amounts and category badge classes that match the category names
- [ ] Category breakdown shows at most 4 categories ordered by total descending, with Indian-formatted `₹` totals
- [ ] A brand-new registered user (no expenses) sees `/profile` with empty-state copy, no crashes, and no Python tracebacks in the server log
- [ ] `templates/profile.html` no longer contains the "hardcoded" / "What's next?" placeholder copy
- [ ] No hex colour values appear in `templates/profile.html`
- [ ] No DB code appears inside route functions in `app.py` — every DB call is delegated to `database/db.py`
- [ ] All SQL uses `?` placeholders — `rg "\.execute\(.*\".*%.*\"" app.py database/` returns no matches
- [ ] `python app.py` starts the server on port 5001 without errors
- [ ] Manual smoke test: log out → `/profile` redirects to `/login`; log in as demo → `/profile` shows real data