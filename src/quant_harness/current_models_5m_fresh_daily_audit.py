"""Fresh Toss 1d comparison for the already-collected 15 pilot sessions."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any

import pandas as pd

from quant_harness.current_models_5m_data import _load_daily, _session_validation
from quant_harness.current_models_5m_validation import _cache_path
from quant_harness.three_model_backtest import _timestamp_date
from quant_harness.v104_end_to_end_causal_challenger_audit.adapter import build_candidate_ledgers, load_candidate_specs
from quant_harness.v72_integration_ready.toss_openapi import TossOpenApiClient


KST = timezone(timedelta(hours=9))


def _transport_counter():
    counts = {"total": 0, "GET": 0, "POST": 0, "status": {}}

    def transport(request, timeout):
        method = request.get_method().upper()
        counts["total"] += 1
        counts[method] = counts.get(method, 0) + 1
        status, headers, body = TossOpenApiClient._default_transport(request, timeout)
        counts["status"][str(status)] = counts["status"].get(str(status), 0) + 1
        return status, headers, body

    return transport, counts


def _minute_aggregate(root: Path, symbol: str, session: str) -> tuple[dict[str, float], dict[str, Any]]:
    path = _cache_path(root, symbol, session)
    frame = pd.read_csv(path, dtype={"symbol": str})
    ts = pd.to_datetime(frame["timestamp"], utc=True).dt.tz_convert("Asia/Seoul")
    regular = (ts.dt.date.astype(str) == session) & (ts.dt.time >= datetime.strptime("09:00", "%H:%M").time()) & (ts.dt.time <= datetime.strptime("15:30", "%H:%M").time())
    data = frame.loc[regular].copy()
    ordered_ts = ts.loc[regular]
    aggregate = {
        "open": float(data.iloc[0]["open"]), "high": float(pd.to_numeric(data["high"]).max()),
        "low": float(pd.to_numeric(data["low"]).min()), "close": float(data.iloc[-1]["close"]),
        "volume": float(pd.to_numeric(data["volume"]).sum()),
    }
    return aggregate, {
        "bar_count": int(len(data)), "duplicate_timestamp": int(ordered_ts.duplicated().sum()),
        "first_timestamp": str(ordered_ts.iloc[0]), "last_timestamp": str(ordered_ts.iloc[-1]),
        "zero_volume_minutes": int((pd.to_numeric(data["volume"]) == 0).sum()),
    }


def _fresh_daily(client: TossOpenApiClient, symbol: str, session: str) -> dict[str, float]:
    rows = client.get_daily_candles(symbol, start_date=session, end_date=session)
    if len(rows) != 1:
        raise RuntimeError(f"fresh Toss 1d returned {len(rows)} rows for {symbol} {session}")
    row = rows[0]
    return {"open": float(row["open"]), "high": float(row["high"]), "low": float(row["low"]),
            "close": float(row["adj_close"]), "volume": float(row["volume"])}


def _model_participation(root: Path) -> dict[str, Any]:
    specs = load_candidate_specs(root)
    output: dict[str, Any] = {}
    for candidate_id in ("V69_PARENT", "V79_NO63_VOL_GUARD"):
        built = build_candidate_ledgers(root, specs[candidate_id], use_common_cutoff=True)
        index = built["market"]["close"].index
        period = index[(index >= pd.Timestamp("2023-01-30")) & (index <= pd.Timestamp("2024-08-30"))]
        features = built["f69"] if candidate_id.startswith("V69") else built["f79"]
        selection = built["selection"].reindex(period)
        ledger = built["ledger"]
        eligible = int(features["eligible"].reindex(period)["139290"].fillna(False).sum())
        gate = int(features["universe_gate"]["gate"].reindex(period)["139290"].fillna(False).sum())
        selection_column = "leader_ticker" if "leader_ticker" in selection.columns else "sleeve_ticker"
        selected = int(selection[selection_column].astype(str).eq("139290").sum())
        targets = ledger[ledger["date"].isin(period)]["target_weights_json"].map(lambda value: value if isinstance(value, dict) else json.loads(str(value)))
        target_days = int(targets.map(lambda value: "139290" in value).sum())
        pilot_symbols = ("305720", "157490", "139290")
        pilot_symbol_days: dict[str, dict[str, int]] = {}
        for pilot_symbol in pilot_symbols:
            pilot_symbol_days[pilot_symbol] = {
                "selected_candidate_days": int(selection[selection_column].astype(str).eq(pilot_symbol).sum()),
                "target_inclusion_days": int(targets.map(lambda value, ticker=pilot_symbol: ticker in value).sum()),
            }
        output[candidate_id] = {
            "evaluation_days_with_daily_input": int(len(period)),
            "universe_gate_days": gate,
            "ranking_eligible_days": eligible,
            "selected_candidate_days": selected,
            "target_inclusion_days": target_days,
            "minute_session_required_for_139290": bool(selected or target_days),
            "pilot_symbol_days": pilot_symbol_days,
        }
    return output


def run_fresh_daily_audit(root: Path | str) -> dict[str, Any]:
    root = Path(root).resolve()
    try:
        from dotenv import load_dotenv
        load_dotenv(root / ".env")
    except Exception:
        pass
    pilot = json.loads((root / "runtime/current_models_5m_validation/pilot_summary.json").read_text(encoding="utf-8"))
    sessions = [(row["symbol"], row["date"]) for row in pilot["sessions"]]
    transport, calls = _transport_counter()
    client = TossOpenApiClient(transport=transport)
    rows: list[dict[str, Any]] = []
    for symbol, session in sessions:
        minute, minute_meta = _minute_aggregate(root, symbol, session)
        fresh = _fresh_daily(client, symbol, session)
        cached = _load_daily(root, symbol).loc[session]
        cached_values = {field: float(cached[field]) for field in ("open", "high", "low", "close", "volume")}
        minute_fresh_diff = {field: minute[field] - fresh[field] for field in minute}
        fresh_cached_diff = {field: fresh[field] - cached_values[field] for field in fresh}
        minute_cached_diff = {field: minute[field] - cached_values[field] for field in minute}
        price_fields = ("open", "high", "low", "close")
        rows.append({"symbol": symbol, "date": session, **minute_meta, "minute": minute, "fresh_toss_1d": fresh, "existing_daily_cache": cached_values,
                     "minute_vs_fresh": minute_fresh_diff, "fresh_vs_cache": fresh_cached_diff, "minute_vs_cache": minute_cached_diff,
                     "minute_price_matches_fresh": all(abs(minute_fresh_diff[field]) <= 1e-8 for field in price_fields),
                     "fresh_price_matches_cache": all(abs(fresh_cached_diff[field]) <= 1e-8 for field in price_fields),
                     "minute_volume_matches_fresh": minute_fresh_diff["volume"] == 0.0,
                     "fresh_volume_matches_cache": fresh_cached_diff["volume"] == 0.0})
    participation = _model_participation(root)
    participating_symbols = {
        symbol
        for candidate in participation.values()
        for symbol, counts in candidate["pilot_symbol_days"].items()
        if counts["selected_candidate_days"] or counts["target_inclusion_days"]
    }
    participating_symbols.discard("139290")
    actual_evaluated = [row for row in rows if row["symbol"] in participating_symbols]
    price_contract_valid = all(row["minute_price_matches_fresh"] for row in actual_evaluated)
    cache_source_mismatch = price_contract_valid and any(not row["fresh_price_matches_cache"] for row in actual_evaluated)
    if not price_contract_valid:
        judgement = "BLOCKED_BY_ADJUSTED_PRICE_SEMANTICS"
    elif cache_source_mismatch:
        judgement = "DAILY_CACHE_SOURCE_MISMATCH"
    else:
        judgement = "PILOT_PRICE_CONTRACT_VALID"
    details = [row for row in rows if row["symbol"] == "139290" and (not row["minute_price_matches_fresh"] or not row["fresh_price_matches_cache"])]
    summary = {
        "mode": "CURRENT_MODELS_5M_FRESH_DAILY_AUDIT", "source_pilot_preserved": True,
        "sessions": len(rows), "fresh_endpoint": "GET /api/v1/candles", "fresh_interval": "1d", "fresh_adjusted": True,
        "volume_contract": "NON_AUTHORITATIVE_FOR_INTRADAY_MODEL_SIGNAL",
        "minute_volume_used_by_model": False, "daily_d1_volume_value_still_used": True,
        "model_participation": participation, "actual_evaluated_symbols": sorted(participating_symbols),
        "judgement": judgement, "broker_mutation_calls": 0, "account_api_calls": 0,
        "api_calls": calls, "fresh_daily_cache_modified": False,
        "139290_discrepancy_count": len(details),
    }
    out = root / "runtime/current_models_5m_validation"
    (out / "fresh_daily_audit.json").write_text(json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    (out / "fresh_daily_comparison.json").write_text(json.dumps(rows, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    (out / "139290_discrepancies.json").write_text(json.dumps(details, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return summary


__all__ = ["run_fresh_daily_audit"]
