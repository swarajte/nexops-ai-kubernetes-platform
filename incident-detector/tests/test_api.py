import os
import tempfile

_fd, _db = tempfile.mkstemp(suffix=".sqlite")
os.close(_fd)
os.environ["WATCH_ENABLED"] = "false"
os.environ["SQLITE_PATH"] = _db

from fastapi.testclient import TestClient

from app.classify import Finding
from app.main import app, store

client = TestClient(app)


def test_health():
    assert client.get("/health").status_code == 200


def test_upsert_and_list_and_resolve():
    finding = Finding(
        service="payment-api",
        problem="OOMKilled",
        pod="payment-api-xyz",
        message="container exceeded memory limit",
    )
    created = store.upsert_open(finding, namespace="nexops", evidence={"pod": finding.pod})
    assert created["status"] == "OPEN"
    listed = client.get("/incidents?status=OPEN").json()["incidents"]
    assert any(i["problem"] == "OOMKilled" for i in listed)
    one = client.get(f"/incidents/{created['id']}")
    assert one.status_code == 200
    store.resolve_missing(set())
    listed2 = client.get("/incidents?status=OPEN").json()["incidents"]
    assert listed2 == []
