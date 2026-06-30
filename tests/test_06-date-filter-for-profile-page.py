"""Spec-anchored pytest cases for Step 6: Date Filter For Profile Page.

Spec source: .claude/specs/06-date-filter-for-profile-page.md

The feature extends `GET /profile` with optional `?start=YYYY-MM-DD` and
`?end=YYYY-MM-DD` query-string filters. The filter is applied entirely
server-side; invalid dates are silently ignored; the rendered page surfaces
an "active filter" pill with a working Clear link. No new routes, no new
templates, no new dependencies.

These tests assert observable behavior (HTTP status, response body strings,
redirect targets, DB-level helper results) and never read internal helpers
or implementation internals. The Flask app and SQLite database are real
(not mocked); the test DB is a per-test temp file, isolated from
`spendly.db` at the project root.
"""

from __future__ import annotations

import os
import sqlite3
import sys
import types

import pytest


# --------------------------------------------------------------------------- #
# Test isolation: redirect the project's SQLite DB to a temp file            #
# --------------------------------------------------------------------------- #

# We must patch DB_PATH *before* importing the app, because the app module
# runs init_db() and seed_db() at import time against whatever DB_PATH is
# currently bound. Patching the module attribute before import also means
# the helpers' get_db() will read the patched path on every call.

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import database.db as _db_module  # noqa: E402

_TEMP_DB_PATH: str | None = None


def _make_temp_db_path() -> str:
    """Allocate a per-session temp DB path. We re-use a single file across
    the whole test module to keep seeded data stable between tests."""
    import tempfile

    fd, path = tempfile.mkstemp(prefix="spendly_test_", suffix=".db")
    os.close(fd)
    return path


@pytest.fixture(scope="module")
def temp_db_path() -> str:
    """One temp DB per test module. Initialized via the project's own
    init_db() and seeded via seed_db() so the schema and demo data are
    exactly what the real app uses."""
    global _TEMP_DB_PATH
    if _TEMP_DB_PATH is None:
        _TEMP_DB_PATH = _make_temp_db_path()
        _db_module.DB_PATH = _TEMP_DB_PATH
        _db_module.init_db()
        _db_module.seed_db()
    return _TEMP_DB_PATH


# --------------------------------------------------------------------------- #
# App + client fixtures (local — do NOT modify tests/conftest.py)             #
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def app(temp_db_path):
    """Flask app with the real routes, pointed at the temp DB."""
    # Reset DB_PATH one more time in case any prior import cached it.
    _db_module.DB_PATH = temp_db_path

    # Import the app after DB_PATH is patched; the startup init_db/seed_db
    # in app.py will run against the temp file.
    import importlib

    if "app" in sys.modules:
        importlib.reload(sys.modules["app"])
    import app as _app_module
    # Re-confirm the path in case of import-order weirdness.
    _db_module.DB_PATH = temp_db_path
    _app_module.app.config["TESTING"] = True
    _app_module.app.config["SECRET_KEY"] = "test-secret-key"
    return _app_module.app


@pytest.fixture()
def client(app):
    """Flask test client. Fresh per-test to avoid session bleed."""
    return app.test_client()


@pytest.fixture()
def logged_in_client(client, app):
    """A test client already authenticated as the seeded demo user.

    The spec does not mandate a specific login mechanism beyond the
    existing `session["user_id"]` check in /profile, so we POST to the
    project's existing /login route with the seeded demo credentials.
    """
    resp = client.post(
        "/login",
        data={"email": "demo@spendly.com", "password": "demo123"},
        follow_redirects=False,
    )
    # Spec doesn't require the response code, only that the user is
    # authenticated. A successful login redirects (302/303).
    assert resp.status_code in (302, 303), (
        f"expected login redirect, got {resp.status_code}: {resp.data!r}"
    )
    return client


# --------------------------------------------------------------------------- #
# Sanity: the spec says invalid `start`/`end` must NEVER 500.                  #
# Also: a helper-level smoke test for the date filter.                        #
# --------------------------------------------------------------------------- #

# --- Auth boundary --------------------------------------------------------- #

def test_logged_out_profile_with_query_params_redirects_to_login(client):
    # Spec: "logged-in only (redirect to /login if session['user_id'] is missing)"
    # Spec DoD: "Visiting /profile while logged out still redirects to /login"
    resp = client.get(
        "/profile?start=2026-06-01&end=2026-06-30",
        follow_redirects=False,
    )
    assert resp.status_code in (301, 302)
    # The redirect target must be the login route, not a 200 on /profile.
    location = resp.headers.get("Location", "")
    assert location.endswith("/login") or location.endswith("/login?"), (
        f"expected redirect to /login, got Location={location!r}"
    )


def test_logged_out_profile_without_query_params_redirects_to_login(client):
    # Spec DoD: logged-out /profile must redirect to /login (no filter applied
    # at the auth layer — query params are read AFTER the auth gate).
    resp = client.get("/profile", follow_redirects=False)
    assert resp.status_code in (301, 302)
    assert resp.headers.get("Location", "").endswith("/login")


# --- Baseline: no filter ---------------------------------------------------- #

def test_logged_in_profile_without_query_params_renders_baseline(logged_in_client):
    # Spec DoD: "When both `start` and `end` are absent, /profile renders
    # identically to before this step (same data, same totals)"
    # Spec rule: filter form is always present, but the active-filter pill is
    # NOT present when no range is applied.
    resp = logged_in_client.get("/profile")
    assert resp.status_code == 200

    body = resp.data.decode("utf-8")

    # The filter form is always present.
    assert "filter-form" in body, "expected filter form on baseline view"
    assert 'name="start"' in body
    assert 'name="end"' in body
    assert 'action="' in body  # form action attr

    # The active-filter pill must NOT appear when no filter is applied.
    assert "Showing expenses from" not in body, (
        "active-filter pill must be hidden when no range is applied"
    )
    assert "active-filter" not in body, (
        "active-filter block must not appear when no range is applied"
    )


# --- Both bounds: rows in range -------------------------------------------- #

def test_profile_with_both_bounds_and_rows_in_range_shows_active_pill(
    logged_in_client, temp_db_path,
):
    # Spec DoD: "When start=2026-06-01&end=2026-06-30 is passed and the user
    # has expenses in that range, the recent-expenses table, summary stats,
    # and category breakdown all reflect only those rows"
    # Spec template: pill text "Showing expenses from {start} to {end}" with
    # a working Clear link back to /profile.
    from datetime import date

    today = date.today()
    year, month = today.year, today.month
    start = f"{year:04d}-{month:02d}-01"
    end = f"{year:04d}-{month:02d}-28"

    resp = logged_in_client.get(f"/profile?start={start}&end={end}")
    assert resp.status_code == 200

    body = resp.data.decode("utf-8")

    # The pill text per the spec template.
    assert "Showing expenses from" in body
    assert start in body
    assert end in body
    assert "active-filter" in body

    # The Clear link in the pill points to /profile (no query string).
    assert "active-filter-clear" in body
    # There must be an anchor in the pill with href ending in /profile
    # (and no query string) — at least one such link exists.
    assert 'class="active-filter-clear" href="/profile"' in body


# --- Open-ended lower bound ------------------------------------------------- #

def test_profile_with_only_start_uses_open_ended_lower_bound(logged_in_client):
    # Spec DoD: "When only start=2026-06-01 is passed, the filters apply an
    # open-ended lower bound (everything from that date onward)"
    # Spec template: when only one bound is present, the other chip is `…`
    from datetime import date

    today = date.today()
    year, month = today.year, today.month
    start = f"{year:04d}-{month:02d}-01"

    resp = logged_in_client.get(f"/profile?start={start}")
    assert resp.status_code == 200

    body = resp.data.decode("utf-8")
    assert "Showing expenses from" in body
    assert start in body
    # The end chip should render the placeholder `…` when end is absent.
    assert "…" in body


# --- Open-ended upper bound ------------------------------------------------- #

def test_profile_with_only_end_uses_open_ended_upper_bound(logged_in_client):
    # Spec DoD: "When only end=2026-06-30 is passed, the filters apply an
    # open-ended upper bound (everything up to that date)"
    # Spec template: when only one bound is present, the other chip is `…`
    from datetime import date

    today = date.today()
    year, month = today.year, today.month
    end = f"{year:04d}-{month:02d}-28"

    resp = logged_in_client.get(f"/profile?end={end}")
    assert resp.status_code == 200

    body = resp.data.decode("utf-8")
    assert "Showing expenses from" in body
    assert end in body
    # The start chip should render the placeholder `…` when start is absent.
    assert "…" in body


# --- Invalid input: silent fallback ---------------------------------------- #

def test_profile_with_invalid_start_renders_without_error(logged_in_client):
    # Spec DoD: "When start=invalid-date is passed, the page renders as if no
    # filter were applied (no flash, no traceback)"
    # Spec rule: "Invalid or missing dates are ignored (no error flash) —
    # the page falls back to 'All time'"
    resp = logged_in_client.get("/profile?start=not-a-date")
    assert resp.status_code == 200, (
        "invalid `start` must not cause a 500; the spec mandates silent fallback"
    )

    body = resp.data.decode("utf-8")
    # No flash messages rendered.
    assert "auth-error" not in body, (
        "spec forbids flash messages on invalid date input"
    )
    # The active-filter pill must NOT be rendered (filter is treated as
    # absent, same as the no-filter baseline).
    assert "Showing expenses from" not in body
    assert "active-filter" not in body


def test_profile_with_invalid_end_renders_without_error(logged_in_client):
    # Spec rule: invalid `end` is silently ignored, same as invalid `start`.
    resp = logged_in_client.get("/profile?end=garbage")
    assert resp.status_code == 200
    body = resp.data.decode("utf-8")
    assert "auth-error" not in body
    assert "Showing expenses from" not in body
    assert "active-filter" not in body


def test_profile_with_one_valid_and_one_invalid_keeps_valid_bound_only(
    logged_in_client,
):
    # Spec rule (one-valid-one-invalid case): the valid bound still applies;
    # the invalid bound is silently dropped. The pill shows the valid date
    # and `…` for the missing/invalid side.
    from datetime import date

    today = date.today()
    year, month = today.year, today.month
    start = f"{year:04d}-{month:02d}-01"

    resp = logged_in_client.get(f"/profile?start={start}&end=junk")
    assert resp.status_code == 200
    body = resp.data.decode("utf-8")

    # No flash, no error.
    assert "auth-error" not in body

    # Pill is rendered (start was valid).
    assert "Showing expenses from" in body
    assert start in body
    # The invalid end side is dropped → placeholder.
    assert "…" in body


# --- Zero-row range --------------------------------------------------------- #

def test_profile_with_zero_row_range_shows_empty_state(logged_in_client):
    # Spec DoD: "When the range matches zero expenses, the summary stats show
    # ₹ 0 / 0 / —, the transactions table shows the empty-state row, and the
    # category breakdown shows 'No spending yet'"
    resp = logged_in_client.get("/profile?start=2099-01-01&end=2099-12-31")
    assert resp.status_code == 200

    body = resp.data.decode("utf-8")

    # Empty-state row in the transactions table.
    assert "No expenses yet" in body, (
        "transactions table must show its empty-state row when range matches nothing"
    )
    # Empty-state in the category breakdown.
    assert "No spending yet" in body, (
        "category breakdown must show 'No spending yet' when range matches nothing"
    )
    # Summary stats: total = 0.00, count = 0, top = em-dash.
    assert "₹ 0.00" in body
    assert "0</div>" in body  # transaction_count cell
    assert "—" in body        # top_category fallback

    # The active-filter pill is still rendered (filter is active, just empty).
    assert "Showing expenses from" in body
    assert "2099-01-01" in body
    assert "2099-12-31" in body


# --- Inverted range: start > end ------------------------------------------- #

def test_profile_with_inverted_range_renders_empty_without_traceback(
    logged_in_client,
):
    # Spec rule: "When start > end, treat the range as empty (no rows match)
    # and continue rendering normally — the empty-state row handles it"
    resp = logged_in_client.get("/profile?start=2026-06-30&end=2026-06-01")
    assert resp.status_code == 200, (
        "inverted range must not 500; spec says treat as empty and continue"
    )

    body = resp.data.decode("utf-8")
    # Empty-state markers must appear.
    assert "No expenses yet" in body
    assert "No spending yet" in body
    # Both date chips render in the pill even though the range is empty.
    assert "Showing expenses from" in body
    assert "2026-06-30" in body
    assert "2026-06-01" in body


# --- Clear link targets ----------------------------------------------------- #

def test_active_filter_pill_clear_link_points_to_profile(logged_in_client):
    # Spec template: "a small inline (Clear) link" that returns to /profile
    # with no query string.
    from datetime import date

    today = date.today()
    year, month = today.year, today.month

    resp = logged_in_client.get(
        f"/profile?start={year:04d}-{month:02d}-01&end={year:04d}-{month:02d}-15"
    )
    assert resp.status_code == 200
    body = resp.data.decode("utf-8")

    # The pill's clear anchor must be exactly href="/profile" (no query
    # string) and carry the active-filter-clear class.
    assert 'class="active-filter-clear" href="/profile"' in body
    # Belt-and-braces: no clear link in the pill may carry a ?start= or ?end=.
    assert "active-filter-clear" in body


def test_filter_form_clear_link_points_to_profile(logged_in_client):
    # Spec template: "a 'Clear' link (btn-ghost) that points to
    # url_for('profile') with no params" — inside the filter form.
    resp = logged_in_client.get("/profile")
    assert resp.status_code == 200
    body = resp.data.decode("utf-8")

    # The form's Clear anchor has the btn-ghost class and href="/profile".
    # It must NOT carry any query string.
    assert 'class="btn-ghost" href="/profile"' in body
    # The Clear text itself.
    assert ">Clear</a>" in body


# --- DB helper layer: direct test on summarise_expenses_for_user ----------- #

def test_summarise_expenses_for_user_filters_by_date_range(temp_db_path):
    # Spec: "DB helpers (summarise_expenses_for_user, ...) accept start and
    # end kwargs and filter results correctly."
    # Spec DoD: helpers expose optional start/end kwargs defaulting to None.
    # We exercise the helper directly against the seeded temp DB.
    _db_module.DB_PATH = temp_db_path

    # Look up the seeded demo user's id.
    conn = _db_module.get_db()
    try:
        row = conn.execute(
            "SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)
        ).fetchone()
        demo_id = int(row["id"])
    finally:
        conn.close()

    from datetime import date

    today = date.today()
    year, month = today.year, today.month
    start_iso = f"{year:04d}-{month:02d}-01"
    end_iso = f"{year:04d}-{month:02d}-28"

    # Baseline: no bounds → matches every seeded expense (8 rows).
    no_bounds = _db_module.summarise_expenses_for_user(demo_id)
    assert no_bounds["transaction_count"] == 8, (
        f"expected 8 seeded expenses without bounds, got {no_bounds['transaction_count']}"
    )
    baseline_total = no_bounds["total_spent"]
    assert baseline_total > 0.0

    # With bounds covering the seeded month → same count, same total.
    bounded = _db_module.summarise_expenses_for_user(
        demo_id, start=start_iso, end=end_iso
    )
    assert bounded["transaction_count"] == 8
    assert bounded["total_spent"] == pytest.approx(baseline_total)

    # With a far-future range → zero rows, total 0.0, no top category.
    empty = _db_module.summarise_expenses_for_user(
        demo_id, start="2099-01-01", end="2099-12-31"
    )
    assert empty["transaction_count"] == 0
    assert empty["total_spent"] == 0.0
    assert empty["top_category"] is None

    # Tighter range (just the first half of the month) → strictly fewer
    # rows than the full-month bound.
    partial = _db_module.summarise_expenses_for_user(
        demo_id,
        start=f"{year:04d}-{month:02d}-01",
        end=f"{year:04d}-{month:02d}-10",
    )
    assert 0 <= partial["transaction_count"] < 8
    assert partial["total_spent"] <= baseline_total
