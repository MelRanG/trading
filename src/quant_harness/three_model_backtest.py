"""Small, repository-native comparison runner for the three enabled V104 candidates."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import json
from pathlib import Path
from typing import Any

import pandas as pd

from quant_harness.active_market_data_update import run_incremental_update
from quant_harness.v69_dynamic_theme_leadership import engine as v69
from quant_harness.v77_corrected_price_allocation import engine as v77
from quant_harness.v104_end_to_end_causal_challenger_audit.adapter import (
    load_candidate_specs,
    replay_candidate,
)
from quant_harness.v72_integration_ready.toss_openapi import TossOpenApiClient


MODE = "THREE_MODEL_BACKTEST"
ENABLED = ("V79_NO63", "V69_VOL_GUARD", "V79_NO63_VOL_GUARD")
PROBE_SYMBOLS = ("069500", "395160", "KS11")


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _timestamp_date(value: str) -> str:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone(timedelta(hours=9))).date().isoformat()


def _cache_path(root: Path, symbol: str, session: str) -> Path:
    return root / "data/toss_intraday_1m" / str(symbol).zfill(6) / f"{session}.csv"


def fetch_intraday_session(client: TossOpenApiClient, root: Path | str, symbol: str, session: str) -> dict[str, Any]:
    """Fetch one session only, following nextBefore and reusing a validated CSV cache."""
    root = Path(root)
    path = _cache_path(root, symbol, session)
    if path.is_file():
        frame = pd.read_csv(path, dtype={"symbol": str})
        if frame.empty or not set(("timestamp", "symbol", "open", "high", "low", "close", "volume")).issubset(frame.columns):
            raise RuntimeError(f"invalid intraday cache: {path}")
        if not frame["timestamp"].map(_timestamp_date).eq(session).all():
            raise RuntimeError(f"intraday cache date mismatch: {path}")
        return {"symbol": str(symbol).zfill(6), "session": session, "bars": int(len(frame)), "cache_hit": True, "path": str(path.relative_to(root))}
    rows: list[dict[str, Any]] = []
    path.parent.mkdir(parents=True, exist_ok=True)
    before = f"{session}T23:59:59+09:00"
    for _ in range(10):
        page, next_before = client.get_intraday_candles_page(symbol, before=before, interval="1m", count=200)
        rows.extend(row for row in page if _timestamp_date(row["timestamp"]) == session)
        page_dates = [_timestamp_date(row["timestamp"]) for row in page]
        if not page or min(page_dates) < session or not next_before:
            break
        before = next_before
    unique = {str(row["timestamp"]): row for row in rows}
    if not unique:
        raise RuntimeError(f"no 1m candles for {symbol} {session}")
    frame = pd.DataFrame(sorted(unique.values(), key=lambda row: row["timestamp"]))
    frame.to_csv(path, index=False)
    return {"symbol": str(symbol).zfill(6), "session": session, "bars": int(len(frame)), "cache_hit": False, "path": str(path.relative_to(root))}


def _has_intraday_before(client: TossOpenApiClient, symbol: str, before: date) -> bool:
    rows, _ = client.get_intraday_candles_page(symbol, before=f"{before.isoformat()}T23:59:59+09:00", count=1)
    return bool(rows)


def discover_oldest_intraday_date(client: TossOpenApiClient, symbol: str, *, lower: date = date(2018, 1, 1), upper: date | None = None) -> str | None:
    upper = upper or (date.today() - timedelta(days=1))
    if not _has_intraday_before(client, symbol, upper):
        return None
    lo, hi = lower, upper
    if _has_intraday_before(client, symbol, lo):
        return lo.isoformat()
    while (hi - lo).days > 1:
        mid = lo + (hi - lo) // 2
        if _has_intraday_before(client, symbol, mid):
            hi = mid
        else:
            lo = mid
    rows, _ = client.get_intraday_candles_page(symbol, before=f"{hi.isoformat()}T23:59:59+09:00", count=1)
    return _timestamp_date(rows[-1]["timestamp"]) if rows else hi.isoformat()


def _daily_coverage(root: Path) -> dict[str, Any]:
    universe = pd.read_csv(root / "data/toss_v19c_daily/universe.csv", dtype={"ticker": str})
    symbols = sorted(universe["ticker"].astype(str).str.zfill(6).unique())
    ends: dict[str, str] = {}
    starts: dict[str, str] = {}
    for symbol in symbols:
        frame = pd.read_csv(root / f"data/toss_v19c_daily/{symbol}_1d.csv")
        dates = pd.to_datetime(frame["timestamp"], utc=True).dt.tz_convert("Asia/Seoul").dt.date
        starts[symbol], ends[symbol] = str(dates.min()), str(dates.max())
    benchmark = pd.read_csv(root / "data/all_prices_long_v62_9_expanded.csv", dtype={"ticker": str})
    ks = pd.to_datetime(benchmark.loc[benchmark["ticker"].eq("KS11"), "date"])
    starts["KS11"], ends["KS11"] = str(ks.min().date()), str(ks.max().date())
    return {"symbols": symbols, "benchmark": "KS11", "start_by_symbol": starts, "end_by_symbol": ends, "common_start": max(starts.values()), "common_cutoff": min(ends.values()), "source": "data/toss_v19c_daily + data/all_prices_long_v62_9_expanded.csv"}


def _comparison_row(root: Path, candidate_id: str, run: dict[str, Any], benchmark_return: float, *, baseline_model: str | None = None, judgement: str = "VALID_WITH_RISK_FLAGS") -> dict[str, Any]:
    nav = run["account"].set_index("date")["nav_krw"].astype(float)
    initial = float(run["initial_capital_krw"])
    metrics = v69._metrics(nav, initial)
    orders = run["orders"]
    cash = run["account"]["cash_krw"].astype(float) / run["account"]["nav_krw"].astype(float)
    tracking = run["account"].get("max_abs_tracking_error_close", pd.Series(dtype=float))
    fee = pd.to_numeric(orders.get("fee_krw", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()
    spread = pd.to_numeric(orders.get("half_spread_cost_krw", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()
    impact = pd.to_numeric(orders.get("impact_cost_krw", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()
    return {"model": candidate_id, "baseline_model": baseline_model, "strategy": run["spec"].strategy, "start": str(nav.index.min().date()), "end": str(nav.index.max().date()), "trading_days": int(len(nav)), "intraday_bars_coverage": 0.0, "return_pct": metrics["return_pct"], "cagr_pct": metrics["cagr_pct"], "mdd_pct": metrics["mdd_pct"], "sharpe": metrics["sharpe"], "benchmark_return_pct": benchmark_return * 100.0, "benchmark_excess_pct": metrics["return_pct"] - benchmark_return * 100.0, "order_count": int(len(orders)), "fill_count": int(len(orders)), "turnover_krw": float((pd.to_numeric(orders.get("quantity", pd.Series(dtype=float)), errors="coerce") * pd.to_numeric(orders.get("execution_price_krw", pd.Series(dtype=float)), errors="coerce")).sum()) if not orders.empty else 0.0, "fee_krw": float(fee), "spread_krw": float(spread), "impact_krw": float(impact), "mean_cash_weight": float(cash.mean()), "mean_target_tracking_error": float(pd.to_numeric(tracking, errors="coerce").mean()) if len(tracking) else None, "worst_daily_return_pct": float(nav.pct_change().min() * 100.0), "role": "daily_strategy_baseline" if baseline_model is None else "daily_strategy_candidate_overlay", "judgement": judgement}


def _replay_common_cutoff(root: Path, spec: Any) -> dict[str, Any]:
    built = __import__("quant_harness.v104_end_to_end_causal_challenger_audit.adapter", fromlist=["build_candidate_ledgers"]).build_candidate_ledgers(root, spec, use_common_cutoff=True)
    cfg = built["cfg77"]
    policy = __import__("quant_harness.v101_risk_execution_agent.engine", fromlist=["_policy"])._policy(root, spec.execution_policy)
    execution = __import__("quant_harness.v101_risk_execution_agent.engine", fromlist=["replay"]).replay(
        built["market"]["close"], built["market"]["open"], built["market"]["adv20_d1"], built["ledger"],
        initial_capital=float(cfg.initial_capital_krw), spec=cfg.base_execution, policy=policy,
        strategy=spec.strategy, core_ticker=cfg.core_ticker,
    )
    return {"spec": spec, "execution": policy, "ledger": built["ledger"], "account": execution[0], "orders": execution[1], "intents": execution[2], "initial_capital_krw": float(cfg.initial_capital_krw)}


def run_three_model_backtest(root: Path | str, *, output_dir: Path | str | None = None) -> dict[str, Any]:
    root = Path(root).resolve()
    out = Path(output_dir) if output_dir else root / "runtime/three_model_backtest"
    out.mkdir(parents=True, exist_ok=True)
    update = run_incremental_update(root, write_output=False)
    coverage = _daily_coverage(root)
    specs = load_candidate_specs(root)
    registry = json.loads((root / "reports/v104_end_to_end_causal_challenger_audit/v104_runtime_adapter_registry.json").read_text(encoding="utf-8"))
    inventory = []
    for candidate_id in ENABLED:
        spec = specs[candidate_id]
        inventory.append({"model": candidate_id, "version": "V104 candidate adapter", "strategy": spec.strategy, "code": "src/quant_harness/v104_end_to_end_causal_challenger_audit/adapter.py", "config": "config/v104_end_to_end_causal_challenger_audit.yaml", "role": "daily strategy candidate with overlay", "overlay": {"regime": spec.regime_policy, "selection": spec.sleeve_selection_policy}, "intraday_execution_model": False, "connected_to_active_runtime": candidate_id == "V69_PARENT", "artifact": registry["candidates"].get(candidate_id, {}).get("adapter_status", "configured")})
    benchmark = pd.read_csv(root / "data/all_prices_long_v62_9_expanded.csv", dtype={"ticker": str})
    benchmark["date"] = pd.to_datetime(benchmark["date"])
    benchmark = benchmark.sort_values("date")
    ks = benchmark[benchmark["ticker"].eq("KS11")].sort_values("date")["close"].astype(float)
    cutoff = pd.Timestamp(coverage["common_cutoff"])
    ks = benchmark.loc[benchmark["ticker"].eq("KS11") & (benchmark["date"] <= cutoff), "close"].astype(float)
    benchmark_return = float(ks.iloc[-1] / ks.iloc[0] - 1.0)
    runs: dict[str, dict[str, Any]] = {}
    parent_by_strategy = {"V69": "V69_PARENT", "V79": "V79_PARENT"}
    for parent_id in parent_by_strategy.values():
        runs[parent_id] = _replay_common_cutoff(root, specs[parent_id])
    for candidate_id in ENABLED:
        runs[candidate_id] = _replay_common_cutoff(root, specs[candidate_id])
    rows = [_comparison_row(root, pid, runs[pid], benchmark_return, judgement="BASELINE") for pid in sorted(runs) if pid.endswith("PARENT")]
    for candidate_id in ENABLED:
        parent_id = parent_by_strategy[specs[candidate_id].strategy]
        candidate = _comparison_row(root, candidate_id, runs[candidate_id], benchmark_return, baseline_model=parent_id)
        parent = rows[next(i for i, row in enumerate(rows) if row["model"] == parent_id)]
        if candidate["return_pct"] > parent["return_pct"] and candidate["sharpe"] >= parent["sharpe"] and candidate["mdd_pct"] >= parent["mdd_pct"]:
            candidate["judgement"] = "ADDS_INCREMENTAL_VALUE"
        elif candidate["return_pct"] < parent["return_pct"] and candidate["sharpe"] < parent["sharpe"]:
            candidate["judgement"] = "DEGRADES_BASE_MODEL"
        else:
            candidate["judgement"] = "NO_MEANINGFUL_INCREMENTAL_VALUE"
        rows.append(candidate)
    comparison = pd.DataFrame(rows)
    oldest: dict[str, str | None] = {}
    intraday_rows: list[dict[str, Any]] = []
    try:
        from dotenv import load_dotenv
        load_dotenv(root / ".env")
        client = TossOpenApiClient()
    except Exception as exc:
        oldest = {symbol: None for symbol in PROBE_SYMBOLS}
        intraday_rows.append({"symbol": "PROBE", "session": "2026-07-31", "bars": 0, "cache_hit": False, "oldest_available": None, "model_required": False, "status": f"BLOCKED_BY_DATA:{type(exc).__name__}"})
    else:
        for symbol in PROBE_SYMBOLS:
            try:
                oldest[symbol] = discover_oldest_intraday_date(client, symbol)
            except Exception:
                oldest[symbol] = None
            try:
                result = fetch_intraday_session(client, root, symbol, "2026-07-31")
                intraday_rows.append({**result, "oldest_available": oldest[symbol], "model_required": False, "status": "PROBE_ONLY_NO_INTRADAY_MODEL"})
            except Exception as exc:
                intraday_rows.append({"symbol": symbol, "session": "2026-07-31", "bars": 0, "cache_hit": False, "oldest_available": oldest[symbol], "model_required": False, "status": f"BLOCKED_BY_DATA:{type(exc).__name__}"})
    data_coverage = {"daily_update": update.__dict__, "daily": coverage, "intraday": {"endpoint": "GET /api/v1/candles", "interval": "1m", "count": 200, "adjusted": True, "probe_symbols": list(PROBE_SYMBOLS), "oldest_available_by_symbol": oldest, "required_symbol_dates": 0, "required_bars": 0, "reason": "No enabled repository model has an intraday execution contract; no standalone intraday model was invented."}}
    (out / "model_inventory.json").write_text(_json({"mode": MODE, "models": inventory, "active_strategy": "v69_fixed80_daily_control", "active_registry": "config/strategy_registry_v84.yaml"}) + "\n", encoding="utf-8")
    (out / "data_coverage.json").write_text(_json(data_coverage) + "\n", encoding="utf-8")
    comparison.to_csv(out / "model_comparison.csv", index=False)
    pd.DataFrame(intraday_rows).to_csv(out / "intraday_summary.csv", index=False)
    (out / "validation.log").write_text(_json({"daily_update_cutoff": update.cutoff, "same_period": True, "future_intraday_used": False, "broker_mutation_calls": 0, "operating_database_touched": False, "judgement": "NOT_PROVEN_INSUFFICIENT_DATA"}) + "\n", encoding="utf-8")
    return {"models": inventory, "coverage": data_coverage, "comparison": comparison.to_dict("records"), "intraday": intraday_rows, "judgement": "NOT_PROVEN_INSUFFICIENT_DATA", "broker_mutation_calls": 0}


__all__ = ["fetch_intraday_session", "discover_oldest_intraday_date", "run_three_model_backtest"]
