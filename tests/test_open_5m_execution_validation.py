from __future__ import annotations

import pandas as pd
import pytest

from quant_harness.open_5m_execution_validation import aggregate_regular_five_minute, next_one_minute_open


def _bars() -> pd.DataFrame:
    rows = []
    for minute in range(1, 7):
        rows.append({"timestamp": f"2026-07-31T09:{minute:02d}:00+09:00", "open": 100 + minute, "high": 101 + minute, "low": 99 + minute, "close": 100 + minute, "volume": 1})
    return pd.DataFrame(rows)


def test_first_five_minutes_complete_before_next_minute_open() -> None:
    bars = _bars()
    grouped = aggregate_regular_five_minute(bars, "2026-07-31")
    assert grouped.iloc[0]["bars"] == 5
    assert next_one_minute_open(bars, "2026-07-31") == 106


def test_missing_first_minute_data_fails_closed() -> None:
    with pytest.raises(ValueError, match="first five-minute bar is incomplete"):
        next_one_minute_open(_bars().iloc[1:], "2026-07-31")


def test_future_minute_is_not_used_as_execution_reference() -> None:
    bars = _bars()
    bars.loc[len(bars)] = {"timestamp": "2026-07-31T09:07:00+09:00", "open": 9999, "high": 9999, "low": 9999, "close": 9999, "volume": 1}
    assert next_one_minute_open(bars, "2026-07-31") == 106
