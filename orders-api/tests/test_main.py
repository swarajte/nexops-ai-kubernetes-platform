import os

import httpx
import respx
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["service"] == "orders-api"


@respx.mock
def test_create_order_success():
    payment_url = os.getenv("PAYMENT_API_URL", "http://localhost:8000").rstrip("/") + "/pay"
    respx.post(payment_url).mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "success",
                "message": "Payment successful",
                "order_id": "ignored",
                "amount": 59.98,
                "currency": "USD",
                "payment_id": "pay_test",
            },
        )
    )

    response = client.post(
        "/orders",
        json={
            "product_id": "nx-watch",
            "product_name": "NexOps Watch",
            "quantity": 2,
            "unit_price": 29.99,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "confirmed"
    assert body["payment_status"] == "success"
    assert body["total_amount"] == 59.98
    assert body["payment_id"] == "pay_test"
    assert body["order_id"].startswith("ord_")


@respx.mock
def test_create_order_payment_unreachable():
    payment_url = os.getenv("PAYMENT_API_URL", "http://localhost:8000").rstrip("/") + "/pay"
    respx.post(payment_url).mock(side_effect=httpx.ConnectError("connection refused"))

    response = client.post(
        "/orders",
        json={
            "product_id": "nx-mug",
            "product_name": "NexOps Mug",
            "quantity": 1,
            "unit_price": 14.0,
        },
    )
    assert response.status_code == 502
