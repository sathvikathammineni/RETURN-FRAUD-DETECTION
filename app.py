
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, get_flashed_messages
)
import sqlite3
import uuid
from datetime import date, datetime, timedelta

app = Flask(__name__)
app.secret_key = "return-fraud-demo-secret-key"

DATABASE = "returns.db"
STAFF_EMAIL = "staff@store.com"
STAFF_PASSWORD = "Staff123!"


# ---------------- DATABASE ----------------

def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def create_tables():
    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS returns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product TEXT NOT NULL,
            price REAL NOT NULL,
            reason TEXT NOT NULL,
            status TEXT NOT NULL,
            risk_score INTEGER NOT NULL DEFAULT 0,
            tracking_id TEXT,
            order_date TEXT,
            delivery_date TEXT,
            return_request_date TEXT,
            account_age INTEGER DEFAULT 30,
            new_card INTEGER DEFAULT 0,
            expected_weight REAL DEFAULT 0,
            received_weight REAL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    cursor.execute("PRAGMA table_info(returns)")
    columns = [row["name"] for row in cursor.fetchall()]

    migrations = {
        "tracking_id": "ALTER TABLE returns ADD COLUMN tracking_id TEXT",
        "order_date": "ALTER TABLE returns ADD COLUMN order_date TEXT",
        "delivery_date": "ALTER TABLE returns ADD COLUMN delivery_date TEXT",
        "return_request_date": (
            "ALTER TABLE returns ADD COLUMN return_request_date TEXT"
        ),
        "account_age": (
            "ALTER TABLE returns ADD COLUMN account_age INTEGER DEFAULT 30"
        ),
        "new_card": (
            "ALTER TABLE returns ADD COLUMN new_card INTEGER DEFAULT 0"
        ),
        "expected_weight": (
            "ALTER TABLE returns ADD COLUMN expected_weight REAL DEFAULT 0"
        ),
        "received_weight": (
            "ALTER TABLE returns ADD COLUMN received_weight REAL DEFAULT 0"
        ),
        "created_at": (
            "ALTER TABLE returns ADD COLUMN created_at TEXT"
        )
    }

    for column, sql in migrations.items():
        if column not in columns:
            cursor.execute(sql)

    cursor.execute("""
        SELECT id FROM returns
        WHERE tracking_id IS NULL OR tracking_id = ''
    """)

    for row in cursor.fetchall():
        tracking_id = "RET-" + uuid.uuid4().hex[:10].upper()
        cursor.execute(
            "UPDATE returns SET tracking_id = ? WHERE id = ?",
            (tracking_id, row["id"])
        )

    cursor.execute("""
        UPDATE returns
        SET return_request_date = substr(created_at, 1, 10)
        WHERE return_request_date IS NULL
           OR return_request_date = ''
    """)

    connection.commit()
    connection.close()


# ---------------- RISK CALCULATION ----------------

def calculate_risk(
    price, reason, account_age, new_card,
    previous_returns, previous_missing_claims,
    expected_weight, received_weight
):
    score = 0

    # 1. Item value
    if price >= 50000:
        score += 20
    elif price >= 10000:
        score += 10

    # 2. Previous return requests
    if previous_returns >= 3:
        score += 20

    # 3. New customer account
    if account_age < 7:
        score += 15

    # 4. New payment card
    if new_card:
        score += 10

    # 5. Package weight difference
    if expected_weight > 0:
        difference_percentage = (
            abs(expected_weight - received_weight)
            / expected_weight
        ) * 100

        if difference_percentage >= 20:
            score += 30

    # 6. Repeated Missing Item claims
    if reason == "Missing Item" and previous_missing_claims >= 2:
        score += 15

    return min(score, 100)


def risk_level_for(score):
    return "High" if score > 70 else "Low"


# ---------------- TRACKING ----------------

def get_tracking_events(return_row):
    status = return_row["status"]
    request_date_text = return_row["return_request_date"]

    try:
        request_date = date.fromisoformat(request_date_text)
    except (ValueError, TypeError):
        try:
            request_date = datetime.strptime(
                return_row["created_at"][:10], "%Y-%m-%d"
            ).date()
        except (ValueError, TypeError):
            request_date = date.today()

    def formatted(day):
        return day.strftime("%d %b %Y")

    if status == "Under Staff Review":
        return [{
            "title": "Return request under staff review",
            "date": formatted(request_date),
            "expected": "Awaiting staff decision",
            "current": True
        }]

    if status == "Rejected":
        return [{
            "title": "Return request rejected",
            "date": formatted(request_date),
            "expected": "Request closed",
            "current": True
        }]

    if status not in ("Auto-approved", "Accepted"):
        return [{
            "title": "Return request submitted",
            "date": formatted(request_date),
            "expected": "Awaiting status update",
            "current": True
        }]

    stages = [
        ("Return Requested", 0),
        ("Pickup Scheduled", 1),
        ("Item Picked Up", 2),
        ("Warehouse Received", 4),
        ("Refund Issued", 6)
    ]

    return [
        {
            "title": title,
            "date": formatted(request_date + timedelta(days=offset)),
            "expected": (
                "Request date entered by you"
                if offset == 0 else "Estimated date"
            ),
            "current": offset == 0
        }
        for title, offset in stages
    ]


# ---------------- CUSTOMER DASHBOARD ----------------

def show_dashboard(error=None, result=None):
    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db()

    row = connection.execute("""
        SELECT *
        FROM returns
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 1
    """, (session["user_id"],)).fetchone()

    connection.close()

    customer_returns = []

    if row:
        item = dict(row)
        item["tracking_events"] = get_tracking_events(item)
        item["risk_level"] = risk_level_for(item["risk_score"])
        customer_returns.append(item)

    return render_template(
        "dashboard.html",
        name=session.get("name", "Customer"),
        returns=customer_returns,
        error=error,
        result=result,
        today=date.today().isoformat()
    )


@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return show_dashboard()


# ---------------- CUSTOMER REGISTRATION ----------------

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or not email or not password:
            return render_template(
                "register.html",
                error="Please fill in every field."
            )

        connection = get_db()

        try:
            connection.execute("""
                INSERT INTO users (name, email, password)
                VALUES (?, ?, ?)
            """, (name, email, password))
            connection.commit()
        except sqlite3.IntegrityError:
            connection.close()
            return render_template(
                "register.html",
                error="This email is already registered."
            )

        connection.close()
        return redirect(url_for("login"))

    return render_template("register.html")


# ---------------- CUSTOMER LOGIN ----------------

@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        connection = get_db()
        user = connection.execute("""
            SELECT * FROM users
            WHERE email = ? AND password = ?
        """, (email, password)).fetchone()
        connection.close()

        if user:
            session.clear()
            session["user_id"] = user["id"]
            session["name"] = user["name"]
            return redirect(url_for("dashboard"))

        return render_template(
            "login.html",
            error="Invalid email or password."
        )

    return render_template("login.html")


# ---------------- SUBMIT RETURN REQUEST ----------------

@app.route("/submit_return", methods=["POST"])
def submit_return():
    if "user_id" not in session:
        return redirect(url_for("login"))

    product = request.form.get("product", "").strip()
    reason = request.form.get("reason", "").strip()
    order_date = request.form.get("order_date", "").strip()
    delivery_date = request.form.get("delivery_date", "").strip()
    return_request_date = request.form.get(
        "return_request_date", ""
    ).strip()

    try:
        price = float(request.form.get("price", "0"))
        account_age = int(request.form.get("account_age", "30"))
        expected_weight = float(
            request.form.get("expected_weight", "0")
        )
        received_weight = float(
            request.form.get("received_weight", "0")
        )
    except (ValueError, TypeError):
        return show_dashboard(
            error="Enter valid numeric values for price, account age and weights."
        )

    new_card = 1 if request.form.get("new_card") else 0

    if not product or not reason:
        return show_dashboard(
            error="Please enter the product and return reason."
        )

    if (
        price <= 0 or account_age < 0
        or expected_weight <= 0 or received_weight < 0
    ):
        return show_dashboard(
            error="Price and expected weight must be positive. "
                  "Account age and received weight cannot be negative."
        )

    if not return_request_date:
        return show_dashboard(
            error="Please select the return-request date."
        )

    try:
        if order_date:
            datetime.strptime(order_date, "%Y-%m-%d")
        if delivery_date:
            datetime.strptime(delivery_date, "%Y-%m-%d")

        request_date_obj = datetime.strptime(
            return_request_date, "%Y-%m-%d"
        ).date()
    except ValueError:
        return show_dashboard(error="Please enter valid dates.")

    if request_date_obj > date.today():
        return show_dashboard(
            error="The return-request date cannot be in the future."
        )

    if order_date and delivery_date and order_date > delivery_date:
        return show_dashboard(
            error="Delivery date cannot be before the order date."
        )

    if delivery_date and delivery_date > date.today().isoformat():
        return show_dashboard(
            error="Delivery date cannot be in the future."
        )

    connection = get_db()

    previous_returns = connection.execute("""
        SELECT COUNT(*) AS total
        FROM returns
        WHERE user_id = ?
    """, (session["user_id"],)).fetchone()["total"]

    previous_missing_claims = connection.execute("""
        SELECT COUNT(*) AS total
        FROM returns
        WHERE user_id = ? AND reason = 'Missing Item'
    """, (session["user_id"],)).fetchone()["total"]

    risk_score = calculate_risk(
        price=price,
        reason=reason,
        account_age=account_age,
        new_card=new_card,
        previous_returns=previous_returns,
        previous_missing_claims=previous_missing_claims,
        expected_weight=expected_weight,
        received_weight=received_weight
    )

    risk_level = risk_level_for(risk_score)
    status = (
        "Under Staff Review"
        if risk_level == "High"
        else "Auto-approved"
    )

    tracking_id = "RET-" + uuid.uuid4().hex[:10].upper()

    cursor = connection.execute("""
        INSERT INTO returns (
            user_id, product, price, reason, status, risk_score,
            tracking_id, order_date, delivery_date, return_request_date,
            account_age, new_card, expected_weight, received_weight
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        session["user_id"], product, price, reason, status, risk_score,
        tracking_id, order_date, delivery_date, return_request_date,
        account_age, new_card, expected_weight, received_weight
    ))

    return_id = cursor.lastrowid
    connection.commit()

    saved_return = connection.execute("""
        SELECT * FROM returns WHERE id = ?
    """, (return_id,)).fetchone()

    connection.close()

    result = dict(saved_return)
    result["risk_level"] = risk_level_for(risk_score)
    result["tracking_events"] = get_tracking_events(result)

    return show_dashboard(result=result)


# ---------------- STAFF LOGIN ----------------

@app.route("/staff", methods=["GET", "POST"])
@app.route("/staff/login", methods=["GET", "POST"])
def staff_login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if email == STAFF_EMAIL and password == STAFF_PASSWORD:
            session.clear()
            session["staff_logged_in"] = True
            return redirect(url_for("staff_dashboard"))

        return render_template(
            "staff_login.html",
            error="Invalid staff credentials."
        )

    return render_template("staff_login.html")


# ---------------- STAFF DASHBOARD ----------------

@app.route("/staff/dashboard")
def staff_dashboard():
    if not session.get("staff_logged_in"):
        return redirect(url_for("staff_login"))

    connection = get_db()

    all_returns = connection.execute("""
        SELECT returns.*, users.name, users.email
        FROM returns
        JOIN users ON returns.user_id = users.id
        ORDER BY returns.id DESC
    """).fetchall()

    all_returns = [dict(row) for row in all_returns]

    pending_returns = [
        row for row in all_returns
        if row["status"] == "Under Staff Review"
    ]

    approved_returns = [
        row for row in all_returns
        if row["status"] == "Auto-approved"
    ]

    reviewed_cases = [
        row for row in all_returns
        if row["status"] in ("Accepted", "Rejected")
    ]

    high_risk_count = sum(
        1 for row in all_returns if row["risk_score"] > 70
    )

    rejected_count = sum(
        1 for row in all_returns if row["status"] == "Rejected"
    )

    # This is a demo metric, not a verified fraud rate.
    fraud_percentage = round(
        rejected_count / high_risk_count * 100
    ) if high_risk_count else 0

    connection.close()

    return render_template(
        "staff_dashboard.html",
        all_returns=all_returns,
        pending_returns=pending_returns,
        approved_returns=approved_returns,
        reviewed_cases=reviewed_cases,
        total_requests=len(all_returns),
        low_risk_count=len(approved_returns),
        high_risk_count=high_risk_count,
        fraud_percentage=fraud_percentage,
        reason_stats=[],
        message=" ".join(get_flashed_messages())
    )
    
# ---------------- CLEAR ALL DATA ----------------

@app.route("/staff/clear-data", methods=["POST"])
def clear_all_data():
    if not session.get("staff_logged_in"):
        return redirect(url_for("staff_login"))

    confirmation = request.form.get("confirmation", "")

    if confirmation != "CLEAR ALL DATA":
        flash("Data was not cleared. Confirmation did not match.")
        return redirect(url_for("staff_dashboard"))

    connection = get_db()

    try:
        connection.execute("DELETE FROM returns")
        connection.execute("DELETE FROM users")

        # Reset SQLite auto-increment counters.
        connection.execute("""
            DELETE FROM sqlite_sequence
            WHERE name IN ('returns', 'users')
        """)

        connection.commit()
        flash("All customer accounts and return requests have been deleted.")
    except sqlite3.Error:
        connection.rollback()
        flash("Could not clear the data. Please try again.")
    finally:
        connection.close()

    return redirect(url_for("staff_dashboard"))


# ---------------- STAFF DECISION ----------------

@app.route("/staff/decision/<int:return_id>", methods=["POST"])
def staff_decision(return_id):
    if not session.get("staff_logged_in"):
        return redirect(url_for("staff_login"))

    decision = request.form.get("decision")

    if decision not in ("Accepted", "Rejected"):
        flash("Invalid decision.")
        return redirect(url_for("staff_dashboard"))

    connection = get_db()

    cursor = connection.execute("""
        UPDATE returns
        SET status = ?
        WHERE id = ? AND status = 'Under Staff Review'
    """, (decision, return_id))

    connection.commit()
    updated = cursor.rowcount
    connection.close()

    if updated:
        flash(f"Return request marked as {decision}.")
    else:
        flash("This request was already reviewed or could not be found.")

    return redirect(url_for("staff_dashboard"))


# ---------------- BATCH SCORING ----------------

@app.route("/staff/batch-scoring", methods=["POST"])
def run_batch_scoring():
    if not session.get("staff_logged_in"):
        return redirect(url_for("staff_login"))

    connection = get_db()

    rows = connection.execute("""
        SELECT * FROM returns
        WHERE status IN ('Under Staff Review', 'Auto-approved')
    """).fetchall()

    for row in rows:
        previous_returns = connection.execute("""
            SELECT COUNT(*) AS total
            FROM returns
            WHERE user_id = ? AND id < ?
        """, (row["user_id"], row["id"])).fetchone()["total"]

        previous_missing_claims = connection.execute("""
            SELECT COUNT(*) AS total
            FROM returns
            WHERE user_id = ? AND id < ?
              AND reason = 'Missing Item'
        """, (row["user_id"], row["id"])).fetchone()["total"]

        score = calculate_risk(
            price=row["price"],
            reason=row["reason"],
            account_age=row["account_age"] or 30,
            new_card=row["new_card"] or 0,
            previous_returns=previous_returns,
            previous_missing_claims=previous_missing_claims,
            expected_weight=row["expected_weight"] or 0,
            received_weight=row["received_weight"] or 0
        )

        risk_level = risk_level_for(score)
        status = (
            "Under Staff Review"
            if risk_level == "High"
            else "Auto-approved"
        )

        connection.execute("""
            UPDATE returns
            SET risk_score = ?, status = ?
            WHERE id = ?
        """, (score, status, row["id"]))

    connection.commit()
    connection.close()

    flash("Batch scoring completed.")
    return redirect(url_for("staff_dashboard"))


# ---------------- LOGOUT ----------------

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    create_tables()
    app.run(debug=True)