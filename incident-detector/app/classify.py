from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Finding:
    service: str
    problem: str
    pod: str
    message: str


def _label(pod: dict, key: str, default: str = "unknown") -> str:
    meta = pod.get("metadata") or {}
    labels = meta.get("labels") or {}
    return labels.get(key) or labels.get("app.kubernetes.io/component") or default


def classify_pod(pod: dict) -> Optional[Finding]:
    meta = pod.get("metadata") or {}
    if meta.get("deletionTimestamp"):
        return None
    name = meta.get("name") or "unknown"
    service = _label(pod, "app.kubernetes.io/component", "unknown")
    if service in ("unknown", "incident-detector", "ai-analyzer"):
        return None
    status = pod.get("status") or {}
    phase = status.get("phase") or ""
    statuses = status.get("containerStatuses") or []
    waiting_reason = None
    terminated_reason = None
    ready = True
    restart_count = 0
    for cs in statuses:
        ready = ready and bool(cs.get("ready"))
        restart_count += int(cs.get("restartCount") or 0)
        state = cs.get("state") or {}
        waiting = state.get("waiting") or {}
        if waiting.get("reason"):
            waiting_reason = waiting["reason"]
        last = cs.get("lastState") or {}
        term = last.get("terminated") or {}
        if term.get("reason"):
            terminated_reason = term["reason"]
        cur_term = (state.get("terminated") or {}).get("reason")
        if cur_term:
            terminated_reason = cur_term
    if waiting_reason in ("ImagePullBackOff", "ErrImagePull"):
        return Finding(service=service, problem="ImagePullBackOff", pod=name, message=f"kubelet cannot pull the image ({waiting_reason})")
    if terminated_reason == "OOMKilled":
        return Finding(service=service, problem="OOMKilled", pod=name, message="container exceeded memory limit and was killed by the kernel")
    crashish = waiting_reason == "CrashLoopBackOff" or (
        terminated_reason in ("Error", "ContainerCannotRun") and restart_count >= 1
    )
    if crashish:
        return Finding(service=service, problem="CrashLoopBackOff", pod=name, message="container keeps exiting and Kubernetes is restarting it (crash / CrashLoopBackOff)")
    if phase == "Running" and statuses and not ready:
        return Finding(service=service, problem="NotReady", pod=name, message="pod is Running but not Ready (readiness probe failing or container not ready)")
    return None


def fingerprint(finding: Finding) -> str:
    return f"{finding.service}:{finding.problem}"
