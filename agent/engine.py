from __future__ import annotations

import glob
import os
from typing import List

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


def arbitrate_llm(idea: Idea, rules: List[Rule], model_cfg_path: str, mode: str = "llm-only") -> Verdict:
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
    data = llm_verdict_json(idea_d, rules_d, cfg)

    # Parse and coerce
    decision = str(data.get("decision", "caution")).lower()
    if decision not in {"deny", "caution", "go"}:
        decision = "caution"
    conf = float(data.get("conf_level", 0.6) or 0.6)
    reasons = [str(x) for x in (data.get("reasons") or [])]
    redlines = [str(x) for x in (data.get("redlines") or [])]
    # Align redlines with known rule IDs
    allowed_ids = {r["id"] for r in rules_d if r.get("id")}
    redlines = [rl for rl in redlines if rl in allowed_ids]
    next_steps = [str(x) for x in (data.get("next_steps") or [])]

    return Verdict(decision=decision, reasons=reasons, conf_level=conf, redlines=redlines, next_steps=next_steps)
