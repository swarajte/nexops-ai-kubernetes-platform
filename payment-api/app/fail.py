"""Demo-only failure injection for payment-api.

Used in Stage 4 so we can create Kubernetes symptoms on purpose:
OOMKilled, CrashLoopBackOff, readiness failure, CPU, memory, slowness, errors.

Default mode is healthy. Nothing here is used by the store unless we trigger it.
"""

from __future__ import annotations

import os
import random
import threading
import time

_cpu_run = threading.Event()
_oom_run = threading.Event()
_lock = threading.Lock()
_memory_blocks: list[bytearray] = []

ready = True
slow_seconds = 0.0
error_rate = 0.0


def failure_mode() -> str:
    return os.getenv("FAILURE_MODE", "none").strip().lower() or "none"


def apply_startup_mode() -> None:
    """Apply FAILURE_MODE from the environment when the process starts."""
    mode = failure_mode()
    if mode == "crash":
        os._exit(1)
    if mode == "ready":
        set_ready(False)
    if mode == "slow":
        set_slow(5.0)
    if mode == "errors":
        set_error_rate(0.8)
    if mode == "cpu":
        start_cpu()
    if mode == "memory":
        allocate_memory_mb(40)
    if mode == "oom":
        start_oom()


def status() -> dict:
    return {
        "service": "payment-api",
        "failure_mode_env": failure_mode(),
        "ready": ready,
        "slow_seconds": slow_seconds,
        "error_rate": error_rate,
        "cpu": _cpu_run.is_set(),
        "oom": _oom_run.is_set(),
        "memory_blocks": len(_memory_blocks),
    }


def set_ready(value: bool) -> None:
    global ready
    ready = value


def set_slow(seconds: float) -> None:
    global slow_seconds
    slow_seconds = max(0.0, seconds)


def set_error_rate(rate: float) -> None:
    global error_rate
    error_rate = min(1.0, max(0.0, rate))


def maybe_fail_payment() -> str | None:
    """Return an error message if this payment should fail; otherwise None."""
    if slow_seconds:
        time.sleep(slow_seconds)
    if error_rate and random.random() < error_rate:
        return "injected payment error"
    return None


def _cpu_loop() -> None:
    while _cpu_run.is_set():
        pass


def start_cpu() -> None:
    if _cpu_run.is_set():
        return
    _cpu_run.set()
    threading.Thread(target=_cpu_loop, name="nexops-cpu", daemon=True).start()


def stop_cpu() -> None:
    _cpu_run.clear()


def allocate_memory_mb(megabytes: int) -> int:
    size = max(1, megabytes) * 1024 * 1024
    with _lock:
        _memory_blocks.append(bytearray(size))
        return len(_memory_blocks)


def _oom_loop() -> None:
    # Keep allocating until kubelet OOM-kills the container.
    while _oom_run.is_set():
        try:
            allocate_memory_mb(8)
        except MemoryError:
            time.sleep(0.1)
            continue
        time.sleep(0.05)


def start_oom() -> None:
    if _oom_run.is_set():
        return
    _oom_run.set()
    threading.Thread(target=_oom_loop, name="nexops-oom", daemon=True).start()


def reset() -> None:
    global ready, slow_seconds, error_rate
    ready = True
    slow_seconds = 0.0
    error_rate = 0.0
    stop_cpu()
    _oom_run.clear()
    with _lock:
        _memory_blocks.clear()
