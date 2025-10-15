from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Any

import yaml

from agent.schemas import Idea
from agent.engine import load_rules, arbitrate_llm


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RULES_DIR = ROOT / "config" / "rules" / "core"
DEFAULT_MODEL_CFG = ROOT / "config" / "model.local.yaml"
REPORTS_DIR = ROOT / "reports"


def evaluate_one(idea_path: Path, rules_dir: Path, model_cfg: Path) -> Path:
    with open(idea_path, "r", encoding="utf-8") as f:
        idea = Idea(**(yaml.safe_load(f) or {}))
    rules = load_rules(str(rules_dir))
    verdict = arbitrate_llm(idea, rules, str(model_cfg))
    slug = idea_path.stem
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_json = REPORTS_DIR / f"{slug}.verdict.json"
    with open(out_json, "w", encoding="utf-8") as f:
        payload = (
            verdict.model_dump() if hasattr(verdict, "model_dump") else verdict.__dict__
        )
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return out_json


def collect_stats(verdict_paths: List[Path]) -> Dict[str, Any]:
    decisions: Dict[str, int] = {}
    redline_counts: Dict[str, int] = {}
    total = 0
    for p in verdict_paths:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        total += 1
        d = str(data.get("decision", "caution")).lower()
        decisions[d] = decisions.get(d, 0) + 1
        for rl in data.get("redlines", []) or []:
            redline_counts[rl] = redline_counts.get(rl, 0) + 1

    decision_pct = {k: (v / total if total else 0.0) for k, v in decisions.items()}
    redline_hit_rate = {
        k: (v / total if total else 0.0) for k, v in redline_counts.items()
    }

    # Top-1 / Top-3 by hit-rate
    sorted_rl = sorted(redline_hit_rate.items(), key=lambda x: x[1], reverse=True)
    top1 = sorted_rl[:1]
    top3 = sorted_rl[:3]

    return {
        "decision_counts": decisions,
        "decision_pct": {k: float(f"{v:.4f}") for k, v in decision_pct.items()},
        "redline_counts": redline_counts,
        "redline_hit_rate": {k: float(f"{v:.4f}") for k, v in redline_hit_rate.items()},
        "top1": {k: v for k, v in top1},
        "top3": {k: v for k, v in top3},
        "total": total,
    }


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Batch evaluate ideas and compute simple stats."
    )
    ap.add_argument("--ideas-dir", type=str, default=str(ROOT / "ideas"))
    ap.add_argument("--rules-dir", type=str, default=str(DEFAULT_RULES_DIR))
    ap.add_argument("--model-cfg", type=str, default=str(DEFAULT_MODEL_CFG))
    ap.add_argument(
        "--pattern", type=str, default="*.yaml", help="Glob pattern under ideas-dir"
    )
    ap.add_argument(
        "--stats",
        action="store_true",
        help="Compute and write stats JSON to reports/_stats.json",
    )
    args = ap.parse_args()

    ideas_dir = Path(args.ideas_dir)
    idea_files = sorted(ideas_dir.glob(args.pattern))
    if not idea_files:
        print(f"No ideas matched under {ideas_dir} with pattern {args.pattern}")
        return

    out_paths: List[Path] = []
    for i, idea_path in enumerate(idea_files, start=1):
        out = evaluate_one(idea_path, Path(args.rules_dir), Path(args.model_cfg))
        print(f"[{i}/{len(idea_files)}] -> {out}")
        out_paths.append(out)

    if args.stats:
        stats = collect_stats(out_paths)
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        stats_path = REPORTS_DIR / "_stats.json"
        stats_path.write_text(
            json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"Stats written -> {stats_path}")


if __name__ == "__main__":
    main()
