from flask import Flask, abort, flash, redirect, render_template, request, url_for

from database.db import create_user, init_db, seed_db

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



@app.route("/login")
def login():
    return render_template("login.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    return "Logout — coming in Step 3"


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
