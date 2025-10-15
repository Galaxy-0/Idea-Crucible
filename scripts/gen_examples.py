from __future__ import annotations

import subprocess
import sys
from pathlib import Path
import os


ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("IC_LANG", "zh-CN")


def run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, cwd=ROOT, text=True)
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


def ensure_demo(idea_rel: str) -> None:
    idea = ROOT / idea_rel
    slug = idea.stem
    verdict = ROOT / "reports" / f"{slug}.verdict.json"
    # Only run evaluate if verdict is missing (avoids requiring LLM/network)
    if not verdict.exists():
        run([sys.executable, "-m", "agent.main", "evaluate", "--idea", str(idea)])
    # Always render report for consistency
    run([sys.executable, "-m", "agent.main", "report", "--idea", str(idea)])


def main() -> None:
    # English demo
    ensure_demo("ideas/demo-idea.yaml")
    # Chinese demo
    ensure_demo("ideas/一句话-想法.yaml")
    print("Demo examples available under reports/: demo-idea.*, 一句话-想法.*")


if __name__ == "__main__":
    main()
