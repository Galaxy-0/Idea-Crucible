from __future__ import annotations

import sys
from pathlib import Path
import os

import yaml


ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("IC_LANG", "zh-CN")
IDEAS_DIR = ROOT / "ideas"


def prompt(msg: str, default: str = "") -> str:
    val = input(f"{msg}{' [' + default + ']' if default else ''}: ").strip()
    return val or default


def collect_idea() -> dict:
    print("=== 录入启动想法（按回车采用默认）===")
    intent = prompt("目标/一句话想法", "Untitled idea")
    user = prompt("目标用户", "early adopters")
    scenario = prompt("核心场景", "initial use case")
    triggers = prompt("触发/痛点", "pain/need trigger")
    alts = prompt("备选方案/竞品", "status quo / competitors")
    assumptions = prompt("关键假设(以;分隔)", intent)
    risks = prompt("已知风险(以;分隔)", "")
    data = {
        "intent": intent,
        "user": user,
        "scenario": scenario,
        "triggers": triggers,
        "alts": alts,
        "assumptions": [s.strip() for s in assumptions.split(";") if s.strip()]
        or [intent],
        "risks": [s.strip() for s in risks.split(";") if s.strip()],
    }
    return data


def slugify(text: str) -> str:
    return "-".join([t for t in text.lower().strip().split()[:6]]) or "idea"


def write_idea(data: dict) -> Path:
    IDEAS_DIR.mkdir(parents=True, exist_ok=True)
    slug = slugify(data.get("intent", "idea"))
    path = IDEAS_DIR / f"{slug}.yaml"
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
    print(str(path))
    return path


def run_pipeline(idea_path: Path) -> Path:
    import subprocess

    # Evaluate (will require model config if verdict not present)
    proc = subprocess.run(
        [sys.executable, "-m", "agent.main", "evaluate", "--idea", str(idea_path)],
        cwd=ROOT,
        text=True,
    )
    if proc.returncode != 0:
        print("[warn] 评估阶段失败，尝试继续渲染报告（若已有 verdict）")

    # Report
    proc2 = subprocess.run(
        [sys.executable, "-m", "agent.main", "report", "--idea", str(idea_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if proc2.returncode != 0:
        print(proc2.stdout)
        print(proc2.stderr)
        raise SystemExit(proc2.returncode)
    out_md = Path(proc2.stdout.strip().splitlines()[-1])
    print(str(out_md))
    return out_md


def main() -> None:
    data = collect_idea()
    idea_path = write_idea(data)
    run_pipeline(idea_path)
    print("完成：已生成 verdict 与报告（若模型配置就绪）。")


if __name__ == "__main__":
    main()
