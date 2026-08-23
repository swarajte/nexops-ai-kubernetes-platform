from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen

from kubernetes import client, config

logger = logging.getLogger("ai-analyzer")

DETECTOR_URL = os.getenv("INCIDENT_DETECTOR_URL", "http://incident-detector:8080")
NAMESPACE = os.getenv("WATCH_NAMESPACE", "nexops")


def load_kube() -> client.CoreV1Api:
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()
    return client.CoreV1Api()


def fetch_incident(incident_id: str) -> dict[str, Any]:
    url = f"{DETECTOR_URL.rstrip('/')}/incidents/{incident_id}"
    with urlopen(url, timeout=8) as resp:
        return json.loads(resp.read().decode())


def list_open_incidents() -> list[dict[str, Any]]:
    url = f"{DETECTOR_URL.rstrip('/')}/incidents?status=OPEN"
    try:
        with urlopen(url, timeout=8) as resp:
            body = json.loads(resp.read().decode())
        return body.get("incidents") or []
    except (URLError, HTTPError, TimeoutError, json.JSONDecodeError):
        logger.exception("could not list OPEN incidents from detector")
        return []


def gather_evidence(api: client.CoreV1Api, incident: dict[str, Any]) -> dict[str, Any]:
    service = incident.get("service") or ""
    pod_name = incident.get("pod") or ""
    evidence: dict[str, Any] = {
        "pod": pod_name,
        "events": [],
        "restart_count": 0,
        "last_terminated_reason": None,
        "memory_limit": None,
        "memory_request": None,
        "log_tail": None,
    }

    pods = api.list_namespaced_pod(
        NAMESPACE, label_selector=f"app.kubernetes.io/component={service}"
    )
    target = None
    for pod in pods.items:
        if pod.metadata and pod.metadata.name == pod_name:
            target = pod
            break
    if target is None and pods.items:
        target = pods.items[0]
    if target is None:
        return evidence

    evidence["pod"] = target.metadata.name
    statuses = (target.status.container_statuses or []) if target.status else []
    if statuses:
        cs = statuses[0]
        evidence["restart_count"] = int(cs.restart_count or 0)
        last = cs.last_state.terminated if cs.last_state and cs.last_state.terminated else None
        if last:
            evidence["last_terminated_reason"] = last.reason
        cur = cs.state.terminated if cs.state and cs.state.terminated else None
        if cur and cur.reason:
            evidence["last_terminated_reason"] = cur.reason

    containers = (target.spec.containers or []) if target.spec else []
    if containers and containers[0].resources:
        res = containers[0].resources
        if res.limits:
            evidence["memory_limit"] = res.limits.get("memory")
        if res.requests:
            evidence["memory_request"] = res.requests.get("memory")

    field = f"involvedObject.name={evidence['pod']}"
    try:
        evs = api.list_namespaced_event(NAMESPACE, field_selector=field)
        for item in (evs.items or [])[-8:]:
            evidence["events"].append(
                {
                    "reason": item.reason,
                    "message": (item.message or "")[:240],
                    "type": item.type,
                    "count": item.count,
                }
            )
    except Exception:
        logger.exception("could not list events")

    try:
        logs = api.read_namespaced_pod_log(
            name=evidence["pod"],
            namespace=NAMESPACE,
            tail_lines=30,
            timestamps=False,
        )
        evidence["log_tail"] = (logs or "")[-1500:]
    except Exception:
        logger.info("could not read logs for %s (pod may be gone)", evidence["pod"])

    return evidence


def post_json(url: str, payload: dict[str, Any], timeout: int = 20) -> Optional[dict[str, Any]]:
    data = json.dumps(payload).encode()
    req = Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
        return json.loads(raw) if raw else {}
    except Exception:
        logger.exception("LLM HTTP call failed")
        return None
