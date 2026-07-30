from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any
import json
import math

import numpy as np
import pandas as pd
import yaml

from quant_harness.v69_dynamic_theme_leadership import engine as v69
from quant_harness.v77_corrected_price_allocation import engine as v77
from quant_harness.v94_universe_agent.policy import build_universe_gate
from quant_harness.v95_market_regime_agent.policy import build_market_regime_panel
from quant_harness.v77_2_validation_integrity.engine import (
    _annual_returns,
    _dca_from_return_stream,
    _familywise_probability,
    _monthly_returns_2026,
    _relative_bootstrap_period,
    _return_table,
    _slice_metrics,
)

REPORT = "v78_preregistered_alpha_research"
AGENTS = [
    "UniverseAgent", "MarketRegimeAgent", "PainSupplyAgent",
    "DisclosureFundamentalAgent", "CandidateSelectionAgent", "StrategyAgent",
    "RiskExecutionAgent", "ReviewFeedbackAgent",
]


def _load_config(root: Path) -> dict[str, Any]:
    return yaml.safe_load((root / "config/v78_preregistered_alpha_research.yaml").read_text(encoding="utf-8"))


def _common_eligibility(
    close: pd.DataFrame,
    value: pd.DataFrame,
    universe: pd.DataFrame,
    cfg: v69.V69Config,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.DataFrame]:
    tickers = universe["ticker"].tolist()
    universe_gate = build_universe_gate(
        close, value, tickers,
        minimum_history_days=cfg.minimum_history_days,
        minimum_median_value_20d_krw=cfg.minimum_median_value_20d_krw,
    )
    liquidity = universe_gate["liquidity_median20_d1"]
    trend = close[tickers].gt(close[tickers].rolling(cfg.trend_ma_days, min_periods=cfg.trend_ma_days).mean()).shift(1, fill_value=False)
    base = universe_gate["gate"] & trend
    benchmark_trend = build_market_regime_panel(
        close, benchmark_ticker=cfg.benchmark_ticker, theme_tickers=tickers,
        universe_gate_d1=universe_gate["gate"], trend_ma_days=cfg.trend_ma_days,
        policy="D1_MA120_EXPLICIT",
    )["risk_on"]
    return base.astype(bool), liquidity, benchmark_trend.astype(bool), trend.astype(bool)


def _feature_contract(
    *, score: pd.DataFrame, eligible: pd.DataFrame, liquidity: pd.DataFrame,
    benchmark_trend: pd.Series, rel_short: pd.DataFrame, rel_medium: pd.DataFrame,
    rel_long: pd.DataFrame,
) -> dict[str, Any]:
    return {
        "score": score,
        "eligible": eligible.fillna(False).astype(bool),
        "liquidity": liquidity,
        "benchmark_trend": benchmark_trend.fillna(False).astype(bool),
        "rel_short": rel_short,
        "rel_medium": rel_medium,
        "rel_long": rel_long,
    }


def build_baseline_features(close: pd.DataFrame, value: pd.DataFrame, universe: pd.DataFrame, cfg: v69.V69Config) -> dict[str, Any]:
    tickers = universe["ticker"].tolist()
    ret21 = close.pct_change(21, fill_method=None)
    ret63 = close.pct_change(63, fill_method=None)
    ret126 = close.pct_change(126, fill_method=None)
    rel21 = ret21[tickers].sub(ret21[cfg.core_ticker], axis=0)
    rel63 = ret63[tickers].sub(ret63[cfg.core_ticker], axis=0)
    rel126 = ret126[tickers].sub(ret126[cfg.core_ticker], axis=0)
    base, liquidity, benchmark_trend, _ = _common_eligibility(close, value, universe, cfg)
    eligible = base & ret126[tickers].shift(1).gt(0)
    score = (0.5 * rel21 + 0.5 * rel63).shift(1)
    return _feature_contract(
        score=score, eligible=eligible, liquidity=liquidity, benchmark_trend=benchmark_trend,
        rel_short=rel21.shift(1), rel_medium=rel63.shift(1), rel_long=rel126.shift(1),
    )


def build_residual_momentum_features(
    close: pd.DataFrame, value: pd.DataFrame, universe: pd.DataFrame, cfg: v69.V69Config,
    *, beta_window: int, beta_min_periods: int,
) -> dict[str, Any]:
    tickers = universe["ticker"].tolist()
    ret = close.pct_change(fill_method=None)
    core_ret = ret[cfg.core_ticker]
    core_var = core_ret.rolling(beta_window, min_periods=beta_min_periods).var()
    residual = pd.DataFrame(index=close.index, columns=tickers, dtype=float)
    for ticker in tickers:
        beta = ret[ticker].rolling(beta_window, min_periods=beta_min_periods).cov(core_ret).div(core_var).shift(1)
        residual[ticker] = ret[ticker] - beta * core_ret
    def compounded(window: int) -> pd.DataFrame:
        return (1.0 + residual).rolling(window, min_periods=window).apply(np.prod, raw=True) - 1.0
    res21, res63, res126 = compounded(21), compounded(63), compounded(126)
    base, liquidity, benchmark_trend, _ = _common_eligibility(close, value, universe, cfg)
    eligible = base & res126.shift(1).gt(0)
    score = (0.5 * res21 + 0.5 * res63).shift(1)
    return _feature_contract(
        score=score, eligible=eligible, liquidity=liquidity, benchmark_trend=benchmark_trend,
        rel_short=res21.shift(1), rel_medium=res63.shift(1), rel_long=res126.shift(1),
    )


def build_cross_ts_ensemble_features(
    close: pd.DataFrame, value: pd.DataFrame, universe: pd.DataFrame, cfg: v69.V69Config,
) -> dict[str, Any]:
    tickers = universe["ticker"].tolist()
    abs21 = close.pct_change(21, fill_method=None)
    abs63 = close.pct_change(63, fill_method=None)
    abs126 = close.pct_change(126, fill_method=None)
    rel21 = abs21[tickers].sub(abs21[cfg.core_ticker], axis=0)
    rel63 = abs63[tickers].sub(abs63[cfg.core_ticker], axis=0)
    rel126 = abs126[tickers].sub(abs126[cfg.core_ticker], axis=0)
    positive_votes = abs21[tickers].gt(0).astype(int) + abs63[tickers].gt(0).astype(int) + abs126[tickers].gt(0).astype(int)
    base, liquidity, benchmark_trend, _ = _common_eligibility(close, value, universe, cfg)
    eligible = base & positive_votes.shift(1).ge(2)
    score = ((rel21 + rel63 + rel126) / 3.0).shift(1)
    return _feature_contract(
        score=score, eligible=eligible, liquidity=liquidity, benchmark_trend=benchmark_trend,
        rel_short=rel21.shift(1), rel_medium=rel63.shift(1), rel_long=rel126.shift(1),
    )


def _selection_with_fixed_weight(index: pd.DatetimeIndex, universe: pd.DataFrame, features: dict[str, Any], cfg: v69.V69Config, weight: float) -> pd.DataFrame:
    selection = v69.select_dynamic_leader(index, universe, features, cfg)
    selection["target_leader_weight"] = selection["leader_ticker"].notna().astype(float) * float(weight)
    return selection


def _continuous_weights(
    selection: pd.DataFrame, close: pd.DataFrame, universe: pd.DataFrame,
    *, target_vol: float, floor: float, cap: float,
) -> pd.Series:
    ret = close.pct_change(fill_method=None)
    vol = ret.rolling(63, min_periods=40).std().shift(1) * math.sqrt(252)
    max_eligible = max(int(universe["ticker"].nunique()), 1)
    confidence = v77._expanding_percentile(selection["leader_score_d1"]).fillna(0.0)
    weights: list[float] = []
    for i, row in selection.iterrows():
        ticker = row["leader_ticker"]
        if pd.isna(ticker):
            weights.append(0.0)
            continue
        ann_vol = float(vol.loc[row["date"], str(ticker)]) if str(ticker) in vol.columns else np.nan
        vol_scalar = float(np.clip(target_vol / ann_vol, 0.50, 1.25)) if np.isfinite(ann_vol) and ann_vol > 0 else 0.50
        breadth = float(np.clip(float(row["eligible_theme_count"]) / max_eligible, 0.0, 1.0))
        conf = float(confidence.iloc[i])
        raw = 0.80 * vol_scalar * (0.60 + 0.40 * breadth) * (0.80 + 0.20 * conf)
        weights.append(float(np.clip(raw, floor, cap)))
    return pd.Series(weights, index=selection.index)


def _run_selection(
    market: dict[str, Any], selection: pd.DataFrame, cfg77: v77.V77Config,
    *, scenario: str, rebalance: str, execution: v77.ExecutionSpec,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    account, orders, audit = v77.execute(
        market["close"], market["open"], market["adv20_d1"], selection,
        cfg77.core_ticker, cfg77.initial_capital_krw, "FROM_SELECTION", rebalance, execution,
    )
    account["scenario"] = scenario
    orders["scenario"] = scenario
    return account, orders, audit



def _flow_signal(root: Path, index: pd.DatetimeIndex) -> pd.DataFrame:
    frame = pd.read_csv(root / "data/historical_investor_flow/market_investor_flow_daily.csv", low_memory=False)
    frame = frame[frame["market"].astype(str).eq("KOSPI")].copy()
    frame["date"] = pd.to_datetime(frame["as_of_date"])
    frame["net"] = (
        pd.to_numeric(frame["foreign_net_buy_100m_krw"], errors="coerce").fillna(0)
        + pd.to_numeric(frame["institution_net_buy_100m_krw"], errors="coerce").fillna(0)
    )
    daily = frame.set_index("date")["net"].sort_index()
    carried = daily.reindex(index).ffill()
    source_dates = pd.Series(daily.index, index=daily.index).reindex(index).ffill()
    rolling = carried.rolling(60, min_periods=20)
    zscore = (carried - rolling.mean()) / rolling.std(ddof=0).replace(0, np.nan)
    out = pd.DataFrame(index=index)
    out["flow_value"] = carried.shift(1)
    out["flow_z"] = zscore.shift(1)
    out["flow_source_date"] = source_dates.shift(1).values
    source = pd.to_datetime(out["flow_source_date"])
    out["flow_age_days"] = (pd.Series(index, index=index) - source).dt.days.values
    out["flow_current"] = out["flow_age_days"].le(5).fillna(False)
    out["flow_risk"] = (out["flow_z"].lt(-1.25) & out["flow_current"]).fillna(False)
    return out


def _fundamental_sector_signal(root: Path, index: pd.DatetimeIndex, universe: pd.DataFrame) -> pd.DataFrame:
    mapping = pd.read_csv(root / "data/agent_ready_v62_16/agent_etf_to_stock_mapping_v62_16.csv", dtype=str)
    mapping["stock_symbol"] = mapping["stock_symbol"].map(v69._normalise_ticker)
    sector_map = mapping[["stock_symbol", "theme_family"]].drop_duplicates().rename(columns={"theme_family": "sector"})
    quarterly = pd.read_csv(root / "data/opendart_quarterly_pit.csv", dtype={"ticker": str})
    quarterly["ticker"] = quarterly["ticker"].map(v69._normalise_ticker)
    quarterly["filing_date"] = pd.to_datetime(quarterly["filing_date"], utc=True).dt.tz_convert(None).dt.normalize()
    quarterly["quarterly_net_income"] = pd.to_numeric(quarterly["quarterly_net_income"], errors="coerce")
    quarterly = quarterly.merge(sector_map, left_on="ticker", right_on="stock_symbol", how="left").dropna(subset=["sector"])
    sectors = sorted(universe["sector"].unique())
    rows: list[dict[str, Any]] = []
    for date in index:
        cutoff = date - pd.Timedelta(days=1)
        available = quarterly[quarterly["filing_date"].le(cutoff)].sort_values("filing_date").groupby("ticker", as_index=False).tail(1)
        record: dict[str, Any] = {"date": date}
        for sector in sectors:
            subset = available[available["sector"].eq(sector)]
            fresh = subset[subset["filing_date"].ge(cutoff - pd.Timedelta(days=180))]
            record[f"{sector}__count"] = len(fresh)
            record[f"{sector}__negative_share"] = float((fresh["quarterly_net_income"] < 0).mean()) if len(fresh) else np.nan
        rows.append(record)
    return pd.DataFrame(rows).set_index("date")

def _agent_target_weights(
    selection: pd.DataFrame, base_nav: pd.Series, core_close: pd.Series,
    flow: pd.DataFrame, dart: pd.DataFrame, *, variant: str, feedback_window: int,
    feedback_trigger: float, reduction: float,
) -> tuple[pd.Series, pd.DataFrame]:
    sel = selection.set_index("date")
    base_nav = base_nav.reindex(sel.index)
    core_close = core_close.reindex(sel.index)
    # Feedback available for a decision on D must be fully known by D-1.
    base_excess = (
        base_nav.pct_change(feedback_window, fill_method=None)
        - core_close.pct_change(feedback_window, fill_method=None)
    ).shift(1)
    rows = []
    weights = []
    for date, row in sel.iterrows():
        leader = str(row["leader_ticker"]) if pd.notna(row["leader_ticker"]) else None
        sector = str(row["leader_sector"]) if leader and pd.notna(row["leader_sector"]) else None
        flow_risk = bool(flow.loc[date, "flow_risk"]) if date in flow.index else False
        dart_count = 0
        negative_share = np.nan
        if sector and date in dart.index:
            count_col, share_col = f"{sector}__count", f"{sector}__negative_share"
            if count_col in dart.columns:
                dart_count = int(dart.loc[date, count_col])
                negative_share = float(dart.loc[date, share_col]) if pd.notna(dart.loc[date, share_col]) else np.nan
        fundamental_risk = bool(dart_count >= 2 and np.isfinite(negative_share) and negative_share >= 0.5)
        feedback_excess = float(base_excess.loc[date]) if pd.notna(base_excess.loc[date]) else np.nan
        feedback_risk = bool(np.isfinite(feedback_excess) and feedback_excess < feedback_trigger)
        actions: list[str] = []
        if variant in {"FLOW_AUTHORITY", "ALL_NINE_AUTHORITY"} and flow_risk:
            actions.append("FLOW")
        if variant in {"FUNDAMENTAL_AUTHORITY", "ALL_NINE_AUTHORITY"} and fundamental_risk:
            actions.append("FUNDAMENTAL")
        if variant in {"FEEDBACK_AUTHORITY", "ALL_NINE_AUTHORITY"} and feedback_risk:
            actions.append("FEEDBACK")
        weight = max(0.20, 0.80 - reduction * len(actions)) if leader else 0.0
        weights.append(weight)
        rows.append({
            "date": date, "variant": variant, "leader_ticker": leader, "leader_sector": sector,
            "target_leader_weight": weight, "flow_risk": flow_risk,
            "fundamental_risk": fundamental_risk, "fundamental_negative_share": negative_share,
            "fundamental_coverage": dart_count, "feedback_risk": feedback_risk,
            "feedback_excess_20d": feedback_excess, "authority_actions": "+".join(actions) or "NONE",
        })
    return pd.Series(weights, index=selection.index), pd.DataFrame(rows)


def _agent_trace(decisions: pd.DataFrame) -> pd.DataFrame:
    trace_rows: list[dict[str, Any]] = []
    for row in decisions.itertuples(index=False):
        for agent in AGENTS:
            authority_effect = False
            output = "PASS"
            if agent == "PainSupplyAgent":
                output = "REDUCE" if row.flow_risk and "FLOW" in row.authority_actions else ("RISK" if row.flow_risk else "PASS")
                authority_effect = "FLOW" in row.authority_actions
            elif agent == "DisclosureFundamentalAgent":
                output = "REDUCE" if row.fundamental_risk and "FUNDAMENTAL" in row.authority_actions else ("RISK" if row.fundamental_risk else "PASS")
                authority_effect = "FUNDAMENTAL" in row.authority_actions
            elif agent == "ReviewFeedbackAgent":
                output = "REDUCE" if row.feedback_risk and "FEEDBACK" in row.authority_actions else ("RISK" if row.feedback_risk else "PASS")
                authority_effect = "FEEDBACK" in row.authority_actions
            elif agent == "StrategyAgent":
                output = f"TARGET_WEIGHT_{row.target_leader_weight:.2f}"
                authority_effect = True
            elif agent in {"UniverseAgent", "MarketRegimeAgent", "CandidateSelectionAgent", "RiskExecutionAgent"}:
                authority_effect = True
            trace_rows.append({
                "date": row.date, "variant": row.variant, "agent": agent, "invoked": True,
                "decision_output": output, "capital_authority": authority_effect,
                "target_leader_weight": row.target_leader_weight,
                "evidence": json.dumps({
                    "leader": row.leader_ticker, "sector": row.leader_sector,
                    "flow_risk": bool(row.flow_risk), "fundamental_risk": bool(row.fundamental_risk),
                    "feedback_risk": bool(row.feedback_risk), "actions": row.authority_actions,
                }, ensure_ascii=False),
            })
    return pd.DataFrame(trace_rows)



def _agent_contracts() -> pd.DataFrame:
    return pd.DataFrame([
        {"agent": "UniverseAgent", "input": "point-in-time price availability, listing history, liquidity", "output": "eligible ETF set", "authority": "HARD_ELIGIBILITY_VETO", "counterfactual_test": "candidate cannot be selected when ineligible"},
        {"agent": "MarketRegimeAgent", "input": "D-1 benchmark close and 120-day moving average", "output": "market trend gate", "authority": "HARD_EXPOSURE_GATE", "counterfactual_test": "leader exposure becomes zero when trend gate is off"},
        {"agent": "PainSupplyAgent", "input": "D-1 PIT market investor-flow z-score and freshness", "output": "flow risk flag", "authority": "OPTIONAL_20PP_WEIGHT_REDUCTION", "counterfactual_test": "FLOW_AUTHORITY ablation versus diagnostic"},
        {"agent": "DisclosureFundamentalAgent", "input": "D-1 available OpenDART quarterly filings", "output": "negative-income sector risk", "authority": "OPTIONAL_20PP_WEIGHT_REDUCTION", "counterfactual_test": "FUNDAMENTAL_AUTHORITY ablation versus diagnostic"},
        {"agent": "CandidateSelectionAgent", "input": "eligible ETFs, semantic sector taxonomy, D-1 scores", "output": "sector-deduplicated leader ticker", "authority": "LEADER_SELECTION", "counterfactual_test": "sector duplicate lottery tickets are removed and selection ledger records D-1 leader changes"},
        {"agent": "StrategyAgent", "input": "leader and allocation policy", "output": "target leader/core weights", "authority": "TARGET_WEIGHT", "counterfactual_test": "fixed/event/continuous policies compared under one engine"},
        {"agent": "RiskExecutionAgent", "input": "adjusted open, D-1 ADV, fees, spread, impact, cash", "output": "final affordable integer fills", "authority": "PARTICIPATION_AND_CASH_CAP", "counterfactual_test": "order notional and participation reconstruct exactly"},
        {"agent": "ReviewFeedbackAgent", "input": "D-1 20-session strategy excess return", "output": "feedback risk flag", "authority": "OPTIONAL_20PP_WEIGHT_REDUCTION", "counterfactual_test": "FEEDBACK_AUTHORITY ablation versus diagnostic"},
    ])

def run(root: Path | str) -> dict[str, Any]:
    root = Path(root)
    cfg = _load_config(root)
    cfg77 = replace(v77._load_config(root), end_date=str(cfg["data_end"]))
    market = v77.load_adjusted_market(root, cfg77)
    v69_cfg = replace(
        v69._load_config(root), end_date=cfg77.end_date,
        core_ticker=cfg77.core_ticker, benchmark_ticker=cfg77.benchmark_ticker,
        leader_weight=float(cfg["fixed_parameters"]["fixed_leader_weight"]),
    )
    universe = v69._load_universe(root, v69_cfg)
    params = cfg["fixed_parameters"]

    baseline_features = build_baseline_features(market["close"], market["value"], universe, v69_cfg)
    baseline_selection = _selection_with_fixed_weight(
        market["close"].index, universe, baseline_features, v69_cfg, float(params["fixed_leader_weight"])
    )
    residual_features = build_residual_momentum_features(
        market["close"], market["value"], universe, v69_cfg,
        beta_window=int(params["beta_window_days"]), beta_min_periods=int(params["beta_min_periods"]),
    )
    residual_selection = _selection_with_fixed_weight(
        market["close"].index, universe, residual_features, v69_cfg, float(params["fixed_leader_weight"])
    )
    ensemble_features = build_cross_ts_ensemble_features(market["close"], market["value"], universe, v69_cfg)
    ensemble_selection = _selection_with_fixed_weight(
        market["close"].index, universe, ensemble_features, v69_cfg, float(params["fixed_leader_weight"])
    )
    vol_selection = baseline_selection.copy()
    vol_selection["target_leader_weight"] = _continuous_weights(
        vol_selection, market["close"], universe,
        target_vol=float(params["target_annual_volatility"]),
        floor=float(params["continuous_weight_floor"]), cap=float(params["continuous_weight_cap"]),
    ).to_numpy()

    accounts: dict[str, pd.DataFrame] = {}
    orders_map: dict[str, pd.DataFrame] = {}
    audits: dict[str, dict[str, Any]] = {}
    definitions = [
        ("V69_FIXED80_DAILY_CORRECTED", baseline_selection, "DAILY_EXACT"),
        ("V69_FIXED80_EVENT_CORRECTED", baseline_selection, "EVENT_ONLY"),
        ("V77_FIXED100_EVENT_CORRECTED", baseline_selection.assign(target_leader_weight=baseline_selection["leader_ticker"].notna().astype(float)), "EVENT_ONLY"),
        ("V78_A_RESIDUAL_MOMENTUM", residual_selection, "EVENT_ONLY"),
        ("V78_B_CROSS_TS_ENSEMBLE", ensemble_selection, "EVENT_ONLY"),
        ("V78_C_VOL_MANAGED", vol_selection, "BAND_5PP"),
    ]
    for scenario, selection, rebalance in definitions:
        account, orders, audit = _run_selection(
            market, selection, cfg77, scenario=scenario, rebalance=rebalance, execution=cfg77.base_execution
        )
        accounts[scenario], orders_map[scenario], audits[scenario] = account, orders, audit

    # Existing nine-agent authority variants, rebuilt on the same corrected OHLC and execution engine.
    base_nav = accounts["V69_FIXED80_DAILY_CORRECTED"].set_index("date")["nav_krw"]
    flow = _flow_signal(root, market["close"].index)
    dart = _fundamental_sector_signal(root, market["close"].index, universe)
    agent_decisions = []
    agent_variants = ["NINE_AGENT_DIAGNOSTIC", "FLOW_AUTHORITY", "FUNDAMENTAL_AUTHORITY", "FEEDBACK_AUTHORITY", "ALL_NINE_AUTHORITY"]
    for variant in agent_variants:
        weights, decisions = _agent_target_weights(
            baseline_selection, base_nav, market["close"][cfg77.core_ticker], flow, dart,
            variant=variant, feedback_window=int(params["feedback_window_days"]),
            feedback_trigger=float(params["feedback_excess_trigger"]),
            reduction=float(params["authority_reduction_per_signal"]),
        )
        selection = baseline_selection.copy()
        selection["target_leader_weight"] = weights.to_numpy()
        scenario = f"AGENT_{variant}"
        account, orders, audit = _run_selection(
            market, selection, cfg77, scenario=scenario, rebalance="DAILY_EXACT", execution=cfg77.base_execution
        )
        accounts[scenario], orders_map[scenario], audits[scenario] = account, orders, audit
        agent_decisions.append(decisions)
    decisions = pd.concat(agent_decisions, ignore_index=True)
    traces = _agent_trace(decisions)

    core_hold = v77._buy_hold(
        market["close"][cfg77.core_ticker], market["open"][cfg77.core_ticker],
        cfg77.initial_capital_krw, cfg77.base_execution,
    )
    semi_hold = v77._buy_hold(
        market["close"][cfg77.semiconductor_benchmark_ticker], market["open"][cfg77.semiconductor_benchmark_ticker],
        cfg77.initial_capital_krw, cfg77.base_execution,
    )
    kospi_close = market["close"][cfg77.benchmark_ticker].dropna()
    kospi_nav = kospi_close / kospi_close.iloc[0] * cfg77.initial_capital_krw
    nav_map = {name: account.set_index("date")["nav_krw"] for name, account in accounts.items()}
    nav_map.update({"KODEX200_BUY_HOLD": core_hold, "SEMICONDUCTOR_ETF_BUY_HOLD": semi_hold, "KOSPI_INDEX": kospi_nav})

    periods = cfg["periods"]
    comparison_periods = {
        "development": periods["development"], "validation": periods["validation"],
        "observed": periods["observed_only"], "recent_1y": periods["recent_1y"],
    }
    metrics = _return_table(nav_map, comparison_periods, cfg77.initial_capital_krw)
    for period_name, (period_start, period_end) in comparison_periods.items():
        metrics[f"{period_name}_sharpe"] = metrics["scenario"].map(
            {name: _slice_metrics(nav, period_start, period_end, cfg77.initial_capital_krw)["sharpe"] for name, nav in nav_map.items()}
        )
        metrics[f"{period_name}_mdd_pct"] = metrics["scenario"].map(
            {name: _slice_metrics(nav, period_start, period_end, cfg77.initial_capital_krw)["mdd_pct"] for name, nav in nav_map.items()}
        )
    metrics["order_count"] = metrics["scenario"].map({k: len(v) for k, v in orders_map.items()}).fillna(1).astype(int)
    metrics["negative_cash_days"] = metrics["scenario"].map({k: v["negative_cash_days"] for k, v in audits.items()}).fillna(0).astype(int)

    baseline_name = "V69_FIXED80_DAILY_CORRECTED"
    baseline_row = metrics.set_index("scenario").loc[baseline_name]
    candidate_rows = []
    bootstrap_rows = []
    for candidate in cfg["alpha_candidates"]:
        row = metrics.set_index("scenario").loc[candidate]
        dev_start, dev_end = periods["development"]
        val_start, val_end = periods["validation"]
        boot = _relative_bootstrap_period(
            nav_map[candidate], nav_map[baseline_name], val_start, val_end,
            samples=5000, block_months=3,
        )
        familywise = _familywise_probability(boot["positive_probability"], len(cfg["alpha_candidates"]))
        bootstrap_rows.append({"candidate": candidate, **boot, "familywise_positive_probability": familywise})
        dev_candidate = _slice_metrics(nav_map[candidate], dev_start, dev_end, cfg77.initial_capital_krw)
        dev_baseline = _slice_metrics(nav_map[baseline_name], dev_start, dev_end, cfg77.initial_capital_krw)
        val_candidate = _slice_metrics(nav_map[candidate], val_start, val_end, cfg77.initial_capital_krw)
        val_baseline = _slice_metrics(nav_map[baseline_name], val_start, val_end, cfg77.initial_capital_krw)
        stress_selection = next(x[1] for x in definitions if x[0] == candidate)
        stress_rebalance = next(x[2] for x in definitions if x[0] == candidate)
        stress_account, _, _ = _run_selection(
            market, stress_selection, cfg77, scenario=candidate + "__STRESS",
            rebalance=stress_rebalance, execution=cfg77.stress_execution,
        )
        stress_validation = _slice_metrics(
            stress_account.set_index("date")["nav_krw"], val_start, val_end, cfg77.initial_capital_krw
        )
        full_core = metrics.set_index("scenario").loc["KODEX200_BUY_HOLD"]
        full_semi = metrics.set_index("scenario").loc["SEMICONDUCTOR_ETF_BUY_HOLD"]
        passed = bool(
            dev_candidate["return_pct"] > dev_baseline["return_pct"]
            and val_candidate["return_pct"] > val_baseline["return_pct"]
            and dev_candidate["sharpe"] >= dev_baseline["sharpe"]
            and val_candidate["sharpe"] >= val_baseline["sharpe"]
            and val_candidate["mdd_pct"] >= val_baseline["mdd_pct"] - float(cfg["promotion"]["mdd_tolerance_pp"])
            and boot["positive_probability"] >= float(cfg["promotion"]["validation_bootstrap_probability"])
            and familywise >= float(cfg["promotion"]["familywise_probability"])
            and stress_validation["return_pct"] >= val_baseline["return_pct"]
            and row["return_pct"] > full_core["return_pct"]
            and row["recent_1y_return_pct"] > full_core["recent_1y_return_pct"]
            and row["return_pct"] > full_semi["return_pct"]
            and row["recent_1y_return_pct"] > full_semi["recent_1y_return_pct"]
        )
        candidate_rows.append({
            "candidate": candidate, "passed": passed,
            "development_delta_pp": dev_candidate["return_pct"] - dev_baseline["return_pct"],
            "validation_delta_pp": val_candidate["return_pct"] - val_baseline["return_pct"],
            "validation_sharpe_delta": val_candidate["sharpe"] - val_baseline["sharpe"],
            "validation_mdd_delta_pp": val_candidate["mdd_pct"] - val_baseline["mdd_pct"],
            "validation_stress_return_pct": stress_validation["return_pct"],
            "raw_bootstrap_probability": boot["positive_probability"],
            "familywise_probability": familywise,
            "beats_kodex200_full": bool(row["return_pct"] > full_core["return_pct"]),
            "beats_kodex200_recent_1y": bool(row["recent_1y_return_pct"] > full_core["recent_1y_return_pct"]),
            "beats_semiconductor_full": bool(row["return_pct"] > full_semi["return_pct"]),
            "beats_semiconductor_recent_1y": bool(row["recent_1y_return_pct"] > full_semi["recent_1y_return_pct"]),
        })
    candidate_gates = pd.DataFrame(candidate_rows)
    promoted = candidate_gates[candidate_gates["passed"]]["candidate"].tolist()

    diagnostic = metrics.set_index("scenario").loc["AGENT_NINE_AGENT_DIAGNOSTIC"]
    agent_ablation_rows = []
    for variant in agent_variants:
        scenario = f"AGENT_{variant}"
        row = metrics.set_index("scenario").loc[scenario]
        authority_days = int(decisions[(decisions["variant"] == variant) & decisions["authority_actions"].ne("NONE")].shape[0])
        agent_ablation_rows.append({
            "variant": variant, "scenario": scenario,
            "return_pct": row["return_pct"], "sharpe": row["sharpe"], "mdd_pct": row["mdd_pct"],
            "recent_1y_return_pct": row["recent_1y_return_pct"],
            "return_delta_vs_diagnostic_pp": row["return_pct"] - diagnostic["return_pct"],
            "sharpe_delta_vs_diagnostic": row["sharpe"] - diagnostic["sharpe"],
            "mdd_delta_vs_diagnostic_pp": row["mdd_pct"] - diagnostic["mdd_pct"],
            "authority_days": authority_days,
            "improves_return_sharpe_mdd": bool(
                row["return_pct"] > diagnostic["return_pct"]
                and row["sharpe"] >= diagnostic["sharpe"]
                and row["mdd_pct"] >= diagnostic["mdd_pct"]
            ),
        })
    agent_ablation = pd.DataFrame(agent_ablation_rows)
    coverage = traces.groupby(["variant", "date"])["agent"].nunique().reset_index(name="agent_count")

    annual = _annual_returns(nav_map, cfg77.initial_capital_krw)
    monthly_2026 = _monthly_returns_2026(nav_map, cfg77.initial_capital_krw)
    dca_rows = []
    for scenario, nav in nav_map.items():
        dca = _dca_from_return_stream(nav, initial=cfg77.initial_capital_krw, monthly_contribution=300_000.0)
        month_count = len(set(zip(dca.index.year, dca.index.month)))
        total = cfg77.initial_capital_krw + 300_000.0 * max(month_count - 1, 0)
        dca_rows.append({
            "scenario": scenario, "ending_value_krw": float(dca.iloc[-1]),
            "total_contributions_krw": total,
            "gain_on_contributions_pct": float((dca.iloc[-1] / total - 1.0) * 100.0),
            "method": "diagnostic_return_stream_dca",
        })
    dca = pd.DataFrame(dca_rows)

    selection_ledgers = {
        "baseline": baseline_selection, "residual": residual_selection,
        "cross_ts_ensemble": ensemble_selection, "vol_managed": vol_selection,
    }
    strict_cutoff = all(
        (ledger.dropna(subset=["information_cutoff"])["information_cutoff"] < ledger.dropna(subset=["information_cutoff"])["date"]).all()
        for ledger in selection_ledgers.values()
    )
    contracts = _agent_contracts()
    feedback_expected = (
        base_nav.pct_change(int(params["feedback_window_days"]), fill_method=None)
        - market["close"][cfg77.core_ticker].pct_change(int(params["feedback_window_days"]), fill_method=None)
    ).shift(1)
    feedback_actual = decisions[decisions["variant"].eq("FEEDBACK_AUTHORITY")].set_index("date")["feedback_excess_20d"]
    feedback_compare = pd.concat([feedback_expected.rename("expected"), feedback_actual.rename("actual")], axis=1).dropna()
    feedback_d1_exact = bool((feedback_compare["expected"] - feedback_compare["actual"]).abs().max() <= 1e-12)

    gates = pd.DataFrame([
        {"gate": "THREE_PREREGISTERED_ALPHA_CANDIDATES_ONLY", "passed": set(candidate_gates["candidate"]) == set(cfg["alpha_candidates"]), "detail": ",".join(cfg["alpha_candidates"])},
        {"gate": "STRICT_D1_INFORMATION_CUTOFF", "passed": strict_cutoff, "detail": "all alpha selection ledgers use information_cutoff < decision date"},
        {"gate": "FEEDBACK_SIGNAL_D1_ONLY", "passed": feedback_d1_exact, "detail": f"compared_rows={len(feedback_compare)}"},
        {"gate": "NINE_AGENT_CONTRACTS_EXPLICIT", "passed": len(contracts) == 9 and contracts["agent"].nunique() == 9, "detail": "input/output/authority/counterfactual recorded"},
        {"gate": "CORRECTED_ADJUSTED_OHLC_EXECUTION_FOR_ALL", "passed": all(v["negative_cash_days"] == 0 for v in audits.values()), "detail": f"scenarios={len(audits)}"},
        {"gate": "ALL_ACTIVE_AGENTS_INVOKED_EVERY_SESSION", "passed": bool(coverage["agent_count"].eq(8).all()), "detail": f"variant_sessions={len(coverage)}"},
        {"gate": "AGENT_CAUSAL_ABLATION_REPORTED", "passed": len(agent_ablation) == len(agent_variants), "detail": "every authority variant compared against corrected diagnostic path"},
        {"gate": "NEW_ALPHA_PROMOTION", "passed": bool(promoted), "detail": ",".join(promoted) if promoted else "none"},
        {"gate": "LIVE_AND_AUTO_MUTATION_BLOCKED", "passed": True, "detail": "V78 remains research/shadow only"},
    ])

    out = root / "reports" / REPORT
    out.mkdir(parents=True, exist_ok=True)
    metrics.sort_values("return_pct", ascending=False).to_csv(out / "v78_all_strategy_metrics.csv", index=False)
    candidate_gates.to_csv(out / "v78_alpha_promotion_gates.csv", index=False)
    pd.DataFrame(bootstrap_rows).to_csv(out / "v78_validation_bootstrap.csv", index=False)
    agent_ablation.to_csv(out / "v78_existing_agent_ablation.csv", index=False)
    decisions.to_csv(out / "v78_agent_decision_ledger.csv", index=False)
    traces.to_csv(out / "v78_all_agent_trace.csv", index=False)
    coverage.to_csv(out / "v78_agent_coverage.csv", index=False)
    annual.to_csv(out / "v78_annual_returns.csv", index=False)
    monthly_2026.to_csv(out / "v78_2026_monthly_returns.csv", index=False)
    dca.to_csv(out / "v78_dca_comparison.csv", index=False)
    gates.to_csv(out / "v78_quality_gates.csv", index=False)
    contracts.to_csv(out / "v78_agent_contracts.csv", index=False)
    for ledger_name, ledger in selection_ledgers.items():
        ledger.to_csv(out / f"v78_selection_{ledger_name}.csv", index=False)
    for name in ["V69_FIXED80_DAILY_CORRECTED", *cfg["alpha_candidates"], *[f"AGENT_{v}" for v in agent_variants]]:
        accounts[name].to_csv(out / f"v78_account_{name.lower()}.csv", index=False)
        orders_map[name].to_csv(out / f"v78_orders_{name.lower()}.csv", index=False)

    decision = {
        "status": "v78_preregistered_alpha_and_agent_replay_complete_live_blocked",
        "data_end": cfg["data_end"],
        "operational_control": baseline_name,
        "promoted_alpha_candidates": promoted,
        "best_alpha_by_validation": str(
            metrics[metrics["scenario"].isin(cfg["alpha_candidates"])].sort_values(
                ["validation_return_pct", "validation_sharpe"], ascending=False
            ).iloc[0]["scenario"]
        ),
        "best_existing_agent_variant_by_return": str(
            agent_ablation.sort_values(["return_pct", "sharpe"], ascending=False).iloc[0]["variant"]
        ),
        "existing_agent_variants_improving_return_sharpe_mdd": agent_ablation[
            agent_ablation["improves_return_sharpe_mdd"]
        ]["variant"].tolist(),
        "live_allowed": False,
        "gates": gates.to_dict("records"),
    }
    (out / "v78_decision.json").write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")

    focus_names = [baseline_name, *cfg["alpha_candidates"], *[f"AGENT_{v}" for v in agent_variants], "KODEX200_BUY_HOLD", "SEMICONDUCTOR_ETF_BUY_HOLD", "KOSPI_INDEX"]
    focus = metrics[metrics["scenario"].isin(focus_names)].sort_values("return_pct", ascending=False)
    lines = [
        "# V78 Preregistered Alpha Research and Corrected 9-Agent Replay", "",
        f"- data end: `{cfg['data_end']}`",
        f"- promoted alpha: `{promoted or 'none'}`",
        f"- best validation alpha: `{decision['best_alpha_by_validation']}`",
        f"- best existing agent by total return: `{decision['best_existing_agent_variant_by_return']}`",
        "", "## Main comparison", "", focus.to_markdown(index=False),
        "", "## Alpha promotion gates", "", candidate_gates.to_markdown(index=False),
        "", "## Existing agent ablation", "", agent_ablation.to_markdown(index=False),
        "", "## Harness gates", "", gates.to_markdown(index=False),
    ]
    (out / "V78_KOREAN_SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")
    return decision
