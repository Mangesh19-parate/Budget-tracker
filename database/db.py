"""SQLite data layer for Spendly.

This module is intentionally lightweight (no ORM).

Exposes:
- get_db(): returns a configured SQLite connection
- init_db(): creates the schema
- seed_db(): inserts demo data once (idempotent)

Additional helpers used by auth:
- get_user_by_email(email)
"""

from __future__ import annotations

import os
import sqlite3
from datetime import date

from werkzeug.security import generate_password_hash


# Path to the sqlite database in the project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "spendly.db")


def get_db() -> sqlite3.Connection:
    """Return a SQLite connection with row access by column name.

    Also enables foreign key enforcement.
    """

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Create tables if they do not already exist."""

    schema_users = """CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );"""

    schema_expenses = """CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        category TEXT NOT NULL,
        date TEXT NOT NULL,
        description TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );"""

    conn = get_db()
    try:
        conn.execute(schema_users)
        conn.execute(schema_expenses)
        conn.commit()
    finally:
        conn.close()


def create_user(name: str, email: str, password: str) -> int:
    """Create a user row.

    Args:
        name: Display name
        email: Unique email address
        password: Plaintext password to be hashed

    Returns:
        Newly created user's id.

    Raises:
        sqlite3.IntegrityError: if email is already taken.
    """

    password_hash = generate_password_hash(password)

    conn = get_db()
    try:
        cursor = conn.execute(
            """
            INSERT INTO users (name, email, password_hash)
            VALUES (?, ?, ?)
            """,
            (name, email, password_hash),
        )
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()


def get_user_by_email(email: str) -> sqlite3.Row | None:
    """Fetch a user by email.

    Returns None if not found.
    """

    conn = get_db()
    try:
        row = conn.execute(
            """
            SELECT id, email, password_hash
            FROM users
            WHERE email = ?
            """,
            (email,),
        ).fetchone()
        return row
    finally:
        conn.close()


def _current_month_dates() -> list[str]:
    """Create YYYY-MM-DD strings spread across the current month."""

    today = date.today()
    # Pick safe day values (avoid month-end edge cases)
    days = [3, 7, 10, 14, 18, 22, 26, 28]
    return [date(today.year, today.month, d).isoformat() for d in days]


def seed_db() -> None:
    """Insert a demo user and sample expenses once.

    This function is idempotent:
    - If a user exists already, it does not insert duplicates.
    """

    categories = [
        "Food",
        "Transport",
        "Bills",
        "Health",
        "Entertainment",
        "Shopping",
        "Other",
    ]

    conn = get_db()
    try:
        existing = conn.execute("SELECT id FROM users LIMIT 1").fetchone()
        if existing is not None:
            return

        password_hash = generate_password_hash("demo123")
        conn.execute(
            """
            INSERT INTO users (name, email, password_hash)
            VALUES (?, ?, ?)
            """,
            ("Demo User", "demo@spendly.com", password_hash),
        )

        demo_user_id = conn.execute(
            "SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)
        ).fetchone()["id"]

        expense_dates = _current_month_dates()

        sample_expenses = [
            (25.50, "Food", expense_dates[0], "Groceries"),
            (12.75, "Transport", expense_dates[1], "Bus pass"),
            (89.90, "Bills", expense_dates[2], "Internet bill"),
            (18.20, "Health", expense_dates[3], "Vitamins"),
            (40.00, "Entertainment", expense_dates[4], "Movie tickets"),
            (65.45, "Shopping", expense_dates[5], "Household items"),
            (30.00, "Other", expense_dates[6], "Miscellaneous"),
            (22.10, categories[0], expense_dates[7], "Coffee & snacks"),
        ]

        conn.executemany(
            """
            INSERT INTO expenses (user_id, amount, category, date, description)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (demo_user_id, amount, category, d, desc)
                for amount, category, d, desc in sample_expenses
            ],
        )

        conn.commit()
    finally:
        conn.close()


def summarise_expenses_for_user(
    user_id: int,
    start: str | None = None,
    end: str | None = None,
) -> dict:
    """Return aggregate stats for a user's expenses, optionally date-scoped.

    Args:
        user_id: Owning user id.
        start: Optional inclusive lower bound (YYYY-MM-DD) on expenses.date.
        end:   Optional inclusive upper bound (YYYY-MM-DD) on expenses.date.
               When only one bound is provided, the other side is open.

    Returns a dict with:
        total_spent: float      — sum of all matching amounts (0.0 when empty)
        transaction_count: int  — number of matching expense rows
        top_category: str | None — top category within the match set
                                  (None when no rows match;
                                   ties broken alphabetically by category)

    This helper is self-contained — it does NOT depend on
    list_category_totals_for_user.
    """

    clauses = ["user_id = ?"]
    params: list = [user_id]
    if start is not None:
        clauses.append("date >= ?")
        params.append(start)
    if end is not None:
        clauses.append("date <= ?")
        params.append(end)
    where_sql = " AND ".join(clauses)

    conn = get_db()
    try:
        totals_row = conn.execute(
            f"""
            SELECT COALESCE(SUM(amount), 0.0) AS total_spent,
                   COUNT(*) AS transaction_count
            FROM expenses
            WHERE {where_sql}
            """,
            tuple(params),
        ).fetchone()

        top_row = conn.execute(
            f"""
            SELECT category
            FROM expenses
            WHERE {where_sql}
            GROUP BY category
            ORDER BY SUM(amount) DESC, category ASC
            LIMIT 1
            """,
            tuple(params),
        ).fetchone()

        return {
            "total_spent": float(totals_row["total_spent"]),
            "transaction_count": int(totals_row["transaction_count"]),
            "top_category": top_row["category"] if top_row is not None else None,
        }
    finally:
        conn.close()


def list_category_totals_for_user(
    user_id: int,
    limit: int = 4,
    start: str | None = None,
    end: str | None = None,
) -> list[sqlite3.Row]:
    """Return up to `limit` categories with the highest total spend for a user.

    Optionally scoped to ``start`` / ``end`` (YYYY-MM-DD, inclusive).
    See ``summarise_expenses_for_user`` for argument semantics.

    Each row has columns: category (str), total (float).
    Ordered by total descending, ties broken alphabetically by category.
    Returns an empty list when no rows match.
    """

    clauses = ["user_id = ?"]
    params: list = [user_id]
    if start is not None:
        clauses.append("date >= ?")
        params.append(start)
    if end is not None:
        clauses.append("date <= ?")
        params.append(end)
    where_sql = " AND ".join(clauses)

    conn = get_db()
    try:
        rows = conn.execute(
            f"""
            SELECT category, COALESCE(SUM(amount), 0.0) AS total
            FROM expenses
            WHERE {where_sql}
            GROUP BY category
            ORDER BY total DESC, category ASC
            LIMIT ?
            """,
            tuple(params + [limit]),
        ).fetchall()
        return list(rows)
    finally:
        conn.close()


def get_user_by_id(user_id: int) -> sqlite3.Row | None:
    """Fetch a user by id.

    Returns None if the row does not exist. Selects only the columns
    needed by the profile page (never the password hash, even though
    it's safe to expose to server-side code).
    """

    conn = get_db()
    try:
        row = conn.execute(
            """
            SELECT id, name, email, created_at
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        ).fetchone()
        return row
    finally:
        conn.close()


def list_recent_expenses_for_user(
    user_id: int,
    limit: int = 5,
    start: str | None = None,
    end: str | None = None,
) -> list[sqlite3.Row]:
    """Return up to `limit` most-recent expenses for the given user.

    Optionally scoped to ``start`` / ``end`` (YYYY-MM-DD, inclusive).
    See ``summarise_expenses_for_user`` for argument semantics.

    Sorted by expense date descending, then by id descending (newest first).
    Returns an empty list when no rows match.
    """

    clauses = ["user_id = ?"]
    params: list = [user_id]
    if start is not None:
        clauses.append("date >= ?")
        params.append(start)
    if end is not None:
        clauses.append("date <= ?")
        params.append(end)
    where_sql = " AND ".join(clauses)

    conn = get_db()
    try:
        rows = conn.execute(
            f"""
            SELECT id, amount, category, date, description
            FROM expenses
            WHERE {where_sql}
            ORDER BY date DESC, id DESC
            LIMIT ?
            """,
            tuple(params + [limit]),
        ).fetchall()
        return list(rows)
    finally:
        conn.close()

