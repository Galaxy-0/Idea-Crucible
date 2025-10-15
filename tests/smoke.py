import json
import os
import sys
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def run_cmd(args):
    proc = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
        raise SystemExit(proc.returncode)
    return proc.stdout.strip()


def main() -> None:
    idea_path = ROOT / "ideas" / "demo-idea.yaml"
    if not idea_path.exists():
        out = run_cmd(
            [
                sys.executable,
                "-m",
                "agent.main",
                "intake",
                "--desc",
                "Test idea for CI",
                "--out",
                str(idea_path),
            ]
        )

    # Try LLM eval only if an API key is present (legacy env), otherwise skip (CI-safe)
    if os.environ.get("OPENAI_API_KEY"):
        out = run_cmd(
            [
                sys.executable,
                "-m",
                "agent.main",
                "evaluate",
                "--idea",
                str(idea_path),
            ]
        )
        verdict_path = Path(out.splitlines()[-1].strip())
        assert verdict_path.exists(), f"Verdict path not found: {verdict_path}"
        data = json.loads(verdict_path.read_text(encoding="utf-8"))
        for k in ["decision", "conf_level", "reasons", "redlines", "next_steps"]:
            assert k in data, f"Missing key in verdict: {k}"

        # Report render
        out = run_cmd(
            [
                sys.executable,
                "-m",
                "agent.main",
                "report",
                "--idea",
                str(idea_path),
            ]
        )
        report_path = Path(out.splitlines()[-1].strip())
        assert report_path.exists(), f"Report path not found: {report_path}"
        content = report_path.read_text(encoding="utf-8")
        assert "结论" in content or "decision" in content.lower(), (
            "Report content seems empty"
        )

    print("Smoke test passed.")


if __name__ == "__main__":
    main()
