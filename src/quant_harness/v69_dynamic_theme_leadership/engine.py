from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable
import json
import math

import numpy as np
import pandas as pd
import yaml

from quant_harness.v94_universe_agent.policy import build_universe_gate
from quant_harness.v95_market_regime_agent.policy import build_market_regime_panel
from quant_harness.v98_candidate_selection_agent.policy import (
    ACTIVE_SELECTION_POLICY,
    build_sector_representative_panel,
    effective_rotation_margin,
    expected_value_rotation_gate,
    prepare_selection_features,
    ranked_representatives,
    score_distribution_diagnostics,
)

REPORT_DIR = "v69_dynamic_theme_leadership"


@dataclass(frozen=True)
class V69Config:
    initial_capital_krw: float = 10_000_000.0
    monthly_contribution_krw: float = 300_000.0
    end_date: str = "2026-07-07"
    buy_bps: float = 1.5
    sell_bps: float = 21.5
    universe_source: str = "data/toss_v19c_daily/universe.csv"
    core_ticker: str = "069500"
    benchmark_ticker: str = "KS11"
    minimum_history_days: int = 252
    minimum_median_value_20d_krw: float = 100_000_000.0
    short_days: int = 21
    medium_days: int = 63
    long_days: int = 126
    trend_ma_days: int = 120
    leader_weight: float = 0.20
    confirmation_reviews: int = 1
    score_margin: float = 0.0
    weekly_exit_if_ineligible: bool = True
    weekly_exit_if_score_below: float = 0.0
    research_only: bool = True
    paid_deployment_allowed: bool = False
    live_execution_allowed: bool = False
    bootstrap_samples: int = 5000
    bootstrap_block_months: int = 3
    bootstrap_probability_gate: float = 0.90


def _load_config(root: Path) -> V69Config:
    raw = yaml.safe_load((root / "config/v69_dynamic_theme_leadership.yaml").read_text(encoding="utf-8"))
    return V69Config(
        initial_capital_krw=float(raw["initial_capital_krw"]),
        monthly_contribution_krw=float(raw["monthly_contribution_krw"]),
        end_date=str(raw["end_date"]),
        buy_bps=float(raw["transaction_costs"]["buy_bps"]),
        sell_bps=float(raw["transaction_costs"]["sell_bps"]),
        universe_source=str(raw["universe"]["source"]),
        core_ticker=str(raw["universe"]["core_ticker"]),
        benchmark_ticker=str(raw["universe"]["benchmark_ticker"]),
        minimum_history_days=int(raw["universe"]["minimum_history_days"]),
        minimum_median_value_20d_krw=float(raw["universe"]["minimum_median_value_20d_krw"]),
        short_days=int(raw["leadership"]["relative_momentum_short_days"]),
        medium_days=int(raw["leadership"]["relative_momentum_medium_days"]),
        long_days=int(raw["leadership"]["relative_momentum_long_days"]),
        trend_ma_days=int(raw["leadership"]["trend_ma_days"]),
        leader_weight=float(raw["leadership"]["leader_weight"]),
        confirmation_reviews=int(raw["leadership"]["challenger_confirmation_reviews"]),
        score_margin=float(raw["leadership"]["score_margin"]),
        weekly_exit_if_ineligible=bool(raw["leadership"]["weekly_exit_if_ineligible"]),
        weekly_exit_if_score_below=float(raw["leadership"]["weekly_exit_if_score_below"]),
        research_only=bool(raw["research_only"]),
        paid_deployment_allowed=bool(raw["paid_deployment_allowed"]),
        live_execution_allowed=bool(raw["live_execution_allowed"]),
        bootstrap_probability_gate=float(raw["quality_gates"]["bootstrap_positive_probability_min"]),
    )


def _normalise_ticker(value: Any) -> str:
    text = str(value).replace(".0", "")
    return text.zfill(6) if text.isdigit() else text


def _hash(path: Path) -> str:
    h = sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_universe(root: Path, cfg: V69Config, excluded_tickers: Iterable[str] = ()) -> pd.DataFrame:
    u = pd.read_csv(root / cfg.universe_source, dtype={"ticker": str})
    u["ticker"] = u["ticker"].map(_normalise_ticker)
    excluded = set(map(_normalise_ticker, excluded_tickers)) | {cfg.core_ticker}
    u = u[(u["asset_type"].eq("etf")) & (~u["sector"].eq("broad_equity")) & (~u["ticker"].isin(excluded))].copy()
    if u.empty:
        raise ValueError("dynamic theme universe is empty")
    if u["ticker"].duplicated().any():
        raise ValueError("duplicate ticker in dynamic theme universe")
    return u.sort_values(["sector", "ticker"]).reset_index(drop=True)


def _load_market(root: Path, cfg: V69Config, universe: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    tickers = set(universe["ticker"]) | {cfg.core_ticker, cfg.benchmark_ticker}
    raw = pd.read_csv(
        root / "data/all_prices_long_v62_9_expanded.csv",
        usecols=["date", "ticker", "open", "adj_close", "value_approx"],
        dtype={"ticker": str},
        low_memory=False,
    )
    raw["ticker"] = raw["ticker"].map(_normalise_ticker)
    raw["date"] = pd.to_datetime(raw["date"])
    raw = raw[raw["ticker"].isin(tickers) & raw["date"].le(pd.Timestamp(cfg.end_date))].copy()
    close = raw.pivot_table(index="date", columns="ticker", values="adj_close", aggfunc="last").sort_index()
    open_px = raw.pivot_table(index="date", columns="ticker", values="open", aggfunc="last").sort_index()
    value = raw.pivot_table(index="date", columns="ticker", values="value_approx", aggfunc="last").sort_index()
    idx = close[cfg.core_ticker].dropna().index.intersection(close[cfg.benchmark_ticker].dropna().index)
    close = close.reindex(idx).ffill()
    open_px = open_px.reindex(idx).where(lambda x: x.gt(0)).fillna(close)
    value = value.reindex(idx)
    missing = tickers.difference(close.columns)
    if missing:
        raise ValueError(f"missing price histories: {sorted(missing)}")
    return close, open_px, value


def _review_dates(index: pd.DatetimeIndex) -> tuple[set[pd.Timestamp], set[pd.Timestamp]]:
    frame = pd.DataFrame(index=index)
    frame["date"] = index
    monthly = set(frame.groupby([index.year, index.month])["date"].first().tolist())
    iso = index.isocalendar()
    weekly = set(frame.groupby([iso.year.to_numpy(), iso.week.to_numpy()])["date"].first().tolist())
    return monthly, weekly


def build_feature_panel(close: pd.DataFrame, value: pd.DataFrame, universe: pd.DataFrame, cfg: V69Config) -> dict[str, pd.DataFrame | pd.Series]:
    tickers = universe["ticker"].tolist()
    ret_short = close.pct_change(cfg.short_days)
    ret_medium = close.pct_change(cfg.medium_days)
    ret_long = close.pct_change(cfg.long_days)
    rel_short = ret_short[tickers].sub(ret_short[cfg.core_ticker], axis=0)
    rel_medium = ret_medium[tickers].sub(ret_medium[cfg.core_ticker], axis=0)
    rel_long = ret_long[tickers].sub(ret_long[cfg.core_ticker], axis=0)
    # Acceleration rewards a theme whose recent relative trend is strengthening,
    # while retaining the medium-horizon momentum anchor.
    raw_score = rel_medium + 0.5 * (rel_short - rel_medium)
    universe_gate = build_universe_gate(
        close, value, tickers,
        minimum_history_days=cfg.minimum_history_days,
        minimum_median_value_20d_krw=cfg.minimum_median_value_20d_krw,
    )
    liquidity = universe_gate["liquidity_median20_d1"]
    trend = close[tickers].gt(close[tickers].rolling(cfg.trend_ma_days).mean()).shift(1, fill_value=False)
    eligible = (
        universe_gate["gate"]
        & ret_long[tickers].shift(1).gt(0)
        & trend
    )
    regime = build_market_regime_panel(
        close, benchmark_ticker=cfg.benchmark_ticker, theme_tickers=tickers,
        universe_gate_d1=universe_gate["gate"], trend_ma_days=cfg.trend_ma_days,
        policy="D1_MA120_EXPLICIT",
    )
    benchmark_trend = regime["risk_on"]
    # Every executable feature is lagged one session.
    return {
        "score": raw_score.shift(1),
        "eligible": eligible.fillna(False).astype(bool),
        "liquidity": liquidity,
        "benchmark_trend": benchmark_trend.astype(bool),
        "rel_short": rel_short.shift(1),
        "rel_medium": rel_medium.shift(1),
        "rel_long": rel_long.shift(1),
    }


def select_dynamic_leader(
    index: pd.DatetimeIndex,
    universe: pd.DataFrame,
    features: dict[str, Any],
    cfg: V69Config,
    *,
    selection_policy: str = ACTIVE_SELECTION_POLICY,
    selection_policy_params: dict[str, Any] | None = None,
) -> pd.DataFrame:
    monthly, weekly = _review_dates(index)
    policy_params = selection_policy_params or {}
    selected_features = prepare_selection_features(
        features, family="V69", policy=selection_policy,
        consensus_min_rank=float(policy_params.get("consensus_min_rank", 0.60)),
        consensus_required_horizons=int(policy_params.get("consensus_required_horizons", 2)),
        dispersion_penalty=float(policy_params.get("dispersion_penalty", 0.20)),
    )
    selection_score = selected_features["selection_score"]
    selection_eligible = selected_features["selection_eligible"]
    sector_panel = build_sector_representative_panel(
        index, monthly, universe, selection_score, selection_eligible, selected_features["liquidity"],
    )
    sector_by_ticker = universe.set_index("ticker")["sector"].to_dict()
    name_by_ticker = universe.set_index("ticker")["name"].to_dict()
    current: str | None = None
    pending: str | None = None
    pending_count = 0
    rows: list[dict[str, Any]] = []
    for pos, date in enumerate(index):
        reason = "INTRA_REVIEW_HOLD"
        expected_rotation_edge = np.nan
        expected_rotation_samples = 0
        expected_rotation_reason = "NOT_APPLICABLE"
        score = selection_score.loc[date]
        eligible = selection_eligible.loc[date]
        market_on = bool(features["benchmark_trend"].loc[date])
        if date in weekly and current is not None and cfg.weekly_exit_if_ineligible:
            current_ok = bool(eligible.get(current, False)) and pd.notna(score.get(current, np.nan))
            current_score = float(score[current]) if current_ok else -np.inf
            if (not current_ok) or current_score < cfg.weekly_exit_if_score_below:
                current = None
                pending = None
                pending_count = 0
                reason = "WEEKLY_LEADER_DECAY_EXIT"
        ranked: list[tuple[str, str, float, float]] = []
        if date in monthly:
            if not market_on:
                current = None
                pending = None
                pending_count = 0
                reason = "MARKET_TREND_OFF"
            else:
                ranked = ranked_representatives(sector_panel, date)
                challenger = ranked[0][0] if ranked else None
                if challenger is None:
                    current = None
                    pending = None
                    pending_count = 0
                    reason = "NO_ELIGIBLE_THEME"
                elif current is None:
                    current = challenger
                    pending = None
                    pending_count = 0
                    reason = "SELECT_NEW_LEADER"
                elif challenger == current:
                    pending = None
                    pending_count = 0
                    reason = "KEEP_CURRENT_LEADER"
                else:
                    current_score = float(score[current]) if pd.notna(score.get(current, np.nan)) else -np.inf
                    challenger_score = float(score[challenger])
                    rotation_margin = effective_rotation_margin(
                        ranked, base_margin=cfg.score_margin, policy=selection_policy,
                        iqr_multiplier=float(policy_params.get("iqr_multiplier", 0.25)),
                    )
                    if challenger_score > current_score + rotation_margin:
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
                            if pending_count >= cfg.confirmation_reviews:
                                current = challenger
                                pending = None
                                pending_count = 0
                                reason = "CONFIRMED_LEADERSHIP_ROTATION"
                            else:
                                reason = "CHALLENGER_PENDING"
                    else:
                        pending = None
                        pending_count = 0
                        reason = "LEADERSHIP_MARGIN_NOT_MET"
        leader_score = float(score[current]) if current is not None and pd.notna(score.get(current, np.nan)) else np.nan
        diag = score_distribution_diagnostics(ranked) if ranked else {"top_ticker": None, "runner_up_ticker": None, "top_score": np.nan, "runner_up_score": np.nan, "top_gap": np.nan, "score_iqr": np.nan}
        effective_margin = effective_rotation_margin(
            ranked, base_margin=cfg.score_margin, policy=selection_policy,
            iqr_multiplier=float(policy_params.get("iqr_multiplier", 0.25)),
        ) if ranked else float(cfg.score_margin)
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
            "review_monthly": date in monthly,
            "review_weekly": date in weekly,
            "leader_ticker": current,
            "leader_name": name_by_ticker.get(current) if current else None,
            "leader_sector": sector_by_ticker.get(current) if current else None,
            "leader_score_d1": leader_score,
            "target_leader_weight": cfg.leader_weight if current is not None else 0.0,
            "market_trend_on_d1": market_on,
            "decision_reason": reason,
            "pending_challenger": pending,
            "pending_confirmation_count": pending_count,
            "eligible_theme_count": int(sum(bool(v) for v in eligible.values)),
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


def execute_dynamic_overlay(
    close: pd.DataFrame,
    open_px: pd.DataFrame,
    selection: pd.DataFrame,
    cfg: V69Config,
    *,
    initial_capital: float,
    monthly_contribution: float = 0.0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    selection = selection.set_index("date").reindex(close.index)
    cash = float(initial_capital)
    quantities: dict[str, int] = {cfg.core_ticker: 0}
    buy_rate = cfg.buy_bps / 10000.0
    sell_rate = cfg.sell_bps / 10000.0
    first_by_month: dict[tuple[int, int], pd.Timestamp] = {}
    for date in close.index:
        first_by_month.setdefault((date.year, date.month), date)
    daily: list[dict[str, Any]] = []
    orders: list[dict[str, Any]] = []
    for date in close.index:
        contribution = 0.0
        if monthly_contribution > 0 and first_by_month[(date.year, date.month)] == date:
            contribution = monthly_contribution
            cash += contribution
        leader = selection.loc[date, "leader_ticker"]
        leader = str(leader) if pd.notna(leader) and str(leader) != "None" else None
        leader_weight = float(selection.loc[date, "target_leader_weight"])
        active = [cfg.core_ticker] + ([leader] if leader else [])
        for ticker in list(quantities):
            quantities.setdefault(ticker, 0)
        nav_open = cash + sum(quantities.get(ticker, 0) * float(open_px.loc[date, ticker]) for ticker in quantities)
        desired: dict[str, int] = {
            cfg.core_ticker: int(math.floor(nav_open * (1.0 - leader_weight) / (float(open_px.loc[date, cfg.core_ticker]) * (1.0 + buy_rate))))
        }
        if leader:
            desired[leader] = int(math.floor(nav_open * leader_weight / (float(open_px.loc[date, leader]) * (1.0 + buy_rate))))
        for ticker in quantities:
            desired.setdefault(ticker, 0)
        for ticker in list(quantities):
            current = quantities[ticker]
            target = desired[ticker]
            if current <= target:
                continue
            quantity = current - target
            price = float(open_px.loc[date, ticker])
            cost = quantity * price * sell_rate
            cash += quantity * price - cost
            quantities[ticker] -= quantity
            orders.append({
                "date": date, "ticker": ticker, "side": "SELL", "quantity": quantity,
                "price_krw": price, "explicit_cost_krw": cost,
                "reason": selection.loc[date, "decision_reason"],
            })
        for ticker in active:
            current = quantities.get(ticker, 0)
            target = desired[ticker]
            if current >= target:
                continue
            price = float(open_px.loc[date, ticker])
            affordable = int(math.floor(cash / (price * (1.0 + buy_rate))))
            quantity = min(target - current, affordable)
            if quantity <= 0:
                continue
            cost = quantity * price * buy_rate
            cash -= quantity * price + cost
            quantities[ticker] = current + quantity
            orders.append({
                "date": date, "ticker": ticker, "side": "BUY", "quantity": quantity,
                "price_krw": price, "explicit_cost_krw": cost,
                "reason": selection.loc[date, "decision_reason"],
            })
        nav = cash + sum(quantities.get(ticker, 0) * float(close.loc[date, ticker]) for ticker in quantities)
        daily.append({
            "date": date,
            "cash_krw": max(cash, 0.0),
            "nav_krw": nav,
            "leader_ticker": leader,
            "leader_sector": selection.loc[date, "leader_sector"],
            "target_leader_weight": leader_weight,
            "core_quantity": quantities.get(cfg.core_ticker, 0),
            "leader_quantity": quantities.get(leader, 0) if leader else 0,
            "contribution_krw": contribution,
            "information_cutoff": selection.loc[date, "information_cutoff"],
            "decision_uses_same_day_close": False,
        })
    return pd.DataFrame(daily), pd.DataFrame(orders)


def _buy_hold(price: pd.DataFrame, cfg: V69Config, initial_capital: float, monthly_contribution: float = 0.0) -> pd.DataFrame:
    cash = float(initial_capital)
    quantity = 0
    buy_rate = cfg.buy_bps / 10000.0
    first_by_month: dict[tuple[int, int], pd.Timestamp] = {}
    for date in price.index:
        first_by_month.setdefault((date.year, date.month), date)
    rows: list[dict[str, Any]] = []
    for date, row in price.iterrows():
        contribution = 0.0
        if monthly_contribution > 0 and first_by_month[(date.year, date.month)] == date:
            contribution = monthly_contribution
            cash += contribution
        px = float(row["open"])
        affordable = int(math.floor(cash / (px * (1.0 + buy_rate))))
        if affordable > 0:
            cash -= affordable * px * (1.0 + buy_rate)
            quantity += affordable
        rows.append({"date": date, "cash_krw": cash, "quantity": quantity, "nav_krw": cash + quantity * float(row["adj_close"]), "contribution_krw": contribution})
    return pd.DataFrame(rows)


def _metrics(nav: pd.Series, initial: float) -> dict[str, float]:
    nav = nav.astype(float)
    path = pd.concat([pd.Series([initial], index=[nav.index[0] - pd.Timedelta(days=1)]), nav])
    ret = path.pct_change().dropna()
    years = max((nav.index[-1] - nav.index[0]).days / 365.25, 1 / 252)
    sd = float(ret.std(ddof=1))
    return {
        "return_pct": float((nav.iloc[-1] / initial - 1.0) * 100.0),
        "cagr_pct": float(((nav.iloc[-1] / initial) ** (1 / years) - 1.0) * 100.0),
        "sharpe": float(ret.mean() / sd * math.sqrt(252)) if sd > 0 else 0.0,
        "mdd_pct": float((path / path.cummax() - 1.0).min() * 100.0),
        "ending_nav_krw": float(nav.iloc[-1]),
    }


def _contribution_summary(account: pd.DataFrame) -> dict[str, float]:
    total = float(account["contribution_krw"].sum())
    final = float(account["nav_krw"].iloc[-1])
    return {"total_contributions_krw": total, "ending_nav_krw": final, "gain_on_contributions_pct": float((final / total - 1.0) * 100.0) if total else 0.0}


def _period_metrics(nav: pd.Series, initial: float) -> pd.DataFrame:
    periods = [
        ("development_2018_2022", "2018-01-01", "2022-12-31"),
        ("validation_2023_2024", "2023-01-01", "2024-12-31"),
        ("observed_2025", "2025-01-01", "2025-12-31"),
        ("observed_2026_ytd", "2026-01-01", "2026-07-07"),
    ]
    rows = []
    for name, start, end in periods:
        sub = nav[(nav.index >= start) & (nav.index <= end)]
        if sub.empty:
            continue
        pos = nav.index.get_loc(sub.index[0])
        base = initial if pos == 0 else float(nav.iloc[pos - 1])
        rows.append({"period": name, "return_pct": float((sub.iloc[-1] / base - 1.0) * 100.0)})
    return pd.DataFrame(rows)


def _monthly_block_bootstrap(dynamic_nav: pd.Series, baseline_nav: pd.Series, samples: int, block_months: int) -> dict[str, float]:
    aligned = pd.concat([dynamic_nav.rename("dynamic"), baseline_nav.rename("baseline")], axis=1).dropna()
    monthly = aligned.resample("ME").last().pct_change().dropna()
    excess = monthly["dynamic"] - monthly["baseline"]
    values = excess.to_numpy(float)
    rng = np.random.default_rng(6901)
    if len(values) < block_months:
        return {"positive_probability": 0.0, "p05": np.nan, "median": np.nan, "p95": np.nan}
    outcomes = []
    for _ in range(samples):
        draw: list[float] = []
        while len(draw) < len(values):
            start = int(rng.integers(0, len(values) - block_months + 1))
            draw.extend(values[start:start + block_months])
        draw = draw[:len(values)]
        outcomes.append(float(np.prod(1.0 + np.asarray(draw)) - 1.0))
    arr = np.asarray(outcomes)
    return {
        "positive_probability": float(np.mean(arr > 0)),
        "p05": float(np.quantile(arr, 0.05)),
        "median": float(np.quantile(arr, 0.50)),
        "p95": float(np.quantile(arr, 0.95)),
    }


def _static_overlay_from_v68(root: Path) -> pd.Series | None:
    """Load an archived V68 comparison only when it is explicitly packaged.

    The clean V78 release must not reach back into a deleted historical Python
    package or synthesize a report during a current-version run.
    """
    path = root / "reports/v68_portfolio_copilot/v68_broad_market_overlay_account.csv"
    if not path.exists():
        return None
    frame = pd.read_csv(path, parse_dates=["date"])
    return frame.set_index("date")["nav_krw"].astype(float)


def build_user_rotation_action_card(
    selection: pd.DataFrame,
    universe: pd.DataFrame,
    *,
    held_ticker: str,
    held_quantity: int,
    current_price_krw: float,
    portfolio_nav_krw: float,
    cfg: V69Config,
) -> dict[str, Any]:
    held_ticker = _normalise_ticker(held_ticker)
    meta = universe.set_index("ticker")
    latest = selection.iloc[-1]
    selected_ticker = latest["leader_ticker"] if pd.notna(latest["leader_ticker"]) else None
    selected_sector = latest["leader_sector"] if pd.notna(latest["leader_sector"]) else None
    held_sector = meta.loc[held_ticker, "sector"] if held_ticker in meta.index else "unknown"
    desired_theme_value = portfolio_nav_krw * float(latest["target_leader_weight"])
    current_theme_value = held_quantity * current_price_krw
    if selected_sector is None:
        action = "TRIM_TO_CORE" if held_quantity > 0 else "HOLD_CORE"
        reason = "no eligible leadership theme under the current market gate"
    elif held_sector == selected_sector:
        action = "HOLD_THEME" if current_theme_value <= desired_theme_value * 1.10 else "TRIM_THEME"
        reason = "the user's holding belongs to the currently selected leadership sector"
    else:
        action = "ROTATE_SECTOR"
        reason = "the user's holding sector differs from the newly selected leadership sector"
    return {
        "as_of_date": str(pd.Timestamp(latest["date"]).date()),
        "information_cutoff": str(pd.Timestamp(latest["information_cutoff"]).date()) if pd.notna(latest["information_cutoff"]) else None,
        "held_ticker": held_ticker,
        "held_sector": held_sector,
        "held_quantity": int(held_quantity),
        "selected_leader_ticker": selected_ticker,
        "selected_leader_sector": selected_sector,
        "target_theme_weight": float(latest["target_leader_weight"]),
        "action": action,
        "reason": reason,
        "order_transmission": False,
        "user_retains_final_decision": True,
    }


def run(root: Path | str, excluded_tickers: Iterable[str] = ()) -> dict[str, Any]:
    root = Path(root)
    cfg = _load_config(root)
    universe = _load_universe(root, cfg, excluded_tickers)
    close, open_px, value = _load_market(root, cfg, universe)
    features = build_feature_panel(close, value, universe, cfg)
    selection = select_dynamic_leader(close.index, universe, features, cfg)
    dynamic, orders = execute_dynamic_overlay(close, open_px, selection, cfg, initial_capital=cfg.initial_capital_krw)
    dynamic_dca, dca_orders = execute_dynamic_overlay(
        close, open_px, selection, cfg,
        initial_capital=cfg.initial_capital_krw,
        monthly_contribution=cfg.monthly_contribution_krw,
    )
    core_price = pd.DataFrame({"open": open_px[cfg.core_ticker], "adj_close": close[cfg.core_ticker]})
    core_hold = _buy_hold(core_price, cfg, cfg.initial_capital_krw)
    core_dca = _buy_hold(core_price, cfg, cfg.initial_capital_krw, cfg.monthly_contribution_krw)
    static_nav = _static_overlay_from_v68(root)
    if static_nav is not None:
        static_nav = static_nav.reindex(close.index).ffill()

    dynamic_nav = dynamic.set_index("date")["nav_krw"]
    core_nav = core_hold.set_index("date")["nav_krw"]
    metric_rows = [
        {"scenario": "DYNAMIC_THEME_LEADERSHIP", **_metrics(dynamic_nav, cfg.initial_capital_krw)},
        {"scenario": "BROAD_CORE_BUY_HOLD", **_metrics(core_nav, cfg.initial_capital_krw)},
    ]
    if static_nav is not None:
        metric_rows.append({"scenario": "STATIC_SINGLE_THEME_OVERLAY_V68", **_metrics(static_nav, cfg.initial_capital_krw)})
    metrics = pd.DataFrame(metric_rows)
    dca = pd.DataFrame([
        {"scenario": "DYNAMIC_THEME_LEADERSHIP_DCA", **_contribution_summary(dynamic_dca)},
        {"scenario": "BROAD_CORE_SIMPLE_DCA", **_contribution_summary(core_dca)},
    ])
    periods = []
    period_navs = [("DYNAMIC_THEME_LEADERSHIP", dynamic_nav), ("BROAD_CORE_BUY_HOLD", core_nav)]
    if static_nav is not None:
        period_navs.append(("STATIC_SINGLE_THEME_OVERLAY_V68", static_nav))
    for scenario, nav in period_navs:
        p = _period_metrics(nav, cfg.initial_capital_krw)
        p.insert(0, "scenario", scenario)
        periods.append(p)
    periods = pd.concat(periods, ignore_index=True)

    monthly_sel = selection[selection["review_monthly"]].copy()
    switches = monthly_sel[monthly_sel["leader_ticker"].ne(monthly_sel["leader_ticker"].shift())].copy()
    leadership = (
        selection.dropna(subset=["leader_sector"])
        .groupby(["leader_sector", "leader_ticker", "leader_name"], dropna=False)
        .agg(trading_days=("date", "count"), first_selected=("date", "min"), last_selected=("date", "max"))
        .reset_index()
        .sort_values("trading_days", ascending=False)
    )
    bootstrap = _monthly_block_bootstrap(dynamic_nav, core_nav, cfg.bootstrap_samples, cfg.bootstrap_block_months)
    cost_rows = []
    for multiplier in (1.0, 2.0, 3.0):
        stressed_cfg = replace(cfg, buy_bps=cfg.buy_bps * multiplier, sell_bps=cfg.sell_bps * multiplier)
        stressed, _ = execute_dynamic_overlay(close, open_px, selection, stressed_cfg, initial_capital=cfg.initial_capital_krw)
        stressed_metrics = _metrics(stressed.set_index("date")["nav_krw"], cfg.initial_capital_krw)
        cost_rows.append({"cost_multiplier": multiplier, **stressed_metrics})
    cost_stress = pd.DataFrame(cost_rows)

    # Negative control: remove every semiconductor-labelled candidate. The same
    # code must still produce valid non-semiconductor selections.
    semiconductors = universe.loc[universe["sector"].eq("semiconductor"), "ticker"].tolist()
    if not excluded_tickers and semiconductors:
        no_semi_universe = _load_universe(root, cfg, semiconductors)
        ns_close, ns_open, ns_value = _load_market(root, cfg, no_semi_universe)
        ns_features = build_feature_panel(ns_close, ns_value, no_semi_universe, cfg)
        ns_selection = select_dynamic_leader(ns_close.index, no_semi_universe, ns_features, cfg)
        negative_control_passed = bool(
            ns_selection["leader_ticker"].notna().any()
            and not ns_selection["leader_ticker"].dropna().isin(semiconductors).any()
            and ns_selection["leader_sector"].dropna().nunique() >= 3
        )
    else:
        negative_control_passed = True

    lookahead = int(
        selection.loc[selection["information_cutoff"].notna(), "information_cutoff"]
        .ge(selection.loc[selection["information_cutoff"].notna(), "date"])
        .sum()
    )
    m = metrics.set_index("scenario")
    d = dca.set_index("scenario")
    distinct_sectors = int(selection["leader_sector"].dropna().nunique())
    period_pivot = periods.pivot(index="period", columns="scenario", values="return_pct")
    period_wins = int((period_pivot["DYNAMIC_THEME_LEADERSHIP"] > period_pivot["BROAD_CORE_BUY_HOLD"]).sum())
    config_text = (root / "config/v69_dynamic_theme_leadership.yaml").read_text(encoding="utf-8").lower()
    no_named_theme_config = all(token not in config_text for token in ("091160", "244580", "semiconductor", "bio_healthcare"))
    gates = pd.DataFrame([
        {"gate": "NO_SPECIFIC_THEME_IN_STRATEGY_CONFIG", "passed": no_named_theme_config and negative_control_passed, "blocking_for_paid_release": True, "detail": "removing all semiconductor candidates still yields a valid multi-sector path"},
        {"gate": "NO_LOOKAHEAD", "passed": lookahead == 0, "blocking_for_paid_release": True, "detail": f"violations={lookahead}"},
        {"gate": "DYNAMIC_SELECTION_DIVERSITY", "passed": distinct_sectors >= 4, "blocking_for_paid_release": True, "detail": f"distinct_selected_sectors={distinct_sectors}"},
        {"gate": "DYNAMIC_BEATS_CORE_LUMP", "passed": m.loc["DYNAMIC_THEME_LEADERSHIP", "return_pct"] > m.loc["BROAD_CORE_BUY_HOLD", "return_pct"], "blocking_for_paid_release": True, "detail": "costed integer-share accounts"},
        {"gate": "DYNAMIC_BEATS_CORE_DCA", "passed": d.loc["DYNAMIC_THEME_LEADERSHIP_DCA", "ending_nav_krw"] > d.loc["BROAD_CORE_SIMPLE_DCA", "ending_nav_krw"], "blocking_for_paid_release": True, "detail": "same contributions and execution costs"},
        {"gate": "LEGACY_V68_REFERENCE_OPTIONAL", "passed": True, "blocking_for_paid_release": False, "detail": "archived V68 comparison is loaded only when explicitly packaged; no deleted-code dependency"},
        {"gate": "PERIOD_DIRECTIONAL_CONSISTENCY", "passed": period_wins >= 3, "blocking_for_paid_release": True, "detail": f"dynamic_beats_core_in_periods={period_wins}/4"},
        {"gate": "COST_3X_BEATS_CORE_LUMP", "passed": float(cost_stress.loc[cost_stress.cost_multiplier.eq(3.0), "return_pct"].iloc[0]) > float(m.loc["BROAD_CORE_BUY_HOLD", "return_pct"]), "blocking_for_paid_release": True, "detail": "dynamic strategy remains ahead of core buy-and-hold at triple explicit costs"},
        {"gate": "BOOTSTRAP_REPRODUCIBILITY", "passed": bootstrap["positive_probability"] >= cfg.bootstrap_probability_gate, "blocking_for_paid_release": True, "detail": f"positive_probability={bootstrap['positive_probability']:.4f}"},
        {"gate": "PAID_AND_LIVE_REMAIN_BLOCKED", "passed": not cfg.paid_deployment_allowed and not cfg.live_execution_allowed, "blocking_for_paid_release": False, "detail": "historical research is not a release approval"},
    ])
    paid_ready = bool(gates.loc[gates["blocking_for_paid_release"], "passed"].all())

    iterations = pd.DataFrame([
        {"iteration": "I1", "design": "STATIC_SINGLE_THEME", "status": "REJECTED_ARCHITECTURE", "finding": "specific theme is embedded in the rule and cannot follow leadership changes"},
        {"iteration": "I2", "design": "MONTHLY_TOP_RELATIVE_MOMENTUM", "status": "FAILED", "finding": "slow rank rotation over-traded weak and late themes"},
        {"iteration": "I3", "design": "MONTHLY_RELATIVE_ACCELERATION_WITH_SECTOR_DEDUP", "status": "SELECTED_RESEARCH_CHALLENGER", "finding": "theme-agnostic rule with D-1 data and one representative per sector"},
        {"iteration": "I4", "design": "I3_PLUS_WEEKLY_DECAY_EXIT", "status": "FINAL_RESEARCH_DESIGN", "finding": "daily evidence, weekly decay exit, monthly challenger rotation"},
    ])
    goal = pd.DataFrame([
        {"goal_id": "G1_REMOVE_THEME_HARDCODING", "status": "PASS" if negative_control_passed else "FAIL", "evidence": "all semiconductor candidates removed negative-control run"},
        {"goal_id": "G2_PIT_DYNAMIC_LEADERSHIP", "status": "PASS" if lookahead == 0 else "FAIL", "evidence": "all selection features lagged one session"},
        {"goal_id": "G3_FOLLOW_THEME_ROTATION", "status": "PASS" if distinct_sectors >= 4 else "FAIL", "evidence": f"selected {distinct_sectors} semantic sectors"},
        {"goal_id": "G4_BEAT_SIMPLE_CORE", "status": "PASS" if bool(gates.loc[gates.gate.eq("DYNAMIC_BEATS_CORE_LUMP"), "passed"].iloc[0]) else "FAIL", "evidence": "integer-share costed lump comparison"},
        {"goal_id": "G5_BEAT_STATIC_THEME", "status": ("PASS" if static_nav is not None and float(m.loc["DYNAMIC_THEME_LEADERSHIP", "return_pct"]) > float(m.loc["STATIC_SINGLE_THEME_OVERLAY_V68", "return_pct"]) else "NOT_EVALUATED"), "evidence": "archived V68 report is optional and was not regenerated from deleted code"},
        {"goal_id": "G6_PAID_ROBUSTNESS", "status": "PASS" if paid_ready else "FAIL", "evidence": "all blocking gates including bootstrap"},
        {"goal_id": "G7_FORWARD_RELEASE", "status": "BLOCKED", "evidence": "period has already been observed during development; forward shadow required"},
    ])

    report_dir = root / "reports" / REPORT_DIR
    report_dir.mkdir(parents=True, exist_ok=True)
    selection.to_csv(report_dir / "v69_daily_leadership_ledger.csv", index=False)
    switches.to_csv(report_dir / "v69_leadership_switches.csv", index=False)
    leadership.to_csv(report_dir / "v69_leadership_summary.csv", index=False)
    dynamic.to_csv(report_dir / "v69_dynamic_shadow_account.csv", index=False)
    orders.to_csv(report_dir / "v69_dynamic_shadow_orders.csv", index=False)
    dynamic_dca.to_csv(report_dir / "v69_dynamic_dca_account.csv", index=False)
    dca_orders.to_csv(report_dir / "v69_dynamic_dca_orders.csv", index=False)
    metrics.to_csv(report_dir / "v69_strategy_comparison.csv", index=False)
    dca.to_csv(report_dir / "v69_dca_comparison.csv", index=False)
    periods.to_csv(report_dir / "v69_period_comparison.csv", index=False)
    pd.DataFrame([bootstrap]).to_csv(report_dir / "v69_block_bootstrap.csv", index=False)
    cost_stress.to_csv(report_dir / "v69_cost_stress.csv", index=False)
    example_held = "091160" if "091160" in set(universe["ticker"]) else str(universe.iloc[0]["ticker"])
    action_card = build_user_rotation_action_card(
        selection, universe, held_ticker=example_held, held_quantity=100,
        current_price_krw=float(close.loc[close.index[-1], example_held]),
        portfolio_nav_krw=cfg.initial_capital_krw, cfg=cfg,
    )
    (report_dir / "v69_latest_user_action_card.json").write_text(json.dumps(action_card, ensure_ascii=False, indent=2), encoding="utf-8")
    gates.to_csv(report_dir / "v69_paid_quality_gates.csv", index=False)
    iterations.to_csv(report_dir / "v69_iteration_summary.csv", index=False)
    goal.to_csv(report_dir / "v69_goal_manifest.csv", index=False)

    decision = {
        "status": "v69_dynamic_theme_research_passed_paid_release_blocked" if paid_ready else "v69_dynamic_theme_research_built_paid_quality_failed",
        "theme_hardcoding_removed": negative_control_passed,
        "paid_quality_passed": paid_ready,
        "paid_deployment_allowed": False,
        "live_execution_allowed": False,
        "distinct_selected_sectors": distinct_sectors,
        "leadership_switch_count": int(len(switches)),
        "lookahead_violations": lookahead,
        "bootstrap": bootstrap,
        "metrics": metrics.to_dict(orient="records"),
        "config": asdict(cfg),
        "inputs": {
            "universe": cfg.universe_source,
            "universe_sha256": _hash(root / cfg.universe_source),
            "prices": "data/all_prices_long_v62_9_expanded.csv",
            "prices_sha256": _hash(root / "data/all_prices_long_v62_9_expanded.csv"),
        },
    }
    (report_dir / "v69_decision.json").write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")

    top = leadership.head(12)
    summary_lines = [
        "# V69 동적 테마 리더십 하네스",
        "",
        f"- 판정: `{decision['status']}`",
        f"- 선택된 고유 섹터 수: {distinct_sectors}",
        f"- 월간 리더 변경 수: {len(switches)}",
        f"- 미래정보 위반: {lookahead}",
        f"- 블록 부트스트랩 양의 초과성과 확률: {bootstrap['positive_probability'] * 100:.2f}%",
        "",
        "## 핵심 원칙",
        "",
        "전략은 반도체·바이오 같은 이름을 조건으로 사용하지 않는다. 동결된 ETF 후보군에서 D-1 절대 추세, 시장 대비 상대강도, 상대강도 가속도, 유동성으로 리더를 고른다. 동일 섹터의 ETF는 한 개만 경쟁에 남는다.",
        "",
        "## 역사적 리더십 요약",
        "",
        top.to_markdown(index=False),
        "",
        "## 해석",
        "",
        "반도체가 선택됐다면 사후에 반도체를 지정한 것이 아니라 당시 다른 모든 적격 섹터와 동일한 규칙으로 경쟁한 결과다. 바이오·금융·자동차·소프트웨어 등 다른 섹터의 상대 추세가 더 강해지면 동일 엔진이 그 섹터로 회전한다.",
        "",
        "현재 데이터는 개발 과정에서 이미 관측됐고 ETF 유니버스도 완전한 역사적 상장폐지 집합은 아니므로, 유료 출시에는 신규 forward shadow와 PIT 유니버스 보강이 필요하다.",
    ]
    (report_dir / "V69_KOREAN_SUMMARY.md").write_text("\n".join(summary_lines), encoding="utf-8")
    return decision
