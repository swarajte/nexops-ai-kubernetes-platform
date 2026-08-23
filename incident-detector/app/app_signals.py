from __future__ import annotations

from typing import Any, Optional

from app.classify import Finding

_ENV_TO_PROBLEM = {
    "cpu": ("HighCpu", "payment-api FAILURE_MODE=cpu (busy loop)"),
    "memory": ("HighMemory", "payment-api FAILURE_MODE=memory (extra heap, pod still Ready)"),
    "slow": ("SlowRequests", "payment-api FAILURE_MODE=slow (/pay sleeps)"),
    "errors": ("HighErrorRate", "payment-api FAILURE_MODE=errors (/pay returns 500s)"),
}


def classify_fail_status(payload: dict[str, Any], pod: str = "payment-api") -> Optional[Finding]:
    mode = (payload.get("failure_mode_env") or "none").strip().lower()
    if mode in _ENV_TO_PROBLEM:
        problem, message = _ENV_TO_PROBLEM[mode]
        return Finding(service="payment-api", problem=problem, pod=pod, message=message)
    if payload.get("cpu"):
        return Finding(service="payment-api", problem="HighCpu", pod=pod, message="payment-api reports injected CPU burn")
    if int(payload.get("memory_blocks") or 0) > 0:
        return Finding(service="payment-api", problem="HighMemory", pod=pod, message="payment-api reports injected extra heap")
    if float(payload.get("slow_seconds") or 0) > 0:
        return Finding(service="payment-api", problem="SlowRequests", pod=pod, message="payment-api reports injected delay on /pay")
    if float(payload.get("error_rate") or 0) > 0:
        return Finding(service="payment-api", problem="HighErrorRate", pod=pod, message="payment-api reports injected /pay errors")
    return None
