from __future__ import annotations

import sys
from pathlib import Path
import glob
import yaml

ROOT = Path(__file__).resolve().parents[1]


def assert_rule_files() -> None:
    from agent.schemas import Rule
    rules_dir = ROOT / "config" / "rules" / "core"
    files = sorted(glob.glob(str(rules_dir / "*.yaml")))
    assert files, "No rule files found"
    for p in files:
        data = yaml.safe_load(Path(p).read_text(encoding="utf-8")) or {}
        Rule(**data)


def assert_idea_file() -> None:
    from agent.schemas import Idea
    idea_path = ROOT / "ideas" / "demo-idea.yaml"
    data = yaml.safe_load(idea_path.read_text(encoding="utf-8")) or {}
    Idea(**data)


def main() -> None:
    assert_rule_files()
    assert_idea_file()
    print("Schema checks passed.")


if __name__ == "__main__":
    main()

