import pytest
import app as expense_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(
        expense_app, "DB_PATH", str(tmp_path / "test_expenses.db")
    )
    expense_app.init_db()
    expense_app.app.config["TESTING"] = True

    with expense_app.app.test_client() as client:
        yield client


def test_home_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Expense Tracker" in response.data


def test_add_expense(client):
    response = client.post("/add", data={
        "title": "Lunch",
        "amount": "150",
        "category": "Food",
        "date": "2026-10-22"
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"Lunch" in response.data
    assert b"150.00" in response.data


def test_reject_invalid_amount(client):
    response = client.post("/add", data={
        "title": "Test",
        "amount": "-10",
        "category": "Food",
        "date": "2026-10-22"
    })
    assert response.status_code == 400


def test_delete_expense(client):
    client.post("/add", data={
        "title": "Bus",
        "amount": "40",
        "category": "Travel",
        "date": "2026-10-22"
    })

    with expense_app.get_db() as conn:
        expense_id = conn.execute(
            "SELECT id FROM expenses WHERE title = 'Bus'"
        ).fetchone()["id"]

    response = client.post(
        f"/delete/{expense_id}", follow_redirects=True
    )
    assert response.status_code == 200
    assert b"Bus" not in response.data


def test_health_and_metrics(client):
    assert client.get("/health").status_code == 200
    metrics_response = client.get("/metrics")
    assert metrics_response.status_code == 200
    assert b"expense_tracker_requests_total" in metrics_response.data
