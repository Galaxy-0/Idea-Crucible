from __future__ import annotations

import json
import sys
from pathlib import Path
import os
import sys
from typing import Dict, Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("IC_LANG", "zh-CN")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
CONFIG = ROOT / "config"
MODEL_LOCAL = CONFIG / "model.local.yaml"
MODEL_DEFAULT = CONFIG / "model.yaml"
IDEAS_DIR = ROOT / "ideas"


def slugify(text: str) -> str:
    return "-".join([t for t in text.lower().strip().split()[:6]]) or "idea"


def load_llm_client():
    from agent.llm import load_model_config, get_client

    cfg_path = MODEL_LOCAL if MODEL_LOCAL.exists() else MODEL_DEFAULT
    if not cfg_path.exists():
        raise RuntimeError(
            "未找到模型配置：请创建 config/model.local.yaml 或 config/model.yaml"
        )
    cfg = load_model_config(str(cfg_path))
    client = get_client(cfg)
    return cfg, client


def expand_idea(desc: str) -> Dict[str, Any]:
    cfg, client = load_llm_client()
    language_hint = (getattr(cfg, "language", "zh-CN") or "zh-CN").strip()
    lang_directive = (
        f"Respond strictly in {language_hint}."
        if language_hint and language_hint.lower() != "auto"
        else ""
    )

    system = (
        "You are a startup product strategist. Expand a terse idea description into a normalized idea object. "
        "Return ONLY a strict JSON object with these keys: intent, user, scenario, triggers, alts, assumptions (array), risks (array)."
    )
    user = (
        f"Language: {language_hint}. {lang_directive}\n"
        "Given a short idea description, expand into a concrete, concise plan suitable for evaluation.\n\n"
        f"Short Idea: {desc}\n\n"
        "Output JSON (single object, no extra text):\n"
        '{\n  "intent": "...",\n  "user": "...",\n  "scenario": "...",\n  "triggers": "...",\n  "alts": "...",\n  "assumptions": ["..."],\n  "risks": ["..."]\n}'
    )

    raw = client.complete_json(system, user)
    # Reuse strip_code_fences from agent.llm to be safe
    from agent.llm import strip_code_fences

    raw = strip_code_fences(raw)
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("Non-object JSON")
    except Exception:
        # Minimal fallback
        data = {
            "intent": desc,
            "user": "early adopters",
            "scenario": "initial use case",
            "triggers": "pain/need trigger",
            "alts": "status quo / competitors",
            "assumptions": [desc],
            "risks": [],
        }

    # Coerce fields
    def as_str(x: Any, default: str = "") -> str:
        return str(x) if isinstance(x, str) and x.strip() else default

    def as_list(x: Any) -> list[str]:
        if isinstance(x, list):
            return [str(i) for i in x if str(i).strip()]
        if isinstance(x, str) and x.strip():
            return [x.strip()]
        return []

    expanded = {
        "intent": as_str(data.get("intent"), desc),
        "user": as_str(data.get("user"), "early adopters"),
        "scenario": as_str(data.get("scenario"), "initial use case"),
        "triggers": as_str(data.get("triggers"), "pain/need trigger"),
        "alts": as_str(data.get("alts"), "status quo / competitors"),
        "assumptions": as_list(data.get("assumptions")) or [desc],
        "risks": as_list(data.get("risks")),
    }
    return expanded


def write_idea(data: Dict[str, Any]) -> Path:
    IDEAS_DIR.mkdir(parents=True, exist_ok=True)
    slug = slugify(data.get("intent", "idea"))
    path = IDEAS_DIR / f"{slug}.yaml"
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
    print(str(path))
    return path


def run_pipeline(idea_path: Path) -> Path:
    import subprocess

    # Evaluate then report; use current interpreter
    proc = subprocess.run(
        [sys.executable, "-m", "agent.main", "evaluate", "--idea", str(idea_path)],
        cwd=ROOT,
        text=True,
    )
    if proc.returncode != 0:
        print("[warn] 评估失败（可能未配置 LLM），尝试直接渲染报告（若已有 verdict）")
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
    if len(sys.argv) > 1:
        desc = " ".join(sys.argv[1:]).strip()
    else:
        desc = input("输入一句话想法（将自动扩写并评估）：\n> ").strip()
    if not desc:
        print("请输入非空想法描述。")
        raise SystemExit(2)

    try:
        data = expand_idea(desc)
    except Exception as e:
        print(f"[error] 扩写失败：{e}")
        print("回退为最小模板。")
        data = {
            "intent": desc,
            "user": "early adopters",
            "scenario": "initial use case",
            "triggers": "pain/need trigger",
            "alts": "status quo / competitors",
            "assumptions": [desc],
            "risks": [],
        }

    idea_path = write_idea(data)
    run_pipeline(idea_path)
    print("完成：已扩写 → 评估 → 报告。")


if __name__ == "__main__":
    main()
