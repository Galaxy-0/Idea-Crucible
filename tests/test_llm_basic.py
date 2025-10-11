import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    cfg_path = ROOT / "config" / "model.yaml"
    if not cfg_path.exists():
        print("[skip] config/model.yaml not found")
        return

    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    api_key = (cfg or {}).get("api_key", "")
    if not api_key or "your" in api_key:
        print("[skip] LLM api_key not configured in config/model.yaml")
        return

    idea_path = ROOT / "ideas" / "demo-idea.yaml"
    out_dir = ROOT / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Call the CLI evaluate to produce a verdict JSON
    import subprocess

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent.main",
            "evaluate",
            "--idea",
            str(idea_path),
            "--model-cfg",
            str(cfg_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr)
        raise SystemExit(proc.returncode)

    verdict_path = Path(proc.stdout.strip().splitlines()[-1])
    assert verdict_path.exists(), f"verdict file not found: {verdict_path}"
    data = json.loads(verdict_path.read_text(encoding="utf-8"))

    # Basic shape assertions (do not check content quality)
    assert isinstance(data, dict)
    assert data.get("decision") in {"deny", "caution", "go"}
    assert isinstance(data.get("conf_level"), (int, float))
    assert isinstance(data.get("reasons"), list)
    assert isinstance(data.get("redlines"), list)
    assert isinstance(data.get("next_steps"), list)

    print("LLM basic test passed.")


if __name__ == "__main__":
    main()

