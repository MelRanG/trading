import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from quant_harness.pain_supply_shadow import inspect_flow


def main():
    parser = argparse.ArgumentParser(description="Read-only readiness; required date must be a verified preceding market session")
    parser.add_argument("--required-source-date", required=True)
    args = parser.parse_args()
    result = inspect_flow(ROOT / "data/historical_investor_flow/market_investor_flow_daily.csv",
                          required_source_date=args.required_source_date)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
