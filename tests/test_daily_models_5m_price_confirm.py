from __future__ import annotations

import pandas as pd

from quant_harness import daily_models_5m_price_confirm as overlay


def _session_frame(closes: list[float]) -> pd.DataFrame:
    # Toss timestamps are candle end labels; 09:01..09:06 KST are
    # represented by 00:01..00:06 UTC.
    closes = list(closes) + [closes[-1]]
    return pd.DataFrame(
        {
            "timestamp": [f"2023-01-30T00:{i:02d}:00Z" for i in range(1, 7)] + ["2023-01-30T06:30:00Z"],
            "symbol": ["069500"] * 7,
            "open": [99, 99, 99, 99, 99, 101, closes[-1]],
            "high": closes,
            "low": [98] * 7,
            "close": closes,
            "volume": [1, 1, 1, 1, 1, 999999, 1],
        }
    )


def test_price_confirmation_uses_next_minute_open(monkeypatch):
    frame = _session_frame([100, 100, 100, 100, 100, 101])
    monkeypatch.setattr(overlay, "_load_session", lambda *args: frame)
    result = overlay._first_open_and_confirmation(
        None, "069500", "2023-01-30", 100.0, 99.0
    )
    assert result["status"] == "CONFIRMED"
    assert result["execution_time"].endswith("09:06:00+09:00")
    assert result["execution_open"] == 101.0


def test_price_confirmation_fails_closed_without_signal(monkeypatch):
    frame = _session_frame([98, 98, 98, 98, 98, 98])
    monkeypatch.setattr(overlay, "_load_session", lambda *args: frame)
    result = overlay._first_open_and_confirmation(
        None, "069500", "2023-01-30", 100.0, 99.0
    )
    assert result["status"] == "NO_INTRADAY_CONFIRMATION"


def test_minute_volume_is_not_part_of_price_confirmation(monkeypatch):
    frame = _session_frame([100, 100, 100, 100, 100, 101])
    monkeypatch.setattr(overlay, "_load_session", lambda *args: frame)
    first = overlay._first_open_and_confirmation(None, "069500", "2023-01-30", 100.0, 99.0)
    frame.loc[:, "volume"] = 0
    second = overlay._first_open_and_confirmation(None, "069500", "2023-01-30", 100.0, 99.0)
    assert first["status"] == second["status"] == "CONFIRMED"
    assert first["execution_open"] == second["execution_open"]
