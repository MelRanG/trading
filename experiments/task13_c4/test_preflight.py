"""Synthetic tests only, including reuse parity for the frozen H252 endpoint rule."""
import numpy as np
import pandas as pd
import pytest

from preflight import controls_at, gate
from run import open_to_open


def test_horizon_uses_calendar_distance_and_fails_on_missing_intermediate():
    days = pd.bdate_range("2020-01-01",periods=254)
    px = pd.Series(np.linspace(100, 200, len(days)), index=days)
    assert open_to_open(px,days[1],days[253]) == pytest.approx(px.iloc[253]/px.iloc[1]-1)
    px.iloc[70] = np.nan
    with pytest.raises(ValueError):
        open_to_open(px,days[1],days[253])
    with pytest.raises(ValueError):
        open_to_open(px,days[1],days[252])


def test_prefiling_controls_ignore_stock_and_market_future():
    rng = np.random.default_rng(44)
    days = pd.bdate_range("2020-01-01",periods=180)
    market = pd.Series(100*np.exp(np.cumsum(rng.normal(0,.02,len(days)))),index=days)
    stock = market*pd.Series(np.exp(np.cumsum(rng.normal(0,.02,len(days)))),index=days)
    anchor = days[150]
    before = controls_at(stock,market,anchor)
    assert len(before)==5
    assert controls_at(stock.where(stock.index<=anchor, 42),market.where(market.index<=anchor, 17),anchor)==before
    stock.iloc[149] = np.nan
    assert controls_at(stock,market,anchor) is None


def test_minimum_cohorts_and_distinct_issuers():
    rows = [{"CIK":str(i%40),"filed_year":2019+i//34} for i in range(102)]
    assert gate(rows)
    assert not gate([{**r,"CIK":"same"} for r in rows])
    assert not gate([{**r,"filed_year":2019} for r in rows])
