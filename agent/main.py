from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import yaml

from .schemas import Idea
from .engine import load_rules, arbitrate_llm, arbitrate
from .claude_agent import evaluate_with_claude_agent


ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"
RULES_DIR = CONFIG_DIR / "rules" / "core"
MODEL_CFG_PATH = CONFIG_DIR / "model.yaml"
TEMPLATES_DIR = ROOT / "templates"
IDEAS_DIR = ROOT / "ideas"
REPORTS_DIR = ROOT / "reports"
BENCH_DIR = REPORTS_DIR / "benchmarks"


def ensure_dirs():
    IDEAS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    BENCH_DIR.mkdir(parents=True, exist_ok=True)


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
    mode = args.mode or "llm-only"

    if mode == "llm-only":
        model_cfg = str(Path(args.model_cfg or MODEL_CFG_PATH))
        verdict = arbitrate_llm(idea, rules, model_cfg, mode="llm-only")
    elif mode == "agent-claude":
        verdict = evaluate_with_claude_agent(idea, rules)
    else:
        raise SystemExit("Unsupported mode. Use llm-only or agent-claude.")

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


def cmd_benchmark(args: argparse.Namespace) -> None:
    ensure_dirs()
    data_path = Path(args.data)
    rules = load_rules(str(RULES_DIR))

    # metrics containers
    labels = ["deny", "caution", "go"]
    idx = {l: i for i, l in enumerate(labels)}
    cm = [[0 for _ in labels] for _ in labels]  # rows=gold, cols=pred
    per_item = []
    redline_sims: list[float] = []

    def evaluate_one(idea_path: Path) -> Any:
        with open(idea_path, "r", encoding="utf-8") as f:
            idea = Idea(**(yaml.safe_load(f) or {}))
        if args.mode == "rules":
            v = arbitrate(idea, rules, {})
        elif args.mode == "llm-only":
            model_cfg = str(Path(args.model_cfg or MODEL_CFG_PATH))
            v = arbitrate_llm(idea, rules, model_cfg, mode="llm-only")
        elif args.mode == "agent-claude":
            v = evaluate_with_claude_agent(idea, rules)
        else:
            raise SystemExit("Unsupported mode. Use rules, llm-only or agent-claude.")
        return v

    # read JSONL
    with open(data_path, "r", encoding="utf-8") as f:
        lines = [ln.strip() for ln in f if ln.strip()]

    for ln in lines:
        try:
            item = json.loads(ln)
        except Exception:
            continue
        iid = item.get("id") or "item"
        idea_path = ROOT / str(item.get("idea_path"))
        gold = str(item.get("gold_decision", "caution")).lower()
        gold_red = [str(x) for x in (item.get("gold_redlines") or [])]

        verdict = evaluate_one(idea_path)
        pred = verdict.decision
        pred_red = list(verdict.redlines or [])

        # confusion
        if gold in idx and pred in idx:
            cm[idx[gold]][idx[pred]] += 1

        # redline Jaccard if gold available
        jacc = None
        if gold_red is not None:
            s_gold, s_pred = set(gold_red), set(pred_red)
            if s_gold or s_pred:
                inter = len(s_gold & s_pred)
                union = len(s_gold | s_pred)
                jacc = inter / union if union else 1.0
                redline_sims.append(jacc)

        per_item.append({
            "id": iid,
            "idea_path": str(idea_path),
            "gold_decision": gold,
            "pred_decision": pred,
            "match": gold == pred,
            "gold_redlines": gold_red,
            "pred_redlines": pred_red,
            "redline_jaccard": jacc,
        })

    n = len(per_item)
    correct = sum(1 for it in per_item if it["match"]) if n else 0
    accuracy = correct / n if n else 0.0

    # per-class precision/recall/f1
    per_class = {}
    for l in labels:
        i = idx[l]
        tp = cm[i][i]
        fp = sum(cm[r][i] for r in range(len(labels)) if r != i)
        fn = sum(cm[i][c] for c in range(len(labels)) if c != i)
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) else 0.0
        per_class[l] = {"precision": round(prec, 4), "recall": round(rec, 4), "f1": round(f1, 4), "support": sum(cm[i])}

    redline_macro_j = sum(redline_sims) / len(redline_sims) if redline_sims else None

    slug = args.out or data_path.stem
    out_dir = BENCH_DIR / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "dataset": str(data_path),
        "mode": args.mode,
        "n_items": n,
        "accuracy": round(accuracy, 4),
        "per_class": per_class,
        "confusion_matrix": {labels[i]: {labels[j]: cm[i][j] for j in range(len(labels))} for i in range(len(labels))},
        "redline_macro_jaccard": round(redline_macro_j, 4) if redline_macro_j is not None else None,
    }

    with open(out_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    with open(out_dir / "details.jsonl", "w", encoding="utf-8") as f:
        for it in per_item:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")

    print(str(out_dir / "summary.json"))


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
    s = sub.add_parser("evaluate", help="Evaluate an idea against redline rules (LLM required)")
    s.add_argument("--idea", required=True, type=str, help="Path to idea YAML")
    s.add_argument("--mode", choices=["llm-only", "agent-claude"], default="llm-only", help="Evaluation mode")
    s.add_argument("--model-cfg", type=str, help="Path to LLM config (YAML)")
    s.set_defaults(func=cmd_evaluate)

    # report
    s = sub.add_parser("report", help="Render one-page verdict report")
    s.add_argument("--idea", required=True, type=str, help="Path to idea YAML")
    s.set_defaults(func=cmd_report)

    # benchmark
    s = sub.add_parser("benchmark", help="Run a triage benchmark dataset and aggregate metrics")
    s.add_argument("--data", required=True, type=str, help="Path to benchmark JSONL")
    s.add_argument("--mode", choices=["rules", "llm-only", "agent-claude"], default="rules", help="Evaluation backend")
    s.add_argument("--model-cfg", type=str, help="Path to LLM config (YAML)")
    s.add_argument("--out", type=str, help="Slug for output under reports/benchmarks/")
    s.set_defaults(func=cmd_benchmark)

    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
