from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant_harness.toss_snapshot_runtime import run_toss_snapshot


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"").strip("'"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("mock", "real-read-only"), required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    _load_dotenv(root / ".env")
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print(json.dumps({"status": "SKIPPED_NOT_CONFIGURED", "reason": "DATABASE_URL"}))
        return 0
    result = run_toss_snapshot(database_url=database_url, mode=args.mode)
    print(json.dumps(result, default=str, ensure_ascii=False))
    return 0 if result["status"] != "FAILED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
