"""Append only the verified, already-staged Toss candle rows to active data."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
load_dotenv(ROOT / ".env")
from quant_harness.active_market_data_update import append_canonical, run_incremental_update, run_toss_incremental_update, run_toss_market_indicator_ks11_update  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--live-toss", action="store_true", help="use the existing Toss GET candle adapter")
    parser.add_argument("--market-indicator-ks11", action="store_true", help="use Toss Market Indicators for the KS11 contract")
    args = parser.parse_args()
    updater = run_toss_market_indicator_ks11_update if args.market_indicator_ks11 else (run_toss_incremental_update if args.live_toss else run_incremental_update)
    result = updater(ROOT, write_output=not args.dry_run)
    if result.failed:
        print({"status": "HOLD_ONLY", "cutoff": result.cutoff, "failed": result.failed})
        return 2
    canonical_added = 0
    # KS11 is maintained in its own canonical benchmark CSV.  It must not
    # trigger the ETF canonical append path.
    if not args.dry_run and result.backup_dir and not args.market_indicator_ks11:
        canonical_added = append_canonical(ROOT, result.cutoff, Path(result.backup_dir))
    print({
        "status": "UPDATED" if not args.dry_run else "DRY_RUN",
        "provider": result.provider,
        "endpoint": result.endpoint,
        "symbols": result.symbols,
        "succeeded": result.succeeded,
        "cutoff": result.cutoff,
        "rows_added": result.rows_added,
        "canonical_rows_added": canonical_added,
        "backup_dir": result.backup_dir,
        "live_execution_allowed": False,
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
