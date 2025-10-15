from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import yaml

from .schemas import Idea
from .engine import load_rules, arbitrate_llm


ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"
RULES_DIR = CONFIG_DIR / "rules" / "core"
MODEL_CFG_PATH = CONFIG_DIR / "model.yaml"
MODEL_LOCAL_CFG_PATH = CONFIG_DIR / "model.local.yaml"
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
        yaml.safe_dump(
            json.loads(json.dumps(idea, default=lambda o: o.__dict__)),
            f,
            allow_unicode=True,
            sort_keys=False,
        )
    print(str(out_path))


def cmd_evaluate(args: argparse.Namespace) -> None:
    ensure_dirs()
    # Optional language override
    if getattr(args, "lang", None):
        os.environ["IC_LANG"] = args.lang
    with open(args.idea, "r", encoding="utf-8") as f:
        idea = Idea(**(yaml.safe_load(f) or {}))

    rules = load_rules(str(RULES_DIR))
    # Resolve model config: prefer local override, then default
    chosen_cfg = None
    if getattr(args, "model_cfg", None):
        chosen_cfg = Path(args.model_cfg)
    else:
        chosen_cfg = (
            MODEL_LOCAL_CFG_PATH if MODEL_LOCAL_CFG_PATH.exists() else MODEL_CFG_PATH
        )
    model_cfg = str(Path(chosen_cfg))
    verdict = arbitrate_llm(idea, rules, model_cfg, mode="llm-only")

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


def render_report(
    idea_path: Path, verdict_path: Path, template_path: Path, out_path: Path
) -> None:
    with open(idea_path, "r", encoding="utf-8") as f:
        idea_data = yaml.safe_load(f) or {}
    with open(verdict_path, "r", encoding="utf-8") as f:
        verdict = json.load(f)
    with open(template_path, "r", encoding="utf-8") as f:
        tmpl = f.read()

    def bullets(items: list[str]) -> str:
        return ("\n- " + "\n- ".join(items)) if items else "暂无"

    ctx: dict[str, Any] = {
        "intent": idea_data.get("intent", ""),
        "user": idea_data.get("user", ""),
        "scenario": idea_data.get("scenario", ""),
        "triggers": idea_data.get("triggers", ""),
        "alts": idea_data.get("alts", ""),
        "assumptions": bullets(idea_data.get("assumptions", []) or []),
        "risks": bullets(idea_data.get("risks", []) or []),
        "decision": verdict.get("decision", ""),
        "conf_level": f"{verdict.get('conf_level', 0):.2f}",
        "reasons": bullets(verdict.get("reasons", []) or []),
        "redlines": bullets(verdict.get("redlines", []) or []),
        "next_steps": bullets(verdict.get("next_steps", []) or []),
    }

    content = tmpl.format(**ctx)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)


def cmd_report(args: argparse.Namespace) -> None:
    ensure_dirs()
    # Optional language override
    if getattr(args, "lang", None):
        os.environ["IC_LANG"] = args.lang
    idea_path = Path(args.idea)
    slug = slugify(idea_path.stem)
    verdict_path = REPORTS_DIR / f"{slug}.verdict.json"
    # Template selection by language
    lang = os.environ.get("IC_LANG", "").lower()
    if lang.startswith("en") and (TEMPLATES_DIR / "report.en.md").exists():
        template_path = TEMPLATES_DIR / "report.en.md"
    elif (lang.startswith("zh") or not lang) and (
        TEMPLATES_DIR / "report.zh-CN.md"
    ).exists():
        template_path = TEMPLATES_DIR / "report.zh-CN.md"
    else:
        template_path = TEMPLATES_DIR / "report.md"
    out_path = REPORTS_DIR / f"{slug}.md"
    render_report(idea_path, verdict_path, template_path, out_path)
    print(str(out_path))

    # no benchmark functionality in minimal build


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="idea-crucible", description="Redline-first idea evaluation CLI"
    )
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
    s = sub.add_parser("evaluate", help="Evaluate an idea against redline rules (LLM)")
    s.add_argument("--idea", required=True, type=str, help="Path to idea YAML")
    # model config is optional and hidden behind a flag; by default, we use config/model.local.yaml if present, else config/model.yaml
    s.add_argument("--model-cfg", type=str, help=argparse.SUPPRESS)
    s.add_argument(
        "--lang", type=str, help="Override report/LLM language, e.g. en or zh-CN"
    )
    s.set_defaults(func=cmd_evaluate)

    # report
    s = sub.add_parser("report", help="Render one-page verdict report")
    s.add_argument("--idea", required=True, type=str, help="Path to idea YAML")
    s.add_argument(
        "--lang", type=str, help="Override report language, e.g. en or zh-CN"
    )
    s.set_defaults(func=cmd_report)

    # no benchmark subcommand in minimal build

    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
