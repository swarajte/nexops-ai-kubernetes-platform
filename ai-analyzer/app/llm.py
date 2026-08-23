from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger("ai-analyzer")

LLM_URL = os.getenv("LLM_URL", "").strip()
LLM_API_KEY = os.getenv("LLM_API_KEY", "").strip()
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini").strip()


def maybe_refine_with_llm(rules_result: dict[str, Any], incident: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    """If LLM_URL + LLM_API_KEY are set, ask the model to fill the same JSON shape.

    On any failure, return the rule-engine result unchanged.
    Never send secrets. Never ask the model to run commands.
    """
    if not LLM_URL or not LLM_API_KEY:
        return rules_result

    prompt = {
        "model": LLM_MODEL,
        "temperature": 0.1,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You analyze Kubernetes incidents. Reply with JSON only, keys: "
                    "problem, evidence (array of strings), likely_cause, suggested_fix, "
                    "suggested_action (object with type and target), confidence (0-100 integer). "
                    "Do not invent kubectl commands. Do not claim you applied a fix."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {"incident": incident, "evidence": evidence, "rules_draft": rules_result},
                    default=str,
                )[:12000],
            },
        ],
    }
    headers_url = LLM_URL
    import urllib.request

    data = json.dumps(prompt).encode()
    req = urllib.request.Request(
        headers_url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {LLM_API_KEY}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            raw = json.loads(resp.read().decode())
        text = raw["choices"][0]["message"]["content"]
        parsed = json.loads(text)
        parsed["source"] = "llm"
        parsed.setdefault("suggested_action", rules_result.get("suggested_action"))
        parsed.setdefault("evidence", rules_result.get("evidence"))
        return parsed
    except Exception:
        logger.exception("LLM refine failed; using rules")
        return rules_result
