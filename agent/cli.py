from __future__ import annotations

import sys
from pathlib import Path
import argparse
from types import SimpleNamespace

import yaml

from . import main as am


def _slugify(text: str) -> str:
    return "-".join([t for t in text.lower().strip().split()[:6]]) or "idea"


def intake_entry() -> None:
    if len(sys.argv) < 2:
        print("Usage: intake <short-description>")
        sys.exit(2)

    desc = " ".join(sys.argv[1:]).strip()
    am.ensure_dirs()
    slug = _slugify(desc)
    out_path = am.IDEAS_DIR / f"{slug}.yaml"

    idea = {
        "intent": desc,
        "user": "early adopters",
        "scenario": "initial use case",
        "triggers": "pain/need trigger",
        "alts": "status quo / competitors",
        "assumptions": [desc],
        "risks": [],
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        yaml.safe_dump(idea, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    print(str(out_path))


def evaluate_entry() -> None:
    if len(sys.argv) < 2:
        print("Usage: evaluate <idea.yaml>")
        sys.exit(2)
    idea = Path(sys.argv[1])
    # model config is auto-resolved in agent.main (model.local.yaml > model.yaml)
    args = argparse.Namespace(idea=str(idea), model_cfg=None)
    am.cmd_evaluate(args)


def report_entry() -> None:
    if len(sys.argv) < 2:
        print("Usage: report <idea.yaml>")
        sys.exit(2)
    idea = Path(sys.argv[1])
    args = argparse.Namespace(idea=str(idea))
    am.cmd_report(args)
