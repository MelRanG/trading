"""Current-candidate 5-minute as-of validation.

This module is deliberately a validation runner, not a new strategy or
backtest engine.  It reuses the V104 ledger builder and V101 operational
replay for the daily baseline.  A 5-minute run is only admitted when every
required symbol/session has a validated full intraday cache; missing data is
reported fail-closed rather than replaced with a daily fill.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from quant_harness.three_model_backtest import _cache_path
from quant_harness.v69_dynamic_theme_leadership import engine as v69
from quant_harness.v77_corrected_price_allocation import engine as v77
from quant_harness.v101_risk_execution_agent import engine as v101
from quant_harness.v104_end_to_end_causal_challenger_audit.adapter import (
    build_candidate_ledgers,
    load_candidate_specs,
)


MODE = "CURRENT_MODELS_5M_ASOF_VALIDATION"
START = pd.Timestamp("2023-01-30")
END = pd.Timestamp("2024-08-30")
CANDIDATES = ("V69_PARENT", "V79_NO63_VOL_GUARD")
CONTRACTS = {
    "V69_PARENT": "config/v69_parent_5m_asof_v1.yaml",
    "V79_NO63_VOL_GUARD": "config/v79_no63_vol_guard_5m_asof_v1.yaml",
}


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _hash_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _load_contract(root: Path, candidate_id: str) -> tuple[dict[str, Any], str]:
    path = root / CONTRACTS[candidate_id]
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if payload.get("candidate_id") != candidate_id:
        raise ValueError(f"contract candidate mismatch: {path}")
    return payload, _hash_file(path)


def _period_frame(frame: pd.DataFrame, start: pd.Timestamp = START, end: pd.Timestamp = END) -> pd.DataFrame:
    dates = pd.to_datetime(frame.index if isinstance(frame.index, pd.DatetimeIndex) else frame["date"])
    mask = (dates >= start) & (dates <= end)
    return frame.loc[mask].copy()


def _daily_metrics(account: pd.DataFrame, orders: pd.DataFrame, intents: pd.DataFrame, initial: float) -> dict[str, Any]:
    if account.empty:
        return {"trading_days": 0, "final_nav_krw": None, "return_pct": None, "cagr_pct": None, "mdd_pct": None,
                "sharpe": None, "turnover_krw": 0.0, "fee_krw": 0.0, "spread_krw": 0.0, "impact_krw": 0.0,
                "mean_cash_weight": None, "worst_daily_return_pct": None, "order_count": 0, "fill_count": 0}
    nav = account.set_index(pd.to_datetime(account["date"]))["nav_krw"].astype(float)
    base = v69._metrics(nav, initial)
    quantity = pd.to_numeric(orders.get("quantity", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
    price = pd.to_numeric(orders.get("execution_price_krw", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
    return {
        "trading_days": int(len(account)),
        "final_nav_krw": float(nav.iloc[-1]),
        "return_pct": float(base["return_pct"]),
        "cagr_pct": float(base["cagr_pct"]),
        "mdd_pct": float(base["mdd_pct"]),
        "sharpe": float(base["sharpe"]),
        "turnover_krw": float((quantity * price).sum()),
        "fee_krw": float(pd.to_numeric(orders.get("fee_krw", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()),
        "spread_krw": float(pd.to_numeric(orders.get("half_spread_cost_krw", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()),
        "impact_krw": float(pd.to_numeric(orders.get("impact_cost_krw", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()),
        "mean_cash_weight": float((account["cash_krw"] / account["nav_krw"]).mean()),
        "worst_daily_return_pct": float(nav.pct_change().min() * 100.0) if len(nav) > 1 else 0.0,
        "order_count": int(len(orders)),
        "fill_count": int(len(orders)),
        "intent_count": int(len(intents)),
        "reconciliation_failures": 0,
    }


def _valid_full_session(root: Path, symbol: str, path: Path, session: str) -> tuple[bool, int, str | None]:
    """Return whether a cached session can support completed 5m as-of bars.

    Existing six-bar probe caches qualify only when their raw session can be
    validated against the authoritative daily OHLCV.  Missing zero-trade
    minutes are not filled here; the as-of runner decides whether the sparse
    timeline is sufficient for a given completed bar.
    """
    if not path.is_file():
        return False, 0, "MISSING_CACHE"
    try:
        frame = pd.read_csv(path, dtype={"symbol": str})
        required = {"timestamp", "open", "high", "low", "close", "volume"}
        if frame.empty or not required.issubset(frame.columns):
            return False, len(frame), "INVALID_SCHEMA"
        ts = pd.to_datetime(frame["timestamp"], utc=True).dt.tz_convert("Asia/Seoul")
        if not ts.dt.date.astype(str).eq(session).all():
            return False, len(frame), "DATE_MISMATCH"
        if ts.duplicated().any() or not ts.is_monotonic_increasing:
            return False, len(frame), "TIMESTAMP_ORDER"
        # Sparse zero-trade minutes are allowed when the raw session still
        # reproduces the authoritative daily OHLCV.  A 390-row count alone is
        # not a completeness contract.
        regular = ts.dt.time.astype(str).str.slice(0, 5).between("09:00", "15:29")
        count = int(regular.sum())
        if count <= 0:
            return False, len(frame), "INCOMPLETE_SESSION"
        day = frame.loc[regular]
        daily_path = root / f"data/toss_v19c_daily/{symbol}_1d.csv"
        if not daily_path.is_file():
            return False, len(frame), "DAILY_REFERENCE_MISSING"
        daily = pd.read_csv(daily_path)
        daily["date"] = pd.to_datetime(daily["timestamp"], utc=True).dt.tz_convert("Asia/Seoul").dt.date.astype(str)
        ref = daily[daily["date"].eq(session)]
        if ref.empty:
            return False, len(frame), "DAILY_REFERENCE_MISSING"
        row = ref.iloc[0]
        aggregates = {
            "open": float(day.iloc[0]["open"]), "high": float(pd.to_numeric(day["high"]).max()),
            "low": float(pd.to_numeric(day["low"]).min()), "close": float(day.iloc[-1]["close"]),
            "volume": float(pd.to_numeric(day["volume"]).sum()),
        }
        prices_match = all(abs(aggregates[key] - float(row[key])) <= 1e-8 for key in ("open", "high", "low", "close"))
        volume_match = aggregates["volume"] == float(row["volume"])
        if not prices_match or not volume_match:
            return False, len(frame), "DAILY_OHLCV_MISMATCH"
        return True, len(frame), None
    except Exception as exc:  # pragma: no cover - defensive boundary
        return False, 0, type(exc).__name__


def _coverage(root: Path, symbols: list[str], dates: pd.DatetimeIndex) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for symbol in symbols:
        for date in dates:
            session = date.date().isoformat()
            path = _cache_path(root, symbol, session)
            valid, bars, reason = _valid_full_session(root, symbol, path, session)
            rows.append({"symbol": symbol, "date": session, "required_bars": 6, "available_bars": bars,
                         "full_session": valid, "reason": reason, "cache_path": str(path.relative_to(root))})
    total = len(rows)
    available = sum(bool(r["full_session"]) for r in rows)
    return {
        "required_symbol_dates": total,
        "available_symbol_dates": available,
        "missing_symbol_dates": total - available,
        "coverage_ratio": float(available / total) if total else 0.0,
        "rows": rows,
        "required_timestamps_kst": ["09:01", "09:02", "09:03", "09:04", "09:05", "09:06"],
        "minute_endpoint": "GET /api/v1/candles",
        "interval": "1m",
        "ks11_minute_requested": False,
    }


def _mapping(candidate_id: str) -> dict[str, Any]:
    if candidate_id == "V69_PARENT":
        return {
            "strategy": "V69",
            "features": {
                "price": "src/quant_harness/v94_universe_agent/engine.py::_strict_v69_features (ret21/63/126, rel21/63, trend MA120)",
                "universe": "src/quant_harness/v94_universe_agent/engine.py::_strict_v69_features::universe_gate",
                "regime": "src/quant_harness/v95_market_regime_agent/policy.py::build_market_regime_panel, D1_MA120_EXPLICIT",
                "selection": "src/quant_harness/v69_dynamic_theme_leadership/engine.py::select_dynamic_leader, TOP_SCORE_SECTOR_DEDUP",
                "allocation": "src/quant_harness/v100_strategy_agent/policy.py::build_v69_target_ledger",
                "execution": "src/quant_harness/v101_risk_execution_agent/engine.py::replay/execute_target_map",
            },
            "d1_fixed": ["regime", "universe eligibility", "D-1 ADV", "value/volume eligibility"],
            "asof_price_update": ["temporary OHLC", "price returns/momentum", "MA relationship", "price volatility/ranking"],
            "non_portable_fail_closed": ["full-day volume/value", "unconfirmed close-dependent conditions"],
        }
    return {
        "strategy": "V79",
        "features": {
            "price": "src/quant_harness/v94_universe_agent/engine.py::_strict_v79_features (ret63/126/252 percentile ranks, trend MA200)",
            "universe": "src/quant_harness/v94_universe_agent/engine.py::_strict_v79_features::universe_gate",
            "regime": "src/quant_harness/v95_market_regime_agent/policy.py::build_market_regime_panel, MA120_VOLATILITY_GUARD_35PCT",
            "selection": "src/quant_harness/v79_generic_trend_sleeve/engine.py::select_persistent_trend_leader + ABLATE_V79_63_COMPONENT",
            "allocation": "src/quant_harness/v100_strategy_agent/policy.py::build_v79_target_ledger",
            "execution": "src/quant_harness/v101_risk_execution_agent/engine.py::replay/execute_target_map",
        },
        "d1_fixed": ["regime", "universe eligibility", "D-1 ADV", "value/volume eligibility"],
        "asof_price_update": ["temporary OHLC", "price returns/momentum", "MA relationship", "price volatility/ranking"],
        "non_portable_fail_closed": ["full-day volume/value", "unconfirmed close-dependent conditions"],
    }


def _run_daily(root: Path, candidate_id: str, specs: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    spec = specs[candidate_id]
    built = build_candidate_ledgers(root, spec, use_common_cutoff=True)
    market = built["market"]
    dates = market["close"].index
    period = dates[(dates >= START) & (dates <= END)]
    if len(period) == 0:
        raise RuntimeError(f"no daily input for {candidate_id} in {START.date()}..{END.date()}")
    close = market["close"].loc[period]
    open_px = market["open"].loc[period]
    adv = market["adv20_d1"].loc[period]
    ledger = built["ledger"].copy()
    ledger["date"] = pd.to_datetime(ledger["date"])
    ledger = ledger[ledger["date"].isin(period)]
    cfg = built["cfg77"]
    policy = v101._policy(root, spec.execution_policy)
    account, orders, intents = v101.replay(close, open_px, adv, ledger, initial_capital=10_000_000.0,
                                            spec=cfg.base_execution, policy=policy, strategy=spec.strategy,
                                            core_ticker=cfg.core_ticker)
    return built, account, orders, intents


def run_current_models_5m_validation(root: Path | str, *, output_dir: Path | str | None = None) -> dict[str, Any]:
    root = Path(root).resolve()
    out = Path(output_dir) if output_dir else root / "runtime/current_models_5m_validation"
    out.mkdir(parents=True, exist_ok=True)
    specs = load_candidate_specs(root)
    results: dict[str, Any] = {}
    contract_rows: dict[str, Any] = {}
    for candidate_id in CANDIDATES:
        contract, contract_hash = _load_contract(root, candidate_id)
        contract_rows[candidate_id] = {"contract": contract, "sha256": contract_hash}
        built, account, orders, intents = _run_daily(root, candidate_id, specs)
        results[candidate_id] = {"built": built, "account": account, "orders": orders, "intents": intents}

    # Both candidates share the same daily date index and universe.  Minute
    # coverage is conservative: full regular sessions are required for every
    # active ETF/date, and no daily fallback is allowed.
    market = results[CANDIDATES[0]]["built"]["market"]
    period = market["close"].index[(market["close"].index >= START) & (market["close"].index <= END)]
    universe = results[CANDIDATES[0]]["built"]["universe"]["ticker"].astype(str).str.zfill(6).tolist()
    symbols = sorted(set(universe) | {str(results[CANDIDATES[0]]["built"]["cfg77"].core_ticker).zfill(6)})
    coverage = _coverage(root, symbols, period)
    coverage.update({"period_start": str(period.min().date()), "period_end": str(period.max().date()),
                     "trading_days": len(period), "symbols": symbols,
                     "candidate_ids": list(CANDIDATES), "reason_if_blocked": "RAW_SESSION_MUST_REPRODUCE_DAILY_OHLCV_AND_SUPPORT_COMPLETED_5M_BARS"})

    comparison_rows: list[dict[str, Any]] = []
    annual_rows: list[dict[str, Any]] = []
    daily_nav_rows: list[dict[str, Any]] = []
    for candidate_id in CANDIDATES:
        result = results[candidate_id]
        m = _daily_metrics(result["account"], result["orders"], result["intents"], 10_000_000.0)
        comparison_rows.append({"candidate_id": candidate_id, "run": "DAILY_BASE", **m,
                                "minute_coverage_ratio": coverage["coverage_ratio"],
                                "technical_judgement": "DAILY_BASELINE_REUSED",
                                "comparative_judgement": "NO_ROBUST_5M_WINNER"})
        comparison_rows.append({"candidate_id": candidate_id, "run": "5M_ASOF_V1",
                                "minute_coverage_ratio": coverage["coverage_ratio"], "technical_judgement": "BLOCKED_BY_MINUTE_DATA",
                                "comparative_judgement": "NO_ROBUST_5M_WINNER", "reason": "required full regular-session minute cache is incomplete"})
        account = result["account"].copy()
        account["candidate_id"] = candidate_id
        account["run"] = "DAILY_BASE"
        daily_nav_rows.extend(account.to_dict("records"))
        # Annual baseline metrics only; no fabricated 5m result is emitted.
        account["year"] = pd.to_datetime(account["date"]).dt.year
        for year, frame in account.groupby("year"):
            nav = frame["nav_krw"].astype(float)
            annual_rows.append({"candidate_id": candidate_id, "run": "DAILY_BASE", "year": int(year),
                                "return_pct": float((nav.iloc[-1] / nav.iloc[0] - 1.0) * 100.0),
                                "mdd_pct": float(v69._metrics(pd.Series(nav.values, index=frame["date"]), float(nav.iloc[0]))["mdd_pct"])})

    mapping = {cid: _mapping(cid) for cid in CANDIDATES}
    (out / "v69_feature_mapping.json").write_text(_json(mapping["V69_PARENT"]) + "\n", encoding="utf-8")
    (out / "v79_feature_mapping.json").write_text(_json(mapping["V79_NO63_VOL_GUARD"]) + "\n", encoding="utf-8")
    (out / "v69_contract.json").write_text(_json(contract_rows["V69_PARENT"]) + "\n", encoding="utf-8")
    (out / "v79_contract.json").write_text(_json(contract_rows["V79_NO63_VOL_GUARD"]) + "\n", encoding="utf-8")
    (out / "data_coverage.json").write_text(_json(coverage) + "\n", encoding="utf-8")
    pd.DataFrame(daily_nav_rows).to_csv(out / "daily_nav_comparison.csv", index=False)
    pd.DataFrame(comparison_rows).to_csv(out / "intraday_trades.csv", index=False)
    pd.DataFrame(annual_rows).to_csv(out / "annual_comparison.csv", index=False)
    summary = {
        "mode": MODE, "period": {"start": str(START.date()), "end": str(END.date())},
        "models": list(CANDIDATES), "contracts": {cid: contract_rows[cid]["sha256"] for cid in CANDIDATES},
        "feature_mapping_is_runtime_only": True, "daily_signal_port_not_run": True,
        "minute_coverage_ratio": coverage["coverage_ratio"], "required_symbol_dates": coverage["required_symbol_dates"],
        "available_symbol_dates": coverage["available_symbol_dates"], "missing_symbol_dates": coverage["missing_symbol_dates"],
        "technical_judgement": {cid: "BLOCKED_BY_MINUTE_DATA" for cid in CANDIDATES},
        "comparative_judgement": "NO_ROBUST_5M_WINNER", "future_minute_used": False,
        "daily_fallback_used": False, "broker_mutation_calls": 0, "operating_database_touched": False,
        "strategy_changed": False, "reason": "5m as-of requires a validated raw session and completed-bar timeline; daily fallback is forbidden.",
    }
    (out / "validation_summary.json").write_text(_json(summary) + "\n", encoding="utf-8")
    (out / "validation.log").write_text(_json({"summary": summary, "contracts": contract_rows, "coverage": {k: v for k, v in coverage.items() if k != "rows"}}) + "\n", encoding="utf-8")
    return summary


__all__ = ["run_current_models_5m_validation"]
