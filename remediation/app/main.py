from __future__ import annotations

import json
import logging
import os
import threading
from typing import Any, Literal, Optional
from urllib import error, request

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel

from app.allowlist import UnsafeAction, validate
from app.executor import apply_action, best_effort_runtime_reset, wait_for_recovery
from app.store import RemediationStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s level=%(levelname)s service=remediation %(message)s")
logger = logging.getLogger("remediation")
NAMESPACE = os.getenv("WATCH_NAMESPACE", "nexops")
DB_PATH = os.getenv("SQLITE_PATH", "/tmp/nexops-remediations.db")
DETECTOR_URL = os.getenv("INCIDENT_DETECTOR_URL", "http://incident-detector:8080").rstrip("/")
ANALYZER_URL = os.getenv("AI_ANALYZER_URL", "http://ai-analyzer:8081").rstrip("/")
PAYMENT_API_URL = os.getenv("PAYMENT_API_URL", "http://payment-api:8000").rstrip("/")
KNOWN_GOOD_IMAGE = os.getenv("KNOWN_GOOD_IMAGE", "nexops/payment-api:v3")
ALLOWED_TARGETS = {item.strip() for item in os.getenv("ALLOWED_TARGETS", "payment-api").split(",") if item.strip()}
MAX_MEMORY_MI = int(os.getenv("MAX_MEMORY_MI", "512"))
VERIFY_TIMEOUT = float(os.getenv("VERIFY_TIMEOUT_SECONDS", "120"))
VERIFY_POLL = float(os.getenv("VERIFY_POLL_SECONDS", "5"))
store = RemediationStore(DB_PATH)
app = FastAPI(title="NexOps remediation", version="1.0.0")


class DecisionBody(BaseModel):
    incident_id: str
    analysis_id: str
    decision: Literal["approved", "rejected"]


def _fetch(url: str) -> dict[str, Any]:
    try:
        with request.urlopen(url, timeout=5) as response:
            return json.loads(response.read().decode())
    except error.HTTPError as exc:
        if exc.code == 404:
            raise HTTPException(status_code=404, detail="incident or analysis not found") from exc
        raise HTTPException(status_code=502, detail=f"dependency returned {exc.code}") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"dependency unavailable: {exc}") from exc


def _load_pair(incident_id: str, analysis_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    incident = _fetch(f"{DETECTOR_URL}/incidents/{incident_id}")
    analysis = _fetch(f"{ANALYZER_URL}/analyses/{analysis_id}")
    if incident.get("status") != "OPEN":
        raise UnsafeAction("incident is no longer OPEN")
    if analysis.get("incident_id") != incident_id:
        raise UnsafeAction("analysis does not belong to this incident")
    if analysis.get("incident_problem") != incident.get("problem"):
        raise UnsafeAction("analysis problem is stale")
    return incident, analysis


def _run(record_id: str) -> None:
    record = store.get(record_id)
    if not record:
        return
    try:
        store.update(record_id, status="validating", message="Revalidating live incident")
        incident, analysis = _load_pair(record["incident_id"], record["analysis_id"])
        action = validate(incident, analysis, allowed_targets=ALLOWED_TARGETS, max_memory_mi=MAX_MEMORY_MI)
        store.step(record_id, "validated", "Incident, analysis, target, and action match")
        store.update(record_id, status="applying", message="Applying allowlisted change")
        applied = apply_action(action, namespace=NAMESPACE, known_good_image=KNOWN_GOOD_IMAGE)
        store.update(record_id, applied=applied)
        store.step(record_id, "deployment_patched", json.dumps(applied, sort_keys=True))
        best_effort_runtime_reset(PAYMENT_API_URL)
        store.update(record_id, status="verifying", message="Waiting for verified recovery")
        verified = wait_for_recovery(
            incident_id=record["incident_id"], target=str(action["target"]), namespace=NAMESPACE,
            detector_url=DETECTOR_URL, payment_api_url=PAYMENT_API_URL,
            timeout_seconds=VERIFY_TIMEOUT, poll_seconds=VERIFY_POLL,
        )
        store.step(record_id, "recovery_verified", json.dumps(verified, sort_keys=True))
        store.update(record_id, status="succeeded", message="Change applied and recovery verified")
    except Exception as exc:
        logger.exception("remediation failed id=%s", record_id)
        store.update(record_id, status="failed", message="Remediation failed", error=str(exc))


@app.get("/health")
def health():
    return {"status": "healthy", "service": "remediation"}


@app.get("/ready")
def ready():
    return {"status": "ready", "service": "remediation"}


@app.post("/decisions", status_code=status.HTTP_202_ACCEPTED)
def submit_decision(body: DecisionBody):
    existing = store.latest_for_incident(body.incident_id)
    if existing:
        raise HTTPException(status_code=409, detail="decision already recorded for incident")
    try:
        incident, analysis = _load_pair(body.incident_id, body.analysis_id)
        action = dict(analysis.get("suggested_action") or {})
        if body.decision == "approved":
            action = validate(incident, analysis, allowed_targets=ALLOWED_TARGETS, max_memory_mi=MAX_MEMORY_MI)
    except UnsafeAction as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    initial_status = "queued" if body.decision == "approved" else "rejected"
    record = store.create(incident_id=body.incident_id, analysis_id=body.analysis_id,
                          decision=body.decision, action=action, status=initial_status)
    if body.decision == "approved":
        threading.Thread(target=_run, args=(record["id"],), daemon=True).start()
    return record


@app.get("/remediations")
def list_remediations(incident_id: Optional[str] = None):
    return {"remediations": store.list_all(incident_id=incident_id)}


@app.get("/remediations/{record_id}")
def get_remediation(record_id: str):
    record = store.get(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="remediation not found")
    return record
