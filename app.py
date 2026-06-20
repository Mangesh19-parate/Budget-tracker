from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash


def _is_logged_in() -> bool:
    return "user_id" in session


from database.db import create_user, get_user_by_email, init_db, seed_db

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
    return redirect(url_for("landing"))


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))



@app.route("/profile")
def profile():
    return "Profile page — coming in Step 4"


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
