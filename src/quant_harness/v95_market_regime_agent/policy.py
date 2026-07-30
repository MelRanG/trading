from __future__ import annotations

from typing import Any, Iterable
import math

import numpy as np
import pandas as pd

ACTIVE_POLICY = "D1_MA120_EXPLICIT"
SUPPORTED_POLICIES = (
    ACTIVE_POLICY,
    "MA120_HYSTERESIS_1PCT",
    "MA120_BREADTH_CONFIRM_40PCT",
    "MA120_VOLATILITY_GUARD_35PCT",
)


def _hysteresis_signal(deviation_d1: pd.Series, band: float) -> pd.Series:
    state = False
    out: list[bool] = []
    for value in pd.to_numeric(deviation_d1, errors="coerce"):
        if not np.isfinite(value):
            state = False
        elif state and value <= -float(band):
            state = False
        elif (not state) and value >= float(band):
            state = True
        out.append(state)
    return pd.Series(out, index=deviation_d1.index, dtype=bool)


def build_market_regime_panel(
    close: pd.DataFrame,
    *,
    benchmark_ticker: str,
    theme_tickers: Iterable[str],
    universe_gate_d1: pd.DataFrame | None,
    trend_ma_days: int = 120,
    breadth_floor: float = 0.40,
    breadth_minimum_tickers: int = 5,
    hysteresis_band: float = 0.01,
    volatility_window: int = 20,
    volatility_cap_annualized: float = 0.35,
    policy: str = ACTIVE_POLICY,
) -> dict[str, Any]:
    """Create a causal D-1 market-regime decision panel.

    Every executable field is shifted by one session. Candidate policies alter only
    the market exposure gate; universe ranking, alpha, sizing and execution remain
    unchanged. Breadth uses only point-in-time eligible theme ETFs.
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
    ma_d1 = ma.shift(1)
    deviation_d1 = deviation.shift(1)
    return5_d1 = return5.shift(1)
    vol20_d1 = vol20.shift(1)
    baseline = (
        benchmark_actual_d1
        & history_d1.ge(int(trend_ma_days))
        & benchmark.shift(1).gt(ma_d1)
    ).fillna(False).astype(bool)

    theme_close = close.reindex(columns=tickers)
    theme_ma = theme_close.rolling(int(trend_ma_days), min_periods=int(trend_ma_days)).mean()
    theme_trend_d1 = theme_close.shift(1).gt(theme_ma.shift(1))
    theme_ret63_d1 = theme_close.pct_change(63, fill_method=None).shift(1).gt(0)
    if universe_gate_d1 is None:
        eligible_base = theme_close.shift(1).notna()
    else:
        eligible_base = universe_gate_d1.reindex(index=close.index, columns=tickers).fillna(False).astype(bool)
    breadth_member = eligible_base & theme_trend_d1 & theme_ret63_d1
    breadth_denominator = eligible_base.sum(axis=1)
    breadth = breadth_member.sum(axis=1).div(breadth_denominator.where(breadth_denominator.gt(0)))
    breadth_ready = breadth_denominator.ge(int(breadth_minimum_tickers))

    if policy == ACTIVE_POLICY:
        risk_on = baseline
    elif policy == "MA120_HYSTERESIS_1PCT":
        risk_on = _hysteresis_signal(deviation_d1, float(hysteresis_band)) & benchmark_actual_d1
    elif policy == "MA120_BREADTH_CONFIRM_40PCT":
        risk_on = baseline & breadth_ready & breadth.ge(float(breadth_floor))
    elif policy == "MA120_VOLATILITY_GUARD_35PCT":
        risk_on = baseline & vol20_d1.le(float(volatility_cap_annualized))
    else:  # pragma: no cover
        raise AssertionError(policy)
    risk_on = risk_on.fillna(False).astype(bool)

    prior = risk_on.shift(1, fill_value=False)
    state = pd.Series(
        np.where(~benchmark_actual_d1, "DATA_NOT_READY", np.where(risk_on, "RISK_ON", "RISK_OFF")),
        index=close.index,
    )
    switch = risk_on.ne(prior)
    switch.iloc[0] = False
    panel = pd.DataFrame({
        "date": close.index,
        "policy": policy,
        "information_cutoff": pd.Series(close.index, index=close.index).shift(1).to_numpy(),
        "decision_uses_same_day_close": False,
        "benchmark_actual_d1": benchmark_actual_d1.to_numpy(bool),
        "benchmark_history_bars_d1": history_d1.to_numpy(int),
        "benchmark_close_d1": benchmark.shift(1).to_numpy(float),
        "benchmark_ma120_d1": ma_d1.to_numpy(float),
        "benchmark_distance_to_ma_d1": deviation_d1.to_numpy(float),
        "benchmark_return_5d_d1": return5_d1.to_numpy(float),
        "benchmark_vol20_ann_d1": vol20_d1.to_numpy(float),
        "breadth_eligible_count_d1": breadth_denominator.to_numpy(int),
        "breadth_above_trend_pct_d1": breadth.to_numpy(float),
        "baseline_ma120_risk_on": baseline.to_numpy(bool),
        "risk_on": risk_on.to_numpy(bool),
        "regime_state": state.to_numpy(str),
        "regime_switch": switch.to_numpy(bool),
    }).set_index("date", drop=False)
    return {
        "risk_on": risk_on,
        "panel": panel,
        "baseline": baseline,
        "breadth": breadth,
        "volatility20_ann": vol20_d1,
        "distance_to_ma": deviation_d1,
    }
