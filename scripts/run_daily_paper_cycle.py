from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quant_harness.daily_paper_runtime import run_daily_paper_cycle, _require_isolated_test_database  # noqa: E402


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one fail-closed daily Paper cycle")
    parser.add_argument("--snapshot-mode", choices=("mock", "real-read-only"), default="real-read-only")
    parser.add_argument("--root", default=str(ROOT))
    args = parser.parse_args()
    root = Path(args.root).resolve()
    _load_dotenv(root / ".env")
    try:
        database_url = _require_isolated_test_database(
            os.getenv("TEST_DATABASE_URL"),
            test_database_url=os.getenv("TEST_DATABASE_URL"),
            operational_database_url=os.getenv("DATABASE_URL"),
        )
    except RuntimeError as exc:
        print(json.dumps({"status": "HOLD_ONLY", "reason": str(exc)}, ensure_ascii=False))
        return 2
    result = run_daily_paper_cycle(database_url, root, snapshot_mode=args.snapshot_mode)
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
