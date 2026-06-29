from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash


def _is_logged_in() -> bool:
    return "user_id" in session


from datetime import datetime

from database.db import (
    create_user,
    get_user_by_email,
    get_user_by_id,
    init_db,
    list_category_totals_for_user,
    list_recent_expenses_for_user,
    seed_db,
    summarise_expenses_for_user,
)

app = Flask(__name__)

# Needed for Flask flash() messages.
# In production, replace with a secure environment-based secret.
app.secret_key = "dev-secret-key-change-me"




# ------------------------------------------------------------------ #
# Startup (DB init + seed)                                         #
# ------------------------------------------------------------------ #

with app.app_context():
    init_db()
    seed_db()


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")



@app.route("/register", methods=["GET", "POST"])
def register():
    if _is_logged_in():
        return redirect(url_for("landing"))

    if request.method == "GET":
        return render_template("register.html")


    # POST
    name = (request.form.get("name") or "").strip()
    email = (request.form.get("email") or "").strip()
    password = request.form.get("password") or ""
    confirm_password = request.form.get("confirm_password") or ""

    # Validation: non-empty fields
    if not name or not email or not password or not confirm_password:
        flash("All fields are required.", "error")
        return render_template("register.html")

    # Validation: password match
    if password != confirm_password:
        flash("Passwords do not match.", "error")
        return render_template("register.html")

    # Create user
    try:
        create_user(name=name, email=email, password=password)
    except Exception as exc:
        # Handle duplicate email based on sqlite constraint
        # (sqlite will raise an IntegrityError for UNIQUE violation)
        from sqlite3 import IntegrityError

        if isinstance(exc, IntegrityError):
            flash("Email already registered.", "error")
            return render_template("register.html")
        raise

    flash("Account created. Please sign in.", "success")
    return redirect(url_for("login"))



@app.route("/login", methods=["GET", "POST"])
def login():
    if _is_logged_in():
        return redirect(url_for("landing"))

    if request.method == "GET":
        return render_template("login.html")


# POST
    
    # (If already logged in, landing redirect handled above)



    # POST
    email = (request.form.get("email") or "").strip()
    password = request.form.get("password") or ""

    if not email or not password:
        flash("Invalid email or password.", "error")
        return render_template("login.html")

    user = get_user_by_email(email)
    if user is None:
        flash("Invalid email or password.", "error")
        return render_template("login.html")

    if not check_password_hash(user["password_hash"], password):
        flash("Invalid email or password.", "error")
        return render_template("login.html")

    session["user_id"] = int(user["id"])
    return redirect(url_for("profile"))




# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))



# ------------------------------------------------------------------ #
# Profile display helpers                                            #
# ------------------------------------------------------------------ #

_BADGE_BY_CATEGORY = {
    "Food": "badge-food",
    "Transport": "badge-transport",
    "Travel": "badge-travel",
    "Bills": "badge-bills",
    "Health": "badge-health",
    "Entertainment": "badge-entertainment",
    "Shopping": "badge-shopping",
    "Other": "badge-other",
}


def _format_inr(amount: float) -> str:
    """Format an amount in Indian rupee style: ₹ 1,23,456.00.

    Right-most three digits form one group; remaining digits are grouped
    in pairs from the right. Decimal portion always shows two digits.
    """
    sign = "-" if amount < 0 else ""
    amount = abs(float(amount))
    whole, _, frac = f"{amount:.2f}".partition(".")
    if len(whole) <= 3:
        grouped = whole
    else:
        head, tail = whole[:-3], whole[-3:]
        parts = []
        while len(head) > 2:
            parts.append(head[-2:])
            head = head[:-2]
        parts.append(head)
        grouped = ",".join(reversed(parts)) + "," + tail
    return f"₹ {sign}{grouped}.{frac}"


def _initials(name: str) -> str:
    """First letter of the first two whitespace-split words, uppercased."""
    parts = (name or "").split()
    letters = [p[0].upper() for p in parts if p][:2]
    return "".join(letters) or "?"


def _badge_class(category: str) -> str:
    """Map a category name to its CSS badge class (with a safe fallback)."""
    return _BADGE_BY_CATEGORY.get(category or "", "badge-other")


def _member_since(created_at: str) -> str:
    """Convert a SQLite CURRENT_TIMESTAMP string into 'Mon YYYY' format."""
    if not created_at:
        return "—"
    try:
        return datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S").strftime("%b %Y")
    except ValueError:
        return created_at[:7] or "—"


@app.route("/profile")
def profile():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    user_id = int(user_id)
    user_row = get_user_by_id(user_id)
    if user_row is None:
        # Stale session pointing at a deleted account — clear and redirect.
        session.clear()
        return redirect(url_for("login"))

    summary_row = summarise_expenses_for_user(user_id)
    raw_txns = list_recent_expenses_for_user(user_id)
    raw_categories = list_category_totals_for_user(user_id)

    user = {
        "name": user_row["name"],
        "email": user_row["email"],
        "initials": _initials(user_row["name"]),
        "member_since": _member_since(user_row["created_at"]),
    }

    summary = {
        "total_spent": _format_inr(summary_row["total_spent"]),
        "transaction_count": summary_row["transaction_count"],
        "top_category": summary_row["top_category"] or "—",
    }

    transactions = [
        {
            "date": t["date"],
            "description": t["description"] or "",
            "category": t["category"],
            "badge_class": _badge_class(t["category"]),
            "amount": _format_inr(t["amount"]),
        }
        for t in raw_txns
    ]

    categories = [
        {"name": c["category"], "total": _format_inr(c["total"])}
        for c in raw_categories
    ]

    return render_template(
        "profile.html",
        user=user,
        summary=summary,
        transactions=transactions,
        categories=categories,
    )



@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


@app.route('/terms')
def terms():  
    return render_template('terms.html')


@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

if __name__ == "__main__":
    app.run(debug=True, port=5001)
