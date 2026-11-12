"""One-shot topic-scoped RSS collection; no credentials, broker, DB or scheduler."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from quant_harness.rss_news_shadow import fetch_feed, parse_feed, store_feed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True)
    parser.add_argument("--include-term", action="append", required=True)
    args = parser.parse_args()
    try:
        raw, received_at = fetch_feed(args.query)
        parsed = parse_feed(raw, observed_at=received_at, include_terms=args.include_term)
        result = store_feed(ROOT / "runtime/news_shadow/google_rss", raw=raw, parsed=parsed, query=args.query)
    except Exception:
        print(json.dumps({"status": "BLOCKED_RSS_INTAKE", "capital_authority": "NONE"}))
        return 1
    status = "RSS_SHADOW_OBSERVATIONS_STORED" if parsed["observations"] else "NO_CURRENT_DAY_RSS_EVIDENCE"
    print(json.dumps({"status": status, "observed_at": received_at.isoformat(),
                      **result, "get_calls": 1, "broker_mutation_calls": 0}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
