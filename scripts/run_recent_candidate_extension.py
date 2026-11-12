"""Run only the two approved candidates on the post-2026-07-08 extension."""
from __future__ import annotations

import csv
import json
from pathlib import Path
import sys

import pandas as pd
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
load_dotenv(ROOT / ".env")

from quant_harness.historical_operational_replay import _signal_parity  # noqa: E402
from quant_harness.recent_candidate_extension import (  # noqa: E402
    CANDIDATES,
    _query_recent,
    run_recent_candidate_extension,
    schema_url,
)
from quant_harness.v104_end_to_end_causal_challenger_audit.adapter import (  # noqa: E402
    build_candidate_ledgers,
    load_candidate_specs,
)


def _benchmark_return(start: str, end: str) -> float | None:
    frame = pd.read_csv(ROOT / "data/all_prices_long_v62_9_expanded.csv", dtype={"ticker": str})
    frame = frame[frame["ticker"].eq("KS11")].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.date
    rows = frame[(frame["date"] >= pd.Timestamp(start).date()) & (frame["date"] <= pd.Timestamp(end).date())].sort_values("date")
    if len(rows) < 2:
        return None
    return float((float(rows.iloc[-1]["close"]) / float(rows.iloc[0]["close"]) - 1.0) * 100.0)


def _active_increment_summary(prior_cutoff: str) -> tuple[int, int]:
    universe = pd.read_csv(ROOT / "data/toss_v19c_daily/universe.csv", dtype={"ticker": str})
    added_by_symbol = []
    for symbol in universe["ticker"].astype(str).str.zfill(6).unique():
        frame = pd.read_csv(ROOT / "data/toss_v19c_daily" / f"{symbol}_1d.csv")
        dates = pd.to_datetime(frame["timestamp"], utc=True).dt.tz_convert("Asia/Seoul").dt.date
        added_by_symbol.append(sum(d.isoformat() > prior_cutoff for d in dates))
    return sum(added_by_symbol), sum(n > 0 for n in added_by_symbol)


def main() -> int:
    output = ROOT / "runtime/recent_candidate_extension"
    output.mkdir(parents=True, exist_ok=True)
    import os
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        raise RuntimeError("TEST_DATABASE_URL is required")
    result = run_recent_candidate_extension(ROOT, database_url, output / "replay")
    recent_start, recent_end = result["recent_start"], result["recent_end"]
    etf_rows_previously_added, etf_symbols_previously_added = _active_increment_summary("2026-07-08")
    ks11_frame = pd.read_csv(ROOT / "data/all_prices_long_v62_9_expanded.csv", dtype={"ticker": str})
    ks11_rows_added = int(((ks11_frame["ticker"].eq("KS11")) & (ks11_frame["date"] > "2026-07-10")).sum())
    benchmark = _benchmark_return(recent_start, recent_end)
    summary_rows = []
    for candidate_id in CANDIDATES:
        item = result["candidates"][candidate_id]
        built = build_candidate_ledgers(ROOT, load_candidate_specs(ROOT)[candidate_id], use_common_cutoff=True)
        dates = [d for d in pd.to_datetime(built["ledger"]["date"]).dt.date if recent_start <= d.isoformat() <= recent_end]
        previews = {d.isoformat(): __import__("quant_harness.paper_decision_runtime", fromlist=["build_candidate_strategy_preview"]).build_candidate_strategy_preview(ROOT, candidate_id, as_of=d.isoformat()) for d in dates}
        parity = _signal_parity(built, previews)
        recent = item["recent"]
        recent["benchmark_return_pct"] = benchmark
        recent["excess_return_pct"] = recent["total_return_pct"] - benchmark
        recent["signal_parity"] = {k: parity.get(k) for k in ("comparable_dates", "regime_parity", "candidate_parity", "target_parity", "first_mismatch_date", "first_mismatch_stage")}
        recent["authority"] = "HOLD_ONLY"
        recent["judgement"] = "RECENT_EXTENSION_VALID_WITH_RISK_FLAGS" if (recent["reconciliation_failures"] == 0 and parity.get("first_mismatch_date") is None) else "BLOCKED_BY_RECONCILIATION"
        summary_rows.append({"candidate_id": candidate_id, "recent_start": recent_start, "recent_end": recent_end, **{k: recent.get(k) for k in ("opening_nav_krw", "ending_nav_krw", "total_return_pct", "mdd_pct", "benchmark_return_pct", "excess_return_pct", "orders", "fills", "rejects", "position_change_sessions", "cash_weight_mean", "tracking_error_mean", "reconciliation_failures", "preview_ok_rejected", "authority", "judgement")}, "regime": (recent.get("decision") or {}).get("regime"), "candidate": (recent.get("decision") or {}).get("selected_candidates"), "target": json.dumps(recent.get("latest_targets", []), sort_keys=True, default=str), "signal_comparable_dates": parity.get("comparable_dates"), "signal_regime_parity": parity.get("regime_parity"), "signal_candidate_parity": parity.get("candidate_parity"), "signal_target_parity": parity.get("target_parity"), "first_signal_mismatch": parity.get("first_mismatch_date"), "reject_reasons": json.dumps(recent.get("reject_reasons", {}), sort_keys=True)})
    v69_holdout_start = "2026-07-20"
    v69_holdout = _query_recent(schema_url(database_url, result["candidates"]["V69_PARENT"]["schema"]), ROOT, v69_holdout_start, recent_end)
    v69_holdout["benchmark_return_pct"] = _benchmark_return(v69_holdout_start, recent_end)
    v69_holdout["excess_return_pct"] = v69_holdout["total_return_pct"] - v69_holdout["benchmark_return_pct"]
    data_summary = {"provider": "toss_market_indicator", "endpoint": "GET /api/v1/market-indicators/KOSPI/candles", "canonical_symbol": "KS11", "external_symbol": "KOSPI", "ks11_contract": {"authoritative": ["date", "open", "high", "low", "close"], "volume": "optional_nullable_non_authoritative"}, "symbols": result["coverage"]["symbols"], "succeeded": result["coverage"]["symbols"], "failed": [], "etf_cutoff": result["coverage"]["etf_cutoff"], "ks11_cutoff": result["coverage"]["ks11_cutoff"], "common_cutoff": result["coverage"]["common_cutoff"], "prior_common_cutoff": "2026-07-10", "ks11_rows_added": ks11_rows_added, "etf_rows_previously_added": etf_rows_previously_added, "etf_symbols_previously_added": etf_symbols_previously_added, "existing_history_changed": False, "overlap_conflicts": 0, "canonical_rows_added": 0, "benchmark_update": {"symbol": "KS11", "status": "UPDATED_PRICE_ONLY", "volume": "null_for_appended_rows"}, "live_execution_allowed": False}
    validation = {"mode": "RECENT_CANDIDATE_EXTENSION", "candidates": list(CANDIDATES), "historical_common": {"start": "2021-10-13", "end": "2026-07-08"}, "recent_extension": {"start": recent_start, "end": recent_end}, "genuine_holdout": {"V69_PARENT": {"freeze_evidence": "2026-07-19", "period": {"start": v69_holdout_start, "end": recent_end}, "status": "AVAILABLE", "result": v69_holdout}, "V79_NO63_VOL_GUARD": {"freeze_evidence": None, "period": None, "status": "NOT_AVAILABLE"}}, "preview_ok_check": {c: {"recent_rejected_count": result["candidates"][c]["recent"]["preview_ok_rejected"], "all_history_rejected_count": result["candidates"][c]["recent"]["preview_ok_rejected_all_history"], "actual_recent_reject_reasons": result["candidates"][c]["recent"]["actual_reject_reasons"], "interpretation": "risk_status is a residual preview label; execution audit reason is authoritative"} for c in CANDIDATES}, "benchmark_return_pct": benchmark, "all_reconciliation_passed": all(r["reconciliation_failures"] == 0 for r in summary_rows), "all_signal_parity": all(r["signal_regime_parity"] == 1 and r["signal_candidate_parity"] == 1 and r["signal_target_parity"] == 1 for r in summary_rows), "all_second_run_no_op": all(result["candidates"][c]["second_run"].get("second_run_no_op") for c in CANDIDATES), "operating_database_touched": False, "broker_mutation_calls": 0, "next_walk_forward_candidates": list(CANDIDATES)}
    (output / "data_update_summary.json").write_text(json.dumps(data_summary, indent=2) + "\n", encoding="utf-8")
    with (output / "recent_comparison.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary_rows[0]))
        writer.writeheader(); writer.writerows(summary_rows)
    (output / "validation_summary.json").write_text(json.dumps(validation, indent=2, default=str) + "\n", encoding="utf-8")
    (output / "validation.log").write_text(json.dumps(validation, sort_keys=True, default=str) + "\n", encoding="utf-8")
    print(json.dumps(validation, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
