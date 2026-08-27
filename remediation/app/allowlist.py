from __future__ import annotations

import re
from typing import Any

ALLOWED_ACTIONS = frozenset(
    {"increase_memory", "restart_deployment", "fix_image_tag", "reset_failure_mode"}
)
PROBLEM_ACTION = {
    "OOMKilled": "increase_memory",
    "CrashLoopBackOff": "restart_deployment",
    "ImagePullBackOff": "fix_image_tag",
    "NotReady": "reset_failure_mode",
    "HighCpu": "reset_failure_mode",
    "HighMemory": "reset_failure_mode",
    "SlowRequests": "reset_failure_mode",
    "HighErrorRate": "reset_failure_mode",
}
_MEMORY = re.compile(r"^([1-9][0-9]*)Mi$")


class UnsafeAction(ValueError):
    pass


def validate(
    incident: dict[str, Any],
    analysis: dict[str, Any],
    *,
    allowed_targets: set[str],
    max_memory_mi: int,
) -> dict[str, Any]:
    if incident.get("status") != "OPEN":
        raise UnsafeAction("incident is no longer OPEN")
    if analysis.get("incident_id") != incident.get("id"):
        raise UnsafeAction("analysis does not belong to this incident")
    if analysis.get("incident_problem") != incident.get("problem"):
        raise UnsafeAction("analysis problem is stale")

    action = dict(analysis.get("suggested_action") or {})
    action_type = action.get("type")
    target = action.get("target")
    if action_type not in ALLOWED_ACTIONS:
        raise UnsafeAction(f"action {action_type!r} is not allowlisted")
    if target not in allowed_targets:
        raise UnsafeAction(f"target {target!r} is not allowlisted")
    expected = PROBLEM_ACTION.get(str(incident.get("problem")))
    if expected != action_type:
        raise UnsafeAction(
            f"{incident.get('problem')} requires {expected}, not {action_type}"
        )

    if action_type == "increase_memory":
        match = _MEMORY.fullmatch(str(action.get("to") or ""))
        if not match:
            raise UnsafeAction("memory target must be a positive Mi value")
        target_mi = int(match.group(1))
        if target_mi > max_memory_mi:
            raise UnsafeAction(f"memory target exceeds {max_memory_mi}Mi safety cap")

    return action
