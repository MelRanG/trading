from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from quant_harness.historical_operational_replay import run_historical_operational_replay


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the existing Paper operational path over historical data")
    parser.add_argument("--reset", action="store_true", help="reset Paper tables in TEST_DATABASE_URL before the first run")
    parser.add_argument("--candidate-id", default="V69_PARENT", help="registered candidate id to replay")
    parser.add_argument("--start-date", help="inclusive replay start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", help="inclusive replay end date (YYYY-MM-DD)")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env", override=False)
    test_url = os.environ.get("TEST_DATABASE_URL")
    if not test_url:
        raise SystemExit("TEST_DATABASE_URL is required")
    result = run_historical_operational_replay(
        root,
        test_url,
        reset=args.reset,
        candidate_id=args.candidate_id,
        start_date=args.start_date,
        end_date=args.end_date,
        output_dir=args.output_dir,
    )
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
