from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AnalysisStore:
    def __init__(self, path: str):
        self._path = path
        self._lock = threading.Lock()
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS analyses (
                    id TEXT PRIMARY KEY,
                    incident_id TEXT NOT NULL,
                    service TEXT,
                    problem TEXT,
                    status TEXT,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_analyses_incident ON analyses(incident_id)"
            )
            conn.commit()

    def save(self, incident: dict[str, Any], analysis: dict[str, Any]) -> dict[str, Any]:
        new_id = str(uuid.uuid4())
        row = {
            "id": new_id,
            "incident_id": incident.get("id"),
            "service": incident.get("service"),
            "incident_problem": incident.get("problem"),
            "incident_status": incident.get("status"),
            "created_at": _now(),
            **analysis,
        }
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO analyses (id, incident_id, service, problem, status, payload, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_id,
                    incident.get("id"),
                    incident.get("service"),
                    incident.get("problem"),
                    incident.get("status"),
                    json.dumps(row),
                    row["created_at"],
                ),
            )
            conn.commit()
        return row

    def latest_for_incident(self, incident_id: str) -> Optional[dict[str, Any]]:
        with self._lock, self._connect() as conn:
            rec = conn.execute(
                "SELECT payload FROM analyses WHERE incident_id = ? ORDER BY created_at DESC LIMIT 1",
                (incident_id,),
            ).fetchone()
        return json.loads(rec["payload"]) if rec else None

    def list_all(self) -> list[dict[str, Any]]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT payload FROM analyses ORDER BY created_at DESC"
            ).fetchall()
        return [json.loads(r["payload"]) for r in rows]

    def get(self, analysis_id: str) -> Optional[dict[str, Any]]:
        with self._lock, self._connect() as conn:
            rec = conn.execute(
                "SELECT payload FROM analyses WHERE id = ?",
                (analysis_id,),
            ).fetchone()
        return json.loads(rec["payload"]) if rec else None
