"""Stage 10: chart RBAC must stay least privilege (no cluster-admin, no writes for analyzer)."""

from pathlib import Path

TEMPLATES = Path(__file__).resolve().parents[1] / "templates"


def _read(name: str) -> str:
    return (TEMPLATES / name).read_text(encoding="utf-8")


def test_analyzer_role_is_read_only():
    text = _read("ai-analyzer.yaml")
    assert 'resources: ["pods", "pods/log", "events"]' in text
    assert 'verbs: ["get", "list"]' in text
    for verb in ("create", "update", "patch", "delete", "*"):
        assert f'"{verb}"' not in text.split("kind: Deployment", 1)[0]


def test_detector_role_cannot_write():
    text = _read("incident-detector.yaml").split("kind: Deployment", 1)[0]
    assert 'resources: ["pods", "events"]' in text
    for verb in ("create", "update", "patch", "delete", "*"):
        assert f'"{verb}"' not in text


def test_remediation_role_is_named_payment_api_patch_only():
    text = _read("remediation.yaml").split("kind: Deployment", 1)[0]
    assert 'resourceNames: ["payment-api"]' in text
    assert 'verbs: ["get", "patch"]' in text
    assert "secrets" not in text.lower()
    assert "pods/exec" not in text


def test_store_service_accounts_do_not_mount_tokens():
    text = _read("serviceaccounts-apps.yaml")
    assert text.count("automountServiceAccountToken: false") == 3
    for name in ("frontend", "orders-api", "payment-api"):
        assert f"name: {name}" in text
