from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["service"] == "payment-api"


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
