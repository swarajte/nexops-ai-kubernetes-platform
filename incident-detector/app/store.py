from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from app.classify import Finding, fingerprint


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class IncidentStore:
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
                CREATE TABLE IF NOT EXISTS incidents (
                    id TEXT PRIMARY KEY,
                    service TEXT NOT NULL,
                    problem TEXT NOT NULL,
                    status TEXT NOT NULL,
                    pod TEXT,
                    namespace TEXT,
                    message TEXT,
                    evidence TEXT,
                    fingerprint TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status)"
            )
            conn.commit()

    def upsert_open(self, finding: Finding, namespace: str, evidence: dict[str, Any]) -> dict[str, Any]:
        fp = fingerprint(finding)
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM incidents WHERE fingerprint = ? AND status = 'OPEN' LIMIT 1",
                (fp,),
            ).fetchone()
            now = _now()
            ev = json.dumps(evidence)
            if row:
                conn.execute(
                    """
                    UPDATE incidents
                    SET pod = ?, message = ?, evidence = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (finding.pod, finding.message, ev, now, row["id"]),
                )
                conn.commit()
                return self._row(conn.execute("SELECT * FROM incidents WHERE id = ?", (row["id"],)).fetchone())
            new_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO incidents (
                    id, service, problem, status, pod, namespace, message,
                    evidence, fingerprint, created_at, updated_at
                ) VALUES (?, ?, ?, 'OPEN', ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_id,
                    finding.service,
                    finding.problem,
                    finding.pod,
                    namespace,
                    finding.message,
                    ev,
                    fp,
                    now,
                    now,
                ),
            )
            conn.commit()
            return self._row(conn.execute("SELECT * FROM incidents WHERE id = ?", (new_id,)).fetchone())

    def resolve_missing(self, open_fingerprints: set[str]) -> int:
        with self._lock, self._connect() as conn:
            rows = conn.execute("SELECT id, fingerprint FROM incidents WHERE status = 'OPEN'").fetchall()
            now = _now()
            n = 0
            for row in rows:
                if row["fingerprint"] not in open_fingerprints:
                    conn.execute(
                        "UPDATE incidents SET status = 'RESOLVED', updated_at = ? WHERE id = ?",
                        (now, row["id"]),
                    )
                    n += 1
            conn.commit()
            return n

    def list_incidents(self, status: Optional[str] = None) -> list[dict[str, Any]]:
        with self._lock, self._connect() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM incidents WHERE status = ? ORDER BY updated_at DESC",
                    (status,),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM incidents ORDER BY updated_at DESC").fetchall()
            return [self._row(r) for r in rows]

    def get(self, incident_id: str) -> Optional[dict[str, Any]]:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)).fetchone()
            return self._row(row) if row else None

    @staticmethod
    def _row(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        if data.get("evidence"):
            try:
                data["evidence"] = json.loads(data["evidence"])
            except json.JSONDecodeError:
                pass
        return data
