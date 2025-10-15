from __future__ import annotations

from pathlib import Path
import re
import yaml


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "config" / "rules" / "core"


TEMPLATE = {
    "id": "",
    "title": "",
    "scope": "core",
    "severity": "medium",  # critical|high|medium|low
    "decision": "caution",  # deny|caution
    "rationale": "",
    "condition": "",
    "keywords": [],
    "sources": [],
    "owner": "core",
    "version": 1,
    "next_steps": [
        "Define a narrow experiment to de-risk this redline.",
    ],
}


def next_rule_id() -> tuple[str, str]:
    # Determine next RL-XXX number from existing files
    nums = []
    for p in CORE.glob("*.yaml"):
        m = re.search(r"RL-(\d{3})", p.read_text(encoding="utf-8"))
        if m:
            nums.append(int(m.group(1)))
    n = max(nums) + 1 if nums else 1
    return f"RL-{n:03d}", f"{n:02d}_custom_rule.yaml"


def prompt(msg: str, default: str = "") -> str:
    val = input(f"{msg}{' [' + default + ']' if default else ''}: ").strip()
    return val or default


def main() -> None:
    CORE.mkdir(parents=True, exist_ok=True)
    rid, fname = next_rule_id()
    print(f"新规则 ID 将为：{rid}")
    title = prompt("规则标题", rid)
    severity = prompt("严重级别 (critical|high|medium|low)", "medium")
    decision = prompt("默认决策 (deny|caution)", "caution")
    rationale = prompt("动机/背景", "")
    condition = prompt("触发条件(自然语言或表达式)", "")

    data = dict(TEMPLATE)
    data.update(
        {
            "id": rid,
            "title": title,
            "severity": severity,
            "decision": decision,
            "rationale": rationale,
            "condition": condition,
        }
    )

    path = CORE / fname
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)

    print(str(path))
    print("完成：请审阅该规则文件，并在需要时补充 keywords/sources/next_steps。")


if __name__ == "__main__":
    main()
