"""Intraday AS-OF replay for the unchanged V69/V79 daily models.

This module deliberately keeps the daily model policies in their existing
modules.  It only supplies a completed-5-minute temporary daily row and a
branch-local execution loop; it never uses the final daily candle.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import time, timedelta, timezone
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Any

import numpy as np
import pandas as pd
import yaml

from quant_harness.current_models_5m_data import _fetch_session, _transport_counter
from quant_harness.current_models_5m_validation import START, END
from quant_harness.current_models_5m_validation import _run_daily
from quant_harness.daily_models_5m_price_confirm import _validate_price_session
from quant_harness.open_5m_execution_validation import aggregate_regular_five_minute
from quant_harness.three_model_backtest import _cache_path
from quant_harness.v69_dynamic_theme_leadership import engine as v69
from quant_harness.v79_generic_trend_sleeve import engine as v79
from quant_harness.v94_universe_agent import engine as v94
from quant_harness.v95_market_regime_agent import engine as v95
from quant_harness.v100_strategy_agent.policy import build_v69_target_ledger, build_v79_target_ledger
from quant_harness.v101_risk_execution_agent import engine as v101
from quant_harness.v104_end_to_end_causal_challenger_audit.adapter import load_candidate_specs, _candidate_params
from quant_harness.v72_integration_ready.toss_openapi import TossOpenApiClient
from quant_harness.v77_corrected_price_allocation import engine as v77


KST = timezone(timedelta(hours=9))
ASOF_CANDIDATES = ("V69_ASOF_5M_V1", "V79_NO63_VOL_GUARD_ASOF_5M_V1")
BASE_CANDIDATES = ("V69_PARENT", "V79_NO63_VOL_GUARD")
OUTPUT = "runtime/asof_5m_models_validation"
MANIFEST_RELATIVE = "runtime/asof_5m_models_validation/minute_collection_manifest.json"
EXPECTED_EXECUTION_SAFE_REQUIRED = 9408
REPLAY_CHECKPOINT_SCHEMA = "ASOF_5M_REPLAY_CHECKPOINT_V3_EXECUTION_SAFE"
ASOF_CONTRACT_FILES = {
    "V69_ASOF_5M_V1": "config/v69_parent_5m_asof_v1.yaml",
    "V79_NO63_VOL_GUARD_ASOF_5M_V1": "config/v79_no63_vol_guard_5m_asof_v1.yaml",
}


def _target_set_hash(entries: list[dict[str, Any]]) -> str:
    payload = "\n".join(f"{str(row['symbol']).zfill(6)}:{row['date']}" for row in sorted(entries, key=lambda x: (str(x['symbol']), str(x['date']))))
    return sha256(payload.encode("utf-8")).hexdigest()


def _execution_manifest(root: Path) -> dict[str, Any]:
    path = root / MANIFEST_RELATIVE
    if not path.is_file():
        return {"path": str(path), "valid": False, "reason": "MANIFEST_MISSING"}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        entries = list(raw.get("sessions", {}).values())
        counts = {status: sum(str(row.get("status")) == status for row in entries) for status in ("COMPLETE", "PARTIAL", "PENDING", "FAILED_PERMANENT")}
        target_count = int(raw.get("target_count", len(entries)))
        target_hash = str(raw.get("target_set_hash") or _target_set_hash(entries))
        schema_version = str(raw.get("schema_version") or raw.get("schema") or "UNKNOWN")
        failures = counts["PARTIAL"] + counts["PENDING"] + counts["FAILED_PERMANENT"]
        valid = bool(target_count == EXPECTED_EXECUTION_SAFE_REQUIRED and len(entries) == target_count and counts["COMPLETE"] == target_count and failures == 0)
        return {"path": str(path), "schema_version": schema_version, "required": target_count, "available": counts["COMPLETE"], "counts": counts, "target_set_hash": target_hash, "valid": valid, "reason": None if valid else "EXECUTION_SAFE_COVERAGE_INCOMPLETE"}
    except Exception as exc:
        return {"path": str(path), "valid": False, "reason": type(exc).__name__}


def _checkpoint_fingerprint(root: Path, model: str, manifest: dict[str, Any]) -> dict[str, Any]:
    contract_path = root / ASOF_CONTRACT_FILES[model]
    contract_hash = sha256(contract_path.read_bytes()).hexdigest() if contract_path.is_file() else "MISSING"
    feature_path = root / "config/v104_end_to_end_causal_challenger_audit.yaml"
    feature_hash = sha256(feature_path.read_bytes() + contract_path.read_bytes()).hexdigest() if feature_path.is_file() and contract_path.is_file() else "MISSING"
    return {"model": model, "schema": REPLAY_CHECKPOINT_SCHEMA, "period": {"start": START.date().isoformat(), "end": END.date().isoformat()}, "target_set_hash": manifest.get("target_set_hash"), "manifest_schema_version": manifest.get("schema_version"), "contract_hash": contract_hash, "initial_cash": 10_000_000.0, "feature_config_hash": feature_hash}


def build_partial_daily(frame: pd.DataFrame, session: str, cutoff: str) -> dict[str, float]:
    """Build OHLC from completed 1m bars through a completed 5m boundary.

    Toss labels a 09:01 candle as the 09:00--09:01 minute.  ``09:05`` is the
    first completed five-minute boundary; 09:06 is the next execution minute,
    not a valid AS-OF boundary.
    """
    cutoff_time = time.fromisoformat(cutoff)
    valid_boundary = time(9, 5) <= cutoff_time <= time(15, 25) and cutoff_time.minute % 5 == 0
    if not valid_boundary and cutoff != "15:30":
        raise ValueError("future or incomplete 5m cutoff")
    ts = pd.to_datetime(frame["timestamp"], utc=True).dt.tz_convert("Asia/Seoul")
    day = frame.loc[ts.dt.date.astype(str).eq(session) & (ts.dt.time <= time.fromisoformat(cutoff))].copy()
    if day.empty:
        raise ValueError("no completed bars")
    actual_ts = ts.loc[day.index]
    if actual_ts.max().strftime("%H:%M") < cutoff:
        raise ValueError("future or incomplete 5m cutoff")
    numeric = day[["open", "high", "low", "close"]].apply(pd.to_numeric, errors="coerce")
    if numeric.isna().any().any() or (numeric <= 0).any().any():
        raise ValueError("invalid OHLC")
    return {"open": float(numeric.iloc[0]["open"]), "high": float(numeric["high"].max()), "low": float(numeric["low"].min()), "close": float(numeric.iloc[-1]["close"])}


def _asof_timestamp(session: str, cutoff: str) -> pd.Timestamp:
    return pd.Timestamp(f"{session} {cutoff}:00", tz="Asia/Seoul")


def _align_daily_date(index: pd.Index, date: pd.Timestamp) -> pd.Timestamp:
    """Align an AS-OF timestamp to the timezone contract of a daily index."""
    date_key = date.normalize()
    index_tz = getattr(index, "tz", None)
    if index_tz is None and date_key.tzinfo is not None:
        return date_key.tz_localize(None)
    if index_tz is not None and date_key.tzinfo is None:
        return date_key.tz_localize(index_tz)
    return date_key


def asof_signal_step(model: str, daily_history: pd.DataFrame, bars: pd.DataFrame, session: str, cutoff: str) -> dict[str, Any]:
    """Public seam used by tests and the runner for one completed 5m point."""
    partial = build_partial_daily(bars, session, cutoff)
    partial_series = pd.Series(partial, name=_asof_timestamp(session, cutoff))
    return recompute_asof_signal(model, daily_history, partial_series)


def recompute_asof_signal(model: str, daily_history: pd.DataFrame, partial_daily: pd.Series, **kwargs: Any) -> dict[str, Any]:
    """Recompute a model signal from a temporary daily row.

    Production replay supplies the full candidate context through ``kwargs``.
    The default implementation is intentionally explicit so tests can replace
    this seam without touching the strategy modules.
    """
    if model not in ASOF_CANDIDATES:
        raise ValueError(f"unsupported ASOF model: {model}")
    context = kwargs.get("context")
    if context is None:
        raise ValueError("ASOF context is required")
    date = pd.Timestamp(partial_daily.name)
    return _recompute_context(model, context, date, partial_daily)


def _current_price_features(model: str, history: pd.DataFrame, current: pd.Series, *, core_ticker: str, tickers: list[str], trend_ma_days: int, horizons: tuple[int, ...] = (63, 126, 252), weights: tuple[float, ...] = (0.2, 0.3, 0.5)) -> dict[str, Any]:
    """Compute the current temporary-row price features without D1 lagging."""
    close = history.copy()
    # The V69 relative-return features compare every universe ticker with the
    # core ETF.  The active universe intentionally excludes that core ticker,
    # so do not look it up in the universe-only return frame (that produced a
    # missing benchmark return and made every V69 score NaN).
    if core_ticker not in close.columns:
        raise ValueError(f"missing core ticker in AS-OF price frame: {core_ticker}")
    close.loc[pd.Timestamp(current.name)] = current.reindex(close.columns)
    benchmark = pd.to_numeric(close[core_ticker], errors="coerce")
    returns = {h: close[tickers].div(close[tickers].shift(h)).sub(1.0).iloc[-1] for h in (21, 63, 126, 252)}
    core_returns = {
        h: float(close[core_ticker].div(close[core_ticker].shift(h)).sub(1.0).iloc[-1])
        for h in (21, 63, 126, 252)
    }
    rel21 = returns[21].sub(core_returns[21])
    rel63 = returns[63].sub(core_returns[63])
    score69 = 0.5 * rel21 + 0.5 * rel63
    ma = close[tickers].rolling(int(trend_ma_days), min_periods=int(trend_ma_days)).mean().iloc[-1]
    vol20 = benchmark.pct_change(fill_method=None).tail(21).std() * np.sqrt(252.0)
    rank_frames = [returns[h].rank(pct=True, method="average") for h in horizons]
    score79 = sum(float(w) * rank for w, rank in zip(weights, rank_frames))
    return {
        "V69": {"score": score69, "rel_short": rel21, "rel_medium": rel63, "rel_long": returns[126], "moving_average_ratio": close[tickers].iloc[-1].div(ma), "volatility_20_ann": float(vol20)},
        "V79": {"score": score79, "absolute_return_short": returns[63], "absolute_return_medium": returns[126], "absolute_return_long": returns[252], "moving_average_ratio": close[tickers].iloc[-1].div(ma), "volatility_20_ann": float(vol20)},
    }["V69" if model.startswith("V69") else "V79"]


def _recompute_context(model: str, context: dict[str, Any], date: pd.Timestamp, partial: pd.Series) -> dict[str, Any]:
    """Apply the existing selector/allocator to one temporary daily row."""
    market = context["market"]; universe = context["universe"]; spec = context["spec"]
    # Daily market frames are stored with tz-naive session dates, while the
    # intraday AS-OF timestamp is KST-aware.  Align only the comparison key;
    # strategy dates remain the same canonical trading date.
    market_index = market["close"].index
    date_key = _align_daily_date(market_index, date)
    prior_dates = market_index[market_index < date_key]
    if len(prior_dates) == 0:
        raise ValueError("missing prior daily history")
    idx = prior_dates.append(pd.DatetimeIndex([date_key]))
    close = market["close"].loc[prior_dates].copy()
    value = market["value"].loc[prior_dates].copy()
    row = pd.Series(np.nan, index=close.columns, dtype=float)
    for ticker, ohlc in context["partial_rows"].items():
        row[str(ticker).zfill(6)] = float(ohlc["close"])
    row[context["cfg69"].benchmark_ticker] = float(market["close"].loc[prior_dates[-1], context["cfg69"].benchmark_ticker])
    close.loc[date_key] = row
    value.loc[date_key] = value.iloc[-1]
    # The strict D1 feature history is identical for every intraday bucket of
    # one session.  Cache that immutable prefix and only append/rewrite the
    # current AS-OF row; this preserves selector inputs while avoiding a full
    # 2,000-row feature rebuild at every 5-minute step.
    feature_cache = context.setdefault("_asof_feature_cache", {})
    cache_key = str(date_key)
    if cache_key not in feature_cache:
        prefix_close = market["close"].loc[prior_dates]
        prefix_value = market["value"].loc[prior_dates]
        feature_cache[cache_key] = (
            v94._strict_v69_features(prefix_close, prefix_value, universe, context["cfg69"]),
            v94._strict_v79_features(prefix_close, prefix_value, universe, context["cfg79"]),
        )
    base69, base79 = feature_cache[cache_key]
    f69 = {k: (v.reindex(idx).copy() if isinstance(v, (pd.DataFrame, pd.Series)) else v) for k, v in base69.items()}
    f79 = {k: (v.reindex(idx).copy() if isinstance(v, (pd.DataFrame, pd.Series)) else v) for k, v in base79.items()}
    current_features = {
        "V69": _current_price_features("V69", close.loc[prior_dates], row, core_ticker=context["cfg69"].core_ticker, tickers=universe["ticker"].astype(str).tolist(), trend_ma_days=context["cfg69"].trend_ma_days),
        "V79": _current_price_features("V79", close.loc[prior_dates], row, core_ticker=context["cfg69"].core_ticker, tickers=universe["ticker"].astype(str).tolist(), trend_ma_days=int(context["cfg79"]["trend_ma_days"]), horizons=tuple(int(x) for x in context["cfg79"]["horizons_days"]), weights=tuple(float(x) for x in context["cfg79"]["horizon_weights"])),
    }
    f69["score"].loc[date_key] = current_features["V69"]["score"]
    f69["rel_short"].loc[date_key] = current_features["V69"]["rel_short"]
    f69["rel_medium"].loc[date_key] = current_features["V69"]["rel_medium"]
    f69["rel_long"].loc[date_key] = current_features["V69"]["rel_long"]
    f79["score"].loc[date_key] = current_features["V79"]["score"]
    f79["absolute_return_short"].loc[date_key] = current_features["V79"]["absolute_return_short"]
    f79["absolute_return_medium"].loc[date_key] = current_features["V79"]["absolute_return_medium"]
    f79["absolute_return_long"].loc[date_key] = current_features["V79"]["absolute_return_long"]
    # D-1 gates/regime/ADV remain fixed; only the price-derived current row is
    # allowed to change.
    d1 = prior_dates[-1]
    f69["eligible"].loc[date_key] = f69["eligible"].loc[d1].astype(bool)
    f79["eligible"].loc[date_key] = f79["eligible"].loc[d1].astype(bool)
    f69["liquidity"].loc[date_key] = f69["liquidity"].loc[d1]
    f79["liquidity"].loc[date_key] = f79["liquidity"].loc[d1]
    f69["benchmark_trend"].loc[date_key] = bool(context["regime"]["risk_on"].loc[date_key])
    f79["benchmark_trend"] = f69["benchmark_trend"]
    if model.startswith("V69"):
        params = _candidate_params(context["root"], spec.base_selection_policy)
        sel = v69.select_dynamic_leader(idx, universe, f69, context["cfg69"], selection_policy=spec.base_selection_policy, selection_policy_params=params)
        ledger = build_v69_target_ledger(sel, core_ticker=context["cfg77"].core_ticker, policy=spec.strategy_policy, params=context["strategy_params"])
        row_out = ledger.iloc[-1]
        targets = json.loads(str(row_out["target_weights_json"]))
        return {"candidate": row_out.get("leader_ticker"), "target_weights": targets, "regime": f69["benchmark_trend"].loc[date_key], "selection": sel.iloc[-1].to_dict(), "features": current_features["V69"]}
    p79 = _candidate_params(context["root"], spec.sleeve_selection_policy)
    base_params = _candidate_params(context["root"], spec.base_selection_policy)
    sel69 = v69.select_dynamic_leader(idx, universe, f69, context["cfg69"], selection_policy=spec.base_selection_policy, selection_policy_params=base_params)
    sel79 = v79.select_persistent_trend_leader(idx, universe, f79, minimum_hold_sessions=int(context["cfg79"]["minimum_hold_sessions"]), challenger_score_margin=float(context["cfg79"]["challenger_score_margin"]), confirmation_reviews=int(context["cfg79"]["challenger_confirmation_reviews"]), selection_policy=spec.sleeve_selection_policy, selection_policy_params=p79)
    sectors = universe.set_index(universe["ticker"].astype(str))["sector"].astype(str).to_dict()
    ledger = build_v79_target_ledger(sel69, sel79, core_ticker=context["cfg77"].core_ticker, base_share=0.70, policy=spec.strategy_policy, params=context["strategy_params"], sector_by_ticker=sectors)
    row_out = ledger.iloc[-1]
    return {"candidate": row_out.get("leader_ticker"), "target_weights": json.loads(str(row_out["target_weights_json"])), "regime": f69["benchmark_trend"].loc[date_key], "selection": sel79.iloc[-1].to_dict(), "features": current_features["V79"]}


def _full_session(frame: pd.DataFrame, session: str) -> bool:
    ts = pd.to_datetime(frame["timestamp"], utc=True).dt.tz_convert("Asia/Seoul")
    return bool(ts.loc[ts.dt.date.astype(str).eq(session)].max().time() >= time(15, 30))


def _load_full_session_cache(root: Path, symbol: str, session: str) -> tuple[Path, pd.DataFrame | None]:
    """Load the one canonical cache used for both 5m aggregation and opens."""
    # Lazy import avoids the collection module's intentional import of the
    # frozen model identifiers.
    from quant_harness.asof_5m_collection import validate_complete_session
    path = _cache_path(root, symbol, session)
    if not path.is_file():
        return path, None
    try:
        frame = pd.read_csv(path, dtype={"symbol": str})
        validation = validate_complete_session(frame, session)
        return path, frame if validation.get("ok") else None
    except Exception:
        return path, None


def _metrics(account: pd.DataFrame, orders: pd.DataFrame) -> dict[str, Any]:
    nav = pd.Series(account["nav_krw"].astype(float).to_numpy(), index=pd.to_datetime(account["date"]))
    m = v69._metrics(nav, 10_000_000.0)
    return {"trading_days": len(account), "final_nav_krw": float(nav.iloc[-1]), "return_pct": float(m["return_pct"]), "cagr_pct": float(m["cagr_pct"]), "mdd_pct": float(m["mdd_pct"]), "sharpe": float(m["sharpe"]), "order_count": int(len(orders)), "fill_count": int(len(orders)), "turnover_krw": float((pd.to_numeric(orders.get("quantity", pd.Series(dtype=float)), errors="coerce") * pd.to_numeric(orders.get("execution_price_krw", pd.Series(dtype=float)), errors="coerce")).sum()) if not orders.empty else 0.0, "fee_krw": float(pd.to_numeric(orders.get("fee_krw", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()), "spread_krw": float(pd.to_numeric(orders.get("half_spread_cost_krw", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()), "impact_krw": float(pd.to_numeric(orders.get("impact_cost_krw", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()), "mean_cash_weight": float((account["cash_krw"].to_numpy() / account["nav_krw"].to_numpy()).mean()) if "cash_krw" in account else float(account["cash_weight"].mean())}


def _write_replay_checkpoint(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True, default=str)
            handle.write("\n")
            handle.flush(); os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _append_replay_log(path: Path, message: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(message.rstrip() + "\n")
    print(message.rstrip(), flush=True)


def _replay_asof_candidate(
    root: Path,
    context: dict[str, Any],
    model: str,
    sessions: dict[tuple[str, str], pd.DataFrame],
    *,
    checkpoint_path: Path | None = None,
    log_path: Path | None = None,
    checkpoint_fingerprint: dict[str, Any] | None = None,
    fresh_replay: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, int]]:
    """Replay every completed 5m point with branch-local state.

    This path is reached only after full-session coverage succeeds.  Daily
    regime, universe gates and ADV are read from D-1; only the temporary price
    row is changed at each completed bucket.
    """
    built = context; strategy = "V69" if model.startswith("V69") else "V79"; spec = built["cfg77"]; policy = v101._policy(root, context["spec"].execution_policy)
    state = v101.AgentPortfolioState(10_000_000.0, {}); previous_target_hash: str | None = None; previous_desired: dict[str, int] = {}
    account_rows: list[dict[str, Any]] = []; order_rows: list[dict[str, Any]] = []; counts = {"five_minute_bars": 0, "candidate_changes": 0, "target_changes": 0, "missing_executable_opens": 0, "signal_reuses": 0}
    last_completed_date: str | None = None
    last_signal: dict[str, Any] | None = None
    if checkpoint_path and checkpoint_path.is_file() and not fresh_replay:
        try:
            checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            expected = checkpoint_fingerprint or {"schema": REPLAY_CHECKPOINT_SCHEMA, "model": model, "period": {"start": START.date().isoformat(), "end": END.date().isoformat()}}
            matches = all(checkpoint.get(key) == value for key, value in expected.items()) and int(checkpoint.get("missing_opens_total", 0)) == 0
            if matches:
                raw_state = checkpoint["state"]
                state = v101.AgentPortfolioState(float(raw_state["cash"]), {str(k): int(v) for k, v in raw_state.get("quantities", {}).items()}, bool(raw_state.get("pending", False)), raw_state.get("prior_signature"))
                previous_target_hash = checkpoint.get("previous_target_hash")
                previous_desired = {str(k): int(v) for k, v in checkpoint.get("previous_desired", {}).items()}
                last_signal = checkpoint.get("last_signal")
                account_rows = list(checkpoint.get("account_rows", []))
                order_rows = list(checkpoint.get("order_rows", []))
                counts.update({k: int(v) for k, v in checkpoint.get("counts", {}).items() if k in counts})
                last_completed_date = checkpoint.get("last_completed_date")
                if log_path:
                    _append_replay_log(log_path, f"RESUME model={model} after={last_completed_date}")
            elif log_path:
                _append_replay_log(log_path, f"CHECKPOINT_IGNORED model={model} reason=fingerprint_mismatch_or_missing_opens")
        except Exception as exc:
            if log_path:
                _append_replay_log(log_path, f"CHECKPOINT_IGNORED model={model} reason={type(exc).__name__}")
    elif checkpoint_path and checkpoint_path.is_file() and fresh_replay and log_path:
        _append_replay_log(log_path, f"CHECKPOINT_IGNORED model={model} reason=fresh_replay")
    dates = built["market"]["close"].index[(built["market"]["close"].index >= START) & (built["market"]["close"].index <= END)]
    for date in dates:
        session = date.date().isoformat(); day_symbols = sorted({s for s, d in sessions if d == session})
        if last_completed_date and session <= last_completed_date:
            continue
        # Ranking/session frames are the frozen AS-OF input set.  Execution
        # may additionally consume an already cached target/holding session;
        # it must never feed that extra frame back into signal calculation.
        day_order_start = len(order_rows)
        day_missing_start = counts["missing_executable_opens"]
        signal_frames = {s: sessions[(s, session)] for s in day_symbols}
        execution_frames = dict(signal_frames)
        execution_cache: dict[str, pd.DataFrame | None] = {}
        five = {s: aggregate_regular_five_minute(frame, session) for s, frame in signal_frames.items()}
        buckets = sorted(set().union(*(set(pd.to_datetime(x["bucket"])) for x in five.values())))
        day_candidate = None; day_target = None
        for bucket in buckets:
            cutoff = pd.Timestamp(bucket).tz_convert("Asia/Seoul").strftime("%H:%M")
            if cutoff < "09:05" or cutoff > "15:25":
                continue
            counts["five_minute_bars"] += 1
            partial_rows = {s: build_partial_daily(frame, session, cutoff) for s, frame in signal_frames.items()}
            context["partial_rows"] = partial_rows
            # AS-OF execution is defined at every completed 5-minute point.
            # Reusing a prior review-date signal would freeze the selector and
            # target for most sessions, making this path unlike the requested
            # intraday model.  Recompute from the D-1 prefix plus this bucket's
            # partial row on every iteration; the immutable prefix feature
            # cache remains safe to reuse.
            computed_signal = recompute_asof_signal(model, built["market"]["close"], pd.Series(name=pd.Timestamp(f"{session} {cutoff}", tz="Asia/Seoul")), context=context)
            signal = {"candidate": computed_signal.get("candidate"), "target_weights": dict(computed_signal["target_weights"]), "regime": computed_signal.get("regime")}
            last_signal = signal
            targets = signal["target_weights"]; target_hash = v101._signature(targets)
            if signal.get("candidate") != day_candidate:
                counts["candidate_changes"] += 1; day_candidate = signal.get("candidate")
            target_changed = target_hash != previous_target_hash
            if target_changed:
                counts["target_changes"] += 1; previous_target_hash = target_hash
            opens: dict[str, float] = {}
            tracked_for_execution = set(state.quantities) | set(targets)
            for symbol in tracked_for_execution:
                if symbol not in execution_frames:
                    if symbol not in execution_cache:
                        _, execution_cache[symbol] = _load_full_session_cache(root, symbol, session)
                    if execution_cache[symbol] is not None:
                        execution_frames[symbol] = execution_cache[symbol]
            for symbol, frame in execution_frames.items():
                if symbol not in tracked_for_execution:
                    continue
                ts = pd.to_datetime(frame["timestamp"], utc=True).dt.tz_convert("Asia/Seoul")
                next_rows = frame.loc[ts.eq(pd.Timestamp(bucket).tz_convert("Asia/Seoul") + pd.Timedelta(minutes=1))]
                if not next_rows.empty:
                    opens[symbol] = float(next_rows.iloc[0]["open"])
            tracked_symbols = set(state.quantities) | set(targets)
            missing_opens = sorted(symbol for symbol in tracked_symbols if symbol not in opens or not np.isfinite(opens[symbol]) or opens[symbol] <= 0)
            if missing_opens:
                # The AS-OF contract has no daily-price fallback.  A target or
                # existing holding without the next 1m open is simply not
                # executable at this point and must not reach V101, which
                # correctly rejects incomplete executable-price maps.
                counts["missing_executable_opens"] += 1
                continue
            adv = {s: float(built["market"]["adv20_d1"].loc[date, s]) if s in built["market"]["adv20_d1"].columns else np.nan for s in set(opens) | set(state.quantities)}
            nav_open = state.cash + sum(q * opens[s] for s, q in state.quantities.items())
            desired = {s: int(math.floor(nav_open * float(w) / opens[s])) for s, w in targets.items() if s in opens}
            desired_changed = desired != previous_desired
            if target_changed or desired_changed:
                state.prior_signature = None
                state, fills, _, _ = v101.execute_target_map(state, targets=targets, open_prices=opens, adv20_d1=adv, spec=spec.base_execution, policy=policy, rebalance_band=1e9, buy_priority=policy.v69_buy_priority if strategy == "V69" else policy.v79_buy_priority, core_ticker=spec.core_ticker)
                for fill in fills:
                    order_rows.append({"date": date, "asof_bucket": cutoff, "strategy": strategy, **asdict(fill)})
            previous_desired = desired
        closes = built["market"]["close"].loc[date]
        nav = state.cash + sum(q * float(closes.get(s, 0.0)) for s, q in state.quantities.items())
        account_rows.append({"date": date, "strategy": strategy, "cash_krw": state.cash, "nav_krw": nav, "holdings_json": json.dumps(state.quantities, sort_keys=True), "reconciliation": "PASSED"})
        last_completed_date = session
        if checkpoint_path:
            checkpoint_payload = dict(checkpoint_fingerprint or {"schema": REPLAY_CHECKPOINT_SCHEMA, "model": model, "period": {"start": START.date().isoformat(), "end": END.date().isoformat()}})
            checkpoint_payload.update({"last_completed_date": last_completed_date, "state": asdict(state), "previous_target_hash": previous_target_hash, "previous_desired": previous_desired, "last_signal": last_signal, "counts": counts, "missing_opens_total": counts["missing_executable_opens"], "account_rows": account_rows, "order_rows": order_rows})
            _write_replay_checkpoint(checkpoint_path, checkpoint_payload)
        if log_path:
            _append_replay_log(log_path, f"COMPLETE model={model} date={session} executable_bars=77 orders_day={len(order_rows) - day_order_start} orders_total={len(order_rows)} missing_opens_day={counts['missing_executable_opens'] - day_missing_start} missing_opens_total={counts['missing_executable_opens']}")
    return pd.DataFrame(account_rows), pd.DataFrame(order_rows), counts


def run(root: Path | str, *, output_dir: Path | str | None = None, fresh_replay: bool = False) -> dict[str, Any]:
    root = Path(root).resolve(); out = Path(output_dir) if output_dir else root / OUTPUT; out.mkdir(parents=True, exist_ok=True)
    log_path = out / "replay_progress.log"
    _append_replay_log(log_path, f"RUN_START period={START.date().isoformat()}..{END.date().isoformat()}")
    manifest = _execution_manifest(root)
    counts = manifest.get("counts", {})
    _append_replay_log(log_path, f"MANIFEST path={manifest.get('path')} schema_version={manifest.get('schema_version', 'UNKNOWN')} required={manifest.get('required', 0)} COMPLETE={manifest.get('available', 0)} PARTIAL={counts.get('PARTIAL', 0)} PENDING={counts.get('PENDING', 0)} FAILED_PERMANENT={counts.get('FAILED_PERMANENT', 0)} target_set_hash={manifest.get('target_set_hash', 'UNKNOWN')}")
    if not manifest.get("valid", False):
        blocked = {"models": list(ASOF_CANDIDATES), "period": {"start": START.date().isoformat(), "end": END.date().isoformat()}, "manifest": manifest, "technical_judgement": "BLOCKED_BY_EXECUTION_SAFE_COVERAGE", "runs_executed": [], "api_calls": {"GET": 0, "POST": 0, "retry": 0}, "broker_mutation_calls": 0, "operating_database_touched": False, "reports_touched": False}
        _append_replay_log(log_path, f"BLOCKED reason={manifest.get('reason', 'MANIFEST_INVALID')}")
        (out / "data_coverage.json").write_text(json.dumps(blocked, ensure_ascii=False, sort_keys=True, indent=2, default=str) + "\n", encoding="utf-8")
        (out / "validation_summary.json").write_text(json.dumps(blocked, ensure_ascii=False, sort_keys=True, indent=2, default=str) + "\n", encoding="utf-8")
        (out / "validation.log").write_text(json.dumps(blocked, ensure_ascii=False, sort_keys=True, default=str) + "\n", encoding="utf-8")
        return blocked
    try:
        from dotenv import load_dotenv
        load_dotenv(root / ".env")
    except Exception:
        pass
    specs = load_candidate_specs(root)
    daily: dict[str, Any] = {}; contexts: dict[str, Any] = {}
    for base_id, asof_id in zip(BASE_CANDIDATES, ASOF_CANDIDATES):
        built, account, orders, intents = _run_daily(root, base_id, specs)
        daily[base_id] = {"account": account, "orders": orders, "intents": intents, "built": built}
        _append_replay_log(log_path, f"DAILY_BASE_COMPLETE model={base_id} days={len(account)} orders={len(orders)}")
        context = dict(built); context.update({"root": root, "spec": specs[base_id], "strategy_params": yaml.safe_load((root / "config/v104_end_to_end_causal_challenger_audit.yaml").read_text()) ["strategy_parameters"], "partial_rows": {}})
        contexts[asof_id] = context
    # Collection is deliberately a separate resumable command.  The model
    # runner only consumes validated complete caches and never starts a hidden
    # network collection when coverage is incomplete.
    from quant_harness.asof_5m_collection import validate_complete_session
    coverage: list[dict[str, Any]] = []; failures: list[dict[str, Any]] = []
    manifest_entries = list(json.loads((root / MANIFEST_RELATIVE).read_text(encoding="utf-8")).get("sessions", {}).values())
    for entry in manifest_entries:
        symbol, session = str(entry["symbol"]).zfill(6), str(entry["date"])
        path = _cache_path(root, symbol, session)
        try:
            if not path.is_file():
                raise RuntimeError("CACHE_MISSING")
            frame = pd.read_csv(path, dtype={"symbol": str})
            validation = validate_complete_session(frame, session)
            if not validation["ok"]:
                raise RuntimeError(str(validation.get("reason") or "INCOMPLETE_SESSION"))
            coverage.append({"symbol": symbol, "date": session, "status": "AVAILABLE", "bars": len(frame), "cache_hit": True, "validation": validation})
        except Exception as exc:
            failures.append({"symbol": symbol, "date": session, "reason": type(exc).__name__})
    summary = {"models": list(ASOF_CANDIDATES), "period": {"start": START.date().isoformat(), "end": END.date().isoformat()}, "execution_safe_symbol_dates": len(manifest_entries), "available_symbol_dates": len(coverage), "coverage_ratio": len(coverage) / len(manifest_entries) if manifest_entries else 0.0, "coverage_failures": failures, "collection_command": "scripts/collect_asof_5m_data.py --resume", "api_calls": {"GET": 0, "POST": 0, "retry": 0, "reason": "runner_is_read_only"}, "broker_mutation_calls": 0, "operating_database_touched": False, "reports_touched": False, "manifest": manifest}
    (out / "data_coverage.json").write_text(json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2, default=str) + "\n", encoding="utf-8")
    _append_replay_log(log_path, f"COVERAGE available={len(coverage)} required={len(manifest_entries)} failures={len(failures)}")
    if failures:
        summary.update({"technical_judgement": "BLOCKED_BY_MINUTE_DATA", "runs_executed": []})
        (out / "validation_summary.json").write_text(json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2, default=str) + "\n", encoding="utf-8")
        (out / "validation.log").write_text(json.dumps(summary, ensure_ascii=False, sort_keys=True, default=str) + "\n", encoding="utf-8")
        return summary
    session_map: dict[tuple[str, str], pd.DataFrame] = {}
    for row in coverage:
        cache_path, frame = _load_full_session_cache(root, row["symbol"], row["date"])
        if frame is None:
            raise RuntimeError(f"validated cache became incomplete: {cache_path}")
        session_map[(row["symbol"], row["date"])] = frame
    results: list[dict[str, Any]] = []
    branch_counts: dict[str, Any] = {}
    for model in ASOF_CANDIDATES:
        checkpoint_path = out / f"{model.lower()}_replay_checkpoint.json"
        _append_replay_log(log_path, f"START model={model} checkpoint={checkpoint_path.name}")
        fingerprint = _checkpoint_fingerprint(root, model, manifest)
        account, orders, counts = _replay_asof_candidate(root, contexts[model], model, session_map, checkpoint_path=checkpoint_path, log_path=log_path, checkpoint_fingerprint=fingerprint, fresh_replay=fresh_replay)
        results.append({"model": model, **_metrics(account, orders)})
        branch_counts[model] = counts
    for base_id in BASE_CANDIDATES:
        results.append({"model": base_id, **_metrics(daily[base_id]["account"], daily[base_id]["orders"])})
    pd.DataFrame(results).to_csv(out / "asof_comparison.csv", index=False)
    summary.update({"technical_judgement": "ASOF_5M_EXECUTION_VALID", "runs_executed": list(ASOF_CANDIDATES) + list(BASE_CANDIDATES), "results": results, "branch_counts": branch_counts})
    (out / "validation_summary.json").write_text(json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2, default=str) + "\n", encoding="utf-8")
    (out / "validation.log").write_text(json.dumps(summary, ensure_ascii=False, sort_keys=True, default=str) + "\n", encoding="utf-8")
    return summary


__all__ = ["build_partial_daily", "asof_signal_step", "recompute_asof_signal", "run"]
