from __future__ import annotations

import logging
import os
import threading

from typing import Optional
from fastapi import FastAPI, HTTPException

from app.store import IncidentStore
from app.watch import run_loop

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s level=%(levelname)s service=incident-detector %(message)s",
)

NAMESPACE = os.getenv("WATCH_NAMESPACE", "nexops")
INTERVAL = float(os.getenv("POLL_SECONDS", "10"))
DB_PATH = os.getenv("SQLITE_PATH", "/tmp/nexops-incidents.db")
WATCH_ENABLED = os.getenv("WATCH_ENABLED", "true").lower() == "true"

store = IncidentStore(DB_PATH)
app = FastAPI(title="NexOps incident-detector", version="1.0.0")
_stop = threading.Event()
_thread = None


@app.on_event("startup")
def startup():
    global _thread
    if WATCH_ENABLED:
        _thread = threading.Thread(
            target=run_loop,
            args=(store, NAMESPACE, INTERVAL, _stop.is_set),
            daemon=True,
            name="k8s-watch",
        )
        _thread.start()


@app.on_event("shutdown")
def shutdown():
    _stop.set()


@app.get("/health")
def health():
    return {"status": "healthy", "service": "incident-detector"}


@app.get("/ready")
def ready():
    return {"status": "ready", "service": "incident-detector"}


@app.get("/incidents")
def list_incidents(status: Optional[str] = None):
    if status and status not in ("OPEN", "RESOLVED"):
        raise HTTPException(status_code=400, detail="status must be OPEN or RESOLVED")
    return {"incidents": store.list_incidents(status=status)}


@app.get("/incidents/{incident_id}")
def get_incident(incident_id: str):
    row = store.get(incident_id)
    if not row:
        raise HTTPException(status_code=404, detail="incident not found")
    return row
