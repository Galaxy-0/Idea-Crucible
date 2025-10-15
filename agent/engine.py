from __future__ import annotations

import glob
import os
from typing import List, Any, cast

import yaml

from .schemas import Rule, Idea, Verdict
from .llm import load_model_config, llm_verdict_json


def load_rules(rules_dir: str) -> List[Rule]:
    rules: List[Rule] = []
    for path in sorted(glob.glob(os.path.join(rules_dir, "*.yaml"))):
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            rules.append(Rule(**data))
    return rules


def arbitrate_llm(
    idea: Idea, rules: List[Rule], model_cfg_path: str, mode: str = "llm-only"
) -> Verdict:
    # Prepare plain dicts for LLM
    idea_d = {
        "intent": idea.intent,
        "user": idea.user,
        "scenario": idea.scenario,
        "triggers": idea.triggers,
        "alts": idea.alts,
        "assumptions": list(idea.assumptions or []),
        "risks": list(idea.risks or []),
    }
    rules_d = [
        {
            "id": r.id,
            "scope": r.scope,
            "category": r.category,
            "condition": r.condition,
            "severity": r.severity,
            "decision": r.decision,
            "rationale": r.rationale,
            "keywords": r.keywords or [],
            "next_steps": r.next_steps or [],
        }
        for r in rules
    ]

    cfg = load_model_config(model_cfg_path)
    allowed_ids: List[str] = [str(r.get("id")) for r in rules_d if r.get("id")]
    data = llm_verdict_json(idea_d, rules_d, cfg, allowed_redline_ids=allowed_ids)

    # Parse and coerce
    decision = str(data.get("decision", "caution")).lower()
    if decision not in {"deny", "caution", "go"}:
        decision = "caution"
    # confidence: normalize to [0,1] with two decimals
    try:
        conf_raw = float(data.get("conf_level", 0.6))
    except Exception:
        conf_raw = 0.6
    conf = max(0.0, min(1.0, conf_raw))
    conf = float(f"{conf:.2f}")

    reasons = [str(x) for x in (data.get("reasons") or [])]
    # Optional reasons_map: [{rule_id, reason}] to strengthen mapping
    reasons_map = data.get("reasons_map") or []
    if isinstance(reasons_map, list) and not reasons:
        try:
            reasons = [
                str(item.get("reason"))
                for item in reasons_map
                if isinstance(item, dict) and item.get("reason")
            ]
        except Exception:
            pass

    redlines = [str(x) for x in (data.get("redlines") or [])]
    # If redlines empty but reasons_map present, derive from it
    if not redlines and isinstance(reasons_map, list):
        try:
            redlines = [
                str(item.get("rule_id"))
                for item in reasons_map
                if isinstance(item, dict) and item.get("rule_id")
            ]
        except Exception:
            pass

    # Align redlines with known rule IDs; if invalids exist, one-shot retry
    allowed_set = set(allowed_ids)
    invalid = [rl for rl in redlines if rl not in allowed_set]
    if invalid:
        note = (
            "Some redline IDs were invalid: "
            + ", ".join(sorted(set(invalid)))
            + ". Only use IDs from the allowed list and update reasons_map accordingly."
        )
        data = llm_verdict_json(
            idea_d, rules_d, cfg, allowed_redline_ids=allowed_ids, correction_note=note
        )
        # Re-parse with the same normalization
        decision = str(data.get("decision", decision)).lower()
        if decision not in {"deny", "caution", "go"}:
            decision = "caution"
        try:
            conf_raw = float(data.get("conf_level", conf))
        except Exception:
            conf_raw = conf
        conf = max(0.0, min(1.0, conf_raw))
        conf = float(f"{conf:.2f}")
        reasons = [str(x) for x in (data.get("reasons") or reasons)]
        reasons_map = data.get("reasons_map") or reasons_map
        redlines = [str(x) for x in (data.get("redlines") or [])]
        if not redlines and isinstance(reasons_map, list):
            try:
                redlines = [
                    str(item.get("rule_id"))
                    for item in reasons_map
                    if isinstance(item, dict) and item.get("rule_id")
                ]
            except Exception:
                pass

    redlines = [rl for rl in redlines if rl in allowed_set]
    next_steps = [str(x) for x in (data.get("next_steps") or [])]

    return Verdict(
        decision=decision,
        reasons=reasons,
        conf_level=conf,
        redlines=redlines,
        next_steps=next_steps,
    )
