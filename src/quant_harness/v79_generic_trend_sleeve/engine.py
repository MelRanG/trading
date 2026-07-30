from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any
import inspect
import json
import math

import numpy as np
import pandas as pd
import yaml

from quant_harness.v69_dynamic_theme_leadership import engine as v69
from quant_harness.v77_corrected_price_allocation import engine as v77
from quant_harness.v78_preregistered_alpha_research.engine import build_baseline_features
from quant_harness.v94_universe_agent.policy import build_universe_gate
from quant_harness.v98_candidate_selection_agent.policy import (
    ACTIVE_SELECTION_POLICY,
    build_sector_representative_panel,
    effective_rotation_margin,
    expected_value_rotation_gate,
    prepare_selection_features,
    ranked_representatives,
    score_distribution_diagnostics,
)
from quant_harness.v77_2_validation_integrity.engine import (
    _annual_returns,
    _dca_from_return_stream,
    _familywise_probability,
    _monthly_returns_2026,
    _relative_bootstrap_period,
    _return_table,
    _slice_metrics,
)

REPORT = "v79_generic_trend_sleeve"


def _load_config(root: Path) -> dict[str, Any]:
    return yaml.safe_load((root / "config/v79_generic_trend_sleeve.yaml").read_text(encoding="utf-8"))


def build_generic_trend_features(
    close: pd.DataFrame,
    value: pd.DataFrame,
    universe: pd.DataFrame,
    *,
    horizons: tuple[int, int, int],
    horizon_weights: tuple[float, float, float],
    trend_ma_days: int,
    minimum_history_days: int,
    minimum_median_value_20d_krw: float,
) -> dict[str, Any]:
    """Build one sector-agnostic D-1 trend score for every ETF.

    No ticker or theme receives a special rule. Cross-sectional percentile ranks
    make different-volatility sectors comparable without using future data.
    """
    tickers = universe["ticker"].astype(str).tolist()
    returns = [close[tickers].pct_change(h, fill_method=None) for h in horizons]
    ranks = [frame.rank(axis=1, pct=True, method="average") for frame in returns]
    score_raw = sum(weight * rank for weight, rank in zip(horizon_weights, ranks))
    universe_gate = build_universe_gate(
        close, value, tickers,
        minimum_history_days=minimum_history_days,
        minimum_median_value_20d_krw=minimum_median_value_20d_krw,
    )
    ma = close[tickers].rolling(trend_ma_days, min_periods=trend_ma_days).mean()
    eligible = (
        universe_gate["gate"]
        & returns[1].shift(1).gt(0)
        & returns[2].shift(1).gt(0)
        & close[tickers].shift(1).gt(ma.shift(1))
    )
    return {
        "score": score_raw.shift(1),
        "eligible": eligible.fillna(False).astype(bool),
        "liquidity": universe_gate["liquidity_median20_d1"],
        "absolute_return_short": returns[0].shift(1),
        "absolute_return_medium": returns[1].shift(1),
        "absolute_return_long": returns[2].shift(1),
    }


def select_persistent_trend_leader(
    index: pd.DatetimeIndex,
    universe: pd.DataFrame,
    features: dict[str, Any],
    *,
    minimum_hold_sessions: int,
    challenger_score_margin: float,
    confirmation_reviews: int,
    selection_policy: str = ACTIVE_SELECTION_POLICY,
    selection_policy_params: dict[str, Any] | None = None,
) -> pd.DataFrame:
    """Select a generic persistent trend leader with weekly hysteresis."""
    _, weekly = v69._review_dates(index)
    policy_params = selection_policy_params or {}
    selected_features = prepare_selection_features(
        features, family="V79", policy=selection_policy,
        consensus_min_rank=float(policy_params.get("consensus_min_rank", 0.60)),
        consensus_required_horizons=int(policy_params.get("consensus_required_horizons", 2)),
        dispersion_penalty=float(policy_params.get("dispersion_penalty", 0.20)),
    )
    selection_score = selected_features["selection_score"]
    selection_eligible = selected_features["selection_eligible"]
    sector_panel = build_sector_representative_panel(
        index, weekly, universe, selection_score, selection_eligible, selected_features["liquidity"],
    )
    sector_by_ticker = universe.set_index("ticker")["sector"].to_dict()
    name_by_ticker = universe.set_index("ticker")["name"].to_dict()
    current: str | None = None
    holding_sessions = 0
    pending: str | None = None
    pending_count = 0
    rows: list[dict[str, Any]] = []

    for pos, date in enumerate(index):
        score = selection_score.loc[date]
        eligible = selection_eligible.loc[date]
        reason = "INTRA_WEEK_HOLD"
        expected_rotation_edge = np.nan
        expected_rotation_samples = 0
        expected_rotation_reason = "NOT_APPLICABLE"
        ranked: list[tuple[str, str, float, float]] = []

        if current is not None:
            holding_sessions += 1

        if date in weekly:
            ranked = ranked_representatives(sector_panel, date)
            challenger = ranked[0][0] if ranked else None
            current_eligible = bool(eligible.get(current, False)) if current is not None else False

            if current is not None and not current_eligible:
                current = None
                holding_sessions = 0
                pending = None
                pending_count = 0
                reason = "WEEKLY_HARD_TREND_EXIT"

            if challenger is None:
                if current is None:
                    reason = "NO_ELIGIBLE_GENERIC_TREND"
            elif current is None:
                current = challenger
                holding_sessions = 1
                pending = None
                pending_count = 0
                reason = "SELECT_GENERIC_TREND_LEADER"
            elif challenger == current:
                pending = None
                pending_count = 0
                reason = "KEEP_PERSISTENT_TREND_LEADER"
            elif holding_sessions < minimum_hold_sessions:
                pending = None
                pending_count = 0
                reason = "MINIMUM_HOLD_NOT_SATISFIED"
            else:
                current_score = float(score[current]) if pd.notna(score.get(current, np.nan)) else -np.inf
                challenger_score = float(score[challenger])
                rotation_margin = effective_rotation_margin(
                    ranked, base_margin=challenger_score_margin, policy=selection_policy,
                    iqr_multiplier=float(policy_params.get("iqr_multiplier", 0.25)),
                )
                if challenger_score >= current_score + rotation_margin:
                    allowed, expected_rotation_edge, expected_rotation_samples, expected_rotation_reason = expected_value_rotation_gate(
                        date, ranked, current, policy=selection_policy,
                        schedule=policy_params.get("expected_value_schedule"),
                        minimum_samples=int(policy_params.get("minimum_walk_forward_samples", 30)),
                        cost_buffer_return=float(policy_params.get("cost_buffer_return", 0.008)),
                    )
                    if not allowed:
                        pending = None
                        pending_count = 0
                        reason = "EXPECTED_VALUE_BELOW_COST"
                    else:
                        if pending == challenger:
                            pending_count += 1
                        else:
                            pending = challenger
                            pending_count = 1
                        if pending_count >= confirmation_reviews:
                            current = challenger
                            holding_sessions = 1
                            pending = None
                            pending_count = 0
                            reason = "CONFIRMED_GENERIC_TREND_ROTATION"
                        else:
                            reason = "GENERIC_CHALLENGER_PENDING"
                else:
                    pending = None
                    pending_count = 0
                    reason = "GENERIC_CHALLENGER_MARGIN_NOT_MET"

        current_score = float(score[current]) if current is not None and pd.notna(score.get(current, np.nan)) else np.nan
        diag = score_distribution_diagnostics(ranked) if ranked else {"top_ticker": None, "runner_up_ticker": None, "top_score": np.nan, "runner_up_score": np.nan, "top_gap": np.nan, "score_iqr": np.nan}
        effective_margin = effective_rotation_margin(
            ranked, base_margin=challenger_score_margin, policy=selection_policy,
            iqr_multiplier=float(policy_params.get("iqr_multiplier", 0.25)),
        ) if ranked else float(challenger_score_margin)
        consensus_count = (
            float(selected_features["horizon_consensus_count"].loc[date, current])
            if current is not None and pd.notna(selected_features["horizon_consensus_count"].loc[date, current]) else np.nan
        )
        dispersion = (
            float(selected_features["horizon_dispersion"].loc[date, current])
            if current is not None and pd.notna(selected_features["horizon_dispersion"].loc[date, current]) else np.nan
        )
        rows.append({
            "date": date,
            "information_cutoff": index[pos - 1] if pos > 0 else pd.NaT,
            "decision_uses_same_day_close": False,
            "review_weekly": date in weekly,
            "sleeve_ticker": current,
            "sleeve_name": name_by_ticker.get(current) if current else None,
            "sleeve_sector": sector_by_ticker.get(current) if current else None,
            "sleeve_score_d1": current_score,
            "holding_sessions": holding_sessions if current else 0,
            "decision_reason": reason,
            "pending_challenger": pending,
            "pending_confirmation_count": pending_count,
            "eligible_sector_count": len(ranked),
            "candidate_selection_policy": selection_policy,
            "top_candidate_ticker": diag["top_ticker"],
            "runner_up_ticker": diag["runner_up_ticker"],
            "top_candidate_score_d1": diag["top_score"],
            "runner_up_score_d1": diag["runner_up_score"],
            "top_runner_gap_d1": diag["top_gap"],
            "candidate_score_iqr_d1": diag["score_iqr"],
            "effective_rotation_margin_d1": effective_margin,
            "leader_horizon_consensus_count_d1": consensus_count,
            "leader_horizon_dispersion_d1": dispersion,
            "expected_rotation_edge_60d_d1": expected_rotation_edge,
            "expected_rotation_training_samples_d1": expected_rotation_samples,
            "expected_rotation_gate_reason": expected_rotation_reason,
        })
    return pd.DataFrame(rows)


def build_blended_target_ledger(
    baseline_selection: pd.DataFrame,
    sleeve_selection: pd.DataFrame,
    *,
    core_ticker: str,
    base_share: float,
) -> pd.DataFrame:
    """Blend the existing strategy and a generic trend sleeve into one target map."""
    base = baseline_selection.set_index("date")
    sleeve = sleeve_selection.set_index("date")
    rows: list[dict[str, Any]] = []
    sleeve_share = 1.0 - base_share
    for date in base.index:
        leader_raw = base.loc[date, "leader_ticker"]
        base_leader = str(leader_raw) if pd.notna(leader_raw) else None
        base_leader_weight = float(base.loc[date, "target_leader_weight"] or 0.0) if base_leader else 0.0
        sleeve_raw = sleeve.loc[date, "sleeve_ticker"]
        sleeve_ticker = str(sleeve_raw) if pd.notna(sleeve_raw) else None

        weights: dict[str, float] = {}
        weights[core_ticker] = base_share * (1.0 - base_leader_weight)
        if base_leader:
            weights[base_leader] = weights.get(base_leader, 0.0) + base_share * base_leader_weight
        else:
            weights[core_ticker] += base_share * base_leader_weight
        if sleeve_ticker:
            weights[sleeve_ticker] = weights.get(sleeve_ticker, 0.0) + sleeve_share
        else:
            weights[core_ticker] += sleeve_share
        weights = {ticker: float(weight) for ticker, weight in weights.items() if weight > 1e-12}
        total = sum(weights.values())
        if not np.isclose(total, 1.0, atol=1e-12):
            weights[core_ticker] = weights.get(core_ticker, 0.0) + (1.0 - total)
        rows.append({
            "date": date,
            "information_cutoff": min(base.loc[date, "information_cutoff"], sleeve.loc[date, "information_cutoff"])
            if pd.notna(base.loc[date, "information_cutoff"]) and pd.notna(sleeve.loc[date, "information_cutoff"])
            else pd.NaT,
            "decision_uses_same_day_close": False,
            "base_share": base_share,
            "trend_sleeve_share": sleeve_share,
            "base_leader_ticker": base_leader,
            "trend_sleeve_ticker": sleeve_ticker,
            "target_weights_json": json.dumps(weights, sort_keys=True),
            "target_weight_sum": sum(weights.values()),
        })
    return pd.DataFrame(rows)


def _target_map(value: Any) -> dict[str, float]:
    if isinstance(value, dict):
        return {str(k): float(v) for k, v in value.items()}
    return {str(k): float(v) for k, v in json.loads(str(value)).items()}


def execute_multi_target(
    close: pd.DataFrame,
    open_px: pd.DataFrame,
    adv20_d1: pd.DataFrame,
    target_ledger: pd.DataFrame,
    *,
    initial_capital: float,
    spec: v77.ExecutionSpec,
    rebalance_band: float,
    scenario: str,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    ledger = target_ledger.set_index("date").reindex(close.index)
    cash = float(initial_capital)
    quantities: dict[str, int] = {}
    prior_signature: tuple[tuple[str, float], ...] | None = None
    pending = False
    daily: list[dict[str, Any]] = []
    orders: list[dict[str, Any]] = []
    participation_limited_orders = 0
    missing_open_rejections = 0

    for date in close.index:
        targets = _target_map(ledger.loc[date, "target_weights_json"])
        signature = tuple(sorted((ticker, round(weight, 12)) for ticker, weight in targets.items()))
        tracked = set(quantities) | set(targets)
        missing = [
            ticker for ticker in tracked
            if (quantities.get(ticker, 0) > 0 or targets.get(ticker, 0.0) > 0)
            and (ticker not in open_px.columns or pd.isna(open_px.loc[date, ticker]))
        ]
        if missing:
            missing_open_rejections += 1
            raise ValueError(f"missing adjusted open on executable date {date}: {sorted(missing)}")

        nav_open = cash + sum(qty * float(open_px.loc[date, ticker]) for ticker, qty in quantities.items())
        actual_weights = {
            ticker: quantities.get(ticker, 0) * float(open_px.loc[date, ticker]) / nav_open
            for ticker in tracked
        } if nav_open > 0 else {ticker: 0.0 for ticker in tracked}
        max_drift = max((abs(actual_weights.get(t, 0.0) - targets.get(t, 0.0)) for t in tracked), default=0.0)
        target_changed = signature != prior_signature
        trigger = bool(pending or target_changed or max_drift >= rebalance_band)
        pending = False

        if trigger:
            desired = {
                ticker: int(math.floor(nav_open * weight / float(open_px.loc[date, ticker])))
                for ticker, weight in targets.items()
            }
            for ticker in quantities:
                desired.setdefault(ticker, 0)

            for ticker in sorted(quantities):
                delta = quantities.get(ticker, 0) - desired.get(ticker, 0)
                if delta <= 0:
                    continue
                raw_open = float(open_px.loc[date, ticker])
                adv = float(adv20_d1.loc[date, ticker]) if ticker in adv20_d1.columns else np.nan
                cap_qty = int(math.floor((adv * spec.max_participation_of_d1_adv) / raw_open)) if np.isfinite(adv) and adv > 0 else 0
                fill_qty = min(delta, cap_qty)
                if fill_qty < delta:
                    participation_limited_orders += 1
                    pending = True
                if fill_qty <= 0 or fill_qty * raw_open < spec.minimum_order_notional_krw:
                    pending = pending or delta > 0
                    continue
                notional_at_open = fill_qty * raw_open
                impact = v77._impact_bps(notional_at_open, adv, spec)
                execution_price = raw_open * (1.0 - (spec.half_spread_bps + impact) / 10000.0)
                fee = fill_qty * execution_price * spec.sell_fee_bps / 10000.0
                cash += fill_qty * execution_price - fee
                quantities[ticker] = quantities.get(ticker, 0) - fill_qty
                orders.append({
                    "date": date, "scenario": scenario, "ticker": ticker, "side": "SELL",
                    "quantity": fill_qty, "reference_open_krw": raw_open,
                    "execution_price_krw": execution_price, "fee_krw": fee,
                    "impact_bps": impact, "adv20_d1_krw": adv,
                    "notional_at_reference_open_krw": notional_at_open,
                    "participation_of_d1_adv": notional_at_open / adv if np.isfinite(adv) and adv > 0 else np.nan,
                    "rebalancing_policy": f"TARGET_CHANGE_OR_BAND_{rebalance_band:.2f}",
                })

            buy_order = sorted(
                targets,
                key=lambda ticker: (
                    desired.get(ticker, 0) - quantities.get(ticker, 0),
                    targets[ticker],
                    ticker,
                ),
                reverse=True,
            )
            for ticker in buy_order:
                delta = desired.get(ticker, 0) - quantities.get(ticker, 0)
                if delta <= 0:
                    continue
                raw_open = float(open_px.loc[date, ticker])
                adv = float(adv20_d1.loc[date, ticker]) if ticker in adv20_d1.columns else np.nan
                cap_qty = int(math.floor((adv * spec.max_participation_of_d1_adv) / raw_open)) if np.isfinite(adv) and adv > 0 else 0
                fill_qty = min(delta, cap_qty)
                if fill_qty < delta:
                    participation_limited_orders += 1
                    pending = True
                if fill_qty <= 0 or fill_qty * raw_open < spec.minimum_order_notional_krw:
                    pending = pending or delta > 0
                    continue
                requested = fill_qty
                fill_qty, impact, execution_price, fee, participation = v77._buy_fill_terms(
                    cash=cash, max_quantity=requested, raw_open=raw_open, adv=adv, spec=spec
                )
                if fill_qty < requested:
                    pending = True
                if fill_qty <= 0 or fill_qty * raw_open < spec.minimum_order_notional_krw:
                    pending = True
                    continue
                notional_at_open = fill_qty * raw_open
                cash -= fill_qty * execution_price + fee
                quantities[ticker] = quantities.get(ticker, 0) + fill_qty
                orders.append({
                    "date": date, "scenario": scenario, "ticker": ticker, "side": "BUY",
                    "quantity": fill_qty, "reference_open_krw": raw_open,
                    "execution_price_krw": execution_price, "fee_krw": fee,
                    "impact_bps": impact, "adv20_d1_krw": adv,
                    "notional_at_reference_open_krw": notional_at_open,
                    "participation_of_d1_adv": participation,
                    "rebalancing_policy": f"TARGET_CHANGE_OR_BAND_{rebalance_band:.2f}",
                })

        nav = cash + sum(qty * float(close.loc[date, ticker]) for ticker, qty in quantities.items())
        daily.append({
            "date": date, "scenario": scenario, "cash_krw": cash, "nav_krw": nav,
            "rebalance_triggered": trigger, "pending_execution": pending,
            "max_abs_weight_drift_open": max_drift,
            "target_weights_json": json.dumps(targets, sort_keys=True),
            "holdings_json": json.dumps({k: v for k, v in quantities.items() if v != 0}, sort_keys=True),
            "information_cutoff": ledger.loc[date, "information_cutoff"],
        })
        prior_signature = signature

    account = pd.DataFrame(daily)
    order_frame = pd.DataFrame(orders)
    audit = {
        "missing_open_rejections": missing_open_rejections,
        "participation_limited_orders": participation_limited_orders,
        "negative_cash_days": int(account["cash_krw"].lt(-0.01).sum()),
        "pending_days": int(account["pending_execution"].sum()),
    }
    return account, order_frame, audit


def _strategy_source_genericity() -> dict[str, Any]:
    source = inspect.getsource(build_generic_trend_features) + inspect.getsource(select_persistent_trend_leader)
    forbidden = ["091160", "semiconductor", "battery", "bio", "robot", "energy", "financial"]
    hits = [token for token in forbidden if token.lower() in source.lower()]
    return {"passed": not hits, "forbidden_hits": hits}


def run(root: Path | str) -> dict[str, Any]:
    root = Path(root)
    out = root / "reports" / REPORT
    out.mkdir(parents=True, exist_ok=True)
    cfg = _load_config(root)
    cfg77 = replace(v77._load_config(root), end_date=str(cfg["data_end"]))
    market = v77.load_adjusted_market(root, cfg77)
    v69_cfg = replace(
        v69._load_config(root), end_date=cfg77.end_date,
        core_ticker=cfg77.core_ticker, benchmark_ticker=cfg77.benchmark_ticker,
        leader_weight=float(cfg["strategy_design"]["fixed_existing_alpha_leader_weight"]),
    )
    universe = v69._load_universe(root, v69_cfg)

    baseline_features = build_baseline_features(market["close"], market["value"], universe, v69_cfg)
    baseline_selection = v69.select_dynamic_leader(market["close"].index, universe, baseline_features, v69_cfg)
    baseline_selection["target_leader_weight"] = (
        baseline_selection["leader_ticker"].notna().astype(float)
        * float(cfg["strategy_design"]["fixed_existing_alpha_leader_weight"])
    )

    sleeve_cfg = cfg["trend_sleeve"]
    sleeve_features = build_generic_trend_features(
        market["close"], market["value"], universe,
        horizons=tuple(int(x) for x in sleeve_cfg["horizons_days"]),
        horizon_weights=tuple(float(x) for x in sleeve_cfg["horizon_weights"]),
        trend_ma_days=int(sleeve_cfg["trend_ma_days"]),
        minimum_history_days=int(sleeve_cfg["minimum_history_days"]),
        minimum_median_value_20d_krw=float(sleeve_cfg["minimum_median_value_20d_krw"]),
    )
    sleeve_selection = select_persistent_trend_leader(
        market["close"].index, universe, sleeve_features,
        minimum_hold_sessions=int(sleeve_cfg["minimum_hold_sessions"]),
        challenger_score_margin=float(sleeve_cfg["challenger_score_margin"]),
        confirmation_reviews=int(sleeve_cfg["challenger_confirmation_reviews"]),
    )

    baseline_account, baseline_orders, baseline_audit = v77.execute(
        market["close"], market["open"], market["adv20_d1"], baseline_selection,
        cfg77.core_ticker, cfg77.initial_capital_krw, "FROM_SELECTION", "DAILY_EXACT", cfg77.base_execution,
    )
    baseline_name = "V69_FIXED80_DAILY_CORRECTED"
    baseline_account["scenario"] = baseline_name
    baseline_orders["scenario"] = baseline_name

    accounts: dict[str, pd.DataFrame] = {baseline_name: baseline_account}
    orders_map: dict[str, pd.DataFrame] = {baseline_name: baseline_orders}
    audits: dict[str, dict[str, Any]] = {baseline_name: baseline_audit}
    target_ledgers: dict[str, pd.DataFrame] = {}
    candidate_names: list[str] = []

    for base_share in [float(x) for x in cfg["strategy_design"]["candidate_base_shares"]]:
        scenario = f"V79_GENERIC_TREND_BASE{int(round(base_share * 100))}_SLEEVE{int(round((1-base_share)*100))}"
        candidate_names.append(scenario)
        targets = build_blended_target_ledger(
            baseline_selection, sleeve_selection, core_ticker=cfg77.core_ticker, base_share=base_share
        )
        account, orders, audit = execute_multi_target(
            market["close"], market["open"], market["adv20_d1"], targets,
            initial_capital=cfg77.initial_capital_krw, spec=cfg77.base_execution,
            rebalance_band=float(cfg["execution"]["rebalance_band"]), scenario=scenario,
        )
        accounts[scenario], orders_map[scenario], audits[scenario], target_ledgers[scenario] = account, orders, audit, targets

    core_hold = v77._buy_hold(
        market["close"][cfg77.core_ticker], market["open"][cfg77.core_ticker],
        cfg77.initial_capital_krw, cfg77.base_execution,
    )
    sector_hold = v77._buy_hold(
        market["close"][cfg77.semiconductor_benchmark_ticker],
        market["open"][cfg77.semiconductor_benchmark_ticker],
        cfg77.initial_capital_krw, cfg77.base_execution,
    )
    kospi_close = market["close"][cfg77.benchmark_ticker].dropna()
    kospi_nav = kospi_close / kospi_close.iloc[0] * cfg77.initial_capital_krw
    nav_map = {name: frame.set_index("date")["nav_krw"] for name, frame in accounts.items()}
    nav_map.update({
        "KODEX200_BUY_HOLD": core_hold,
        "BEST_SECTOR_BENCHMARK_BUY_HOLD": sector_hold,
        "KOSPI_INDEX": kospi_nav,
    })

    periods = cfg["periods"]
    comparison_periods = {
        "development": periods["development"],
        "validation": periods["validation"],
        "observed": periods["observed_only"],
        "recent_1y": periods["recent_1y"],
    }
    metrics = _return_table(nav_map, comparison_periods, cfg77.initial_capital_krw)
    for period_name, (start, end) in comparison_periods.items():
        metrics[f"{period_name}_sharpe"] = metrics["scenario"].map({
            name: _slice_metrics(nav, start, end, cfg77.initial_capital_krw)["sharpe"] for name, nav in nav_map.items()
        })
        metrics[f"{period_name}_mdd_pct"] = metrics["scenario"].map({
            name: _slice_metrics(nav, start, end, cfg77.initial_capital_krw)["mdd_pct"] for name, nav in nav_map.items()
        })
    metrics["order_count"] = metrics["scenario"].map({name: len(frame) for name, frame in orders_map.items()}).fillna(1).astype(int)
    metrics["negative_cash_days"] = metrics["scenario"].map({name: audit["negative_cash_days"] for name, audit in audits.items()}).fillna(0).astype(int)

    metrics_idx = metrics.set_index("scenario")
    baseline_row = metrics_idx.loc[baseline_name]
    core_row = metrics_idx.loc["KODEX200_BUY_HOLD"]
    sector_row = metrics_idx.loc["BEST_SECTOR_BENCHMARK_BUY_HOLD"]
    bootstrap_rows: list[dict[str, Any]] = []
    gate_rows: list[dict[str, Any]] = []
    selection_passes: list[str] = []

    for candidate in candidate_names:
        dev_candidate = _slice_metrics(nav_map[candidate], *periods["development"], cfg77.initial_capital_krw)
        dev_baseline = _slice_metrics(nav_map[baseline_name], *periods["development"], cfg77.initial_capital_krw)
        val_candidate = _slice_metrics(nav_map[candidate], *periods["validation"], cfg77.initial_capital_krw)
        val_baseline = _slice_metrics(nav_map[baseline_name], *periods["validation"], cfg77.initial_capital_krw)
        boot = _relative_bootstrap_period(
            nav_map[candidate], nav_map[baseline_name], *periods["validation"], samples=5000, block_months=3
        )
        familywise = _familywise_probability(boot["positive_probability"], len(candidate_names))
        stress_account, stress_orders, stress_audit = execute_multi_target(
            market["close"], market["open"], market["adv20_d1"], target_ledgers[candidate],
            initial_capital=cfg77.initial_capital_krw, spec=cfg77.stress_execution,
            rebalance_band=float(cfg["execution"]["rebalance_band"]), scenario=candidate + "__STRESS",
        )
        stress_validation = _slice_metrics(
            stress_account.set_index("date")["nav_krw"], *periods["validation"], cfg77.initial_capital_krw
        )
        oracle = v77.independent_reconstruct(cfg77.initial_capital_krw, market["close"], orders_map[candidate])
        joined = accounts[candidate].merge(oracle, on="date", how="left")
        oracle_error = float((joined["nav_krw"] - joined["oracle_nav_krw"]).abs().max())
        research_pass = bool(
            dev_candidate["return_pct"] > dev_baseline["return_pct"]
            and val_candidate["return_pct"] > val_baseline["return_pct"]
            and dev_candidate["sharpe"] >= dev_baseline["sharpe"]
            and val_candidate["sharpe"] >= val_baseline["sharpe"]
            and val_candidate["mdd_pct"] >= val_baseline["mdd_pct"] - float(cfg["promotion"]["mdd_tolerance_pp"])
            and boot["positive_probability"] >= float(cfg["promotion"]["validation_bootstrap_probability"])
            and familywise >= float(cfg["promotion"]["familywise_probability"])
            and stress_validation["return_pct"] >= val_baseline["return_pct"]
            and stress_audit["negative_cash_days"] == 0
            and oracle_error <= 0.01
        )
        if research_pass:
            selection_passes.append(candidate)
        row = metrics_idx.loc[candidate]
        user_goal = bool(
            row["return_pct"] > core_row["return_pct"]
            and row["recent_1y_return_pct"] > core_row["recent_1y_return_pct"]
            and row["return_pct"] > sector_row["return_pct"]
            and row["recent_1y_return_pct"] > sector_row["recent_1y_return_pct"]
        )
        bootstrap_rows.append({"candidate": candidate, **boot, "familywise_positive_probability": familywise})
        gate_rows.append({
            "candidate": candidate,
            "research_selection_passed": research_pass,
            "user_goal_diagnostic_passed": user_goal,
            "development_delta_pp": dev_candidate["return_pct"] - dev_baseline["return_pct"],
            "validation_delta_pp": val_candidate["return_pct"] - val_baseline["return_pct"],
            "development_sharpe_delta": dev_candidate["sharpe"] - dev_baseline["sharpe"],
            "validation_sharpe_delta": val_candidate["sharpe"] - val_baseline["sharpe"],
            "validation_mdd_delta_pp": val_candidate["mdd_pct"] - val_baseline["mdd_pct"],
            "validation_stress_return_pct": stress_validation["return_pct"],
            "raw_bootstrap_probability": boot["positive_probability"],
            "familywise_probability": familywise,
            "max_oracle_nav_error_krw": oracle_error,
            "beats_kodex200_full": bool(row["return_pct"] > core_row["return_pct"]),
            "beats_kodex200_recent_1y": bool(row["recent_1y_return_pct"] > core_row["recent_1y_return_pct"]),
            "beats_best_sector_full": bool(row["return_pct"] > sector_row["return_pct"]),
            "beats_best_sector_recent_1y": bool(row["recent_1y_return_pct"] > sector_row["recent_1y_return_pct"]),
        })
        stress_account.to_csv(root / "reports" / REPORT / f"v79_account_{candidate.lower()}__stress.csv", index=False)
        stress_orders.to_csv(root / "reports" / REPORT / f"v79_orders_{candidate.lower()}__stress.csv", index=False)

    candidate_gates = pd.DataFrame(gate_rows)
    genericity = _strategy_source_genericity()
    strict_d1 = bool(
        (sleeve_selection.dropna(subset=["information_cutoff"])["information_cutoff"]
         < sleeve_selection.dropna(subset=["information_cutoff"])["date"]).all()
    )
    distinct_sectors = int(sleeve_selection["sleeve_sector"].dropna().nunique())
    target_weight_ok = all(
        np.allclose(frame["target_weight_sum"].to_numpy(float), 1.0, atol=1e-12)
        for frame in target_ledgers.values()
    )
    order_math_ok = True
    for orders in orders_map.values():
        if orders.empty:
            continue
        expected = orders["quantity"] * orders["reference_open_krw"]
        order_math_ok = order_math_ok and bool((expected - orders["notional_at_reference_open_krw"]).abs().max() <= 0.01)
        valid = orders["adv20_d1_krw"].gt(0)
        if valid.any():
            participation = expected[valid] / orders.loc[valid, "adv20_d1_krw"]
            order_math_ok = order_math_ok and bool((participation - orders.loc[valid, "participation_of_d1_adv"]).abs().max() <= 1e-12)

    shadow = None
    if selection_passes:
        shadow = str(metrics[metrics["scenario"].isin(selection_passes)].sort_values(
            ["validation_return_pct", "validation_sharpe"], ascending=False
        ).iloc[0]["scenario"])

    quality_gates = pd.DataFrame([
        {"gate": "NO_THEME_OR_TICKER_SPECIFIC_STRATEGY_RULE", "passed": genericity["passed"], "detail": json.dumps(genericity, ensure_ascii=False)},
        {"gate": "EXACTLY_TWO_PREREGISTERED_BLEND_CANDIDATES", "passed": len(candidate_names) == 2, "detail": ",".join(candidate_names)},
        {"gate": "STRICT_D1_INFORMATION_CUTOFF", "passed": strict_d1, "detail": "generic sleeve decisions use D-1 information"},
        {"gate": "PERSISTENCE_AND_HYSTERESIS_ENABLED", "passed": int(sleeve_cfg["minimum_hold_sessions"]) > 0 and float(sleeve_cfg["challenger_score_margin"]) > 0 and int(sleeve_cfg["challenger_confirmation_reviews"]) > 1, "detail": f"min_hold={sleeve_cfg['minimum_hold_sessions']}, margin={sleeve_cfg['challenger_score_margin']}, confirmations={sleeve_cfg['challenger_confirmation_reviews']}"},
        {"gate": "MULTI_SECTOR_BEHAVIOUR_OBSERVED", "passed": distinct_sectors >= 4, "detail": f"distinct_selected_sectors={distinct_sectors}"},
        {"gate": "TARGET_WEIGHTS_SUM_TO_ONE", "passed": target_weight_ok, "detail": "all daily target maps sum to 1"},
        {"gate": "CORRECTED_ORDER_MATH", "passed": order_math_ok and all(a["negative_cash_days"] == 0 for a in audits.values()), "detail": f"scenarios={len(audits)}"},
        {"gate": "OBSERVED_PERIOD_EXCLUDED_FROM_RESEARCH_SELECTION", "passed": True, "detail": "selection gates use development and validation only"},
        {"gate": "RESEARCH_SELECTION", "passed": bool(selection_passes), "detail": ",".join(selection_passes) if selection_passes else "none"},
        {"gate": "LIVE_AND_PAPER_AUTO_PROMOTION_BLOCKED", "passed": True, "detail": "requires at least 60 new unseen forward sessions"},
    ])

    metrics.sort_values("return_pct", ascending=False).to_csv(out / "v79_all_strategy_metrics.csv", index=False)
    candidate_gates.to_csv(out / "v79_candidate_gates.csv", index=False)
    pd.DataFrame(bootstrap_rows).to_csv(out / "v79_validation_bootstrap.csv", index=False)
    sleeve_selection.to_csv(out / "v79_generic_trend_selection.csv", index=False)
    quality_gates.to_csv(out / "v79_quality_gates.csv", index=False)
    _annual_returns(nav_map, cfg77.initial_capital_krw).to_csv(out / "v79_annual_returns.csv", index=False)
    _monthly_returns_2026(nav_map, cfg77.initial_capital_krw).to_csv(out / "v79_2026_monthly_returns.csv", index=False)
    dca_rows = []
    for scenario, nav in nav_map.items():
        dca = _dca_from_return_stream(nav, initial=cfg77.initial_capital_krw, monthly_contribution=300_000.0)
        month_count = len(set(zip(dca.index.year, dca.index.month)))
        total = cfg77.initial_capital_krw + 300_000.0 * max(month_count - 1, 0)
        dca_rows.append({
            "scenario": scenario, "ending_value_krw": float(dca.iloc[-1]),
            "total_contributions_krw": total,
            "gain_on_contributions_pct": float((dca.iloc[-1] / total - 1.0) * 100.0),
        })
    pd.DataFrame(dca_rows).to_csv(out / "v79_dca_comparison.csv", index=False)
    for name, account in accounts.items():
        account.to_csv(out / f"v79_account_{name.lower()}.csv", index=False)
        orders_map[name].to_csv(out / f"v79_orders_{name.lower()}.csv", index=False)
    for name, targets in target_ledgers.items():
        targets.to_csv(out / f"v79_targets_{name.lower()}.csv", index=False)

    decision = {
        "status": "v79_generic_persistent_trend_sleeve_research_complete_live_blocked",
        "data_end": cfg["data_end"],
        "operational_control": baseline_name,
        "research_selection_passes": selection_passes,
        "shadow_challenger": shadow,
        "generic_strategy_rule": True,
        "specific_theme_or_ticker_rule_used": False,
        "distinct_selected_sectors": distinct_sectors,
        "user_goal_passes": candidate_gates[candidate_gates["user_goal_diagnostic_passed"]]["candidate"].tolist(),
        "minimum_new_unseen_forward_sessions": int(cfg["promotion"]["minimum_unseen_forward_sessions_after_research"]),
        "live_allowed": False,
        "paper_auto_promotion_allowed": False,
        "quality_gates": quality_gates.to_dict("records"),
    }
    (out / "v79_decision.json").write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")

    focus_names = [baseline_name, *candidate_names, "KODEX200_BUY_HOLD", "BEST_SECTOR_BENCHMARK_BUY_HOLD", "KOSPI_INDEX"]
    focus = metrics[metrics["scenario"].isin(focus_names)].sort_values("return_pct", ascending=False)
    summary = [
        "# V79 범용 지속추세 슬리브 연구", "",
        "- 특정 반도체 티커·섹터 조건: `없음`",
        "- 동일 규칙 적용 대상: `전체 비광역 ETF 유니버스`",
        f"- 연구 선택 통과: `{selection_passes or 'none'}`",
        f"- Shadow challenger: `{shadow or 'none'}`",
        "- Live/Paper 자동 승격: `차단`", "",
        "## 주요 비교", "", focus.to_markdown(index=False), "",
        "## 후보 게이트", "", candidate_gates.to_markdown(index=False), "",
        "## 하네스 게이트", "", quality_gates.to_markdown(index=False), "",
        "## 해석", "",
        "관찰구간과 최근 1년은 전략 선택에 사용하지 않았다. 성공 여부와 관계없이 최근 강세 섹터 참여율은 진단값으로 공개하며, 실제 승격에는 새롭게 쌓이는 최소 60거래일의 미관찰 forward shadow가 필요하다.",
    ]
    (out / "V79_KOREAN_SUMMARY.md").write_text("\n".join(summary), encoding="utf-8")
    return decision
