from __future__ import annotations

import logging
import os
import threading
import time
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.gather import fetch_incident, gather_evidence, list_open_incidents, load_kube
from app.llm import maybe_refine_with_llm
from app.rules import analyze
from app.store import AnalysisStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s level=%(levelname)s service=ai-analyzer %(message)s",
)
logger = logging.getLogger("ai-analyzer")

NAMESPACE = os.getenv("WATCH_NAMESPACE", "nexops")
DB_PATH = os.getenv("SQLITE_PATH", "/tmp/nexops-analyses.db")
POLL_SECONDS = float(os.getenv("POLL_SECONDS", "20"))
WATCH_ENABLED = os.getenv("WATCH_ENABLED", "true").lower() == "true"

store = AnalysisStore(DB_PATH)
app = FastAPI(title="NexOps ai-analyzer", version="1.0.0")
_stop = threading.Event()
_thread = None


class AnalyzeBody(BaseModel):
    incident_id: str


def run_analysis(incident_id: str) -> dict:
    incident = fetch_incident(incident_id)
    api = load_kube()
    evidence = gather_evidence(api, incident)
    draft = analyze(incident, evidence)
    result = maybe_refine_with_llm(draft, incident, evidence)
    saved = store.save(incident, result)
    logger.info(
        "analyzed incident=%s service=%s problem=%s confidence=%s source=%s",
        incident_id,
        incident.get("service"),
        incident.get("problem"),
        saved.get("confidence"),
        saved.get("source"),
    )
    return saved


def _poll_loop() -> None:
    while not _stop.is_set():
        try:
            for inc in list_open_incidents():
                iid = inc.get("id")
                if not iid:
                    continue
                existing = store.latest_for_incident(iid)
                if existing:
                    continue
                try:
                    run_analysis(iid)
                except Exception:
                    logger.exception("auto-analyze failed for %s", iid)
        except Exception:
            logger.exception("poll loop error")
        deadline = time.time() + POLL_SECONDS
        while not _stop.is_set() and time.time() < deadline:
            time.sleep(0.25)


@app.on_event("startup")
def startup():
    global _thread
    if WATCH_ENABLED:
        _thread = threading.Thread(target=_poll_loop, daemon=True, name="analyze-poll")
        _thread.start()


@app.on_event("shutdown")
def shutdown():
    _stop.set()


@app.get("/health")
def health():
    return {"status": "healthy", "service": "ai-analyzer"}


@app.get("/ready")
def ready():
    return {"status": "ready", "service": "ai-analyzer"}


@app.post("/analyze")
def analyze_endpoint(body: AnalyzeBody):
    try:
        return run_analysis(body.incident_id)
    except Exception as exc:
        logger.exception("analyze failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/analyses")
def list_analyses():
    return {"analyses": store.list_all()}


@app.get("/analyses/{analysis_id}")
def get_analysis(analysis_id: str):
    row = store.get(analysis_id)
    if not row:
        raise HTTPException(status_code=404, detail="analysis not found")
    return row
