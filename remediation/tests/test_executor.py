from types import SimpleNamespace

import pytest

from app import executor
from app.executor import build_patch


@pytest.mark.parametrize(("action", "expected"), [
    ({"type": "increase_memory", "target": "payment-api", "to": "64Mi"}, ("resources", "memory_limit", "64Mi")),
    ({"type": "fix_image_tag", "target": "payment-api"}, ("image", "image", "nexops/payment-api:v3")),
    ({"type": "restart_deployment", "target": "payment-api"}, ("env", "failure_mode", "none")),
    ({"type": "reset_failure_mode", "target": "payment-api"}, ("env", "failure_mode", "none")),
])
def test_builds_bounded_deployment_patch(action, expected):
    patch, applied = build_patch(action, container_name="payment-api", known_good_image="nexops/payment-api:v3")
    container = patch["spec"]["template"]["spec"]["containers"][0]
    assert container["name"] == "payment-api"
    assert {"name": "FAILURE_MODE", "value": "none"} in container["env"]
    assert "nexops.io/restarted-at" in patch["spec"]["template"]["metadata"]["annotations"]
    assert expected[0] in container
    assert applied[expected[1]] == expected[2]


def test_rejects_unknown_action():
    with pytest.raises(ValueError, match="unsupported"):
        build_patch({"type": "delete_namespace", "target": "payment-api"}, container_name="payment-api", known_good_image="nexops/payment-api:v3")


def test_apply_uses_stable_field_manager(monkeypatch):
    class FakeApi:
        patch_kwargs = {}
        def read_namespaced_deployment(self, *_):
            container = SimpleNamespace(name="payment-api")
            return SimpleNamespace(spec=SimpleNamespace(template=SimpleNamespace(spec=SimpleNamespace(containers=[container]))))
        def patch_namespaced_deployment(self, *args, **kwargs):
            self.patch_kwargs = kwargs
    api = FakeApi()
    monkeypatch.setattr(executor, "load_apps_api", lambda: api)
    executor.apply_action({"type": "reset_failure_mode", "target": "payment-api"}, namespace="nexops", known_good_image="nexops/payment-api:v3")
    assert api.patch_kwargs["field_manager"] == "nexops-remediation"
