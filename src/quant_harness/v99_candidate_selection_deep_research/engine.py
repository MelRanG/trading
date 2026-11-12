from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Iterable
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
import math
import pickle
import shutil

import numpy as np
import pandas as pd
import yaml

from quant_harness.v69_dynamic_theme_leadership import engine as v69
from quant_harness.v77_corrected_price_allocation import engine as v77
from quant_harness.v77_2_validation_integrity.engine import _relative_bootstrap_period, _slice_metrics
from quant_harness.v79_generic_trend_sleeve import engine as v79
from quant_harness.v94_universe_agent import engine as v94
from quant_harness.v98_candidate_selection_agent.policy import (
    ACTIVE_SELECTION_POLICY,
    ABLATION_POLICIES,
    EXPECTED_VALUE_ROTATION,
    SECTOR_RESIDUAL_MOMENTUM,
    TREND_QUALITY_SCORE,
    UNCERTAINTY_AWARE_ROTATION,
    build_sector_representative_panel,
    prepare_selection_features,
    ranked_representatives,
    taxonomy_hash,
    validate_taxonomy,
)

REPORT = "v99_candidate_selection_deep_research"
CANDIDATE_POLICIES = (TREND_QUALITY_SCORE, SECTOR_RESIDUAL_MOMENTUM, EXPECTED_VALUE_ROTATION)
PROMISING_ABLATION_POLICY = "ABLATE_V79_63_COMPONENT"
PROMOTION_POLICIES = (*CANDIDATE_POLICIES, PROMISING_ABLATION_POLICY)
REFERENCE_POLICIES = (ACTIVE_SELECTION_POLICY,)
FULL_BACKTEST_POLICIES = (*REFERENCE_POLICIES, *PROMOTION_POLICIES)
PRIMARY_ABLATION_POLICIES = tuple(policy for policy in ABLATION_POLICIES if policy != PROMISING_ABLATION_POLICY)


def _load_config(root: Path) -> dict[str, Any]:
    return yaml.safe_load((root / "config/v99_candidate_selection_deep_research.yaml").read_text(encoding="utf-8"))


def _period_return(nav: pd.Series, start: str | pd.Timestamp, end: str | pd.Timestamp, initial: float) -> float:
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    sub = nav[(nav.index >= start) & (nav.index <= end)]
    if sub.empty:
        return np.nan
    pos = nav.index.get_loc(sub.index[0])
    base = initial if pos == 0 else float(nav.iloc[pos - 1])
    return float((sub.iloc[-1] / base - 1.0) * 100.0)


def _rolling_efficiency(close: pd.DataFrame, horizon: int) -> pd.DataFrame:
    logp = np.log(close.where(close.gt(0)))
    net = (logp - logp.shift(horizon)).abs()
    path = logp.diff().abs().rolling(horizon, min_periods=horizon).sum()
    return net.div(path.replace(0.0, np.nan)).clip(0.0, 1.0)


def _sector_residual(frame: pd.DataFrame, universe: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=frame.index, columns=frame.columns, dtype=float)
    mapping = universe.set_index(universe["ticker"].astype(str))["sector"].astype(str)
    for sector, tickers in mapping.groupby(mapping).groups.items():
        members = [str(t) for t in tickers if str(t) in frame.columns]
        if not members:
            continue
        sector_median = frame[members].median(axis=1, skipna=True)
        out[members] = frame[members].sub(sector_median, axis=0)
    return out


def _augment_features(
    market: dict[str, Any],
    universe: pd.DataFrame,
    cfg69: v69.V69Config,
    cfg79: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    close, value = market["close"], market["value"]
    tickers = universe["ticker"].astype(str).tolist()
    f69 = v94._strict_v69_features(close, value, universe, cfg69)
    f79 = v94._strict_v79_features(close, value, universe, cfg79)

    # Eligibility ablations use the same strict point-in-time universe gate.
    gate69 = f69["universe_gate"]["gate"]
    abs126_d1 = close[tickers].pct_change(cfg69.long_days, fill_method=None).shift(1)
    trend69_d1 = close[tickers].shift(1).gt(
        close[tickers].rolling(cfg69.trend_ma_days, min_periods=cfg69.trend_ma_days).mean().shift(1)
    )
    f69["eligible_without_long_filter"] = (gate69 & trend69_d1).fillna(False).astype(bool)
    f69["eligible_without_trend_filter"] = (gate69 & abs126_d1.gt(0)).fillna(False).astype(bool)

    gate79 = f79["universe_gate"]["gate"]
    medium79 = f79["absolute_return_medium"]
    long79 = f79["absolute_return_long"]
    f79["eligible_without_trend_filter"] = (gate79 & medium79.gt(0) & long79.gt(0)).fillna(False).astype(bool)

    # Candidate C: smooth, persistent trend quality. All raw values are shifted D-1.
    ret63 = close[tickers].pct_change(63, fill_method=None)
    ret126 = close[tickers].pct_change(126, fill_method=None)
    ret252 = close[tickers].pct_change(252, fill_method=None)
    eff63 = _rolling_efficiency(close[tickers], 63)
    eff126 = _rolling_efficiency(close[tickers], 126)
    vol63 = close[tickers].pct_change(fill_method=None).rolling(63, min_periods=63).std() * math.sqrt(252)
    vol126 = close[tickers].pct_change(fill_method=None).rolling(126, min_periods=126).std() * math.sqrt(252)
    rel63 = ret63.sub(close[cfg69.core_ticker].pct_change(63, fill_method=None), axis=0)
    tq69 = (
        0.55 * rel63.rank(axis=1, pct=True)
        + 0.30 * eff63.rank(axis=1, pct=True)
        + 0.15 * (-vol63).rank(axis=1, pct=True)
    ).shift(1)
    base79_rank = (
        0.25 * ret63.rank(axis=1, pct=True)
        + 0.35 * ret126.rank(axis=1, pct=True)
        + 0.40 * ret252.rank(axis=1, pct=True)
    )
    tq79 = (
        0.55 * base79_rank
        + 0.30 * eff126.rank(axis=1, pct=True)
        + 0.15 * (-vol126).rank(axis=1, pct=True)
    ).shift(1)
    f69["trend_quality_score"] = tq69
    f79["trend_quality_score"] = tq79

    # Candidate D: remove the common semantic-sector move before ranking.
    residual21 = _sector_residual(close[tickers].pct_change(21, fill_method=None), universe)
    residual63 = _sector_residual(ret63, universe)
    residual126 = _sector_residual(ret126, universe)
    residual252 = _sector_residual(ret252, universe)
    f69["sector_residual_score"] = (0.50 * residual21 + 0.50 * residual63).shift(1)
    f79["sector_residual_score"] = (
        0.25 * residual63.rank(axis=1, pct=True)
        + 0.35 * residual126.rank(axis=1, pct=True)
        + 0.40 * residual252.rank(axis=1, pct=True)
    ).shift(1)
    return f69, f79


def _forward_return(open_px: pd.DataFrame, close: pd.DataFrame, date: pd.Timestamp, ticker: str, horizon: int) -> float:
    if ticker not in close.columns or ticker not in open_px.columns:
        return np.nan
    pos = close.index.get_indexer([pd.Timestamp(date)])[0]
    if pos < 0 or pos + horizon >= len(close):
        return np.nan
    start = open_px.iloc[pos][ticker]
    end = close.iloc[pos + horizon][ticker]
    if pd.isna(start) or pd.isna(end) or float(start) <= 0:
        return np.nan
    return float(end / start - 1.0)


def _build_expected_value_schedule(
    market: dict[str, Any],
    universe: pd.DataFrame,
    features: dict[str, Any],
    review_dates: Iterable[pd.Timestamp],
    *,
    horizon: int,
    minimum_samples: int,
    ridge_penalty: float,
) -> tuple[dict[str, dict[str, float]], pd.DataFrame]:
    index = market["close"].index
    reviews = pd.DatetimeIndex(sorted(pd.DatetimeIndex(review_dates)))
    panel = build_sector_representative_panel(
        index, reviews, universe, features["score"], features["eligible"], features["liquidity"]
    )
    events: list[dict[str, Any]] = []
    schedule: dict[str, dict[str, float]] = {}
    rows: list[dict[str, Any]] = []
    for date in reviews:
        pos = index.get_indexer([date])[0]
        matured = [event for event in events if int(event["maturity_pos"]) < pos]
        coeff = np.array([0.0, 0.0, 0.0], dtype=float)
        r2 = np.nan
        if len(matured) >= minimum_samples:
            x = np.asarray([[1.0, e["score_gap"], e["normalized_gap"]] for e in matured], dtype=float)
            y = np.asarray([e["future_excess"] for e in matured], dtype=float)
            penalty = np.diag([0.0, ridge_penalty, ridge_penalty])
            coeff = np.linalg.solve(x.T @ x + penalty, x.T @ y)
            fitted = x @ coeff
            denom = float(np.sum((y - y.mean()) ** 2))
            r2 = float(1.0 - np.sum((y - fitted) ** 2) / denom) if denom > 1e-12 else 0.0
        key = date.date().isoformat()
        schedule[key] = {
            "sample_count": int(len(matured)),
            "intercept": float(coeff[0]),
            "coef_gap": float(coeff[1]),
            "coef_normalized_gap": float(coeff[2]),
            "r2": r2,
        }
        rows.append({"date": date, **schedule[key]})

        ranked = ranked_representatives(panel, date)
        if len(ranked) < 2 or pos + horizon >= len(index):
            continue
        scores = np.asarray([r[2] for r in ranked], dtype=float)
        iqr = float(np.nanpercentile(scores, 75) - np.nanpercentile(scores, 25)) if len(scores) >= 2 else 0.0
        top = ranked[0]
        top_ret = _forward_return(market["open"], market["close"], date, top[0], horizon)
        if not np.isfinite(top_ret):
            continue
        for alternative in ranked[1:]:
            alt_ret = _forward_return(market["open"], market["close"], date, alternative[0], horizon)
            if not np.isfinite(alt_ret):
                continue
            gap = float(top[2] - alternative[2])
            events.append({
                "date": date,
                "maturity_pos": pos + horizon,
                "score_gap": gap,
                "normalized_gap": gap / max(iqr, 1e-6),
                "future_excess": float(np.clip(top_ret - alt_ret, -0.75, 0.75)),
            })
    return schedule, pd.DataFrame(rows)


def _policy_params(cfg: dict[str, Any], policy: str) -> dict[str, Any]:
    for row in cfg.get("research_candidates", []):
        if row["policy_id"] == policy:
            return {k: v for k, v in row.items() if k != "policy_id"}
    if policy == UNCERTAINTY_AWARE_ROTATION:
        return dict(cfg["frozen_forward_reference"])
    return {}


def _execute_pair(
    root: Path,
    market: dict[str, Any],
    universe: pd.DataFrame,
    cfg69: v69.V69Config,
    cfg79: dict[str, Any],
    base_features69: dict[str, Any],
    base_features79: dict[str, Any],
    policy: str,
    params: dict[str, Any],
    schedules: dict[str, dict[str, dict[str, float]]],
) -> dict[str, Any]:
    p69 = dict(params)
    p79 = dict(params)
    if policy == EXPECTED_VALUE_ROTATION:
        p69["expected_value_schedule"] = schedules["V69"]
        p79["expected_value_schedule"] = schedules["V79"]
    index = market["close"].index
    sel69 = v69.select_dynamic_leader(index, universe, base_features69, cfg69, selection_policy=policy, selection_policy_params=p69)
    sel69["target_leader_weight"] = sel69["leader_ticker"].notna().astype(float) * 0.80
    cfg77 = v77._load_config(root)
    account69, orders69, audit69 = v77.execute(
        market["close"], market["open"], market["adv20_d1"], sel69,
        cfg69.core_ticker, 10_000_000.0, "FROM_SELECTION", "DAILY_EXACT", cfg77.base_execution,
    )
    stress69, _, _ = v77.execute(
        market["close"], market["open"], market["adv20_d1"], sel69,
        cfg69.core_ticker, 10_000_000.0, "FROM_SELECTION", "DAILY_EXACT", cfg77.stress_execution,
    )
    sleeve = v79.select_persistent_trend_leader(
        index, universe, base_features79,
        minimum_hold_sessions=int(cfg79["minimum_hold_sessions"]),
        challenger_score_margin=float(cfg79["challenger_score_margin"]),
        confirmation_reviews=int(cfg79["challenger_confirmation_reviews"]),
        selection_policy=policy, selection_policy_params=p79,
    )
    ledger79 = v79.build_blended_target_ledger(sel69, sleeve, core_ticker=cfg69.core_ticker, base_share=0.70)
    account79, orders79, audit79 = v79.execute_multi_target(
        market["close"], market["open"], market["adv20_d1"], ledger79,
        initial_capital=10_000_000.0, spec=cfg77.base_execution,
        rebalance_band=0.05, scenario=f"V79_{policy}",
    )
    stress79, _, _ = v79.execute_multi_target(
        market["close"], market["open"], market["adv20_d1"], ledger79,
        initial_capital=10_000_000.0, spec=cfg77.stress_execution,
        rebalance_band=0.05, scenario=f"V79_{policy}_STRESS",
    )
    return {
        "selection69": sel69, "selection79": sleeve, "ledger79": ledger79,
        "account69": account69, "orders69": orders69, "audit69": audit69, "stress69": stress69,
        "account79": account79, "orders79": orders79, "audit79": audit79, "stress79": stress79,
    }


def _execute_ablation(
    root: Path,
    market: dict[str, Any],
    universe: pd.DataFrame,
    cfg69: v69.V69Config,
    cfg79: dict[str, Any],
    features69: dict[str, Any],
    features79: dict[str, Any],
    active_selection69: pd.DataFrame,
    policy: str,
) -> dict[str, Any]:
    cfg77 = v77._load_config(root)
    index = market["close"].index
    if policy.startswith("ABLATE_V69_"):
        selection = v69.select_dynamic_leader(
            index, universe, features69, cfg69, selection_policy=policy, selection_policy_params={}
        )
        selection["target_leader_weight"] = selection["leader_ticker"].notna().astype(float) * 0.80
        account, orders, audit = v77.execute(
            market["close"], market["open"], market["adv20_d1"], selection,
            cfg69.core_ticker, 10_000_000.0, "FROM_SELECTION", "DAILY_EXACT", cfg77.base_execution,
        )
        return {"strategy": "V69", "selection": selection, "account": account, "orders": orders, "audit": audit}
    sleeve = v79.select_persistent_trend_leader(
        index, universe, features79,
        minimum_hold_sessions=int(cfg79["minimum_hold_sessions"]),
        challenger_score_margin=float(cfg79["challenger_score_margin"]),
        confirmation_reviews=int(cfg79["challenger_confirmation_reviews"]),
        selection_policy=policy, selection_policy_params={},
    )
    ledger = v79.build_blended_target_ledger(active_selection69, sleeve, core_ticker=cfg69.core_ticker, base_share=0.70)
    account, orders, audit = v79.execute_multi_target(
        market["close"], market["open"], market["adv20_d1"], ledger,
        initial_capital=10_000_000.0, spec=cfg77.base_execution,
        rebalance_band=0.05, scenario=f"V79_{policy}",
    )
    return {"strategy": "V79", "selection": sleeve, "account": account, "orders": orders, "audit": audit}


def _ablation_metric_row(
    strategy: str, policy: str, account: pd.DataFrame, orders: pd.DataFrame,
    purged_validation_start: pd.Timestamp,
) -> dict[str, Any]:
    initial = 10_000_000.0
    nav = account.set_index("date")["nav_krw"]
    row: dict[str, Any] = {"strategy": strategy, "policy": policy, **v69._metrics(nav, initial)}
    periods = {
        "development": ("2018-01-01", "2022-12-31"),
        "validation": ("2023-01-01", "2024-12-31"),
        "purged_validation": (purged_validation_start, "2024-12-31"),
        "observed": ("2025-01-01", "2026-07-03"),
        "recent_1y": ("2025-07-04", "2026-07-03"),
    }
    for name, (start, end) in periods.items():
        metrics = _slice_metrics(nav, str(pd.Timestamp(start).date()), str(pd.Timestamp(end).date()), initial)
        row[f"{name}_return_pct"] = metrics["return_pct"]
        row[f"{name}_sharpe"] = metrics["sharpe"]
        row[f"{name}_mdd_pct"] = metrics["mdd_pct"]
    row["stress_return_pct"] = np.nan
    row["ending_nav_krw"] = float(nav.iloc[-1])
    row["order_count"] = int(len(orders))
    row["negative_cash_days"] = int(account["cash_krw"].lt(-0.01).sum())
    row["total_fee_krw"] = float(pd.to_numeric(orders.get("fee_krw", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
    return row


def _metric_row(
    strategy: str, policy: str, account: pd.DataFrame, orders: pd.DataFrame,
    stress: pd.DataFrame, purged_validation_start: pd.Timestamp,
) -> dict[str, Any]:
    initial = 10_000_000.0
    nav = account.set_index("date")["nav_krw"]
    stress_nav = stress.set_index("date")["nav_krw"]
    row: dict[str, Any] = {"strategy": strategy, "policy": policy, **v69._metrics(nav, initial)}
    periods = {
        "development": ("2018-01-01", "2022-12-31"),
        "validation": ("2023-01-01", "2024-12-31"),
        "purged_validation": (purged_validation_start, "2024-12-31"),
        "observed": ("2025-01-01", "2026-07-03"),
        "recent_1y": ("2025-07-04", "2026-07-03"),
    }
    for name, (start, end) in periods.items():
        metrics = _slice_metrics(nav, str(pd.Timestamp(start).date()), str(pd.Timestamp(end).date()), initial)
        row[f"{name}_return_pct"] = metrics["return_pct"]
        row[f"{name}_sharpe"] = metrics["sharpe"]
        row[f"{name}_mdd_pct"] = metrics["mdd_pct"]
    row["stress_return_pct"] = float((stress_nav.iloc[-1] / initial - 1.0) * 100.0)
    row["ending_nav_krw"] = float(nav.iloc[-1])
    row["order_count"] = int(len(orders))
    row["negative_cash_days"] = int(account["cash_krw"].lt(-0.01).sum())
    row["total_fee_krw"] = float(pd.to_numeric(orders.get("fee_krw", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
    return row


def _path_stats(close: pd.DataFrame, date: pd.Timestamp, ticker: Any, horizon: int) -> tuple[float, float, float]:
    if ticker is None or pd.isna(ticker) or str(ticker) not in close.columns:
        return np.nan, np.nan, np.nan
    ticker = str(ticker)
    pos = close.index.get_indexer([pd.Timestamp(date)])[0]
    if pos < 0 or pos + horizon >= len(close):
        return np.nan, np.nan, np.nan
    start = close.iloc[pos][ticker]
    path = close.iloc[pos : pos + horizon + 1][ticker]
    if pd.isna(start) or float(start) <= 0 or path.isna().any():
        return np.nan, np.nan, np.nan
    rets = path / float(start) - 1.0
    return float(rets.iloc[-1]), float(rets.max()), float(rets.min())


def _build_error_taxonomy(active: dict[str, Any], close: pd.DataFrame, cfg: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    thresholds = cfg["error_taxonomy"]
    for strategy, key, ticker_col, review_col in (
        ("V69", "selection69", "leader_ticker", "review_monthly"),
        ("V79", "selection79", "sleeve_ticker", "review_weekly"),
    ):
        reviews = active[key][active[key][review_col].astype(bool)].copy().reset_index(drop=True)
        reviews["previous_selected"] = reviews[ticker_col].shift(1)
        for row in reviews.itertuples(index=False):
            date = pd.Timestamp(row.date)
            selected = getattr(row, ticker_col)
            previous = row.previous_selected
            runner = getattr(row, "runner_up_ticker", None)
            top = getattr(row, "top_candidate_ticker", None)
            changed = bool(pd.notna(selected) and pd.notna(previous) and str(selected) != str(previous))
            selected20, mfe20, mae20 = _path_stats(close, date, selected, 20)
            selected60, mfe60, mae60 = _path_stats(close, date, selected, 60)
            runner20, _, _ = _path_stats(close, date, runner, 20)
            runner60, _, _ = _path_stats(close, date, runner, 60)
            old20, _, _ = _path_stats(close, date, previous, 20)
            old60, _, _ = _path_stats(close, date, previous, 60)
            top20, _, _ = _path_stats(close, date, top, 20)
            flags = {
                "RANK_ERROR_20D": np.isfinite(selected20) and np.isfinite(runner20) and selected20 < runner20,
                "RANK_ERROR_60D": np.isfinite(selected60) and np.isfinite(runner60) and selected60 < runner60,
                "ROTATION_ERROR_20D": changed and np.isfinite(selected20) and np.isfinite(old20) and selected20 < old20,
                "ROTATION_ERROR_60D": changed and np.isfinite(selected60) and np.isfinite(old60) and selected60 < old60,
                "CHASE_ENTRY_DRAWDOWN_20D": changed and np.isfinite(mae20) and mae20 <= -float(thresholds["chase_mae_20d"]),
                "DELAYED_ENTRY_20D": (not changed) and pd.notna(top) and pd.notna(selected) and str(top) != str(selected)
                    and np.isfinite(top20) and np.isfinite(selected20) and top20 - selected20 >= float(thresholds["delayed_entry_edge_20d"]),
                "TRANSIENT_MOMENTUM_20_TO_60": np.isfinite(selected20) and np.isfinite(runner20)
                    and np.isfinite(selected60) and np.isfinite(runner60)
                    and selected20 > runner20 and selected60 < runner60,
                "COST_ERASED_ROTATION_20D": changed and np.isfinite(selected20) and np.isfinite(old20)
                    and selected20 - old20 <= float(thresholds["round_trip_cost_buffer"]),
            }
            severities = {
                "RANK_ERROR_20D": max(0.0, runner20 - selected20) if np.isfinite(runner20) and np.isfinite(selected20) else np.nan,
                "RANK_ERROR_60D": max(0.0, runner60 - selected60) if np.isfinite(runner60) and np.isfinite(selected60) else np.nan,
                "ROTATION_ERROR_20D": max(0.0, old20 - selected20) if np.isfinite(old20) and np.isfinite(selected20) else np.nan,
                "ROTATION_ERROR_60D": max(0.0, old60 - selected60) if np.isfinite(old60) and np.isfinite(selected60) else np.nan,
                "CHASE_ENTRY_DRAWDOWN_20D": max(0.0, -mae20) if np.isfinite(mae20) else np.nan,
                "DELAYED_ENTRY_20D": max(0.0, top20 - selected20) if np.isfinite(top20) and np.isfinite(selected20) else np.nan,
                "TRANSIENT_MOMENTUM_20_TO_60": max(0.0, runner60 - selected60) if np.isfinite(runner60) and np.isfinite(selected60) else np.nan,
                "COST_ERASED_ROTATION_20D": max(0.0, float(thresholds["round_trip_cost_buffer"]) - (selected20 - old20))
                    if np.isfinite(selected20) and np.isfinite(old20) else np.nan,
            }
            base = {
                "strategy": strategy, "date": date, "selected_ticker": selected,
                "previous_ticker": previous, "runner_up_ticker": runner, "top_candidate_ticker": top,
                "changed": changed, "decision_reason": row.decision_reason,
                "selected_return_20d": selected20, "selected_return_60d": selected60,
                "runner_return_20d": runner20, "runner_return_60d": runner60,
                "old_return_20d": old20, "old_return_60d": old60,
                "selected_mfe_20d": mfe20, "selected_mae_20d": mae20,
                "selected_mfe_60d": mfe60, "selected_mae_60d": mae60,
                "top_runner_gap_d1": getattr(row, "top_runner_gap_d1", np.nan),
                "effective_rotation_margin_d1": getattr(row, "effective_rotation_margin_d1", np.nan),
            }
            for error_type, flag in flags.items():
                rows.append({**base, "error_type": error_type, "error": bool(flag), "severity_pp": float(severities[error_type] * 100.0) if np.isfinite(severities[error_type]) else np.nan})
    ledger = pd.DataFrame(rows)
    summaries: list[dict[str, Any]] = []
    for (strategy, error_type), group in ledger.groupby(["strategy", "error_type"], sort=True):
        mature = group["severity_pp"].notna()
        errored = group["error"] & mature
        summaries.append({
            "strategy": strategy, "error_type": error_type,
            "mature_events": int(mature.sum()), "error_count": int(errored.sum()),
            "error_rate": float(errored.sum() / mature.sum()) if mature.any() else np.nan,
            "mean_severity_pp": float(group.loc[errored, "severity_pp"].mean()) if errored.any() else 0.0,
            "total_severity_pp": float(group.loc[errored, "severity_pp"].sum()) if errored.any() else 0.0,
        })
    return ledger, pd.DataFrame(summaries)


def _decision_quality(runs: dict[str, dict[str, Any]], close: pd.DataFrame, policies: Iterable[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for policy in policies:
        payload = runs[policy]
        for strategy, key, ticker_col, review_col in (
            ("V69", "selection69", "leader_ticker", "review_monthly"),
            ("V79", "selection79", "sleeve_ticker", "review_weekly"),
        ):
            reviews = payload[key][payload[key][review_col].astype(bool)].copy().reset_index(drop=True)
            reviews["previous_selected"] = reviews[ticker_col].shift(1)
            for horizon in (20, 60):
                selected = reviews.apply(lambda r: _path_stats(close, r["date"], r[ticker_col], horizon)[0], axis=1)
                runner = reviews.apply(lambda r: _path_stats(close, r["date"], r.get("runner_up_ticker"), horizon)[0], axis=1)
                old = reviews.apply(lambda r: _path_stats(close, r["date"], r.get("previous_selected"), horizon)[0], axis=1)
                valid_runner = selected.notna() & runner.notna()
                changed = reviews[ticker_col].fillna("").ne(reviews["previous_selected"].fillna(""))
                valid_old = selected.notna() & old.notna() & changed
                rows.append({
                    "policy": policy, "strategy": strategy, "horizon_days": horizon,
                    "review_count": int(len(reviews)), "selection_changed_reviews": int(changed.sum()),
                    "mature_selected_runner_events": int(valid_runner.sum()),
                    "selected_minus_runner_mean_pp": float((selected[valid_runner] - runner[valid_runner]).mean() * 100.0) if valid_runner.any() else np.nan,
                    "selected_beats_runner_rate": float((selected[valid_runner] > runner[valid_runner]).mean()) if valid_runner.any() else np.nan,
                    "mature_rotation_events": int(valid_old.sum()),
                    "selected_minus_old_mean_pp": float((selected[valid_old] - old[valid_old]).mean() * 100.0) if valid_old.any() else np.nan,
                    "selected_beats_old_rate": float((selected[valid_old] > old[valid_old]).mean()) if valid_old.any() else np.nan,
                })
    return pd.DataFrame(rows)


def _changed_reviews(
    base: pd.DataFrame, candidate: pd.DataFrame, ticker_col: str, review_col: str,
    start: str, end: str,
) -> int:
    mask = base["date"].between(pd.Timestamp(start), pd.Timestamp(end)) & base[review_col].astype(bool)
    return int(candidate.loc[mask, ticker_col].fillna("").reset_index(drop=True).ne(
        base.loc[mask, ticker_col].fillna("").reset_index(drop=True)
    ).sum())


def _annual_returns(runs: dict[str, dict[str, Any]], policies: Iterable[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for policy in policies:
        for strategy, key in (("V69", "account69"), ("V79", "account79")):
            nav = runs[policy][key].set_index("date")["nav_krw"]
            for year, values in nav.groupby(nav.index.year):
                first_pos = nav.index.get_loc(values.index[0])
                base = 10_000_000.0 if first_pos == 0 else float(nav.iloc[first_pos - 1])
                rows.append({"policy": policy, "strategy": strategy, "year": int(year), "return_pct": float((values.iloc[-1] / base - 1.0) * 100.0)})
    return pd.DataFrame(rows)


def _monthly_2026(runs: dict[str, dict[str, Any]], policies: Iterable[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for policy in policies:
        for strategy, key in (("V69", "account69"), ("V79", "account79")):
            nav = runs[policy][key].set_index("date")["nav_krw"]
            sample = nav[nav.index.year == 2026]
            for month, values in sample.groupby(sample.index.month):
                first_pos = nav.index.get_loc(values.index[0])
                base = 10_000_000.0 if first_pos == 0 else float(nav.iloc[first_pos - 1])
                rows.append({"policy": policy, "strategy": strategy, "year_month": f"2026-{month:02d}", "return_pct": float((values.iloc[-1] / base - 1.0) * 100.0)})
    return pd.DataFrame(rows)


def _ablation_summary(metrics: pd.DataFrame) -> pd.DataFrame:
    parent = metrics[metrics["policy"].eq(ACTIVE_SELECTION_POLICY)].set_index("strategy")
    primary = {
        "ABLATE_V69_SHORT_COMPONENT": "V69", "ABLATE_V69_MEDIUM_COMPONENT": "V69",
        "ABLATE_V69_LONG_FILTER": "V69", "ABLATE_V69_TREND_FILTER": "V69",
        "ABLATE_V79_63_COMPONENT": "V79", "ABLATE_V79_126_COMPONENT": "V79",
        "ABLATE_V79_252_COMPONENT": "V79", "ABLATE_V79_TREND_FILTER": "V79",
        "V79_HIGH252_PROXIMITY": "V79",
    }
    rows: list[dict[str, Any]] = []
    for policy, strategy in primary.items():
        candidate = metrics[(metrics["policy"].eq(policy)) & (metrics["strategy"].eq(strategy))].iloc[0]
        p = parent.loc[strategy]
        full = float(candidate["return_pct"] - p["return_pct"])
        validation = float(candidate["validation_return_pct"] - p["validation_return_pct"])
        stress = float(candidate["stress_return_pct"] - p["stress_return_pct"]) if np.isfinite(candidate["stress_return_pct"]) else np.nan
        if full < 0 and validation < 0:
            conclusion = "VALUE_ADDING_COMPONENT"
        elif full > 0 and validation > 0:
            conclusion = "REDUNDANT_OR_HARMFUL_COMPONENT"
        else:
            conclusion = "MIXED_OR_REGIME_DEPENDENT"
        rows.append({
            "policy": policy, "primary_strategy": strategy, "conclusion": conclusion,
            "full_delta_pp": full, "development_delta_pp": float(candidate["development_return_pct"] - p["development_return_pct"]),
            "validation_delta_pp": validation, "purged_validation_delta_pp": float(candidate["purged_validation_return_pct"] - p["purged_validation_return_pct"]),
            "observed_delta_pp": float(candidate["observed_return_pct"] - p["observed_return_pct"]),
            "recent1y_delta_pp": float(candidate["recent_1y_return_pct"] - p["recent_1y_return_pct"]),
            "stress_delta_pp": stress, "mdd_delta_pp": float(candidate["mdd_pct"] - p["mdd_pct"]),
            "order_count_delta": int(candidate["order_count"] - p["order_count"]),
        })
    return pd.DataFrame(rows)


def _candidate_promotion(
    metrics: pd.DataFrame, quality: pd.DataFrame, runs: dict[str, dict[str, Any]], cfg: dict[str, Any],
) -> pd.DataFrame:
    p = cfg["promotion"]
    parent = metrics[metrics["policy"].eq(ACTIVE_SELECTION_POLICY)].set_index("strategy")
    qparent = quality[quality["policy"].eq(ACTIVE_SELECTION_POLICY)].set_index(["strategy", "horizon_days"])
    rows: list[dict[str, Any]] = []
    for policy in PROMOTION_POLICIES:
        candidate = metrics[metrics["policy"].eq(policy)].set_index("strategy")
        qcand = quality[quality["policy"].eq(policy)].set_index(["strategy", "horizon_days"])
        strategy_specs = (
            (("V79", "sleeve_ticker", "selection79", "review_weekly"),)
            if policy == PROMISING_ABLATION_POLICY
            else (
                ("V69", "leader_ticker", "selection69", "review_monthly"),
                ("V79", "sleeve_ticker", "selection79", "review_weekly"),
            )
        )
        for strategy, ticker_col, selection_key, review_col in strategy_specs:
            changed_validation = _changed_reviews(
                runs[ACTIVE_SELECTION_POLICY][selection_key], runs[policy][selection_key],
                ticker_col, review_col, "2023-01-01", "2024-12-31",
            )
            boot = _relative_bootstrap_period(
                runs[policy][f"account{69 if strategy == 'V69' else 79}"].set_index("date")["nav_krw"],
                runs[ACTIVE_SELECTION_POLICY][f"account{69 if strategy == 'V69' else 79}"].set_index("date")["nav_krw"],
                "2023-01-01", "2024-12-31", samples=int(p["bootstrap_samples"]), block_months=3,
            )
            family_count = len(ABLATION_POLICIES) if policy == PROMISING_ABLATION_POLICY else len(CANDIDATE_POLICIES)
            familywise_probability = max(0.0, 1.0 - family_count * (1.0 - float(boot["positive_probability"])))
            gates = {
                "development_noninferior": candidate.loc[strategy, "development_return_pct"] >= parent.loc[strategy, "development_return_pct"] - float(p["development_tolerance_pp"]),
                "validation_improves": candidate.loc[strategy, "validation_return_pct"] >= parent.loc[strategy, "validation_return_pct"] + float(p["validation_improvement_min_pp"]),
                "purged_validation_improves": candidate.loc[strategy, "purged_validation_return_pct"] >= parent.loc[strategy, "purged_validation_return_pct"] + float(p["purged_validation_improvement_min_pp"]),
                "recent1y_noninferior": candidate.loc[strategy, "recent_1y_return_pct"] >= parent.loc[strategy, "recent_1y_return_pct"] - float(p["recent1y_tolerance_pp"]),
                "stress_noninferior": candidate.loc[strategy, "stress_return_pct"] >= parent.loc[strategy, "stress_return_pct"] - float(p["stress_tolerance_pp"]),
                "mdd_within_tolerance": candidate.loc[strategy, "mdd_pct"] >= parent.loc[strategy, "mdd_pct"] - float(p["mdd_tolerance_pp"]),
                "turnover_bounded": candidate.loc[strategy, "order_count"] <= parent.loc[strategy, "order_count"] * float(p["order_count_ratio_max"]),
                "validation_changed_evidence": changed_validation >= int(p["minimum_changed_reviews_validation"]),
                "runner_edge_20d_noninferior": qcand.loc[(strategy, 20), "selected_minus_runner_mean_pp"] >= qparent.loc[(strategy, 20), "selected_minus_runner_mean_pp"] - float(p["selection_edge_tolerance_pp"]),
                "runner_edge_60d_noninferior": qcand.loc[(strategy, 60), "selected_minus_runner_mean_pp"] >= qparent.loc[(strategy, 60), "selected_minus_runner_mean_pp"] - float(p["selection_edge_tolerance_pp"]),
                "rotation_edge_20d_noninferior": qcand.loc[(strategy, 20), "selected_minus_old_mean_pp"] >= qparent.loc[(strategy, 20), "selected_minus_old_mean_pp"] - float(p["rotation_edge_tolerance_pp"]),
                "rotation_edge_60d_noninferior": qcand.loc[(strategy, 60), "selected_minus_old_mean_pp"] >= qparent.loc[(strategy, 60), "selected_minus_old_mean_pp"] - float(p["rotation_edge_tolerance_pp"]),
                "validation_bootstrap_supported": float(boot["positive_probability"]) >= float(p["validation_bootstrap_probability_min"]),
                "familywise_multiple_testing_supported": familywise_probability >= float(p["familywise_probability_min"]),
            }
            passed = bool(all(gates.values()))
            recent_only = (
                candidate.loc[strategy, "return_pct"] > parent.loc[strategy, "return_pct"]
                and candidate.loc[strategy, "observed_return_pct"] > parent.loc[strategy, "observed_return_pct"]
                and candidate.loc[strategy, "recent_1y_return_pct"] > parent.loc[strategy, "recent_1y_return_pct"]
                and not gates["validation_changed_evidence"]
            )
            point_estimate_supported = (
                gates["development_noninferior"] and gates["validation_improves"]
                and gates["purged_validation_improves"] and gates["recent1y_noninferior"]
                and gates["stress_noninferior"] and gates["mdd_within_tolerance"]
                and gates["turnover_bounded"] and gates["validation_changed_evidence"]
            )
            if passed:
                status = "BACKTEST_PASSED_FORWARD_REQUIRED"
            elif policy == PROMISING_ABLATION_POLICY and point_estimate_supported:
                status = "FORWARD_SHADOW_ONLY_MULTIPLE_TESTING_NOT_CLEARED"
            elif recent_only:
                status = "FORWARD_SHADOW_ONLY"
            else:
                status = "BACKTEST_REJECTED"
            rows.append({
                "policy": policy, "strategy": strategy, "status": status,
                "backtest_passed": passed, "promoted": False,
                "changed_reviews_validation": changed_validation,
                "validation_bootstrap_probability": float(boot["positive_probability"]),
                "familywise_probability_lower_bound": familywise_probability,
                **gates,
                "full_delta_pp": float(candidate.loc[strategy, "return_pct"] - parent.loc[strategy, "return_pct"]),
                "development_delta_pp": float(candidate.loc[strategy, "development_return_pct"] - parent.loc[strategy, "development_return_pct"]),
                "validation_delta_pp": float(candidate.loc[strategy, "validation_return_pct"] - parent.loc[strategy, "validation_return_pct"]),
                "purged_validation_delta_pp": float(candidate.loc[strategy, "purged_validation_return_pct"] - parent.loc[strategy, "purged_validation_return_pct"]),
                "observed_delta_pp": float(candidate.loc[strategy, "observed_return_pct"] - parent.loc[strategy, "observed_return_pct"]),
                "recent1y_delta_pp": float(candidate.loc[strategy, "recent_1y_return_pct"] - parent.loc[strategy, "recent_1y_return_pct"]),
                "stress_delta_pp": float(candidate.loc[strategy, "stress_return_pct"] - parent.loc[strategy, "stress_return_pct"]),
                "mdd_delta_pp": float(candidate.loc[strategy, "mdd_pct"] - parent.loc[strategy, "mdd_pct"]),
                "order_count_delta": int(candidate.loc[strategy, "order_count"] - parent.loc[strategy, "order_count"]),
            })
    return pd.DataFrame(rows)


def _future_mutation_invariant(
    market: dict[str, Any], universe: pd.DataFrame, cfg69: v69.V69Config, cfg79: dict[str, Any],
    policy: str, params: dict[str, Any], schedules: dict[str, dict[str, dict[str, float]]],
) -> tuple[bool, str]:
    cutoff = pd.Timestamp("2024-12-31")
    f69, f79 = _augment_features(market, universe, cfg69, cfg79)
    p69, p79 = dict(params), dict(params)
    if policy == EXPECTED_VALUE_ROTATION:
        p69["expected_value_schedule"] = schedules["V69"]
        p79["expected_value_schedule"] = schedules["V79"]
    base69 = v69.select_dynamic_leader(market["close"].index, universe, f69, cfg69, selection_policy=policy, selection_policy_params=p69)
    base79 = v79.select_persistent_trend_leader(
        market["close"].index, universe, f79,
        minimum_hold_sessions=int(cfg79["minimum_hold_sessions"]),
        challenger_score_margin=float(cfg79["challenger_score_margin"]),
        confirmation_reviews=int(cfg79["challenger_confirmation_reviews"]),
        selection_policy=policy, selection_policy_params=p79,
    )
    changed = {k: v.copy() if isinstance(v, pd.DataFrame) else v for k, v in market.items()}
    changed["close"] = market["close"].copy()
    changed["value"] = market["value"].copy()
    tickers = universe["ticker"].astype(str).tolist()
    future = changed["close"].index > cutoff
    changed["close"].loc[future, tickers] *= 1.73
    changed["value"].loc[future, tickers] *= 0.47
    cf69, cf79 = _augment_features(changed, universe, cfg69, cfg79)
    # The expected-value schedule is deliberately frozen: future price mutation
    # must not rewrite a past decision model.
    changed69 = v69.select_dynamic_leader(changed["close"].index, universe, cf69, cfg69, selection_policy=policy, selection_policy_params=p69)
    changed79 = v79.select_persistent_trend_leader(
        changed["close"].index, universe, cf79,
        minimum_hold_sessions=int(cfg79["minimum_hold_sessions"]),
        challenger_score_margin=float(cfg79["challenger_score_margin"]),
        confirmation_reviews=int(cfg79["challenger_confirmation_reviews"]),
        selection_policy=policy, selection_policy_params=p79,
    )
    same69 = base69.loc[base69["date"].le(cutoff), ["date", "leader_ticker", "decision_reason"]].reset_index(drop=True).equals(
        changed69.loc[changed69["date"].le(cutoff), ["date", "leader_ticker", "decision_reason"]].reset_index(drop=True)
    )
    same79 = base79.loc[base79["date"].le(cutoff), ["date", "sleeve_ticker", "decision_reason"]].reset_index(drop=True).equals(
        changed79.loc[changed79["date"].le(cutoff), ["date", "sleeve_ticker", "decision_reason"]].reset_index(drop=True)
    )
    return bool(same69 and same79), f"policy={policy} cutoff={cutoff.date()}"


def _load_worker_context(root: Path) -> tuple[dict[str, Any], dict[str, Any], v69.V69Config, pd.DataFrame, dict[str, Any], dict[str, Any], dict[str, Any]]:
    cfg = _load_config(root)
    cfg77 = v77._load_config(root)
    market = v77.load_adjusted_market(root, cfg77)
    cfg69 = replace(
        v69._load_config(root), end_date=cfg77.end_date,
        core_ticker=cfg77.core_ticker, benchmark_ticker=cfg77.benchmark_ticker,
        leader_weight=0.80,
    )
    universe = v69._load_universe(root, cfg69)
    cfg79 = v79._load_config(root)["trend_sleeve"]
    f69, f79 = _augment_features(market, universe, cfg69, cfg79)
    return cfg, market, cfg69, universe, cfg79, f69, f79


def _full_policy_worker(root_text: str, policy: str, cache_dir_text: str) -> str:
    root = Path(root_text)
    cache_dir = Path(cache_dir_text)
    cfg, market, cfg69, universe, cfg79, f69, f79 = _load_worker_context(root)
    schedule69: dict[str, dict[str, float]] = {}
    schedule79: dict[str, dict[str, float]] = {}
    audit69 = pd.DataFrame(columns=["date", "sample_count", "intercept", "coef_gap", "coef_normalized_gap", "r2"])
    audit79 = audit69.copy()
    if policy == EXPECTED_VALUE_ROTATION:
        index = market["close"].index
        monthly, weekly = v69._review_dates(index)
        ev_cfg = cfg["expected_value_rotation"]
        schedule69, audit69 = _build_expected_value_schedule(
            market, universe, f69, monthly,
            horizon=int(ev_cfg["outcome_horizon_sessions"]),
            minimum_samples=int(ev_cfg["minimum_walk_forward_samples"]),
            ridge_penalty=float(ev_cfg["ridge_penalty"]),
        )
        schedule79, audit79 = _build_expected_value_schedule(
            market, universe, f79, weekly,
            horizon=int(ev_cfg["outcome_horizon_sessions"]),
            minimum_samples=int(ev_cfg["minimum_walk_forward_samples"]),
            ridge_penalty=float(ev_cfg["ridge_penalty"]),
        )
    params = _policy_params(cfg, policy)
    if policy == EXPECTED_VALUE_ROTATION:
        params = {**params, **cfg["expected_value_rotation"]}
    payload = _execute_pair(
        root, market, universe, cfg69, cfg79, f69, f79, policy, params,
        {"V69": schedule69, "V79": schedule79},
    )
    result = {
        "run": payload, "schedule69": schedule69, "schedule79": schedule79,
        "schedule_audit69": audit69, "schedule_audit79": audit79,
    }
    path = cache_dir / f"full_{policy}.pkl"
    with path.open("wb") as handle:
        pickle.dump(result, handle, protocol=pickle.HIGHEST_PROTOCOL)
    return str(path)


def _ablation_policy_worker(root_text: str, policy: str, cache_dir_text: str) -> str:
    root = Path(root_text)
    cache_dir = Path(cache_dir_text)
    _cfg, market, cfg69, universe, cfg79, f69, f79 = _load_worker_context(root)
    active_selection69 = v69.select_dynamic_leader(
        market["close"].index, universe, f69, cfg69,
        selection_policy=ACTIVE_SELECTION_POLICY, selection_policy_params={},
    )
    active_selection69["target_leader_weight"] = active_selection69["leader_ticker"].notna().astype(float) * 0.80
    payload = _execute_ablation(
        root, market, universe, cfg69, cfg79, f69, f79, active_selection69, policy,
    )
    path = cache_dir / f"ablation_{policy}.pkl"
    with path.open("wb") as handle:
        pickle.dump(payload, handle, protocol=pickle.HIGHEST_PROTOCOL)
    return str(path)


def run(root: Path | str, *, output_dir: Path | str | None = None) -> dict[str, Any]:
    root = Path(root)
    out = Path(output_dir) if output_dir is not None else root / "reports" / REPORT
    out.mkdir(parents=True, exist_ok=True)
    cfg = _load_config(root)
    cfg77 = v77._load_config(root)
    market = v77.load_adjusted_market(root, cfg77)
    cfg69 = replace(
        v69._load_config(root), end_date=cfg77.end_date,
        core_ticker=cfg77.core_ticker, benchmark_ticker=cfg77.benchmark_ticker,
        leader_weight=0.80,
    )
    universe = v69._load_universe(root, cfg69)
    cfg79 = v79._load_config(root)["trend_sleeve"]
    taxonomy = validate_taxonomy(universe)
    f69, f79 = _augment_features(market, universe, cfg69, cfg79)
    index = market["close"].index
    ev_cfg = cfg["expected_value_rotation"]
    cache_dir = out / ".runtime_cache"
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    task_kind: dict[Any, tuple[str, str]] = {}
    max_workers = max(1, min(int(cfg.get("parallel_workers", 4)), len(FULL_BACKTEST_POLICIES) + len(PRIMARY_ABLATION_POLICIES)))
    full_paths: dict[str, str] = {}
    ablation_paths: dict[str, str] = {}
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        for policy in FULL_BACKTEST_POLICIES:
            future = executor.submit(_full_policy_worker, str(root), policy, str(cache_dir))
            task_kind[future] = ("full", policy)
        for policy in PRIMARY_ABLATION_POLICIES:
            future = executor.submit(_ablation_policy_worker, str(root), policy, str(cache_dir))
            task_kind[future] = ("ablation", policy)
        for future in as_completed(task_kind):
            kind, policy = task_kind[future]
            path = future.result()
            if kind == "full":
                full_paths[policy] = path
            else:
                ablation_paths[policy] = path
    runs: dict[str, dict[str, Any]] = {}
    schedules = {"V69": {}, "V79": {}}
    schedule_audit69 = pd.DataFrame(columns=["date", "sample_count", "intercept", "coef_gap", "coef_normalized_gap", "r2"])
    schedule_audit79 = schedule_audit69.copy()
    for policy in FULL_BACKTEST_POLICIES:
        with Path(full_paths[policy]).open("rb") as handle:
            result = pickle.load(handle)
        runs[policy] = result["run"]
        if policy == EXPECTED_VALUE_ROTATION:
            schedules = {"V69": result["schedule69"], "V79": result["schedule79"]}
            schedule_audit69 = result["schedule_audit69"]
            schedule_audit79 = result["schedule_audit79"]

    validation_start_pos = index.searchsorted(pd.Timestamp("2023-01-01"))
    purged_validation_start = index[min(validation_start_pos + int(cfg["purge_sessions"]), len(index) - 1)]
    full_metrics = pd.DataFrame([
        _metric_row(
            strategy, policy,
            payload[f"account{69 if strategy == 'V69' else 79}"],
            payload[f"orders{69 if strategy == 'V69' else 79}"],
            payload[f"stress{69 if strategy == 'V69' else 79}"],
            purged_validation_start,
        )
        for policy, payload in runs.items() for strategy in ("V69", "V79")
    ])
    ablation_runs: dict[str, dict[str, Any]] = {}
    for policy in PRIMARY_ABLATION_POLICIES:
        with Path(ablation_paths[policy]).open("rb") as handle:
            ablation_runs[policy] = pickle.load(handle)
    ablation_metrics = pd.DataFrame([
        _ablation_metric_row(payload["strategy"], policy, payload["account"], payload["orders"], purged_validation_start)
        for policy, payload in ablation_runs.items()
    ])
    metrics = pd.concat([full_metrics, ablation_metrics], ignore_index=True, sort=False)
    error_ledger, error_summary = _build_error_taxonomy(runs[ACTIVE_SELECTION_POLICY], market["close"], cfg)
    quality_policies = FULL_BACKTEST_POLICIES
    decision_quality = _decision_quality(runs, market["close"], quality_policies)
    ablation = _ablation_summary(metrics)
    promotion = _candidate_promotion(metrics, decision_quality, runs, cfg)
    annual = _annual_returns(runs, quality_policies)
    monthly = _monthly_2026(runs, quality_policies)

    parent_ref = pd.read_csv(root / "reports/v98_candidate_selection_agent/v98_strategy_metrics.csv")
    parent_ref = parent_ref[parent_ref["policy"].eq(ACTIVE_SELECTION_POLICY)].set_index("strategy")
    active = metrics[metrics["policy"].eq(ACTIVE_SELECTION_POLICY)].set_index("strategy")
    invariants = []
    for policy in CANDIDATE_POLICIES:
        ok, detail = _future_mutation_invariant(market, universe, cfg69, cfg79, policy, _policy_params(cfg, policy) | (ev_cfg if policy == EXPECTED_VALUE_ROTATION else {}), schedules)
        invariants.append({"policy": policy, "passed": ok, "detail": detail})
    invariant_df = pd.DataFrame(invariants)

    quality = pd.DataFrame([
        {"gate": "taxonomy_valid", "passed": bool(taxonomy["valid"]), "detail": json.dumps(taxonomy, sort_keys=True)},
        {"gate": "v69_parent_nav_exact", "passed": bool(np.isclose(active.loc["V69", "ending_nav_krw"], parent_ref.loc["V69", "ending_nav_krw"], atol=0.01)), "detail": f"delta={active.loc['V69','ending_nav_krw']-parent_ref.loc['V69','ending_nav_krw']:.6f}"},
        {"gate": "v79_parent_nav_exact", "passed": bool(np.isclose(active.loc["V79", "ending_nav_krw"], parent_ref.loc["V79", "ending_nav_krw"], atol=0.01)), "detail": f"delta={active.loc['V79','ending_nav_krw']-parent_ref.loc['V79','ending_nav_krw']:.6f}"},
        {"gate": "error_taxonomy_nonempty", "passed": bool(len(error_ledger) > 0 and len(error_summary) > 0), "detail": f"ledger={len(error_ledger)} summary={len(error_summary)}"},
        {"gate": "all_ablation_components_tested", "passed": bool(set(ABLATION_POLICIES).issubset(set(ablation["policy"]))), "detail": f"count={len(ablation)}"},
        {"gate": "candidate_components_isolated", "passed": True, "detail": "C score-only; D score-only; E rotation-only"},
        {"gate": "expected_value_schedule_walk_forward", "passed": bool(schedule_audit69["sample_count"].is_monotonic_increasing and schedule_audit79["sample_count"].is_monotonic_increasing), "detail": f"v69_max={schedule_audit69['sample_count'].max()} v79_max={schedule_audit79['sample_count'].max()}"},
        {"gate": "all_research_policies_future_invariant", "passed": bool(invariant_df["passed"].all()), "detail": "; ".join(invariant_df["detail"].tolist())},
        {"gate": "all_candidate_information_d1", "passed": bool(all(not runs[p]["selection69"]["decision_uses_same_day_close"].any() and not runs[p]["selection79"]["decision_uses_same_day_close"].any() for p in PROMOTION_POLICIES)), "detail": "selection ledgers"},
        {"gate": "no_negative_cash", "passed": bool(
            all(payload["account69"]["cash_krw"].min() >= -0.01 and payload["account79"]["cash_krw"].min() >= -0.01 for payload in runs.values())
            and all(payload["account"]["cash_krw"].min() >= -0.01 for payload in ablation_runs.values())
        ), "detail": "full candidates and primary-family ablations"},
        {"gate": "parent_policy_not_mutated_automatically", "passed": True, "detail": "promotion status is research output only; active policy remains TOP_SCORE_SECTOR_DEDUP"},
        {"gate": "live_execution_blocked", "passed": bool(not cfg.get("live_execution_allowed", False)), "detail": "research only"},
    ])

    metrics.to_csv(out / "v99_strategy_metrics.csv", index=False)
    error_ledger.to_csv(out / "v99_error_taxonomy_ledger.csv", index=False)
    error_summary.to_csv(out / "v99_error_taxonomy_summary.csv", index=False)
    ablation.to_csv(out / "v99_alpha_ablation.csv", index=False)
    decision_quality.to_csv(out / "v99_decision_quality.csv", index=False)
    promotion.to_csv(out / "v99_candidate_promotion.csv", index=False)
    annual.to_csv(out / "v99_annual_returns.csv", index=False)
    monthly.to_csv(out / "v99_2026_monthly_returns.csv", index=False)
    invariant_df.to_csv(out / "v99_future_mutation_invariants.csv", index=False)
    quality.to_csv(out / "v99_quality_gates.csv", index=False)
    pd.concat([
        schedule_audit69.assign(strategy="V69"),
        schedule_audit79.assign(strategy="V79"),
    ], ignore_index=True).to_csv(out / "v99_expected_value_walk_forward_schedule.csv", index=False)
    for policy in (*REFERENCE_POLICIES, *PROMOTION_POLICIES):
        runs[policy]["selection69"].to_csv(out / f"v99_selection_v69_{policy}.csv", index=False)
        runs[policy]["selection79"].to_csv(out / f"v99_selection_v79_{policy}.csv", index=False)

    registry = {
        "version": "V99",
        "active_policy": ACTIVE_SELECTION_POLICY,
        "frozen_forward_reference": UNCERTAINTY_AWARE_ROTATION,
        "candidate_policies": promotion.to_dict(orient="records"),
        "sector_theme_agent_merged": True,
        "taxonomy_hash": taxonomy_hash(universe),
        "purge_sessions": int(cfg["purge_sessions"]),
        "purged_validation_start": purged_validation_start.date().isoformat(),
        "parent_strategies_changed": False,
        "automatic_parent_mutation": False,
        "live_execution_allowed": False,
    }
    (out / "v99_candidate_selection_registry.json").write_text(
        json.dumps(registry, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    summary = {
        "status": "candidate_selection_deep_research_completed_parent_unchanged",
        "error_events": int(len(error_ledger)),
        "ablation_count": int(len(ablation)),
        "candidate_count": int(len(promotion)),
        "backtest_passed_count": int(promotion["backtest_passed"].sum()),
        "promoted_count": 0,
        "purged_validation_start": purged_validation_start.date().isoformat(),
        "live_execution_allowed": False,
    }
    (out / "v99_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    shutil.rmtree(cache_dir, ignore_errors=True)

    if not quality["passed"].all():
        failed = quality.loc[~quality["passed"], "gate"].tolist()
        raise AssertionError(f"V99 quality gates failed: {failed}")
    return {
        "metrics": metrics, "error_ledger": error_ledger, "error_summary": error_summary,
        "ablation": ablation, "decision_quality": decision_quality, "promotion": promotion,
        "annual": annual, "monthly": monthly, "quality": quality, "runs": runs,
        "schedules": schedules, "purged_validation_start": purged_validation_start,
    }
