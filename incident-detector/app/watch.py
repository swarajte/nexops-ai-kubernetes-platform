from __future__ import annotations

import json
import logging
import os
import time
from typing import Callable, Optional
from urllib.error import URLError, HTTPError
from urllib.request import urlopen

from kubernetes import client, config

from app.app_signals import classify_fail_status
from app.classify import Finding, classify_pod, fingerprint
from app.store import IncidentStore

logger = logging.getLogger("incident-detector")

PAYMENT_FAIL_STATUS_URL = os.getenv(
    "PAYMENT_FAIL_STATUS_URL", "http://payment-api:8000/fail/status"
)


def load_kube() -> client.CoreV1Api:
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()
    return client.CoreV1Api()


def poll_once(api: client.CoreV1Api, store: IncidentStore, namespace: str) -> list[Finding]:
    pods = api.list_namespaced_pod(namespace)
    findings: list[Finding] = []
    fps: set[str] = set()
    for pod in pods.items:
        raw = api.api_client.sanitize_for_serialization(pod)
        found = classify_pod(raw)
        if not found:
            continue
        findings.append(found)
        fps.add(fingerprint(found))
        store.upsert_open(
            found,
            namespace=namespace,
            evidence={
                "phase": (pod.status.phase if pod.status else None),
                "pod": found.pod,
                "problem": found.problem,
            },
        )
    app_finding = _poll_payment_fail_status(_payment_pod_name(pods.items))
    if app_finding:
        findings.append(app_finding)
        fps.add(fingerprint(app_finding))
        store.upsert_open(
            app_finding,
            namespace=namespace,
            evidence={"source": "fail_status", "problem": app_finding.problem},
        )
    resolved = store.resolve_missing(fps)
    if resolved:
        logger.info("resolved %s incident(s) that are no longer visible", resolved)
    return findings


def run_loop(
    store: IncidentStore,
    namespace: str,
    interval: float,
    stop: Callable[[], bool],
    api_factory: Callable[[], client.CoreV1Api] = load_kube,
) -> None:
    api = None
    while not stop():
        try:
            if api is None:
                api = api_factory()
            poll_once(api, store, namespace)
        except Exception:
            logger.exception("watch poll failed")
            api = None
        deadline = time.time() + interval
        while not stop() and time.time() < deadline:
            time.sleep(0.25)


def _payment_pod_name(items) -> str:
    for pod in items:
        labels = (pod.metadata.labels or {}) if pod.metadata else {}
        if labels.get("app.kubernetes.io/component") == "payment-api":
            return pod.metadata.name
    return "payment-api"


def _poll_payment_fail_status(pod_name: str) -> Optional[Finding]:
    if not PAYMENT_FAIL_STATUS_URL:
        return None
    try:
        with urlopen(PAYMENT_FAIL_STATUS_URL, timeout=3) as resp:
            payload = json.loads(resp.read().decode())
    except (URLError, HTTPError, TimeoutError, json.JSONDecodeError, OSError):
        logger.info("payment-api /fail/status not reachable (pod may be crashing)")
        return None
    return classify_fail_status(payload, pod=pod_name)
