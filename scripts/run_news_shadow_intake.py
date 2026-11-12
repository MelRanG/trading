"""Company-scoped official disclosure intake; no trading/strategy/DB invocation."""
from datetime import date, datetime, timezone
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from dotenv import load_dotenv
from quant_harness.news_shadow_runtime import collect_disclosures, append_observations
from quant_harness.v72_integration_ready.opendart import OpenDartClient, OpenDartError


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--corp-code", required=True)
    parser.add_argument("--stock-code", required=True)
    parser.add_argument("--start-date", required=True, type=date.fromisoformat)
    parser.add_argument("--end-date", required=True, type=date.fromisoformat)
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    client = OpenDartClient()
    if not client.api_key:
        print(json.dumps({"status": "BLOCKED_MISSING_OPENDART_API_KEY", "capital_authority": "NONE"}))
        return 2
    try:
        observations = collect_disclosures(client, corp_code=args.corp_code, stock_code=args.stock_code,
            start=args.start_date, end=args.end_date, observed_at=datetime.now(timezone.utc))
        # Availability is recorded AFTER the HTTP response, never request start.
        received_at = datetime.now(timezone.utc).isoformat()
        for observation in observations:
            observation["first_seen_at"] = received_at
        journal = ROOT / "runtime/news_shadow" / f"opendart_{args.corp_code}_{args.stock_code}.jsonl"
        result = append_observations(journal, observations)
    except Exception:
        # Do not print credential-bearing URL, raw HTTP exception or response.
        print(json.dumps({"status": "BLOCKED_OFFICIAL_NEWS_INTAKE", "capital_authority": "NONE"}))
        return 1
    print(json.dumps({"status": "NEWS_SHADOW_INTAKE_COMPLETE", **result,
                     "exact_publication_time_verified": False, "broker_mutation_calls": 0}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
