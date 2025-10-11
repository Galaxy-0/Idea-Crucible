from __future__ import annotations

import glob
import os
from typing import List, Dict, Any

import yaml

from .schemas import Rule, Idea, Verdict
from .llm import load_model_config, llm_verdict_json


def load_rules(rules_dir: str) -> List[Rule]:
    rules: List[Rule] = []
    for path in sorted(glob.glob(os.path.join(rules_dir, "*.yaml"))):
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            try:
                rules.append(Rule(**data))
            except Exception:
                # Accept partially specified rules for scaffolding
                rules.append(Rule(**{**data}))  # may still raise if malformed
    return rules


def load_weights(weights_path: str) -> Dict[str, Any]:
    with open(weights_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _text_corpus(idea: Idea) -> str:
    parts = [
        idea.intent,
        idea.user,
        idea.scenario,
        idea.triggers,
        idea.alts,
        " ".join(idea.assumptions or []),
        " ".join(idea.risks or []),
    ]
    return (" \n".join([p for p in parts if p])).lower()


def rule_matches(rule: Rule, idea: Idea) -> bool:
    corpus = _text_corpus(idea)
    if rule.keywords:
        return any(kw.lower() in corpus for kw in rule.keywords)
    # Fallback: naive containment of condition terms
    tokens = [t.strip().lower() for t in rule.condition.replace("/", " ").split() if len(t) > 3]
    return any(t in corpus for t in tokens)


def arbitrate(idea: Idea, rules: List[Rule], weights: Dict[str, Any]) -> Verdict:
    triggered: List[Rule] = [r for r in rules if rule_matches(r, idea)]

    deny_hit = any((r.decision or "").lower() == "deny" for r in triggered)
    caution_hit = any((r.decision or "").lower() == "caution" for r in triggered)

    if deny_hit:
        decision = "deny"
    elif caution_hit:
        decision = "caution"
    else:
        decision = "go"

    # Confidence heuristic: more structure and more supporting rules => higher
    base = 0.55
    filled_fields = sum(1 for v in [idea.intent, idea.user, idea.scenario, idea.triggers, idea.alts] if v)
    completeness_bonus = min(0.15, filled_fields * 0.03)
    hit_bonus = min(0.15, len(triggered) * 0.04)
    conf = max(0.45, min(0.95, base + completeness_bonus + hit_bonus))

    reasons = [f"{r.id}: {r.rationale}" for r in triggered]
    redlines = [r.id for r in triggered]
    next_steps: List[str] = []
    for r in triggered:
        if r.next_steps:
            next_steps.extend(r.next_steps)

    return Verdict(decision=decision, reasons=reasons, conf_level=conf, redlines=redlines, next_steps=next_steps)


def arbitrate_llm(idea: Idea, rules: List[Rule], model_cfg_path: str, mode: str = "hybrid") -> Verdict:
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
    next_steps = [str(x) for x in (data.get("next_steps") or [])]

    return Verdict(decision=decision, reasons=reasons, conf_level=conf, redlines=redlines, next_steps=next_steps)
