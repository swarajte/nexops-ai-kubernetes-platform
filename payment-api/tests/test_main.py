from fastapi.testclient import TestClient

from app import fail
from app.main import app

client = TestClient(app)


def setup_function():
    fail.reset()


def test_metrics():
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "http_request_duration_seconds" in response.text


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["service"] == "payment-api"


def test_ready():
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_ready_failure():
    response = client.post("/fail/ready", json={"fail": True})
    assert response.status_code == 200
    assert client.get("/ready").status_code == 503
    assert client.get("/health").status_code == 200


def test_pay_success():
    response = client.post(
        "/pay",
        json={"order_id": "ord_123", "amount": 49.99, "currency": "USD"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["order_id"] == "ord_123"
    assert body["amount"] == 49.99
    assert body["payment_id"] == "pay_ord_123"


def test_pay_rejects_invalid_amount():
    response = client.post(
        "/pay",
        json={"order_id": "ord_bad", "amount": 0},
    )
    assert response.status_code == 422


def test_injected_errors():
    client.post("/fail/errors", json={"rate": 1.0})
    response = client.post(
        "/pay",
        json={"order_id": "ord_err", "amount": 10.0, "currency": "USD"},
    )
    assert response.status_code == 500


def test_fail_reset():
    client.post("/fail/ready", json={"fail": True})
    client.post("/fail/reset")
    assert client.get("/ready").status_code == 200
