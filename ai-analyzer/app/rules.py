from __future__ import annotations

from typing import Any

ACTIONS = {
    "OOMKilled": "increase_memory",
    "CrashLoopBackOff": "restart_deployment",
    "ImagePullBackOff": "fix_image_tag",
    "NotReady": "reset_failure_mode",
    "HighErrorRate": "reset_failure_mode",
    "SlowRequests": "reset_failure_mode",
    "HighCpu": "reset_failure_mode",
    "HighMemory": "reset_failure_mode",
}


def _events_text(evidence: dict[str, Any]) -> str:
    parts = []
    for ev in evidence.get("events") or []:
        parts.append(f"{ev.get('reason')}: {ev.get('message')}")
    return " ".join(parts).lower()


def analyze(incident: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    service = incident.get("service") or "unknown"
    problem = (incident.get("problem") or "").strip()
    pod = incident.get("pod") or evidence.get("pod") or "unknown"
    mem_limit = evidence.get("memory_limit") or "128Mi"
    mem_request = evidence.get("memory_request") or "64Mi"
    restarts = int(evidence.get("restart_count") or 0)
    events = _events_text(evidence)
    terminated = (evidence.get("last_terminated_reason") or "").lower()
    oomish = problem == "OOMKilled" or terminated == "oomkilled" or "oomkilled" in events

    if oomish:
        doubled = _double_mi(mem_limit)
        return _result(
            problem=f"{service} is running out of memory.",
            evidence=["OOMKilled", f"memory limit is {mem_limit}", f"restart_count={restarts}" if restarts else "container killed", f"pod={pod}"],
            likely_cause="memory limit is too low for the workload (or a leak / injected OOM demo).",
            suggested_fix=f"increase memory limit from {mem_limit} to {doubled}",
            suggested_action={"type": ACTIONS["OOMKilled"], "target": service, "from": mem_limit, "to": doubled},
            confidence=88,
        )
    if problem == "CrashLoopBackOff":
        return _result(
            problem=f"{service} is crash-looping (process exits and Kubernetes restarts it).",
            evidence=["CrashLoopBackOff", f"restart_count={restarts}", f"pod={pod}", f"last_terminated_reason={evidence.get('last_terminated_reason') or 'unknown'}"],
            likely_cause="the process exits on start (bad config, crash failure mode, or fatal exception).",
            suggested_fix="inspect logs, then reset FAILURE_MODE / restart after the cause is fixed; do not raise memory unless this is OOMKilled.",
            suggested_action={"type": ACTIONS["CrashLoopBackOff"], "target": service},
            confidence=80,
        )
    if problem == "ImagePullBackOff":
        return _result(
            problem=f"{service} cannot pull its container image.",
            evidence=["ImagePullBackOff", f"pod={pod}", "this is a Kubernetes/image problem, not application code"],
            likely_cause="wrong image tag, missing image on the node, or registry/auth failure.",
            suggested_fix="set the image tag back to a tag that exists on the node (for this POC: import the image into containerd).",
            suggested_action={"type": ACTIONS["ImagePullBackOff"], "target": service},
            confidence=90,
        )
    if problem == "NotReady":
        return _result(
            problem=f"{service} is running but not Ready (readiness probe failing).",
            evidence=["Ready=false", f"pod={pod}", f"memory_request={mem_request} memory_limit={mem_limit}", "Buy Now can fail because the Service has no Ready endpoints"],
            likely_cause="readiness probe (/ready) is failing — injected unready mode, slow start, or a dependency is down.",
            suggested_fix="check /ready vs /health; if this was a demo, helm upgrade --reset-values.",
            suggested_action={"type": ACTIONS["NotReady"], "target": service},
            confidence=70,
        )
    if problem == "HighErrorRate":
        return _result(
            problem=f"{service} is injecting HTTP errors on /pay (pod may still be Ready).",
            evidence=["HighErrorRate", "failure_mode=errors", f"pod={pod}"],
            likely_cause="FAILURE_MODE=errors (or POST /fail/errors) is failing payments on purpose.",
            suggested_fix="helm upgrade --reset-values or POST /fail/reset",
            suggested_action={"type": ACTIONS["HighErrorRate"], "target": service},
            confidence=85,
        )
    if problem == "SlowRequests":
        return _result(
            problem=f"{service} is delaying /pay (pod may still be Ready).",
            evidence=["SlowRequests", "failure_mode=slow", f"pod={pod}"],
            likely_cause="FAILURE_MODE=slow injects sleep on /pay.",
            suggested_fix="helm upgrade --reset-values or POST /fail/reset",
            suggested_action={"type": ACTIONS["SlowRequests"], "target": service},
            confidence=85,
        )
    if problem == "HighCpu":
        return _result(
            problem=f"{service} is burning CPU on purpose (pod may still be Ready).",
            evidence=["HighCpu", "failure_mode=cpu", f"pod={pod}"],
            likely_cause="FAILURE_MODE=cpu starts a busy-loop thread.",
            suggested_fix="helm upgrade --reset-values or POST /fail/reset",
            suggested_action={"type": ACTIONS["HighCpu"], "target": service},
            confidence=85,
        )
    if problem == "HighMemory":
        return _result(
            problem=f"{service} allocated extra heap on purpose (pod may still be Ready).",
            evidence=["HighMemory", "failure_mode=memory", f"pod={pod}"],
            likely_cause="FAILURE_MODE=memory holds extra RAM but may stay under the limit (not OOMKilled).",
            suggested_fix="helm upgrade --reset-values or POST /fail/reset; only raise the limit if this is a real OOMKilled.",
            suggested_action={"type": ACTIONS["HighMemory"], "target": service},
            confidence=80,
        )
    return _result(
        problem=f"{service} reported problem {problem or 'unknown'}.",
        evidence=[f"incident.problem={problem}", f"pod={pod}"],
        likely_cause="not enough signal to pick a specific root cause.",
        suggested_fix="inspect pod describe, events, and logs; compare with Grafana/Loki.",
        suggested_action={"type": "investigate", "target": service},
        confidence=40,
    )


def _result(*, problem, evidence, likely_cause, suggested_fix, suggested_action, confidence):
    return {
        "problem": problem,
        "evidence": _unique(evidence),
        "likely_cause": likely_cause,
        "suggested_fix": suggested_fix,
        "suggested_action": suggested_action,
        "confidence": confidence,
        "source": "rules",
    }


def _double_mi(limit: str) -> str:
    text = (limit or "128Mi").strip()
    if text.lower().endswith("mi"):
        try:
            return f"{int(text[:-2]) * 2}Mi"
        except ValueError:
            return "256Mi"
    return "256Mi"


def _unique(items):
    seen = set()
    out = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out
