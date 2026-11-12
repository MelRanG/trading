"""Bounded Toss 1-minute data collection for the current-models pilot.

The collector is intentionally narrow: it covers only the 26 ETF universe and
the frozen 2023-01-30..2024-08-30 window.  It never calls account or broker
mutation endpoints and it stops before the full collection when any pilot
session fails the official daily OHLCV parity check.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from quant_harness.current_models_5m_validation import END, START
from quant_harness.three_model_backtest import _cache_path
from quant_harness.v104_end_to_end_causal_challenger_audit.adapter import build_candidate_ledgers, load_candidate_specs
from quant_harness.v72_integration_ready.toss_openapi import TossApiError, TossOpenApiClient


KST = timezone(timedelta(hours=9))
REGULAR_OPEN = time(9, 0)
REGULAR_CLOSE = time(15, 30)
UNIVERSE = "data/toss_v19c_daily/universe.csv"
MANIFEST = "runtime/current_models_5m_validation/intraday_collection_manifest.json"


def _ts_date(value: Any) -> str:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(KST).date().isoformat()


def _load_daily(root: Path, symbol: str) -> pd.DataFrame:
    frame = pd.read_csv(root / f"data/toss_v19c_daily/{symbol}_1d.csv")
    frame["date"] = pd.to_datetime(frame["timestamp"], utc=True).dt.tz_convert("Asia/Seoul").dt.date.astype(str)
    return frame.set_index("date").sort_index()


def _pilot_universe_and_dates(root: Path) -> tuple[list[str], list[str], dict[str, float]]:
    """Select liquidity strata from D-1 ADV, never from performance."""
    specs = load_candidate_specs(root)
    built = build_candidate_ledgers(root, specs["V69_PARENT"], use_common_cutoff=True)
    period = built["market"]["close"].index
    period = period[(period >= START) & (period <= END)]
    symbols = sorted(built["universe"]["ticker"].astype(str).str.zfill(6).unique())
    adv = built["market"]["adv20_d1"].reindex(period)[symbols]
    liquidity = adv.median(axis=0, skipna=True).astype(float).to_dict()
    ordered = sorted(symbols, key=lambda symbol: (-float(liquidity.get(symbol, np.nan)), symbol))
    valid = [symbol for symbol in ordered if np.isfinite(liquidity.get(symbol, np.nan))]
    if len(valid) < 3:
        raise RuntimeError("fewer than three symbols have valid D-1 ADV in the common period")
    selected = [valid[0], valid[len(valid) // 2], valid[-1]]
    positions = [0, round((len(period) - 1) * 0.25), len(period) // 2, round((len(period) - 1) * 0.75), len(period) - 1]
    dates = [period[int(position)].date().isoformat() for position in positions]
    return selected, dates, {symbol: float(liquidity[symbol]) for symbol in selected}


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


def _fetch_session(client: TossOpenApiClient, root: Path, symbol: str, session: str, *, force: bool) -> tuple[pd.DataFrame, dict[str, Any]]:
    path = _cache_path(root, symbol, session)
    cached = None
    if path.is_file():
        try:
            cached = pd.read_csv(path, dtype={"symbol": str})
            dates = cached["timestamp"].map(_ts_date) if not cached.empty else pd.Series(dtype=str)
            if not force and not cached.empty and dates.eq(session).all():
                return cached, {"cache_hit": True, "path": str(path.relative_to(root)), "api_pages": 0}
        except Exception:
            cached = None
    rows: list[dict[str, Any]] = []
    before = f"{session}T23:59:59+09:00"
    pages = 0
    for _ in range(20):
        page, next_before = client.get_intraday_candles_page(symbol, before=before, interval="1m", count=200)
        pages += 1
        rows.extend(row for row in page if _ts_date(row["timestamp"]) == session)
        if not page or not next_before or min(_ts_date(row["timestamp"]) for row in page) < session:
            break
        before = next_before
    unique = {str(row["timestamp"]): row for row in rows}
    if not unique:
        raise TossApiError(f"no 1m candle rows for {symbol} {session}")
    frame = pd.DataFrame(sorted(unique.values(), key=lambda row: str(row["timestamp"])))
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    return frame, {"cache_hit": False, "path": str(path.relative_to(root)), "api_pages": pages}


def _session_validation(root: Path, symbol: str, session: str, frame: pd.DataFrame) -> dict[str, Any]:
    required = {"timestamp", "open", "high", "low", "close", "volume"}
    if not required.issubset(frame.columns):
        return {"symbol": symbol, "date": session, "status": "BLOCKED_BY_MINUTE_DAILY_PARITY", "reason": "INVALID_SCHEMA"}
    ts = pd.to_datetime(frame["timestamp"], utc=True).dt.tz_convert("Asia/Seoul")
    regular = (ts.dt.time >= REGULAR_OPEN) & (ts.dt.time <= REGULAR_CLOSE)
    filtered = frame.loc[regular].copy()
    ts_regular = ts.loc[regular]
    duplicate_count = int(ts_regular.duplicated().sum())
    ordered = bool(ts_regular.is_monotonic_increasing)
    expected = pd.date_range(f"{session} 09:01", f"{session} 15:30", freq="min", tz="Asia/Seoul")
    actual = set(ts_regular.tolist())
    missing_minutes = int(len(set(expected) - actual))
    future_count = int((ts.dt.date > pd.Timestamp(session).date()).sum())
    numeric = filtered.apply(pd.to_numeric, errors="coerce")
    valid_numbers = numeric[["open", "high", "low", "close", "volume"]].notna().all().all() if not filtered.empty else False
    daily = _load_daily(root, symbol)
    if session not in daily.index:
        return {"symbol": symbol, "date": session, "status": "BLOCKED_BY_MINUTE_DAILY_PARITY", "reason": "DAILY_ROW_MISSING", "bar_count": int(len(filtered))}
    reference = daily.loc[session]
    if filtered.empty or not valid_numbers or duplicate_count or not ordered or future_count:
        return {"symbol": symbol, "date": session, "status": "BLOCKED_BY_MINUTE_DAILY_PARITY", "reason": "TIMESTAMP_OR_NUMERIC_CONTRACT", "bar_count": int(len(filtered)), "duplicate_timestamp": duplicate_count, "future_bars": future_count}
    aggregate = {
        "open": float(filtered.iloc[0]["open"]),
        "high": float(pd.to_numeric(filtered["high"]).max()),
        "low": float(pd.to_numeric(filtered["low"]).min()),
        "close": float(filtered.iloc[-1]["close"]),
        "volume": float(pd.to_numeric(filtered["volume"]).sum()),
    }
    diffs = {field: float(aggregate[field] - float(reference[field])) for field in aggregate}
    # Prices are tick-priced; volume is authoritative and must match exactly.
    price_ok = all(abs(diffs[field]) <= 1e-8 for field in ("open", "high", "low", "close"))
    volume_ok = abs(diffs["volume"]) <= 0.0
    status = "PASSED" if price_ok and volume_ok else "BLOCKED_BY_MINUTE_DAILY_PARITY"
    return {"symbol": symbol, "date": session, "status": status, "reason": None if status == "PASSED" else "DAILY_OHLCV_MISMATCH",
            "bar_count": int(len(filtered)), "missing_minutes": missing_minutes, "zero_volume_bars": int((pd.to_numeric(filtered["volume"]) == 0).sum()),
            "first_timestamp": str(ts_regular.iloc[0]), "last_timestamp": str(ts_regular.iloc[-1]),
            "duplicate_timestamp": duplicate_count, "future_bars": future_count, "daily_aggregate": aggregate,
            "daily_reference": {field: float(reference[field]) for field in aggregate}, "diff": diffs,
            "price_parity": price_ok, "volume_parity": volume_ok, "sparse_minutes_allowed": bool(missing_minutes and price_ok and volume_ok)}


def run_pilot(root: Path | str, *, force_refresh: bool = True) -> dict[str, Any]:
    root = Path(root).resolve()
    try:
        from dotenv import load_dotenv
        load_dotenv(root / ".env")
    except Exception:
        # The client will fail closed with a redacted credential error if the
        # environment is not configured; secrets are never read into output.
        pass
    selected, dates, liquidity = _pilot_universe_and_dates(root)
    transport, calls = _transport_counter()
    client = TossOpenApiClient(transport=transport)
    sessions: list[dict[str, Any]] = []
    started = datetime.now(tz=KST)
    for symbol in selected:
        for session in dates:
            try:
                frame, fetch_meta = _fetch_session(client, root, symbol, session, force=force_refresh)
                result = _session_validation(root, symbol, session, frame)
                result.update(fetch_meta)
            except Exception as exc:
                result = {"symbol": symbol, "date": session, "status": "BLOCKED_BY_MINUTE_DAILY_PARITY", "reason": type(exc).__name__}
            sessions.append(result)
    passed = all(row.get("status") == "PASSED" for row in sessions) and len(sessions) == 15
    summary = {
        "mode": "CURRENT_MODELS_5M_DATA_PILOT",
        "period": {"start": START.date().isoformat(), "end": END.date().isoformat()},
        "selected_symbols": selected, "selected_dates": dates, "liquidity_median_d1_adv_krw": liquidity,
        "session_count": len(sessions), "passed_sessions": sum(row.get("status") == "PASSED" for row in sessions),
        "status": "PILOT_PASSED" if passed else "BLOCKED_BY_MINUTE_DAILY_PARITY",
        "started_at": started.isoformat(), "finished_at": datetime.now(tz=KST).isoformat(),
        "api_calls": calls, "oauth_post_only": calls.get("POST", 0) <= 1, "broker_mutation_calls": 0,
        "sessions": sessions,
        "full_collection_started": False,
        "reason": None if passed else "At least one pilot session failed timestamp or official daily OHLCV parity.",
    }
    out = root / "runtime/current_models_5m_validation"
    out.mkdir(parents=True, exist_ok=True)
    (out / "pilot_summary.json").write_text(json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    (out / "intraday_collection_manifest.json").write_text(json.dumps({"scope": "pilot_only", "sessions": sessions}, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return summary


__all__ = ["run_pilot"]
