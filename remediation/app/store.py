from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Optional


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RemediationStore:
    def __init__(self, path: str):
        self._path = path
        self._lock = threading.Lock()
        self._init()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        return connection

    def _init(self) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS remediations (
                    id TEXT PRIMARY KEY,
                    incident_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_remediation_incident "
                "ON remediations(incident_id)"
            )
            connection.commit()

    def create(self, *, incident_id: str, analysis_id: str, decision: str,
               action: dict[str, Any], status: str) -> dict[str, Any]:
        timestamp = now()
        record = {
            "id": str(uuid.uuid4()), "incident_id": incident_id,
            "analysis_id": analysis_id, "decision": decision, "status": status,
            "suggested_action": action, "applied": None, "steps": [],
            "message": "Decision recorded", "error": None,
            "created_at": timestamp, "updated_at": timestamp,
            "completed_at": timestamp if status == "rejected" else None,
        }
        self._save(record, insert=True)
        return record

    def update(self, record_id: str, **changes: Any) -> dict[str, Any]:
        record = self.get(record_id)
        if not record:
            raise KeyError(record_id)
        record.update(changes)
        record["updated_at"] = now()
        if record.get("status") in {"succeeded", "failed", "rejected"}:
            record["completed_at"] = record["updated_at"]
        self._save(record, insert=False)
        return record

    def step(self, record_id: str, name: str, detail: str) -> dict[str, Any]:
        record = self.get(record_id)
        if not record:
            raise KeyError(record_id)
        steps = list(record.get("steps") or [])
        steps.append({"at": now(), "step": name, "detail": detail})
        return self.update(record_id, steps=steps)

    def _save(self, record: dict[str, Any], *, insert: bool) -> None:
        payload = json.dumps(record)
        with self._lock, self._connect() as connection:
            if insert:
                connection.execute(
                    "INSERT INTO remediations (id, incident_id, payload, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                    (record["id"], record["incident_id"], payload, record["created_at"], record["updated_at"]),
                )
            else:
                connection.execute(
                    "UPDATE remediations SET payload = ?, updated_at = ? WHERE id = ?",
                    (payload, record["updated_at"], record["id"]),
                )
            connection.commit()

    def get(self, record_id: str) -> Optional[dict[str, Any]]:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM remediations WHERE id = ?", (record_id,)
            ).fetchone()
        return json.loads(row["payload"]) if row else None

    def latest_for_incident(self, incident_id: str) -> Optional[dict[str, Any]]:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM remediations WHERE incident_id = ? ORDER BY created_at DESC LIMIT 1",
                (incident_id,),
            ).fetchone()
        return json.loads(row["payload"]) if row else None

    def list_all(self, incident_id: Optional[str] = None) -> list[dict[str, Any]]:
        query = "SELECT payload FROM remediations"
        params: tuple[Any, ...] = ()
        if incident_id:
            query += " WHERE incident_id = ?"
            params = (incident_id,)
        query += " ORDER BY created_at DESC"
        with self._lock, self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [json.loads(row["payload"]) for row in rows]
