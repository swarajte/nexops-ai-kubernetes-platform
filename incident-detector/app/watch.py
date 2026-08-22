from __future__ import annotations

import logging
import time
from typing import Callable

from kubernetes import client, config

from app.classify import Finding, classify_pod, fingerprint
from app.store import IncidentStore

logger = logging.getLogger("incident-detector")


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
