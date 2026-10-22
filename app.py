
import os
import sqlite3
from pathlib import Path
from flask import Flask, render_template, request, redirect
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

app = Flask(__name__)
DB_PATH = os.environ.get("DB_PATH", "data/expenses.db")

REQUEST_COUNT = Counter("expense_tracker_requests_total", "Total requests", ["method", "endpoint", "status"])
REQUEST_DURATION = Histogram("expense_tracker_request_duration_seconds", "Request duration")


def get_db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                amount REAL NOT NULL CHECK(amount > 0),
                category TEXT NOT NULL,
                date TEXT NOT NULL
            )
        """)


@app.before_request
def start_timer():
    import time
    request.start_time = time.perf_counter()


@app.after_request
def record_metrics(response):
    import time
    REQUEST_COUNT.labels(request.method, request.endpoint or "unknown", str(response.status_code)).inc()
    REQUEST_DURATION.observe(time.perf_counter() - getattr(request, "start_time", time.perf_counter()))
    return response


@app.route("/")
def index():
    with get_db() as conn:
        expenses = conn.execute("SELECT * FROM expenses ORDER BY date DESC, id DESC").fetchall()
        total = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM expenses").fetchone()[0]
    return render_template("expense.html", expenses=expenses, total=total)


@app.route("/add", methods=["POST"])
def add_expense():
    title = request.form.get("title", "").strip()
    category = request.form.get("category", "").strip()
    date = request.form.get("date", "").strip()
    try:
        amount = float(request.form.get("amount", ""))
        if not (0 < amount < float("inf")):
            raise ValueError
    except (ValueError, TypeError):
        return "Enter a valid positive amount.", 400

    if not title or not category or not date:
        return "Please fill in all fields.", 400

    with get_db() as conn:
        conn.execute(
            "INSERT INTO expenses (title, amount, category, date) VALUES (?, ?, ?, ?)",
            (title, amount, category, date)
        )
    return redirect("/")


@app.route("/delete/<int:expense_id>", methods=["POST"])
def delete_expense(expense_id):
    with get_db() as conn:
        conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    return redirect("/")


@app.route("/health")
def health():
    return {"status": "healthy"}, 200


@app.route("/metrics")
def metrics():
    return app.response_class(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


init_db()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
