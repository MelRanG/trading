from __future__ import annotations

import pandas as pd
import pytest

from quant_harness.daily_model_calendar_analysis import _period_metrics, _price_reference_nav, _tail_metrics


def test_period_metrics_uses_first_and_last_valid_nav_for_period_return():
    nav = pd.DataFrame({
        "date": pd.to_datetime(["2026-01-02", "2026-01-05", "2026-01-06"]),
        "nav_krw": [100.0, 90.0, 110.0],
        "cash_krw": [10.0, 10.0, 10.0],
        "positions_value_krw": [90.0, 80.0, 100.0],
    })
    trades = pd.DataFrame(columns=["date", "paper_order_id", "fill_quantity", "fill_price"])
    metrics = _period_metrics(nav, trades, pd.Timestamp("2026-01-02"), pd.Timestamp("2026-01-06"))
    assert metrics["return"] == pytest.approx(0.10)
    assert metrics["mdd"] == pytest.approx(-0.10)
    assert metrics["mean_cash_weight"] == pytest.approx((0.1 + 10 / 90 + 10 / 110) / 3)


def test_tail_metrics_reports_positive_historical_loss_measures():
    nav = pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=101, freq="B"),
        "nav_krw": [100.0 * (1.0 + i * 0.001) for i in range(100)] + [80.0],
        "cash_krw": 0.0,
        "positions_value_krw": 0.0,
    })
    metrics = _tail_metrics(nav)
    assert metrics["var_95"] >= 0
    assert metrics["expected_shortfall_95"] >= metrics["var_95"]
    assert metrics["var_99"] >= 0


def test_reference_nav_rejects_missing_benchmark_session_instead_of_forward_filling():
    dates = pd.DatetimeIndex(["2026-01-02", "2026-01-05", "2026-01-06"])
    prices = pd.Series([100.0, 102.0], index=dates[[0, 2]])
    with pytest.raises(ValueError, match="missing benchmark prices"):
        _price_reference_nav(prices, dates)
