from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant_harness.paper_decision_runtime import run_paper_decision_preview


ROOT = Path(__file__).resolve().parents[1]


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
    parser = argparse.ArgumentParser(description="Persist one non-executable Paper decision preview")
    parser.add_argument("--mode", choices=("mock", "real-read-only"), required=True)
    parser.add_argument("--root", default=str(ROOT))
    args = parser.parse_args()
    root = Path(args.root).resolve()
    _load_dotenv(root / ".env")
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print(json.dumps({"status": "BLOCKED_DATABASE_NOT_CONFIGURED"}))
        return 2
    result = run_paper_decision_preview(root, database_url=database_url, mode=args.mode)
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
