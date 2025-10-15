from __future__ import annotations

import argparse
from pathlib import Path
import shutil


def sync_verdicts(
    src_reports: Path,
    dst_verdicts: Path,
    pattern: str = "*.verdict.json",
    force: bool = True,
) -> int:
    src_reports = src_reports.resolve()
    dst_verdicts = dst_verdicts.resolve()
    if not src_reports.exists() or not src_reports.is_dir():
        raise SystemExit(f"src reports dir not found: {src_reports}")

    dst_verdicts.mkdir(parents=True, exist_ok=True)
    count = 0
    for p in sorted(src_reports.glob(pattern)):
        if not p.is_file():
            continue
        target = dst_verdicts / p.name
        if target.exists() and not force:
            continue
        shutil.copy2(p, target)
        count += 1
    return count


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Copy reports/*.verdict.json to a dataset verdicts/ directory"
    )
    ap.add_argument(
        "--src", type=str, default=str(Path(__file__).resolve().parents[1] / "reports")
    )
    ap.add_argument(
        "--dst", type=str, required=True, help="Path to dataset verdicts/ directory"
    )
    ap.add_argument("--pattern", type=str, default="*.verdict.json")
    ap.add_argument(
        "--no-overwrite", action="store_true", help="Do not overwrite existing files"
    )
    args = ap.parse_args()

    copied = sync_verdicts(
        Path(args.src), Path(args.dst), args.pattern, force=not args.no_overwrite
    )
    print(f"Copied {copied} verdicts -> {args.dst}")


if __name__ == "__main__":
    main()
