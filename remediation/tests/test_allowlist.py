import pytest
from app.allowlist import UnsafeAction, validate


def pair(problem="OOMKilled", action_type="increase_memory", target="payment-api"):
    incident = {"id": "inc-1", "status": "OPEN", "problem": problem}
    analysis = {"incident_id": "inc-1", "incident_problem": problem,
        "suggested_action": {"type": action_type, "target": target, "from": "32Mi", "to": "64Mi"}}
    return incident, analysis


def test_accepts_expected_oom_action():
    incident, analysis = pair()
    action = validate(incident, analysis, allowed_targets={"payment-api"}, max_memory_mi=512)
    assert action["type"] == "increase_memory"
    assert action["to"] == "64Mi"


@pytest.mark.parametrize(("change", "message"), [
    ({"status": "RESOLVED"}, "no longer OPEN"),
    ({"analysis_incident_id": "other"}, "does not belong"),
    ({"action_type": "investigate"}, "not allowlisted"),
    ({"target": "orders-api"}, "target"),
    ({"action_type": "restart_deployment"}, "requires"),
    ({"to": "2048Mi"}, "safety cap"),
])
def test_rejects_unsafe_or_stale_actions(change, message):
    incident, analysis = pair()
    if "status" in change: incident["status"] = change["status"]
    if "analysis_incident_id" in change: analysis["incident_id"] = change["analysis_incident_id"]
    if "action_type" in change: analysis["suggested_action"]["type"] = change["action_type"]
    if "target" in change: analysis["suggested_action"]["target"] = change["target"]
    if "to" in change: analysis["suggested_action"]["to"] = change["to"]
    with pytest.raises(UnsafeAction, match=message):
        validate(incident, analysis, allowed_targets={"payment-api"}, max_memory_mi=512)
