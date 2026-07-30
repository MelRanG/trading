from __future__ import annotations

from typing import Any, Iterable
import math
import numpy as np
import pandas as pd


def build_universe_gate(
    close: pd.DataFrame,
    value: pd.DataFrame,
    tickers: Iterable[str],
    *,
    minimum_history_days: int,
    minimum_median_value_20d_krw: float,
    stable_liquidity_floor_krw: float | None = None,
    minimum_observation_coverage_20d: float = 0.95,
    minimum_observation_coverage_60d: float = 0.95,
) -> dict[str, Any]:
    """Build a D-1 point-in-time eligibility gate from actually observed bars.

    The gate never forward-fills eligibility evidence. A ticker needs an actual,
    positive close and value observation, a count of real bars rather than elapsed
    calendar sessions, and high recent observation coverage. The optional lower-
    quartile liquidity floor is a research-only robustness filter.
    """
    columns = [str(t) for t in tickers]
    c = close.reindex(columns=columns)
    v = value.reindex(index=close.index, columns=columns)
    observed = c.notna() & c.gt(0) & v.notna() & v.gt(0)
    actual_history = observed.cumsum()
    coverage20 = observed.rolling(20, min_periods=20).mean()
    coverage60 = observed.rolling(60, min_periods=60).mean()
    liquidity_min_periods = max(1, int(math.ceil(20 * float(minimum_observation_coverage_20d))))
    liquidity_median20 = v.where(observed).rolling(20, min_periods=liquidity_min_periods).median()
    liquidity_q25_20 = v.where(observed).rolling(20, min_periods=liquidity_min_periods).quantile(0.25)

    lifecycle = pd.DataFrame(False, index=close.index, columns=columns)
    catalog_rows: list[dict[str, Any]] = []
    data_end = close.index.max()
    for ticker in columns:
        valid = observed.index[observed[ticker]]
        if len(valid) == 0:
            first = last = pd.NaT
        else:
            first, last = valid.min(), valid.max()
            lifecycle.loc[(lifecycle.index >= first) & (lifecycle.index <= last), ticker] = True
        catalog_rows.append({
            "ticker": ticker,
            "available_from": first.date().isoformat() if pd.notna(first) else None,
            "available_to": last.date().isoformat() if pd.notna(last) else None,
            "observed_bar_count": int(observed[ticker].sum()),
            "status": "ACTIVE_AS_OF_DATA_END" if pd.notna(last) and last == data_end else "INACTIVE_OR_LAGGING_AS_OF_DATA_END",
            "listing_source": "OBSERVED_FIRST_BAR_PROXY",
            "delisting_complete": False,
            "corporate_action_verified": False,
        })

    raw_gate = (
        lifecycle
        & observed
        & actual_history.ge(int(minimum_history_days))
        & coverage20.ge(float(minimum_observation_coverage_20d))
        & coverage60.ge(float(minimum_observation_coverage_60d))
        & liquidity_median20.ge(float(minimum_median_value_20d_krw))
    )
    if stable_liquidity_floor_krw is not None:
        raw_gate &= liquidity_q25_20.ge(float(stable_liquidity_floor_krw))

    return {
        "gate": raw_gate.shift(1, fill_value=False).astype(bool),
        "observed_d1": observed.shift(1, fill_value=False).astype(bool),
        "actual_history_d1": actual_history.shift(1).fillna(0).astype(int),
        "coverage20_d1": coverage20.shift(1),
        "coverage60_d1": coverage60.shift(1),
        "liquidity_median20_d1": liquidity_median20.shift(1),
        "liquidity_q25_20_d1": liquidity_q25_20.shift(1),
        "catalog": pd.DataFrame(catalog_rows),
    }
