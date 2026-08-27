from fastapi.testclient import TestClient
from app import main
from app.store import RemediationStore


def _pair():
    incident = {"id": "inc-api", "status": "OPEN", "problem": "HighErrorRate"}
    analysis = {"id": "analysis-api", "incident_id": "inc-api", "incident_problem": "HighErrorRate", "suggested_action": {"type": "reset_failure_mode", "target": "payment-api"}}
    return incident, analysis


def test_health():
    response = TestClient(main.app).get("/health")
    assert response.status_code == 200
    assert response.json()["service"] == "remediation"


def test_rejection_is_persisted_without_worker(monkeypatch, tmp_path):
    incident, analysis = _pair()
    main.store = RemediationStore(str(tmp_path / "reject.db"))
    monkeypatch.setattr(main, "_load_pair", lambda *_: (incident, analysis))
    response = TestClient(main.app).post("/decisions", json={"incident_id": incident["id"], "analysis_id": analysis["id"], "decision": "rejected"})
    assert response.status_code == 202
    assert response.json()["status"] == "rejected"
    rows = TestClient(main.app).get("/remediations").json()["remediations"]
    assert rows[0]["decision"] == "rejected"


def test_approved_action_is_queued_and_idempotent(monkeypatch, tmp_path):
    incident, analysis = _pair()
    main.store = RemediationStore(str(tmp_path / "approve.db"))
    monkeypatch.setattr(main, "_load_pair", lambda *_: (incident, analysis))
    class NoStartThread:
        def __init__(self, *args, **kwargs): pass
        def start(self): pass
    monkeypatch.setattr(main.threading, "Thread", NoStartThread)
    client = TestClient(main.app)
    body = {"incident_id": incident["id"], "analysis_id": analysis["id"], "decision": "approved"}
    response = client.post("/decisions", json=body)
    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    assert response.json()["suggested_action"]["type"] == "reset_failure_mode"
    assert client.post("/decisions", json=body).status_code == 409
