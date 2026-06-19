"""SQLite data layer for Spendly.

This module is intentionally lightweight (no ORM).

Exposes:
- get_db(): returns a configured SQLite connection
- init_db(): creates the schema
- seed_db(): inserts demo data once (idempotent)
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
        # If there is already at least one user, assume seeding already ran.
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

        # 8 expenses, covering multiple categories (repeat one if needed)
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
            [(demo_user_id, amount, category, d, desc) for amount, category, d, desc in sample_expenses],
        )

        conn.commit()
    finally:
        conn.close()

