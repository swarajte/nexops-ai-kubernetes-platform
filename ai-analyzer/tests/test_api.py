import os
import tempfile

_fd, _db = tempfile.mkstemp(suffix=".sqlite")
os.close(_fd)
os.environ["WATCH_ENABLED"] = "false"
os.environ["SQLITE_PATH"] = _db

from fastapi.testclient import TestClient

from app.main import app, store
from app.rules import analyze

client = TestClient(app)


def test_health():
    assert client.get("/health").json()["service"] == "ai-analyzer"


def test_store_roundtrip():
    incident = {
        "id": "inc-1",
        "service": "payment-api",
        "problem": "OOMKilled",
        "status": "OPEN",
        "pod": "payment-api-x",
    }
    analysis = analyze(incident, {"memory_limit": "128Mi", "restart_count": 1})
    saved = store.save(incident, analysis)
    listed = client.get("/analyses").json()["analyses"]
    assert listed[0]["id"] == saved["id"]
    one = client.get(f"/analyses/{saved['id']}")
    assert one.status_code == 200
    assert one.json()["suggested_action"]["type"] == "increase_memory"
