from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="NexOps payment-api", version="1.0.0")


class PaymentRequest(BaseModel):
    order_id: str = Field(..., min_length=1)
    amount: float = Field(..., gt=0)
    currency: str = "USD"


class PaymentResponse(BaseModel):
    status: str
    message: str
    order_id: str
    amount: float
    currency: str
    payment_id: str


@app.get("/health")
def health():
    """Used later by Kubernetes and monitoring to check if the service is alive."""
    return {"status": "healthy", "service": "payment-api"}


@app.post("/pay", response_model=PaymentResponse)
def pay(payload: PaymentRequest):
    """Fake payment endpoint — always succeeds for Stage 1 demos."""
    return PaymentResponse(
        status="success",
        message="Payment successful",
        order_id=payload.order_id,
        amount=payload.amount,
        currency=payload.currency,
        payment_id=f"pay_{payload.order_id}",
    )
