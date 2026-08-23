from __future__ import annotations

from typing import Any


def _events_text(evidence: dict[str, Any]) -> str:
    parts = []
    for ev in evidence.get("events") or []:
        parts.append(f"{ev.get('reason')}: {ev.get('message')}")
    return " ".join(parts).lower()


def analyze(incident: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    """Turn an incident + gathered cluster facts into a Stage 7 record.

    This is a rule engine (deterministic). It never runs kubectl write
    commands and never gets a shell. Optional LLM can wrap this later.
    """
    service = incident.get("service") or "unknown"
    problem = (incident.get("problem") or "").strip()
    pod = incident.get("pod") or evidence.get("pod") or "unknown"
    mem_limit = evidence.get("memory_limit") or "128Mi"
    mem_request = evidence.get("memory_request") or "64Mi"
    restarts = int(evidence.get("restart_count") or 0)
    events = _events_text(evidence)
    terminated = (evidence.get("last_terminated_reason") or "").lower()
    oomish = problem == "OOMKilled" or terminated == "oomkilled" or "oomkilled" in events

    if oomish or (problem == "NotReady" and (restarts > 0 or "oom" in events)):
        doubled = _double_mi(mem_limit)
        return {
            "problem": f"{service} is running out of memory.",
            "evidence": _unique(
                [
                    "OOMKilled" if oomish or terminated == "oomkilled" else "pod NotReady while memory-constrained",
                    f"memory limit is {mem_limit}",
                    f"restart_count={restarts}" if restarts else "container restarting or unready",
                    f"pod={pod}",
                ]
            ),
            "likely_cause": "memory limit is too low for the workload (or a leak / injected OOM demo).",
            "suggested_fix": f"increase memory limit from {mem_limit} to {doubled}",
            "suggested_action": {
                "type": "increase_memory",
                "target": service,
                "from": mem_limit,
                "to": doubled,
            },
            "confidence": 88 if oomish else 72,
            "source": "rules",
        }

    if problem == "CrashLoopBackOff":
        return {
            "problem": f"{service} is crash-looping (process exits and Kubernetes restarts it).",
            "evidence": _unique(
                [
                    "CrashLoopBackOff",
                    f"restart_count={restarts}",
                    f"pod={pod}",
                    f"last_terminated_reason={evidence.get('last_terminated_reason') or 'unknown'}",
                ]
            ),
            "likely_cause": "the process exits on start (bad config, crash failure mode, or fatal exception).",
            "suggested_fix": "inspect logs, then restart the deployment after fixing the cause; do not keep raising memory if it is not OOM.",
            "suggested_action": {
                "type": "restart_deployment",
                "target": service,
            },
            "confidence": 80,
            "source": "rules",
        }

    if problem == "ImagePullBackOff":
        return {
            "problem": f"{service} cannot pull its container image.",
            "evidence": _unique(
                [
                    "ImagePullBackOff",
                    f"pod={pod}",
                    "this is a Kubernetes/image problem, not application code",
                ]
            ),
            "likely_cause": "wrong image tag, missing image on the node, or registry/auth failure.",
            "suggested_fix": "set the image tag back to a tag that exists on the node (for this POC: import the image into containerd).",
            "suggested_action": {
                "type": "fix_image_tag",
                "target": service,
            },
            "confidence": 90,
            "source": "rules",
        }

    if problem == "NotReady":
        return {
            "problem": f"{service} is running but not Ready (readiness probe failing).",
            "evidence": _unique(
                [
                    "Ready=false",
                    f"pod={pod}",
                    f"memory_request={mem_request} memory_limit={mem_limit}",
                    "Buy Now can fail because the Service has no Ready endpoints",
                ]
            ),
            "likely_cause": "readiness probe (/ready) is failing — injected unready mode, slow start, or a dependency is down.",
            "suggested_fix": "check /ready vs /health; if this was a demo, helm upgrade --reset-values.",
            "suggested_action": {
                "type": "reset_failure_mode",
                "target": service,
            },
            "confidence": 70,
            "source": "rules",
        }

    return {
        "problem": f"{service} reported problem {problem or 'unknown'}.",
        "evidence": _unique([f"incident.problem={problem}", f"pod={pod}"]),
        "likely_cause": "not enough signal to pick a specific root cause.",
        "suggested_fix": "inspect pod describe, events, and logs; compare with Grafana/Loki.",
        "suggested_action": {"type": "investigate", "target": service},
        "confidence": 40,
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


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out
