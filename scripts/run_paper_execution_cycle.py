from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant_harness.paper_execution_runtime import run_paper_execution_cycle  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"'") )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one deterministic Paper-only execution cycle")
    parser.add_argument("--mode", choices=("historical-development",), default="historical-development")
    args = parser.parse_args()
    _load_dotenv(ROOT / ".env")
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print(json.dumps({"status": "BLOCKED_DATABASE_NOT_CONFIGURED"}))
        return 2
    result = run_paper_execution_cycle(database_url, ROOT, mode=args.mode)
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
    return 0 if result["status"] == "COMPLETED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
