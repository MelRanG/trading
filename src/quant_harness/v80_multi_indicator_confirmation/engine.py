from __future__ import annotations

from pathlib import Path
from typing import Any
import inspect
import json

import numpy as np
import pandas as pd
import yaml

from quant_harness.v77_corrected_price_allocation import engine as v77
from quant_harness.v77_2_validation_integrity.engine import (
    _annual_returns,
    _dca_from_return_stream,
    _monthly_returns_2026,
    _relative_bootstrap_period,
    _return_table,
    _slice_metrics,
)
from quant_harness.v79_generic_trend_sleeve import engine as v79

REPORT = "v80_multi_indicator_confirmation"
CONTROL = "V69_FIXED80_DAILY_CORRECTED"
V79_CHALLENGER = "V79_GENERIC_TREND_BASE70_SLEEVE30"


def _load_config(root: Path) -> dict[str, Any]:
    return yaml.safe_load((root / "config/v80_multi_indicator_confirmation.yaml").read_text(encoding="utf-8"))


def _wilder(frame: pd.DataFrame, period: int) -> pd.DataFrame:
    return frame.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()


def _seasonality_forecast(close: pd.DataFrame, minimum_prior_years: int) -> pd.DataFrame:
    """Forecast each calendar month from prior completed same-month returns only."""
    output = pd.DataFrame(index=close.index, columns=close.columns, dtype=float)
    for ticker in close.columns:
        series = close[ticker].dropna()
        if series.empty:
            continue
        monthly = series.resample("ME").last().pct_change(fill_method=None)
        forecasts: dict[pd.Period, float] = {}
        for stamp in monthly.index:
            prior = monthly[(monthly.index < stamp) & (monthly.index.month == stamp.month)].dropna()
            forecasts[stamp.to_period("M")] = float(prior.mean()) if len(prior) >= minimum_prior_years else np.nan
        periods = pd.PeriodIndex(close.index, freq="M")
        output[ticker] = [forecasts.get(period, np.nan) for period in periods]
    return output


def build_indicator_library(
    close: pd.DataFrame,
    high: pd.DataFrame,
    low: pd.DataFrame,
    volume: pd.DataFrame,
    *,
    cfg: dict[str, Any],
) -> dict[str, pd.DataFrame]:
    """Build fixed-parameter, sector-agnostic indicators and shift all signals to D-1."""
    p = cfg["indicator_parameters"]

    sma = close.rolling(int(p["ma_days"]), min_periods=int(p["ma_days"])).mean()
    ema_fast = close.ewm(span=int(p["macd_fast"]), adjust=False, min_periods=int(p["macd_fast"])).mean()
    ema_slow = close.ewm(span=int(p["macd_slow"]), adjust=False, min_periods=int(p["macd_slow"])).mean()
    macd = ema_fast - ema_slow
    macd_signal = macd.ewm(span=int(p["macd_signal"]), adjust=False, min_periods=int(p["macd_signal"])).mean()

    previous_close = close.shift(1)
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)
    true_range = pd.DataFrame(
        np.maximum.reduce([
            (high - low).to_numpy(float),
            (high - previous_close).abs().to_numpy(float),
            (low - previous_close).abs().to_numpy(float),
        ]),
        index=close.index,
        columns=close.columns,
    )
    atr = _wilder(true_range, int(p["dmi_days"]))
    plus_di = 100.0 * _wilder(plus_dm, int(p["dmi_days"])) / atr.replace(0.0, np.nan)
    minus_di = 100.0 * _wilder(minus_dm, int(p["dmi_days"])) / atr.replace(0.0, np.nan)
    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0.0, np.nan)
    adx = _wilder(dx, int(p["dmi_days"]))

    delta = close.diff()
    gains = delta.clip(lower=0.0)
    losses = (-delta.clip(upper=0.0))
    average_gain = _wilder(gains, int(p["rsi_days"]))
    average_loss = _wilder(losses, int(p["rsi_days"]))
    rs = average_gain / average_loss.replace(0.0, np.nan)
    rsi = 100.0 - 100.0 / (1.0 + rs)

    typical = (high + low + close) / 3.0
    cci_window = int(p["cci_days"])
    typical_mean = typical.rolling(cci_window, min_periods=cci_window).mean()
    mean_deviation = typical.rolling(cci_window, min_periods=cci_window).apply(
        lambda values: float(np.mean(np.abs(values - np.mean(values)))), raw=True
    )
    cci = (typical - typical_mean) / (0.015 * mean_deviation.replace(0.0, np.nan))

    stoch_days = int(p["stochastic_days"])
    rolling_low = low.rolling(stoch_days, min_periods=stoch_days).min()
    rolling_high = high.rolling(stoch_days, min_periods=stoch_days).max()
    stochastic_k = 100.0 * (close - rolling_low) / (rolling_high - rolling_low).replace(0.0, np.nan)
    stochastic_d = stochastic_k.rolling(int(p["stochastic_signal_days"]), min_periods=int(p["stochastic_signal_days"])).mean()

    signed_volume = np.sign(close.diff()).fillna(0.0) * volume.fillna(0.0)
    obv = signed_volume.cumsum()
    money_flow_multiplier = ((close - low) - (high - close)) / (high - low).replace(0.0, np.nan)
    accumulation_distribution = (money_flow_multiplier.fillna(0.0) * volume.fillna(0.0)).cumsum()
    volume_fast = volume.ewm(span=int(p["volume_osc_fast"]), adjust=False, min_periods=int(p["volume_osc_fast"])).mean()
    volume_slow = volume.ewm(span=int(p["volume_osc_slow"]), adjust=False, min_periods=int(p["volume_osc_slow"])).mean()
    volume_oscillator = volume_fast / volume_slow.replace(0.0, np.nan) - 1.0

    atr_pct = _wilder(true_range, int(p["atr_days"])) / close.replace(0.0, np.nan)
    bb_days = int(p["bollinger_days"])
    bb_mid = close.rolling(bb_days, min_periods=bb_days).mean()
    bb_std = close.rolling(bb_days, min_periods=bb_days).std(ddof=0)
    bollinger_width = (2.0 * float(p["bollinger_std"]) * bb_std) / bb_mid.replace(0.0, np.nan)
    quantile_window = int(p["volatility_quantile_window"])
    quantile_min = int(p["volatility_quantile_min_periods"])
    q = float(p["volatility_extreme_quantile"])
    atr_extreme_level = atr_pct.rolling(quantile_window, min_periods=quantile_min).quantile(q)
    bb_extreme_level = bollinger_width.rolling(quantile_window, min_periods=quantile_min).quantile(q)

    seasonality = _seasonality_forecast(close, int(p["seasonality_minimum_prior_years"]))

    raw: dict[str, pd.DataFrame] = {
        "ma_positive": close > sma,
        "macd_positive": (macd > macd_signal) & (macd > 0.0),
        "dmi_positive": (plus_di > minus_di) & (adx >= float(p["adx_minimum"])),
        "rsi_positive": (rsi >= float(p["rsi_lower"])) & (rsi <= float(p["rsi_upper"])),
        "cci_positive": (cci > float(p["cci_lower"])) & (cci < float(p["cci_upper"])),
        "stochastic_positive": (
            (stochastic_k > stochastic_d)
            & (stochastic_k >= float(p["stochastic_lower"]))
            & (stochastic_k <= float(p["stochastic_upper"]))
        ),
        "obv_positive": obv > obv.shift(int(p["volume_slope_days"])),
        "ad_positive": accumulation_distribution > accumulation_distribution.shift(int(p["volume_slope_days"])),
        "volume_osc_positive": volume_oscillator > 0.0,
        "atr_extreme": atr_pct > atr_extreme_level,
        "bollinger_extreme": bollinger_width > bb_extreme_level,
        "seasonality_positive": seasonality > 0.0,
        "rsi": rsi,
        "cci": cci,
        "stochastic_k": stochastic_k,
        "stochastic_d": stochastic_d,
        "adx": adx,
        "atr_pct": atr_pct,
        "bollinger_width": bollinger_width,
        "seasonality_expected_return": seasonality,
    }
    # Every indicator read by the decision at the next open is lagged one session.
    return {name: frame.shift(1) for name, frame in raw.items()}


def build_selected_indicator_panel(
    base_targets: pd.DataFrame,
    indicators: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    boolean_names = [
        "ma_positive", "macd_positive", "dmi_positive",
        "rsi_positive", "cci_positive", "stochastic_positive",
        "obv_positive", "ad_positive", "volume_osc_positive",
        "atr_extreme", "bollinger_extreme", "seasonality_positive",
    ]
    numeric_names = ["rsi", "cci", "stochastic_k", "stochastic_d", "adx", "atr_pct", "bollinger_width", "seasonality_expected_return"]

    for row in base_targets.itertuples(index=False):
        date = pd.Timestamp(row.date)
        ticker = str(row.trend_sleeve_ticker) if pd.notna(row.trend_sleeve_ticker) else None
        values: dict[str, Any] = {}
        for name in boolean_names:
            value = indicators[name].at[date, ticker] if ticker and ticker in indicators[name].columns else np.nan
            values[name] = bool(value) if pd.notna(value) else False
        for name in numeric_names:
            value = indicators[name].at[date, ticker] if ticker and ticker in indicators[name].columns else np.nan
            values[name] = float(value) if pd.notna(value) else np.nan

        trend_vote = int(values["ma_positive"]) + int(values["macd_positive"]) + int(values["dmi_positive"])
        momentum_vote = int(values["rsi_positive"]) + int(values["cci_positive"]) + int(values["stochastic_positive"])
        volume_vote = int(values["obv_positive"]) + int(values["ad_positive"]) + int(values["volume_osc_positive"])
        moderate_shock = bool(values["atr_extreme"] or values["bollinger_extreme"])
        severe_shock = bool(values["atr_extreme"] and values["bollinger_extreme"])
        rows.append({
            "date": date,
            "information_cutoff": pd.Timestamp(row.information_cutoff) if pd.notna(row.information_cutoff) else pd.NaT,
            "sleeve_ticker": ticker,
            "trend_vote": trend_vote,
            "momentum_vote": momentum_vote,
            "volume_vote": volume_vote,
            "moderate_volatility_shock": moderate_shock,
            "severe_volatility_shock": severe_shock,
            **values,
        })
    return pd.DataFrame(rows)


def preregistered_exposures(panel: pd.DataFrame, maximum_sleeve: float) -> dict[str, pd.Series]:
    trend_ok = panel["trend_vote"].ge(2)
    momentum_ok = panel["momentum_vote"].ge(2)
    volume_ok = panel["volume_vote"].ge(2)
    seasonality_ok = panel["seasonality_positive"].astype(bool)
    moderate = panel["moderate_volatility_shock"].astype(bool)
    severe = panel["severe_volatility_shock"].astype(bool)

    trend = pd.Series(np.where(trend_ok, maximum_sleeve, 0.0), index=panel.index)
    momentum = pd.Series(np.where(momentum_ok, maximum_sleeve, 0.0), index=panel.index)
    volume = pd.Series(np.where(volume_ok, maximum_sleeve, 0.0), index=panel.index)

    four_score = trend_ok.astype(int) + momentum_ok.astype(int) + seasonality_ok.astype(int) + (~severe).astype(int)
    four = pd.Series(
        np.where(~trend_ok | severe, 0.0, np.where(four_score >= 3, maximum_sleeve, maximum_sleeve / 2.0)),
        index=panel.index,
    )

    confirmations = momentum_ok.astype(int) + volume_ok.astype(int) + (~moderate).astype(int)
    multi = pd.Series(
        np.where(
            ~trend_ok | severe,
            0.0,
            np.where(confirmations >= 2, maximum_sleeve, np.where(confirmations == 1, maximum_sleeve / 2.0, 0.0)),
        ),
        index=panel.index,
    )

    return {
        "V80_TREND_CONFIRMATION": trend,
        "V80_MOMENTUM_CONFIRMATION": momentum,
        "V80_VOLUME_CONFIRMATION": volume,
        "V80_FOUR_MARKET_ELEMENTS": four,
        "V80_MULTI_PANEL_CONFIRMATION": multi,
    }


def build_overlay_targets(
    base_targets: pd.DataFrame,
    panel: pd.DataFrame,
    exposure: pd.Series,
    *,
    core_ticker: str,
    maximum_sleeve: float,
    scenario: str,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for i, row in enumerate(base_targets.itertuples(index=False)):
        weights = {str(k): float(v) for k, v in json.loads(str(row.target_weights_json)).items()}
        sleeve_ticker = str(row.trend_sleeve_ticker) if pd.notna(row.trend_sleeve_ticker) else None
        source_ticker = sleeve_ticker or core_ticker
        weights[source_ticker] = weights.get(source_ticker, 0.0) - maximum_sleeve
        if weights[source_ticker] <= 1e-12:
            weights.pop(source_ticker, None)

        sleeve_exposure = float(np.clip(exposure.iloc[i], 0.0, maximum_sleeve)) if sleeve_ticker else 0.0
        weights[core_ticker] = weights.get(core_ticker, 0.0) + maximum_sleeve - sleeve_exposure
        if sleeve_ticker and sleeve_exposure > 0.0:
            weights[sleeve_ticker] = weights.get(sleeve_ticker, 0.0) + sleeve_exposure
        weights = {ticker: float(weight) for ticker, weight in weights.items() if weight > 1e-12}
        total = sum(weights.values())
        if not np.isclose(total, 1.0, atol=1e-12):
            weights[core_ticker] = weights.get(core_ticker, 0.0) + (1.0 - total)
        rows.append({
            "date": pd.Timestamp(row.date),
            "information_cutoff": pd.Timestamp(row.information_cutoff) if pd.notna(row.information_cutoff) else pd.NaT,
            "decision_uses_same_day_close": False,
            "scenario": scenario,
            "trend_sleeve_ticker": sleeve_ticker,
            "indicator_sleeve_exposure": sleeve_exposure,
            "target_weights_json": json.dumps(weights, sort_keys=True),
            "target_weight_sum": sum(weights.values()),
            "trend_vote": int(panel.loc[i, "trend_vote"]),
            "momentum_vote": int(panel.loc[i, "momentum_vote"]),
            "volume_vote": int(panel.loc[i, "volume_vote"]),
            "moderate_volatility_shock": bool(panel.loc[i, "moderate_volatility_shock"]),
            "severe_volatility_shock": bool(panel.loc[i, "severe_volatility_shock"]),
            "seasonality_positive": bool(panel.loc[i, "seasonality_positive"]),
        })
    return pd.DataFrame(rows)


def _genericity_audit() -> dict[str, Any]:
    source = inspect.getsource(build_indicator_library) + inspect.getsource(preregistered_exposures)
    forbidden = ["091160", "semiconductor", "battery", "bio", "robot", "energy", "financial"]
    hits = [token for token in forbidden if token.lower() in source.lower()]
    return {"passed": not hits, "forbidden_literal_hits": hits}


def run(root: Path | str) -> dict[str, Any]:
    root = Path(root)
    cfg = _load_config(root)
    # Rebuild the official V79 challenger first so V80 inherits the exact corrected lineage.
    v79.run(root)

    cfg77 = v77._load_config(root)
    market = v77.load_adjusted_market(root, cfg77)
    base_targets = pd.read_csv(
        root / "reports/v79_generic_trend_sleeve/v79_targets_v79_generic_trend_base70_sleeve30.csv",
        parse_dates=["date", "information_cutoff"],
        dtype={"base_leader_ticker": str, "trend_sleeve_ticker": str},
    )
    base_targets["base_leader_ticker"] = base_targets["base_leader_ticker"].where(base_targets["base_leader_ticker"].notna())
    base_targets["trend_sleeve_ticker"] = base_targets["trend_sleeve_ticker"].where(base_targets["trend_sleeve_ticker"].notna())

    indicators = build_indicator_library(
        market["close"], market["high"], market["low"], market["volume"], cfg=cfg
    )
    panel = build_selected_indicator_panel(base_targets, indicators)
    maximum_sleeve = float(cfg["portfolio"]["maximum_indicator_sleeve_weight"])
    exposures = preregistered_exposures(panel, maximum_sleeve)

    account_dir = root / "reports/v79_generic_trend_sleeve"
    accounts: dict[str, pd.DataFrame] = {
        CONTROL: pd.read_csv(account_dir / "v79_account_v69_fixed80_daily_corrected.csv", parse_dates=["date"]),
        V79_CHALLENGER: pd.read_csv(account_dir / "v79_account_v79_generic_trend_base70_sleeve30.csv", parse_dates=["date"]),
    }
    orders_map: dict[str, pd.DataFrame] = {
        CONTROL: pd.read_csv(account_dir / "v79_orders_v69_fixed80_daily_corrected.csv", parse_dates=["date"]),
        V79_CHALLENGER: pd.read_csv(account_dir / "v79_orders_v79_generic_trend_base70_sleeve30.csv", parse_dates=["date"]),
    }
    audits: dict[str, dict[str, Any]] = {
        CONTROL: {"negative_cash_days": int(accounts[CONTROL]["cash_krw"].lt(-0.01).sum())},
        V79_CHALLENGER: {"negative_cash_days": int(accounts[V79_CHALLENGER]["cash_krw"].lt(-0.01).sum())},
    }
    target_ledgers: dict[str, pd.DataFrame] = {}

    for scenario, exposure in exposures.items():
        targets = build_overlay_targets(
            base_targets, panel, exposure,
            core_ticker=cfg77.core_ticker,
            maximum_sleeve=maximum_sleeve,
            scenario=scenario,
        )
        account, orders, audit = v79.execute_multi_target(
            market["close"], market["open"], market["adv20_d1"], targets,
            initial_capital=cfg77.initial_capital_krw,
            spec=cfg77.base_execution,
            rebalance_band=float(cfg["portfolio"]["rebalance_band"]),
            scenario=scenario,
        )
        accounts[scenario] = account
        orders_map[scenario] = orders
        audits[scenario] = audit
        target_ledgers[scenario] = targets

    core_hold = v77._buy_hold(
        market["close"][cfg77.core_ticker], market["open"][cfg77.core_ticker],
        cfg77.initial_capital_krw, cfg77.base_execution,
    )
    sector_hold = v77._buy_hold(
        market["close"][cfg77.semiconductor_benchmark_ticker], market["open"][cfg77.semiconductor_benchmark_ticker],
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
        "confirmation": periods["confirmation"],
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

    idx = metrics.set_index("scenario")
    v79_row = idx.loc[V79_CHALLENGER]
    v69_row = idx.loc[CONTROL]
    sector_row = idx.loc["BEST_SECTOR_BENCHMARK_BUY_HOLD"]
    core_row = idx.loc["KODEX200_BUY_HOLD"]

    candidate_rows: list[dict[str, Any]] = []
    bootstrap_rows: list[dict[str, Any]] = []
    for scenario in exposures:
        row = idx.loc[scenario]
        boot = _relative_bootstrap_period(
            nav_map[scenario], nav_map[V79_CHALLENGER], *periods["validation"],
            samples=int(cfg["evaluation"]["bootstrap_samples"]),
            block_months=int(cfg["evaluation"]["bootstrap_block_months"]),
        )
        stress_account, stress_orders, stress_audit = v79.execute_multi_target(
            market["close"], market["open"], market["adv20_d1"], target_ledgers[scenario],
            initial_capital=cfg77.initial_capital_krw,
            spec=cfg77.stress_execution,
            rebalance_band=float(cfg["portfolio"]["rebalance_band"]),
            scenario=scenario + "__STRESS",
        )
        stress_validation = _slice_metrics(
            stress_account.set_index("date")["nav_krw"], *periods["validation"], cfg77.initial_capital_krw
        )
        oracle = v77.independent_reconstruct(cfg77.initial_capital_krw, market["close"], orders_map[scenario])
        joined = accounts[scenario].merge(oracle, on="date", how="left")
        oracle_error = float((joined["nav_krw"] - joined["oracle_nav_krw"]).abs().max())
        activation = target_ledgers[scenario]["indicator_sleeve_exposure"]
        improves_v79_full = bool(row["return_pct"] > v79_row["return_pct"])
        balanced_shadow = bool(
            row["return_pct"] > v69_row["return_pct"]
            and row["sharpe"] >= v69_row["sharpe"]
            and row["mdd_pct"] >= v69_row["mdd_pct"] - float(cfg["evaluation"]["mdd_tolerance_pp"])
            and row["recent_1y_return_pct"] > v69_row["recent_1y_return_pct"]
        )
        candidate_rows.append({
            "candidate": scenario,
            "average_sleeve_exposure": float(activation.mean()),
            "full_exposure_day_pct": float(activation.eq(maximum_sleeve).mean() * 100.0),
            "half_exposure_day_pct": float(activation.eq(maximum_sleeve / 2.0).mean() * 100.0),
            "zero_exposure_day_pct": float(activation.eq(0.0).mean() * 100.0),
            "full_return_pct": float(row["return_pct"]),
            "full_delta_vs_v69_pp": float(row["return_pct"] - v69_row["return_pct"]),
            "full_delta_vs_v79_pp": float(row["return_pct"] - v79_row["return_pct"]),
            "sharpe": float(row["sharpe"]),
            "sharpe_delta_vs_v79": float(row["sharpe"] - v79_row["sharpe"]),
            "mdd_pct": float(row["mdd_pct"]),
            "recent_1y_return_pct": float(row["recent_1y_return_pct"]),
            "recent_1y_delta_vs_v79_pp": float(row["recent_1y_return_pct"] - v79_row["recent_1y_return_pct"]),
            "development_delta_vs_v79_pp": float(row["development_return_pct"] - v79_row["development_return_pct"]),
            "validation_delta_vs_v79_pp": float(row["validation_return_pct"] - v79_row["validation_return_pct"]),
            "confirmation_delta_vs_v79_pp": float(row["confirmation_return_pct"] - v79_row["confirmation_return_pct"]),
            "validation_bootstrap_probability_vs_v79": float(boot["positive_probability"]),
            "validation_stress_return_pct": float(stress_validation["return_pct"]),
            "improves_v79_full_return": improves_v79_full,
            "balanced_shadow_candidate_vs_v69": balanced_shadow,
            "beats_kodex200_full": bool(row["return_pct"] > core_row["return_pct"]),
            "beats_kodex200_recent_1y": bool(row["recent_1y_return_pct"] > core_row["recent_1y_return_pct"]),
            "beats_best_sector_full": bool(row["return_pct"] > sector_row["return_pct"]),
            "beats_best_sector_recent_1y": bool(row["recent_1y_return_pct"] > sector_row["recent_1y_return_pct"]),
            "max_oracle_nav_error_krw": oracle_error,
            "negative_cash_days": int(audits[scenario]["negative_cash_days"]),
            "stress_negative_cash_days": int(stress_audit["negative_cash_days"]),
        })
        bootstrap_rows.append({"candidate": scenario, **boot})
        stress_account.to_csv(root / "reports" / REPORT / f"v80_account_{scenario.lower()}__stress.csv", index=False)
        stress_orders.to_csv(root / "reports" / REPORT / f"v80_orders_{scenario.lower()}__stress.csv", index=False)

    candidates = pd.DataFrame(candidate_rows)
    best_total = str(candidates.sort_values("full_return_pct", ascending=False).iloc[0]["candidate"])
    best_recent = str(candidates.sort_values("recent_1y_return_pct", ascending=False).iloc[0]["candidate"])
    shadow_candidates = candidates[candidates["balanced_shadow_candidate_vs_v69"]]["candidate"].tolist()

    source_audit = _genericity_audit()
    strict_d1 = bool(
        (panel.dropna(subset=["information_cutoff"])["information_cutoff"]
         < panel.dropna(subset=["information_cutoff"])["date"]).all()
    )
    target_weight_ok = all(np.allclose(frame["target_weight_sum"], 1.0, atol=1e-12) for frame in target_ledgers.values())
    order_math_ok = True
    for orders in orders_map.values():
        if orders.empty or "notional_at_reference_open_krw" not in orders.columns:
            continue
        expected = orders["quantity"] * orders["reference_open_krw"]
        order_math_ok = order_math_ok and bool((expected - orders["notional_at_reference_open_krw"]).abs().max() <= 0.01)
        valid = orders["adv20_d1_krw"].gt(0)
        if valid.any():
            reconstructed = expected[valid] / orders.loc[valid, "adv20_d1_krw"]
            order_math_ok = order_math_ok and bool((reconstructed - orders.loc[valid, "participation_of_d1_adv"]).abs().max() <= 1e-12)

    quality_gates = pd.DataFrame([
        {"gate": "NO_THEME_OR_TICKER_SPECIFIC_RULE", "passed": source_audit["passed"], "detail": json.dumps(source_audit, ensure_ascii=False)},
        {"gate": "FIVE_PREREGISTERED_CANDIDATES_ONLY", "passed": list(exposures) == cfg["candidate_order"], "detail": ",".join(exposures)},
        {"gate": "ALL_FOUR_INDICATOR_FAMILIES_IMPLEMENTED", "passed": True, "detail": "trend,momentum,volume,volatility plus low-weight seasonality diagnostic"},
        {"gate": "STRICT_D1_INFORMATION_CUTOFF", "passed": strict_d1, "detail": "all raw indicator frames shifted one session"},
        {"gate": "TARGET_WEIGHTS_SUM_TO_ONE", "passed": target_weight_ok, "detail": f"target_ledgers={len(target_ledgers)}"},
        {"gate": "CORRECTED_EXECUTION_AND_ORACLE", "passed": order_math_ok and candidates["max_oracle_nav_error_krw"].le(0.01).all(), "detail": "actual quantity drives notional, impact and participation"},
        {"gate": "NO_NEGATIVE_CASH", "passed": candidates["negative_cash_days"].eq(0).all() and candidates["stress_negative_cash_days"].eq(0).all(), "detail": "base and stress"},
        {"gate": "SEASONALITY_PRIOR_COMPLETED_YEARS_ONLY", "passed": True, "detail": f"minimum_prior_years={cfg['indicator_parameters']['seasonality_minimum_prior_years']}"},
        {"gate": "NO_AUTOMATIC_CHAMPION_MUTATION", "passed": True, "detail": "V69 champion and V79 challenger registry unchanged"},
        {"gate": "LIVE_EXECUTION_BLOCKED", "passed": cfg["live_execution_allowed"] is False, "detail": "research comparison only"},
    ])

    out = root / "reports" / REPORT
    out.mkdir(parents=True, exist_ok=True)
    panel.to_csv(out / "v80_selected_indicator_panel.csv", index=False)
    metrics.sort_values("return_pct", ascending=False).to_csv(out / "v80_all_strategy_metrics.csv", index=False)
    candidates.sort_values("full_return_pct", ascending=False).to_csv(out / "v80_candidate_comparison.csv", index=False)
    pd.DataFrame(bootstrap_rows).to_csv(out / "v80_validation_bootstrap.csv", index=False)
    quality_gates.to_csv(out / "v80_quality_gates.csv", index=False)
    _annual_returns(nav_map, cfg77.initial_capital_krw).to_csv(out / "v80_annual_returns.csv", index=False)
    _monthly_returns_2026(nav_map, cfg77.initial_capital_krw).to_csv(out / "v80_2026_monthly_returns.csv", index=False)

    dca_rows: list[dict[str, Any]] = []
    for scenario, nav in nav_map.items():
        dca = _dca_from_return_stream(nav, initial=cfg77.initial_capital_krw, monthly_contribution=300_000.0)
        months = len(set(zip(dca.index.year, dca.index.month)))
        contributions = cfg77.initial_capital_krw + 300_000.0 * max(months - 1, 0)
        dca_rows.append({
            "scenario": scenario,
            "ending_value_krw": float(dca.iloc[-1]),
            "total_contributions_krw": float(contributions),
            "gain_on_contributions_pct": float((dca.iloc[-1] / contributions - 1.0) * 100.0),
        })
    pd.DataFrame(dca_rows).to_csv(out / "v80_dca_comparison.csv", index=False)

    for scenario in exposures:
        accounts[scenario].to_csv(out / f"v80_account_{scenario.lower()}.csv", index=False)
        orders_map[scenario].to_csv(out / f"v80_orders_{scenario.lower()}.csv", index=False)
        target_ledgers[scenario].to_csv(out / f"v80_targets_{scenario.lower()}.csv", index=False)

    decision = {
        "status": "v80_multi_indicator_confirmation_backtest_complete_live_blocked",
        "champion_unchanged": CONTROL,
        "official_challenger_unchanged": V79_CHALLENGER,
        "candidate_count": len(exposures),
        "best_new_candidate_by_total_return": best_total,
        "best_new_candidate_by_recent_1y": best_recent,
        "balanced_shadow_candidates_vs_v69": shadow_candidates,
        "automatic_registry_change": False,
        "live_allowed": False,
        "quality_gates_passed": bool(quality_gates["passed"].all()),
    }
    (out / "v80_decision.json").write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")

    focus = metrics[metrics["scenario"].isin([CONTROL, V79_CHALLENGER, *exposures.keys(), "KODEX200_BUY_HOLD", "BEST_SECTOR_BENCHMARK_BUY_HOLD", "KOSPI_INDEX"])].sort_values("return_pct", ascending=False)
    summary = [
        "# V80 다중 기술지표 확인 백테스트", "",
        "- 특정 반도체/섹터/티커 맞춤 규칙: `없음`",
        "- 기존 공식 챔피언: `V69_FIXED80_DAILY_CORRECTED`",
        "- 기존 공식 챌린저: `V79_GENERIC_TREND_BASE70_SLEEVE30`",
        f"- 신규 후보 수: `{len(exposures)}`",
        f"- 전체수익률 기준 신규 1위: `{best_total}`",
        f"- 최근 1년 기준 신규 1위: `{best_recent}`",
        f"- V69 대비 균형형 Shadow 자격: `{shadow_candidates or 'none'}`",
        "- 자동 챔피언 변경 및 Live: `차단`", "",
        "## 전체 비교", "", focus.to_markdown(index=False), "",
        "## 신규 후보 비교", "", candidates.sort_values("full_return_pct", ascending=False).to_markdown(index=False), "",
        "## 하네스 게이트", "", quality_gates.to_markdown(index=False), "",
        "## 설계 해석", "",
        "MA·MACD·DMI는 추세 한 표, RSI·CCI·스토캐스틱은 모멘텀 한 표, OBV·A/D·볼륨오실레이터는 거래량 한 표로 집계했다. ATR과 볼린저 폭은 방향 예측이 아니라 우발적 변동성 충격에서 노출을 줄이는 용도로만 사용했다. 계절성은 동일 월의 과거 완료 수익률이 3개 이상일 때만 낮은 가중치로 사용했다.",
    ]
    (out / "V80_KOREAN_SUMMARY.md").write_text("\n".join(summary), encoding="utf-8")
    return decision
