from app.rules import analyze


def test_oomkilled():
    out = analyze(
        {"service": "payment-api", "problem": "OOMKilled", "pod": "payment-api-x"},
        {"memory_limit": "128Mi", "restart_count": 3, "last_terminated_reason": "OOMKilled"},
    )
    assert "memory" in out["problem"].lower()
    assert "OOMKilled" in out["evidence"]
    assert out["suggested_action"]["type"] == "increase_memory"
    assert out["suggested_action"]["to"] == "256Mi"
    assert out["confidence"] >= 80
    assert out["source"] == "rules"


def test_notready_with_restarts_treated_as_memory():
    out = analyze(
        {"service": "payment-api", "problem": "NotReady", "pod": "p"},
        {"memory_limit": "32Mi", "restart_count": 2, "events": [{"reason": "OOMKilled", "message": "Memory cgroup"}]},
    )
    assert out["suggested_action"]["type"] == "increase_memory"


def test_image_pull():
    out = analyze(
        {"service": "payment-api", "problem": "ImagePullBackOff", "pod": "p"},
        {},
    )
    assert out["suggested_action"]["type"] == "fix_image_tag"
    assert out["confidence"] >= 85


def test_crashloop():
    out = analyze(
        {"service": "payment-api", "problem": "CrashLoopBackOff", "pod": "p"},
        {"restart_count": 5, "last_terminated_reason": "Error"},
    )
    assert out["suggested_action"]["type"] == "restart_deployment"
