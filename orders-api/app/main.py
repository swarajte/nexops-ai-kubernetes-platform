import os
import uuid
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(title="NexOps orders-api", version="1.0.0")

PAYMENT_API_URL = os.getenv("PAYMENT_API_URL", "http://localhost:8000")
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class OrderRequest(BaseModel):
    product_id: str = Field(..., min_length=1)
    product_name: str = Field(..., min_length=1)
    quantity: int = Field(..., ge=1, le=20)
    unit_price: float = Field(..., gt=0)


class OrderResponse(BaseModel):
    order_id: str
    product_id: str
    product_name: str
    quantity: int
    unit_price: float
    total_amount: float
    currency: str
    status: str
    payment_status: str
    payment_id: Optional[str] = None
    message: str


@app.get("/health")
def health():
    return {"status": "healthy", "service": "orders-api"}


@app.post("/orders", response_model=OrderResponse)
def create_order(payload: OrderRequest):
    order_id = f"ord_{uuid.uuid4().hex[:12]}"
    total_amount = round(payload.unit_price * payload.quantity, 2)

    payment_payload = {
        "order_id": order_id,
        "amount": total_amount,
        "currency": "USD",
    }

    try:
        with httpx.Client(timeout=5.0) as client:
            payment_response = client.post(f"{PAYMENT_API_URL.rstrip('/')}/pay", json=payment_payload)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Unable to reach payment-api: {exc.__class__.__name__}",
        ) from exc

    if payment_response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"payment-api returned status {payment_response.status_code}",
        )

    payment_body = payment_response.json()
    payment_status = payment_body.get("status", "unknown")

    if payment_status != "success":
        return OrderResponse(
            order_id=order_id,
            product_id=payload.product_id,
            product_name=payload.product_name,
            quantity=payload.quantity,
            unit_price=payload.unit_price,
            total_amount=total_amount,
            currency="USD",
            status="failed",
            payment_status=payment_status,
            payment_id=payment_body.get("payment_id"),
            message="Order created but payment failed",
        )

    return OrderResponse(
        order_id=order_id,
        product_id=payload.product_id,
        product_name=payload.product_name,
        quantity=payload.quantity,
        unit_price=payload.unit_price,
        total_amount=total_amount,
        currency="USD",
        status="confirmed",
        payment_status=payment_status,
        payment_id=payment_body.get("payment_id"),
        message="Order placed and payment successful",
    )
