from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app import fail

app = FastAPI(title="NexOps payment-api", version="1.1.0")
fail.apply_startup_mode()


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


class ReadyToggle(BaseModel):
    fail: bool = True


class SlowRequest(BaseModel):
    seconds: float = Field(5.0, ge=0, le=30)


class ErrorRateRequest(BaseModel):
    rate: float = Field(0.8, ge=0, le=1)


class MemoryRequest(BaseModel):
    megabytes: int = Field(40, ge=1, le=256)


@app.get("/health")
def health():
    """Liveness: process is up. Kubernetes should not restart us only because we are unready."""
    return {"status": "healthy", "service": "payment-api"}


@app.get("/ready")
def ready():
    """Readiness: can this pod take traffic?"""
    if not fail.ready:
        raise HTTPException(status_code=503, detail="payment-api is not ready (injected)")
    return {"status": "ready", "service": "payment-api"}


@app.post("/pay", response_model=PaymentResponse)
def pay(payload: PaymentRequest):
    injected = fail.maybe_fail_payment()
    if injected:
        raise HTTPException(status_code=500, detail=injected)
    return PaymentResponse(
        status="success",
        message="Payment successful",
        order_id=payload.order_id,
        amount=payload.amount,
        currency=payload.currency,
        payment_id=f"pay_{payload.order_id}",
    )


@app.get("/fail/status")
def fail_status():
    return fail.status()


@app.post("/fail/reset")
def fail_reset():
    fail.reset()
    return {"status": "reset", **fail.status()}


@app.post("/fail/oom")
def fail_oom():
    fail.start_oom()
    return {"status": "oom_started", "note": "pod should become OOMKilled if memory limit is low"}


@app.post("/fail/crash")
def fail_crash():
    os_exit()
    return {"status": "unreachable"}


def os_exit() -> None:
    import os

    os._exit(1)


@app.post("/fail/ready")
def fail_ready(payload: ReadyToggle):
    fail.set_ready(not payload.fail)
    return fail.status()


@app.post("/fail/cpu")
def fail_cpu():
    fail.start_cpu()
    return fail.status()


@app.post("/fail/memory")
def fail_memory(payload: MemoryRequest):
    blocks = fail.allocate_memory_mb(payload.megabytes)
    return {"status": "allocated", "blocks": blocks, "megabytes": payload.megabytes}


@app.post("/fail/slow")
def fail_slow(payload: SlowRequest):
    fail.set_slow(payload.seconds)
    return fail.status()


@app.post("/fail/errors")
def fail_errors(payload: ErrorRateRequest):
    fail.set_error_rate(payload.rate)
    return fail.status()
