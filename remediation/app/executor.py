from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any
from urllib import request

from kubernetes import client, config
from kubernetes.config.config_exception import ConfigException


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_apps_api() -> client.AppsV1Api:
    try:
        config.load_incluster_config()
    except ConfigException:
        config.load_kube_config()
    return client.AppsV1Api()


def build_patch(action: dict[str, Any], *, container_name: str,
                known_good_image: str) -> tuple[dict[str, Any], dict[str, Any]]:
    action_type = action["type"]
    container: dict[str, Any] = {
        "name": container_name,
        "env": [{"name": "FAILURE_MODE", "value": "none"}],
    }
    applied: dict[str, Any] = {
        "kind": "Deployment", "name": action["target"],
        "action": action_type, "failure_mode": "none",
    }
    if action_type == "increase_memory":
        target = action["to"]
        container["resources"] = {"limits": {"memory": target}}
        applied["memory_limit"] = target
    elif action_type == "fix_image_tag":
        container["image"] = known_good_image
        container["imagePullPolicy"] = "IfNotPresent"
        applied["image"] = known_good_image
    elif action_type not in {"restart_deployment", "reset_failure_mode"}:
        raise ValueError(f"unsupported action {action_type}")

    patch = {
        "metadata": {"annotations": {"nexops.io/remediated-at": _utc_now()}},
        "spec": {"template": {
            "metadata": {"annotations": {"nexops.io/restarted-at": _utc_now()}},
            "spec": {"containers": [container]},
        }},
    }
    return patch, applied


def apply_action(action: dict[str, Any], *, namespace: str,
                 known_good_image: str) -> dict[str, Any]:
    target = str(action["target"])
    api = load_apps_api()
    deployment = api.read_namespaced_deployment(target, namespace)
    containers = deployment.spec.template.spec.containers or []
    if not any(container.name == target for container in containers):
        raise RuntimeError(f"container {target!r} not found in deployment")
    patch, applied = build_patch(
        action, container_name=target, known_good_image=known_good_image
    )
    api.patch_namespaced_deployment(target, namespace, patch, field_manager="nexops-remediation")
    return applied


def _json(url: str, *, timeout: float = 4) -> dict[str, Any]:
    with request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode())


def best_effort_runtime_reset(payment_api_url: str) -> None:
    reset = request.Request(f"{payment_api_url}/fail/reset", data=b"{}", method="POST")
    try:
        request.urlopen(reset, timeout=3).close()
    except Exception:
        pass


def wait_for_recovery(*, incident_id: str, target: str, namespace: str,
                      detector_url: str, payment_api_url: str,
                      timeout_seconds: float, poll_seconds: float) -> dict[str, Any]:
    api = load_apps_api()
    deadline = time.monotonic() + timeout_seconds
    last_detail = "waiting for rollout"
    while time.monotonic() < deadline:
        deployment = api.read_namespaced_deployment(target, namespace)
        desired = deployment.spec.replicas or 1
        status = deployment.status
        rollout_ready = (
            (status.updated_replicas or 0) >= desired
            and (status.available_replicas or 0) >= desired
            and (status.observed_generation or 0) >= (deployment.metadata.generation or 0)
        )
        incident = _json(f"{detector_url}/incidents/{incident_id}")
        incident_resolved = incident.get("status") == "RESOLVED"
        app_healthy = False
        try:
            fail_status = _json(f"{payment_api_url}/fail/status")
            app_healthy = (
                fail_status.get("failure_mode_env") == "none"
                and fail_status.get("ready") is True
                and not fail_status.get("cpu")
                and not fail_status.get("oom")
                and not fail_status.get("slow_seconds")
                and not fail_status.get("error_rate")
            )
        except Exception:
            pass
        if rollout_ready and incident_resolved and app_healthy:
            return {"incident_status": "RESOLVED", "deployment_ready": True,
                    "application_healthy": True}
        last_detail = (
            f"rollout_ready={rollout_ready}, incident={incident.get('status')}, "
            f"application_healthy={app_healthy}"
        )
        time.sleep(poll_seconds)
    raise TimeoutError(f"recovery was not verified: {last_detail}")
