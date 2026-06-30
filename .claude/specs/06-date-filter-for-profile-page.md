# Spec: Date Filter For Profile Page

## Overview
Step 6 extends the existing `/profile` dashboard with a date-range filter so users can scope the displayed summary stats, recent expenses table, and category breakdown to a window that matters to them (e.g. "this month", "last 30 days", or a custom from/to range). The filter is applied entirely server-side: query-string parameters drive a single refactored query path that the existing helpers can reuse, and the rendered page surfaces the active range plus a "Clear filter" affordance. No new page, no JS framework — the filter is a plain HTML form that submits via GET so URLs stay shareable and the back button works.

## Depends on
- Step 1: Database setup (`expenses.date` column must exist)
- Step 4: Profile Page (`templates/profile.html` exists with the four sections)
- Step 5: Backend Routes For Profile Page (the four `database/db.py` helpers and the `/profile` route are already in place — this step extends them)

## Routes
No new routes. The existing `GET /profile` route is modified to accept query-string parameters:

- `GET /profile` — render the profile page, optionally filtered by `start` and `end` query params (`YYYY-MM-DD`) — logged-in only (redirect to `/login` if `session["user_id"]` is missing)

The filter is read from `request.args`:
- `start` (optional) — inclusive lower bound on `expenses.date`
- `end` (optional) — inclusive upper bound on `expenses.date`
- Invalid or missing dates are ignored (no error flash) — the page falls back to "All time"

## Database changes
No database changes. The existing `expenses` table (see `database/db.py:51–60`) is sufficient — the `date` column is already `TEXT NOT NULL` storing ISO `YYYY-MM-DD`, which compares correctly with `>=` / `<=` in SQLite.

## Templates
- **Modify:** `templates/profile.html` — add a date-filter bar above the summary stats row, and an "active filter" indicator below the section title when a range is applied:
  1. New `filters` block before the `.profile-grid` wrapper: a `<form method="get" action="{{ url_for('profile') }}">` with two `<input type="date">` fields (Start / End), an "Apply" submit button (`btn-primary`), and a "Clear" link (`btn-ghost`) that points to `url_for('profile')` with no params.
  2. When `filter.active` is true, render a small `.active-filter` pill below the summary stats showing e.g. `Showing expenses from 2026-06-01 to 2026-06-29` and a small inline `(Clear)` link.
  3. The existing empty-state row in the transactions table stays the same — it now also covers the "no expenses in this range" case.
- **Modify:** `templates/base.html` — no structural changes required. Existing nav remains.

## Files to change
- `app.py` — modify the `/profile` route to:
  - Read `start` and `end` from `request.args`, validate they parse as `YYYY-MM-DD`, and ignore them otherwise (no flash, silent fallback to "all time").
  - Pass the parsed dates through to the DB helpers.
  - Build a `filter` context dict (`active`, `start`, `end`, `start_iso`, `end_iso`) for the template.
  - Keep the route single-responsibility: parse → fetch → render.
- `database/db.py` — extend the existing helpers to accept an optional date range:
  - `list_recent_expenses_for_user(user_id, limit=5, start=None, end=None)` — when `start`/`end` provided, add `AND date >= ?` / `AND date <= ?` to the WHERE clause.
  - `summarise_expenses_for_user(user_id, start=None, end=None)` — same WHERE augmentation; the existing self-contained property (does not depend on `list_category_totals_for_user`) is preserved.
  - `list_category_totals_for_user(user_id, limit=4, start=None, end=None)` — same WHERE augmentation.
  - `get_user_by_id` is **unchanged** — it never reads `expenses`.
  - All helpers must keep their existing return shapes; existing callers (none yet for the filtered versions, but the helpers themselves) must remain backwards-compatible (default args keep prior behaviour).

## Files to create
None.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — use raw `sqlite3` via `get_db()` only
- Parameterised queries only — never f-strings in SQL
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline styles
- No DB logic inside route functions — every query lives in `database/db.py`
- Every helper in `database/db.py` must open and close its own connection via `get_db()` (pattern already used by the Step 5 helpers)
- Date parsing in `app.py` must use `datetime.strptime(s, "%Y-%m-%d")` inside a `try`/`except ValueError` — on failure, silently treat the param as absent (do not flash, do not 400)
- When `start` > `end`, treat the range as empty (no rows match) and continue rendering normally — the empty-state row handles it
- When only one of `start`/`end` is provided, the other bound is open (i.e. behaves as `>= start` or `<= end`)
- Date-range helpers must compose WHERE clauses by appending clauses to a list and joining with `" AND "` — no f-strings inside the SQL string itself; bind values separately
- Formatting rules are unchanged from Step 5:
  - Currency rendering (`₹ 1,23,456` style) stays in `app.py`, not in the helpers or the template
  - Initials, member-since, badge classes all stay derived in the route
- The "active filter" pill must use the same `badge-*` CSS classes for the start/end chips — never inline-colour the date strings
- The filter form must use `method="get"` so the URL reflects the active range (shareable, bookmarkable, browser-back friendly)
- Hidden state: when `start` is provided but `end` is not, the form must submit only `start` (not an empty `end=`) — use Jinja `{% if filter.start_iso %}` to set the input `value` and rely on disabled inputs OR omit the field; preferred: always include both inputs but tolerate missing values server-side
- Follow existing PEP 8 style: snake_case, type hints on new helper signatures, docstrings on changed helpers

## Definition of done
- [ ] `git status` is clean apart from files touched by this step
- [ ] `app.py` reads `start` and `end` from `request.args`, validates them, and silently ignores invalid dates
- [ ] `database/db.py` exposes `list_recent_expenses_for_user`, `summarise_expenses_for_user`, and `list_category_totals_for_user` with optional `start` / `end` kwargs that default to `None`
- [ ] When both `start` and `end` are absent, `/profile` renders identically to before this step (same data, same totals)
- [ ] When `start=2026-06-01&end=2026-06-30` is passed and the user has expenses in that range, the recent-expenses table, summary stats, and category breakdown all reflect only those rows
- [ ] When only `start=2026-06-01` is passed, the filters apply an open-ended lower bound (everything from that date onward)
- [ ] When only `end=2026-06-30` is passed, the filters apply an open-ended upper bound (everything up to that date)
- [ ] When `start=invalid-date` is passed, the page renders as if no filter were applied (no flash, no traceback)
- [ ] When the range matches zero expenses, the summary stats show `₹ 0` / `0` / `—`, the transactions table shows the empty-state row, and the category breakdown shows "No spending yet"
- [ ] The active filter pill displays the chosen range when `filter.active` is true, with a working "Clear" link that returns to `/profile` with no query string
- [ ] The filter form submits via GET — visiting `/profile?start=2026-06-01&end=2026-06-30` directly renders the filtered view
- [ ] Visiting `/profile` while logged out still redirects to `/login`
- [ ] All SQL uses `?` placeholders — `rg "\.execute\(.*\".*%.*\"" app.py database/` returns no matches
- [ ] No hex colour values appear in `templates/profile.html`
- [ ] No DB code appears inside route functions in `app.py`
- [ ] `python app.py` starts the server on port 5001 without errors
- [ ] Manual smoke test: log in as demo → `/profile` shows all seeded data → click filter with `start=2026-06-01&end=2026-06-30` → page reloads with filtered data → click "Clear" → returns to full view