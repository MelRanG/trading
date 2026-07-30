from __future__ import annotations

from typing import Any, Iterable
import math

import numpy as np
import pandas as pd

ACTIVE_POLICY = "D1_MA120_EXPLICIT"
SUPPORTED_POLICIES = (
    ACTIVE_POLICY,
    "MA120_CONTINUOUS_RISK_SCORE",
    "MA120_CRASH_GUARD",
)


def build_market_regime_panel(
    close: pd.DataFrame,
    *,
    benchmark_ticker: str,
    theme_tickers: Iterable[str],
    universe_gate_d1: pd.DataFrame | None,
    trend_ma_days: int = 120,
    continuous_full_distance: float = 0.05,
    continuous_low_volatility: float = 0.20,
    continuous_high_volatility: float = 0.40,
    continuous_min_exposure: float = 0.25,
    crash_return_5d_floor: float = -0.06,
    crash_volatility_floor: float = 0.30,
    volatility_window: int = 20,
    policy: str = ACTIVE_POLICY,
) -> dict[str, Any]:
    """Build causal D-1 market exposure and an exposure multiplier.

    V96 changes only MarketRegimeAgent output. Universe, ranking, alpha, V79
    sleeve, execution and costs remain shared with the active parent.
    """
    if policy not in SUPPORTED_POLICIES:
        raise ValueError(f"unsupported market-regime policy: {policy}")
    benchmark_ticker = str(benchmark_ticker)
    tickers = [str(t) for t in theme_tickers]
    benchmark = pd.to_numeric(close[benchmark_ticker], errors="coerce")
    actual = benchmark.notna() & benchmark.gt(0)
    history = actual.cumsum()
    ma = benchmark.rolling(int(trend_ma_days), min_periods=int(trend_ma_days)).mean()
    deviation = benchmark.div(ma).sub(1.0)
    returns1 = benchmark.pct_change(fill_method=None)
    return5 = benchmark.pct_change(5, fill_method=None)
    vol20 = returns1.rolling(int(volatility_window), min_periods=int(volatility_window)).std() * math.sqrt(252.0)

    benchmark_actual_d1 = actual.shift(1, fill_value=False).astype(bool)
    history_d1 = history.shift(1).fillna(0).astype(int)
    close_d1 = benchmark.shift(1)
    ma_d1 = ma.shift(1)
    deviation_d1 = deviation.shift(1)
    return5_d1 = return5.shift(1)
    vol20_d1 = vol20.shift(1)
    baseline = (
        benchmark_actual_d1
        & history_d1.ge(int(trend_ma_days))
        & close_d1.gt(ma_d1)
    ).fillna(False).astype(bool)

    theme_close = close.reindex(columns=tickers)
    eligible = (
        theme_close.shift(1).notna()
        if universe_gate_d1 is None
        else universe_gate_d1.reindex(index=close.index, columns=tickers).fillna(False).astype(bool)
    )
    breadth_denominator = eligible.sum(axis=1)

    trend_confidence = deviation_d1.div(float(continuous_full_distance)).clip(0.0, 1.0)
    vol_confidence = (
        (float(continuous_high_volatility) - vol20_d1)
        / (float(continuous_high_volatility) - float(continuous_low_volatility))
    ).clip(0.0, 1.0)
    continuous_score = pd.concat([trend_confidence, vol_confidence], axis=1).min(axis=1, skipna=False)
    continuous_exposure = (
        float(continuous_min_exposure)
        + (1.0 - float(continuous_min_exposure)) * continuous_score
    ).clip(0.0, 1.0)
    continuous_exposure = continuous_exposure.where(baseline, 0.0).fillna(0.0)

    crash_flag = (
        baseline
        & return5_d1.le(float(crash_return_5d_floor))
        & vol20_d1.ge(float(crash_volatility_floor))
    ).fillna(False).astype(bool)

    if policy == ACTIVE_POLICY:
        risk_on = baseline
        # Parent V95 keeps an already-selected leader at fixed weight between review dates.
        # Preserve that exact behavior; leader existence is applied by the selection ledger.
        exposure_multiplier = pd.Series(1.0, index=close.index)
    elif policy == "MA120_CONTINUOUS_RISK_SCORE":
        risk_on = baseline
        exposure_multiplier = continuous_exposure
    elif policy == "MA120_CRASH_GUARD":
        # Preserve the parent selection state. Only the daily exposure is reduced
        # while both crash conditions are present, then restored immediately.
        risk_on = baseline
        exposure_multiplier = (~crash_flag).astype(float)
    else:  # pragma: no cover
        raise AssertionError(policy)

    risk_on = risk_on.fillna(False).astype(bool)
    exposure_multiplier = pd.to_numeric(exposure_multiplier, errors="coerce").fillna(0.0).clip(0.0, 1.0)
    prior = risk_on.shift(1, fill_value=False)
    switch = risk_on.ne(prior)
    switch.iloc[0] = False
    state = pd.Series(
        np.where(~benchmark_actual_d1, "DATA_NOT_READY", np.where(risk_on, "RISK_ON", "RISK_OFF")),
        index=close.index,
    )
    panel = pd.DataFrame({
        "date": close.index,
        "policy": policy,
        "information_cutoff": pd.Series(close.index, index=close.index).shift(1).to_numpy(),
        "decision_uses_same_day_close": False,
        "benchmark_actual_d1": benchmark_actual_d1.to_numpy(bool),
        "benchmark_history_bars_d1": history_d1.to_numpy(int),
        "benchmark_close_d1": close_d1.to_numpy(float),
        "benchmark_ma120_d1": ma_d1.to_numpy(float),
        "benchmark_distance_to_ma_d1": deviation_d1.to_numpy(float),
        "benchmark_return_5d_d1": return5_d1.to_numpy(float),
        "benchmark_vol20_ann_d1": vol20_d1.to_numpy(float),
        "breadth_eligible_count_d1": breadth_denominator.to_numpy(int),
        "baseline_ma120_risk_on": baseline.to_numpy(bool),
        "trend_confidence_d1": trend_confidence.to_numpy(float),
        "volatility_confidence_d1": vol_confidence.to_numpy(float),
        "continuous_risk_score_d1": continuous_score.to_numpy(float),
        "crash_guard_triggered_d1": crash_flag.to_numpy(bool),
        "exposure_multiplier": exposure_multiplier.to_numpy(float),
        "risk_on": risk_on.to_numpy(bool),
        "regime_state": state.to_numpy(str),
        "regime_switch": switch.to_numpy(bool),
    }).set_index("date", drop=False)
    return {
        "risk_on": risk_on,
        "exposure_multiplier": exposure_multiplier,
        "panel": panel,
        "baseline": baseline,
        "continuous_score": continuous_score,
        "crash_flag": crash_flag,
    }
