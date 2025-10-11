from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import yaml

from .schemas import Idea
from .engine import load_rules, load_weights, arbitrate, arbitrate_llm
from .claude_agent import evaluate_with_claude_agent


ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"
RULES_DIR = CONFIG_DIR / "rules" / "core"
WEIGHTS_PATH = CONFIG_DIR / "weights.yaml"
MODEL_CFG_PATH = CONFIG_DIR / "model.yaml"
TEMPLATES_DIR = ROOT / "templates"
IDEAS_DIR = ROOT / "ideas"
REPORTS_DIR = ROOT / "reports"


def ensure_dirs():
    IDEAS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def slugify(text: str) -> str:
    return "-".join([t for t in text.lower().strip().split()[:6]]) or "idea"


def cmd_intake(args: argparse.Namespace) -> None:
    ensure_dirs()
    if args.input and os.path.exists(args.input):
        with open(args.input, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        idea = Idea(**data)
        slug = args.out or slugify(idea.intent)
    else:
        desc = args.desc or "Untitled idea"
        slug = args.out or slugify(desc)
        idea = Idea(
            intent=desc,
            user=args.user or "early adopters",
            scenario=args.scenario or "initial use case",
            triggers=args.triggers or "pain/need trigger",
            alts=args.alts or "status quo / competitors",
            assumptions=args.assumptions or [desc],
            risks=args.risks or [],
        )

    out_path = IDEAS_DIR / (slug if slug.endswith(".yaml") else f"{slug}.yaml")
    with open(out_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(json.loads(json.dumps(idea, default=lambda o: o.__dict__)), f, allow_unicode=True, sort_keys=False)
    print(str(out_path))


def cmd_evaluate(args: argparse.Namespace) -> None:
    ensure_dirs()
    with open(args.idea, "r", encoding="utf-8") as f:
        idea = Idea(**(yaml.safe_load(f) or {}))

    rules = load_rules(str(RULES_DIR))
    mode = args.mode or "logic-only"

    if mode == "logic-only":
        weights = load_weights(str(WEIGHTS_PATH)) if WEIGHTS_PATH.exists() else {}
        verdict = arbitrate(idea, rules, weights)
    elif mode == "llm-only":
        model_cfg = str(Path(args.model_cfg or MODEL_CFG_PATH))
        verdict = arbitrate_llm(idea, rules, model_cfg, mode="llm-only")
    elif mode == "agent-claude":
        verdict = evaluate_with_claude_agent(idea, rules)
    else:  # hybrid
        weights = load_weights(str(WEIGHTS_PATH)) if WEIGHTS_PATH.exists() else {}
        base = arbitrate(idea, rules, weights)
        model_cfg = str(Path(args.model_cfg or MODEL_CFG_PATH))
        llm_v = arbitrate_llm(idea, rules, model_cfg, mode="hybrid")
        # Conservative merge: take the "worst" decision order deny > caution > go
        order = {"deny": 2, "caution": 1, "go": 0}
        merged_decision = base.decision if order.get(base.decision, 0) >= order.get(llm_v.decision, 0) else llm_v.decision
        reasons = (base.reasons or []) + (llm_v.reasons or [])
        redlines = list(dict.fromkeys((base.redlines or []) + (llm_v.redlines or [])))
        next_steps = llm_v.next_steps or base.next_steps or []
        conf = max(base.conf_level, llm_v.conf_level)
        verdict = type(base)(decision=merged_decision, reasons=reasons, conf_level=conf, redlines=redlines, next_steps=next_steps)

    slug = slugify(Path(args.idea).stem)
    out_json = REPORTS_DIR / f"{slug}.verdict.json"
    with open(out_json, "w", encoding="utf-8") as f:
        # Support Pydantic v2 and fallback
        if hasattr(verdict, "model_dump_json"):
            payload = json.loads(verdict.model_dump_json())
        else:
            payload = verdict.__dict__
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(str(out_json))


def render_report(idea_path: Path, verdict_path: Path, template_path: Path, out_path: Path) -> None:
    with open(idea_path, "r", encoding="utf-8") as f:
        idea_data = yaml.safe_load(f) or {}
    with open(verdict_path, "r", encoding="utf-8") as f:
        verdict = json.load(f)
    with open(template_path, "r", encoding="utf-8") as f:
        tmpl = f.read()

    ctx: dict[str, Any] = {
        "intent": idea_data.get("intent", ""),
        "user": idea_data.get("user", ""),
        "scenario": idea_data.get("scenario", ""),
        "triggers": idea_data.get("triggers", ""),
        "alts": idea_data.get("alts", ""),
        "assumptions": "\n- " + "\n- ".join(idea_data.get("assumptions", []) or []),
        "risks": "\n- " + "\n- ".join(idea_data.get("risks", []) or []),
        "decision": verdict.get("decision", ""),
        "conf_level": f"{verdict.get('conf_level', 0):.2f}",
        "reasons": "\n- " + "\n- ".join(verdict.get("reasons", []) or []),
        "redlines": "\n- " + "\n- ".join(verdict.get("redlines", []) or []),
        "next_steps": "\n- " + "\n- ".join(verdict.get("next_steps", []) or []),
    }

    content = tmpl.format(**ctx)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)


def cmd_report(args: argparse.Namespace) -> None:
    ensure_dirs()
    idea_path = Path(args.idea)
    slug = slugify(idea_path.stem)
    verdict_path = REPORTS_DIR / f"{slug}.verdict.json"
    template_path = TEMPLATES_DIR / "report.md"
    out_path = REPORTS_DIR / f"{slug}.md"
    render_report(idea_path, verdict_path, template_path, out_path)
    print(str(out_path))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="idea-crucible", description="Redline-first idea evaluation CLI")
    sub = p.add_subparsers(dest="command", required=True)

    # intake
    s = sub.add_parser("intake", help="Normalize an idea YAML from description or file")
    s.add_argument("--desc", type=str, help="Short description of the idea")
    s.add_argument("--input", type=str, help="Existing idea YAML to normalize")
    s.add_argument("--user", type=str)
    s.add_argument("--scenario", type=str)
    s.add_argument("--triggers", type=str)
    s.add_argument("--alts", type=str)
    s.add_argument("--assumptions", nargs="*", default=[])
    s.add_argument("--risks", nargs="*", default=[])
    s.add_argument("--out", type=str, help="Output path under ideas/")
    s.set_defaults(func=cmd_intake)

    # evaluate
    s = sub.add_parser("evaluate", help="Evaluate an idea against redline rules")
    s.add_argument("--idea", required=True, type=str, help="Path to idea YAML")
    s.add_argument("--mode", choices=["logic-only", "hybrid", "llm-only", "agent-claude"], default="logic-only", help="Evaluation mode")
    s.add_argument("--model-cfg", type=str, help="Path to LLM config (YAML)")
    s.set_defaults(func=cmd_evaluate)

    # report
    s = sub.add_parser("report", help="Render one-page verdict report")
    s.add_argument("--idea", required=True, type=str, help="Path to idea YAML")
    s.set_defaults(func=cmd_report)

    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
