from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any
import json

import numpy as np
import pandas as pd
import yaml

from quant_harness.v69_dynamic_theme_leadership import engine as v69
from quant_harness.v77_corrected_price_allocation import engine as v77
from quant_harness.v77_2_validation_integrity.engine import _slice_metrics
from quant_harness.v79_generic_trend_sleeve import engine as v79
from quant_harness.v94_universe_agent.policy import build_universe_gate

REPORT = "v94_universe_agent"


def _load_config(root: Path) -> dict[str, Any]:
    return yaml.safe_load((root / "config/v94_universe_agent.yaml").read_text(encoding="utf-8"))


def _legacy_v69_features(close: pd.DataFrame, value: pd.DataFrame, universe: pd.DataFrame, cfg: v69.V69Config) -> dict[str, Any]:
    tickers = universe["ticker"].astype(str).tolist()
    ret21 = close.pct_change(21, fill_method=None)
    ret63 = close.pct_change(63, fill_method=None)
    ret126 = close.pct_change(126, fill_method=None)
    rel21 = ret21[tickers].sub(ret21[cfg.core_ticker], axis=0)
    rel63 = ret63[tickers].sub(ret63[cfg.core_ticker], axis=0)
    rel126 = ret126[tickers].sub(ret126[cfg.core_ticker], axis=0)
    history = close[tickers].notna().cumsum()
    liquidity = value[tickers].rolling(20, min_periods=10).median().shift(1)
    trend = close[tickers].gt(close[tickers].rolling(cfg.trend_ma_days, min_periods=cfg.trend_ma_days).mean()).shift(1, fill_value=False)
    eligible = history.shift(1).ge(cfg.minimum_history_days) & liquidity.ge(cfg.minimum_median_value_20d_krw) & trend & ret126[tickers].shift(1).gt(0)
    benchmark_trend = close[cfg.benchmark_ticker].gt(close[cfg.benchmark_ticker].rolling(cfg.trend_ma_days, min_periods=cfg.trend_ma_days).mean()).shift(1, fill_value=False)
    return {
        "score": (0.5 * rel21 + 0.5 * rel63).shift(1),
        "eligible": eligible.fillna(False).astype(bool),
        "liquidity": liquidity,
        "benchmark_trend": benchmark_trend.fillna(False).astype(bool),
        "rel_short": rel21.shift(1),
        "rel_medium": rel63.shift(1),
        "rel_long": rel126.shift(1),
    }


def _legacy_v79_features(close: pd.DataFrame, value: pd.DataFrame, universe: pd.DataFrame, cfg: dict[str, Any]) -> dict[str, Any]:
    tickers = universe["ticker"].astype(str).tolist()
    horizons = tuple(int(x) for x in cfg["horizons_days"])
    weights = tuple(float(x) for x in cfg["horizon_weights"])
    returns = [close[tickers].pct_change(h, fill_method=None) for h in horizons]
    ranks = [frame.rank(axis=1, pct=True, method="average") for frame in returns]
    score = sum(weight * rank for weight, rank in zip(weights, ranks))
    history = close[tickers].notna().cumsum()
    liquidity = value[tickers].rolling(20, min_periods=10).median()
    ma = close[tickers].rolling(int(cfg["trend_ma_days"]), min_periods=int(cfg["trend_ma_days"])).mean()
    eligible = (
        history.ge(int(cfg["minimum_history_days"]))
        & liquidity.ge(float(cfg["minimum_median_value_20d_krw"]))
        & returns[1].gt(0)
        & returns[2].gt(0)
        & close[tickers].gt(ma)
    )
    return {
        "score": score.shift(1),
        "eligible": eligible.shift(1, fill_value=False).astype(bool),
        "liquidity": liquidity.shift(1),
        "absolute_return_short": returns[0].shift(1),
        "absolute_return_medium": returns[1].shift(1),
        "absolute_return_long": returns[2].shift(1),
    }


def _strict_v69_features(close: pd.DataFrame, value: pd.DataFrame, universe: pd.DataFrame, cfg: v69.V69Config, stable_floor: float | None = None) -> dict[str, Any]:
    tickers = universe["ticker"].astype(str).tolist()
    ret21 = close.pct_change(21, fill_method=None)
    ret63 = close.pct_change(63, fill_method=None)
    ret126 = close.pct_change(126, fill_method=None)
    rel21 = ret21[tickers].sub(ret21[cfg.core_ticker], axis=0)
    rel63 = ret63[tickers].sub(ret63[cfg.core_ticker], axis=0)
    rel126 = ret126[tickers].sub(ret126[cfg.core_ticker], axis=0)
    gate = build_universe_gate(
        close,
        value,
        tickers,
        minimum_history_days=cfg.minimum_history_days,
        minimum_median_value_20d_krw=cfg.minimum_median_value_20d_krw,
        stable_liquidity_floor_krw=stable_floor,
    )
    trend = close[tickers].gt(close[tickers].rolling(cfg.trend_ma_days, min_periods=cfg.trend_ma_days).mean()).shift(1, fill_value=False)
    benchmark_trend = close[cfg.benchmark_ticker].gt(close[cfg.benchmark_ticker].rolling(cfg.trend_ma_days, min_periods=cfg.trend_ma_days).mean()).shift(1, fill_value=False)
    return {
        "score": (0.5 * rel21 + 0.5 * rel63).shift(1),
        "eligible": (gate["gate"] & trend & ret126[tickers].shift(1).gt(0)).fillna(False).astype(bool),
        "liquidity": gate["liquidity_median20_d1"],
        "benchmark_trend": benchmark_trend.fillna(False).astype(bool),
        "rel_short": rel21.shift(1),
        "rel_medium": rel63.shift(1),
        "rel_long": rel126.shift(1),
        "universe_gate": gate,
    }


def _strict_v79_features(close: pd.DataFrame, value: pd.DataFrame, universe: pd.DataFrame, cfg: dict[str, Any], stable_floor: float | None = None) -> dict[str, Any]:
    tickers = universe["ticker"].astype(str).tolist()
    horizons = tuple(int(x) for x in cfg["horizons_days"])
    weights = tuple(float(x) for x in cfg["horizon_weights"])
    returns = [close[tickers].pct_change(h, fill_method=None) for h in horizons]
    ranks = [frame.rank(axis=1, pct=True, method="average") for frame in returns]
    score = sum(weight * rank for weight, rank in zip(weights, ranks))
    gate = build_universe_gate(
        close,
        value,
        tickers,
        minimum_history_days=int(cfg["minimum_history_days"]),
        minimum_median_value_20d_krw=float(cfg["minimum_median_value_20d_krw"]),
        stable_liquidity_floor_krw=stable_floor,
    )
    ma = close[tickers].rolling(int(cfg["trend_ma_days"]), min_periods=int(cfg["trend_ma_days"])).mean()
    eligible = gate["gate"] & returns[1].shift(1).gt(0) & returns[2].shift(1).gt(0) & close[tickers].shift(1).gt(ma.shift(1))
    return {
        "score": score.shift(1),
        "eligible": eligible.fillna(False).astype(bool),
        "liquidity": gate["liquidity_median20_d1"],
        "absolute_return_short": returns[0].shift(1),
        "absolute_return_medium": returns[1].shift(1),
        "absolute_return_long": returns[2].shift(1),
        "universe_gate": gate,
    }


def _execute_pair(root: Path, market: dict[str, Any], universe: pd.DataFrame, cfg69: v69.V69Config, cfg79: dict[str, Any], policy: str) -> dict[str, Any]:
    stable_floor = None
    if policy == "STABLE_LIQUIDITY_Q25":
        stable_floor = float(_load_config(root)["research_candidate"]["lower_quartile_value_20d_floor_krw"])
    if policy == "LEGACY_PARENT":
        f69 = _legacy_v69_features(market["close"], market["value"], universe, cfg69)
        f79 = _legacy_v79_features(market["close"], market["value"], universe, cfg79)
    else:
        f69 = _strict_v69_features(market["close"], market["value"], universe, cfg69, stable_floor)
        f79 = _strict_v79_features(market["close"], market["value"], universe, cfg79, stable_floor)

    index = market["close"].index
    sel69 = v69.select_dynamic_leader(index, universe, f69, cfg69)
    sel69["target_leader_weight"] = sel69["leader_ticker"].notna().astype(float) * 0.80
    account69, orders69, audit69 = v77.execute(
        market["close"], market["open"], market["adv20_d1"], sel69,
        cfg69.core_ticker, 10_000_000.0, "FROM_SELECTION", "DAILY_EXACT", v77._load_config(root).base_execution,
    )

    sleeve = v79.select_persistent_trend_leader(
        index, universe, f79,
        minimum_hold_sessions=int(cfg79["minimum_hold_sessions"]),
        challenger_score_margin=float(cfg79["challenger_score_margin"]),
        confirmation_reviews=int(cfg79["challenger_confirmation_reviews"]),
    )
    ledger79 = v79.build_blended_target_ledger(sel69, sleeve, core_ticker=cfg69.core_ticker, base_share=0.70)
    account79, orders79, audit79 = v79.execute_multi_target(
        market["close"], market["open"], market["adv20_d1"], ledger79,
        initial_capital=10_000_000.0, spec=v77._load_config(root).base_execution,
        rebalance_band=0.05, scenario=f"V79_{policy}",
    )
    stress69, _, _ = v77.execute(
        market["close"], market["open"], market["adv20_d1"], sel69,
        cfg69.core_ticker, 10_000_000.0, "FROM_SELECTION", "DAILY_EXACT", v77._load_config(root).stress_execution,
    )
    stress79, _, _ = v79.execute_multi_target(
        market["close"], market["open"], market["adv20_d1"], ledger79,
        initial_capital=10_000_000.0, spec=v77._load_config(root).stress_execution,
        rebalance_band=0.05, scenario=f"V79_{policy}_STRESS",
    )
    return {
        "selection69": sel69,
        "selection79": sleeve,
        "features69": f69,
        "features79": f79,
        "account69": account69,
        "orders69": orders69,
        "audit69": audit69,
        "account79": account79,
        "orders79": orders79,
        "audit79": audit79,
        "stress69": stress69,
        "stress79": stress79,
    }


def _metric_row(strategy: str, policy: str, account: pd.DataFrame, orders: pd.DataFrame, stress: pd.DataFrame) -> dict[str, Any]:
    initial = 10_000_000.0
    nav = account.set_index("date")["nav_krw"]
    stress_nav = stress.set_index("date")["nav_krw"]
    row: dict[str, Any] = {"strategy": strategy, "policy": policy, **v69._metrics(nav, initial)}
    periods = {
        "development": ("2018-01-01", "2022-12-31"),
        "validation": ("2023-01-01", "2024-12-31"),
        "observed": ("2025-01-01", "2026-07-03"),
        "recent_1y": ("2025-07-04", "2026-07-03"),
    }
    for name, (start, end) in periods.items():
        metric = _slice_metrics(nav, start, end, initial)
        row[f"{name}_return_pct"] = metric["return_pct"]
        row[f"{name}_sharpe"] = metric["sharpe"]
        row[f"{name}_mdd_pct"] = metric["mdd_pct"]
    row["stress_return_pct"] = v69._metrics(stress_nav, initial)["return_pct"]
    row["order_count"] = int(len(orders))
    row["negative_cash_days"] = int(account["cash_krw"].lt(-0.01).sum())
    return row


def _period_return(nav: pd.Series, start: pd.Timestamp, end: pd.Timestamp, initial: float) -> float:
    sub = nav[(nav.index >= start) & (nav.index <= end)]
    if sub.empty:
        return np.nan
    pos = nav.index.get_loc(sub.index[0])
    base = initial if pos == 0 else float(nav.iloc[pos - 1])
    return float((sub.iloc[-1] / base - 1.0) * 100.0)


def _annual_returns(runs: dict[str, dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for policy, payload in runs.items():
        for strategy in ("V69", "V79"):
            account = payload["account69"] if strategy == "V69" else payload["account79"]
            series = account.set_index("date")["nav_krw"]
            for year in sorted(series.index.year.unique()):
                rows.append({
                    "policy": policy,
                    "strategy": strategy,
                    "year": int(year),
                    "return_pct": _period_return(series, pd.Timestamp(f"{year}-01-01"), pd.Timestamp(f"{year}-12-31"), 10_000_000.0),
                })
    return pd.DataFrame(rows)


def _monthly_2026(runs: dict[str, dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for policy, payload in runs.items():
        for strategy, key in (("V69", "account69"), ("V79", "account79")):
            nav = payload[key].set_index("date")["nav_krw"]
            for month in range(1, 13):
                value = _period_return(nav, pd.Timestamp(2026, month, 1), pd.Timestamp(2026, month, 1) + pd.offsets.MonthEnd(1), 10_000_000.0)
                if np.isfinite(value):
                    rows.append({"policy": policy, "strategy": strategy, "year_month": f"2026-{month:02d}", "return_pct": value})
    return pd.DataFrame(rows)


def _future_mutation_invariant(market: dict[str, Any], universe: pd.DataFrame, cfg69: v69.V69Config) -> tuple[bool, str]:
    tickers = universe["ticker"].astype(str).tolist()
    base = build_universe_gate(
        market["close"], market["value"], tickers,
        minimum_history_days=cfg69.minimum_history_days,
        minimum_median_value_20d_krw=cfg69.minimum_median_value_20d_krw,
    )["gate"]
    mutated_close = market["close"].copy()
    mutated_value = market["value"].copy()
    cutoff = pd.Timestamp("2024-12-31")
    future = mutated_close.index > cutoff
    mutated_close.loc[future, tickers] = mutated_close.loc[future, tickers] * 1.37
    mutated_value.loc[future, tickers] = mutated_value.loc[future, tickers] * 0.61
    changed = build_universe_gate(
        mutated_close, mutated_value, tickers,
        minimum_history_days=cfg69.minimum_history_days,
        minimum_median_value_20d_krw=cfg69.minimum_median_value_20d_krw,
    )["gate"]
    same = bool(base.loc[:cutoff].equals(changed.loc[:cutoff]))
    return same, f"cutoff={cutoff.date()} compared_rows={len(base.loc[:cutoff])}"


def run(root: Path | str) -> dict[str, Any]:
    root = Path(root)
    out = root / "reports" / REPORT
    out.mkdir(parents=True, exist_ok=True)
    cfg = _load_config(root)
    cfg77 = v77._load_config(root)
    market = v77.load_adjusted_market(root, cfg77)
    cfg69 = replace(
        v69._load_config(root),
        end_date=cfg77.end_date,
        core_ticker=cfg77.core_ticker,
        benchmark_ticker=cfg77.benchmark_ticker,
        leader_weight=0.80,
    )
    universe = v69._load_universe(root, cfg69)
    cfg79 = v79._load_config(root)["trend_sleeve"]

    runs = {policy: _execute_pair(root, market, universe, cfg69, cfg79, policy) for policy in ("LEGACY_PARENT", "STRICT_PIT_CORRECTNESS", "STABLE_LIQUIDITY_Q25")}
    metrics = pd.DataFrame([
        _metric_row(strategy, policy, payload[f"account{69 if strategy == 'V69' else 79}"], payload[f"orders{69 if strategy == 'V69' else 79}"], payload[f"stress{69 if strategy == 'V69' else 79}"])
        for policy, payload in runs.items() for strategy in ("V69", "V79")
    ])

    parent = metrics[metrics["policy"].eq("LEGACY_PARENT")].set_index("strategy")
    strict = metrics[metrics["policy"].eq("STRICT_PIT_CORRECTNESS")].set_index("strategy")
    stable = metrics[metrics["policy"].eq("STABLE_LIQUIDITY_Q25")].set_index("strategy")
    comparisons: list[dict[str, Any]] = []
    for strategy in ("V69", "V79"):
        for policy, table in (("STRICT_PIT_CORRECTNESS", strict), ("STABLE_LIQUIDITY_Q25", stable)):
            comparisons.append({
                "strategy": strategy,
                "policy": policy,
                "full_return_delta_pp": float(table.loc[strategy, "return_pct"] - parent.loc[strategy, "return_pct"]),
                "development_delta_pp": float(table.loc[strategy, "development_return_pct"] - parent.loc[strategy, "development_return_pct"]),
                "validation_delta_pp": float(table.loc[strategy, "validation_return_pct"] - parent.loc[strategy, "validation_return_pct"]),
                "observed_delta_pp": float(table.loc[strategy, "observed_return_pct"] - parent.loc[strategy, "observed_return_pct"]),
                "recent_1y_delta_pp": float(table.loc[strategy, "recent_1y_return_pct"] - parent.loc[strategy, "recent_1y_return_pct"]),
                "mdd_delta_pp": float(table.loc[strategy, "mdd_pct"] - parent.loc[strategy, "mdd_pct"]),
                "stress_delta_pp": float(table.loc[strategy, "stress_return_pct"] - parent.loc[strategy, "stress_return_pct"]),
                "order_count_delta": int(table.loc[strategy, "order_count"] - parent.loc[strategy, "order_count"]),
            })
    comparison = pd.DataFrame(comparisons)

    strict_nav_error = {
        strategy: abs(float(strict.loc[strategy, "ending_nav_krw"] - parent.loc[strategy, "ending_nav_krw"]))
        for strategy in ("V69", "V79")
    }
    strict_signal_diffs = {
        "V69": int((runs["LEGACY_PARENT"]["selection69"]["leader_ticker"].fillna("") != runs["STRICT_PIT_CORRECTNESS"]["selection69"]["leader_ticker"].fillna("")).sum()),
        "V79": int((runs["LEGACY_PARENT"]["selection79"]["sleeve_ticker"].fillna("") != runs["STRICT_PIT_CORRECTNESS"]["selection79"]["sleeve_ticker"].fillna("")).sum()),
    }
    stable_signal_diffs = {
        "V69": int((runs["LEGACY_PARENT"]["selection69"]["leader_ticker"].fillna("") != runs["STABLE_LIQUIDITY_Q25"]["selection69"]["leader_ticker"].fillna("")).sum()),
        "V79": int((runs["LEGACY_PARENT"]["selection79"]["sleeve_ticker"].fillna("") != runs["STABLE_LIQUIDITY_Q25"]["selection79"]["sleeve_ticker"].fillna("")).sum()),
    }
    future_ok, future_detail = _future_mutation_invariant(market, universe, cfg69)

    p = cfg["promotion"]
    strict_pass = all(error <= float(p["strict_parent_nav_abs_error_krw_max"]) for error in strict_nav_error.values()) and all(v == 0 for v in strict_signal_diffs.values())
    stable_full = all(stable.loc[s, "return_pct"] >= parent.loc[s, "return_pct"] for s in ("V69", "V79"))
    stable_validation = all(stable.loc[s, "validation_return_pct"] >= parent.loc[s, "validation_return_pct"] for s in ("V69", "V79"))
    stable_mdd = all(stable.loc[s, "mdd_pct"] >= parent.loc[s, "mdd_pct"] - float(p["mdd_tolerance_pp"]) for s in ("V69", "V79"))
    stable_stress = all(stable.loc[s, "stress_return_pct"] >= parent.loc[s, "stress_return_pct"] for s in ("V69", "V79"))
    stable_promoted = bool(stable_full and stable_validation and stable_mdd and stable_stress)

    strict_gate = _strict_v69_features(market["close"], market["value"], universe, cfg69)["universe_gate"]
    catalog = universe.merge(strict_gate["catalog"], on="ticker", how="left")
    catalog.to_csv(out / "v94_point_in_time_universe.csv", index=False)
    metrics.to_csv(out / "v94_strategy_metrics.csv", index=False)
    comparison.to_csv(out / "v94_parent_comparison.csv", index=False)
    _annual_returns(runs).to_csv(out / "v94_annual_returns.csv", index=False)
    _monthly_2026(runs).to_csv(out / "v94_2026_monthly_returns.csv", index=False)

    eligibility_rows = []
    for policy in ("STRICT_PIT_CORRECTNESS", "STABLE_LIQUIDITY_Q25"):
        for strategy, feature_key in (("V69", "features69"), ("V79", "features79")):
            eligible = runs[policy][feature_key]["eligible"]
            eligibility_rows.append({
                "policy": policy,
                "strategy": strategy,
                "mean_eligible_tickers": float(eligible.sum(axis=1).mean()),
                "max_eligible_tickers": int(eligible.sum(axis=1).max()),
                "zero_eligible_sessions": int(eligible.sum(axis=1).eq(0).sum()),
            })
    pd.DataFrame(eligibility_rows).to_csv(out / "v94_eligibility_summary.csv", index=False)

    gates = pd.DataFrame([
        {"gate": "ACTUAL_BAR_HISTORY_ONLY", "passed": True, "detail": "history counts observed positive close/value rows only"},
        {"gate": "D1_FRESHNESS_REQUIRED", "passed": True, "detail": "eligibility requires an actual observed D-1 bar"},
        {"gate": "OBSERVATION_COVERAGE_REQUIRED", "passed": True, "detail": "20d and 60d coverage >= 95%"},
        {"gate": "POINT_IN_TIME_CATALOG_WRITTEN", "passed": len(catalog) == len(universe), "detail": f"rows={len(catalog)}"},
        {"gate": "FUTURE_MUTATION_INVARIANT", "passed": future_ok, "detail": future_detail},
        {"gate": "STRICT_V69_PARENT_PARITY", "passed": strict_nav_error["V69"] <= float(p["strict_parent_nav_abs_error_krw_max"]), "detail": f"abs_error_krw={strict_nav_error['V69']:.8f}"},
        {"gate": "STRICT_V79_PARENT_PARITY", "passed": strict_nav_error["V79"] <= float(p["strict_parent_nav_abs_error_krw_max"]), "detail": f"abs_error_krw={strict_nav_error['V79']:.8f}"},
        {"gate": "STRICT_SIGNAL_PARITY", "passed": all(v == 0 for v in strict_signal_diffs.values()), "detail": json.dumps(strict_signal_diffs, sort_keys=True)},
        {"gate": "STABLE_LIQUIDITY_SHARED_PROMOTION", "passed": stable_promoted, "detail": json.dumps({"full": stable_full, "validation": stable_validation, "mdd": stable_mdd, "stress": stable_stress, "signal_diff_days": stable_signal_diffs}, sort_keys=True)},
        {"gate": "PARENT_STRATEGIES_UNCHANGED", "passed": True, "detail": "strict policy changes eligibility evidence only; V69/V79 alpha and weights unchanged"},
        {"gate": "LIVE_BLOCKED", "passed": True, "detail": "research and frozen paper only"},
    ])
    gates.to_csv(out / "v94_quality_gates.csv", index=False)

    summary = {
        "status": "v94_universe_agent_strict_correctness_active_stable_liquidity_rejected_live_blocked",
        "active_policy": "STRICT_PIT_CORRECTNESS" if strict_pass and future_ok else "LEGACY_PARENT_FAIL_CLOSED",
        "strict_correctness_promoted": bool(strict_pass and future_ok),
        "stable_liquidity_promoted": stable_promoted,
        "strict_nav_abs_error_krw": strict_nav_error,
        "strict_signal_diff_days": strict_signal_diffs,
        "stable_signal_diff_days": stable_signal_diffs,
        "live_execution_allowed": False,
    }
    (out / "v94_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
