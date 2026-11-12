from __future__ import annotations

import pandas as pd
import pytest

from quant_harness import asof_5m_models


def _bars() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": [
                "2023-01-30T00:01:00Z",
                "2023-01-30T00:02:00Z",
                "2023-01-30T00:03:00Z",
                "2023-01-30T00:04:00Z",
                "2023-01-30T00:05:00Z",
                "2023-01-30T00:06:00Z",
            ],
            "open": [100, 101, 99, 102, 103, 104],
            "high": [101, 103, 100, 104, 105, 106],
            "low": [99, 100, 98, 101, 102, 103],
            "close": [101, 102, 99, 103, 104, 105],
            "volume": [10, 10, 10, 10, 10, 10],
        }
    )


def test_partial_daily_uses_only_completed_bars():
    snapshot = asof_5m_models.build_partial_daily(_bars(), "2023-01-30", "09:05")
    assert snapshot == {"open": 100.0, "high": 105.0, "low": 98.0, "close": 104.0}

    with pytest.raises(ValueError, match="future"):
        asof_5m_models.build_partial_daily(_bars(), "2023-01-30", "09:06")


def test_asof_step_recomputes_candidate_and_target(monkeypatch):
    calls: list[tuple[str, pd.Timestamp]] = []

    def fake_recompute(model, daily_history, partial_daily, **kwargs):
        calls.append((model, partial_daily.name))
        return {"candidate": "069500", "target_weights": {"069500": 1.0}}

    monkeypatch.setattr(asof_5m_models, "recompute_asof_signal", fake_recompute)
    result = asof_5m_models.asof_signal_step(
        "V69_ASOF_5M_V1", pd.DataFrame(), _bars(), "2023-01-30", "09:05"
    )
    assert result["candidate"] == "069500"
    assert result["target_weights"] == {"069500": 1.0}
    assert calls == [("V69_ASOF_5M_V1", pd.Timestamp("2023-01-30 09:05:00", tz="Asia/Seoul"))]


def test_current_asof_close_changes_v69_and_v79_price_scores():
    idx = pd.date_range("2022-01-01", periods=260, freq="B")
    history = pd.DataFrame({"069500": 100.0, "228790": 100.0, "KS11": 100.0}, index=idx)
    low = pd.Series({"069500": 90.0, "228790": 100.0, "KS11": 100.0}, name=idx[-1] + pd.Timedelta(days=1))
    high = low.copy()
    high["069500"] = 120.0
    low69 = asof_5m_models._current_price_features("V69_ASOF_5M_V1", history, low, core_ticker="069500", tickers=["069500", "228790"], trend_ma_days=120)
    high69 = asof_5m_models._current_price_features("V69_ASOF_5M_V1", history, high, core_ticker="069500", tickers=["069500", "228790"], trend_ma_days=120)
    low79 = asof_5m_models._current_price_features("V79_NO63_VOL_GUARD_ASOF_5M_V1", history, low, core_ticker="069500", tickers=["069500", "228790"], trend_ma_days=200)
    high79 = asof_5m_models._current_price_features("V79_NO63_VOL_GUARD_ASOF_5M_V1", history, high, core_ticker="069500", tickers=["069500", "228790"], trend_ma_days=200)
    assert float(low69["score"]["228790"]) != float(high69["score"]["228790"])
    assert float(low79["score"]["069500"]) != float(high79["score"]["069500"])
    assert float(low69["moving_average_ratio"]["069500"]) != float(high69["moving_average_ratio"]["069500"])
    assert float(low79["moving_average_ratio"]["069500"]) != float(high79["moving_average_ratio"]["069500"])


def test_v69_asof_relative_score_uses_core_when_universe_excludes_it():
    idx = pd.date_range("2022-01-01", periods=260, freq="B")
    history = pd.DataFrame({"069500": 100.0, "228790": 100.0, "KS11": 100.0}, index=idx)
    current = pd.Series({"069500": 110.0, "228790": 120.0, "KS11": 100.0}, name=idx[-1] + pd.Timedelta(days=1))
    features = asof_5m_models._current_price_features(
        "V69_ASOF_5M_V1",
        history,
        current,
        core_ticker="069500",
        tickers=["228790"],
        trend_ma_days=120,
    )
    assert features["score"]["228790"] == pytest.approx(0.1)


def test_asof_cutoff_is_monotonic_and_excludes_next_execution_minute():
    minutes = list(range(1, 12))
    frame = pd.DataFrame({
        "timestamp": [f"2023-01-30T00:{m:02d}:00Z" for m in minutes],
        "open": [100] * 11,
        "high": [100 + m for m in minutes],
        "low": [99] * 11,
        "close": [100 + m for m in minutes],
    })
    at_905 = asof_5m_models.build_partial_daily(frame, "2023-01-30", "09:05")
    at_910 = asof_5m_models.build_partial_daily(frame, "2023-01-30", "09:10")
    assert at_905["close"] == 105.0
    assert at_910["close"] == 110.0
    assert at_910["high"] == 110.0
    assert at_905["high"] < float(frame.loc[frame.timestamp.str.contains(":06:00"), "high"].iloc[0])
    assert at_910["high"] < float(frame.loc[frame.timestamp.str.contains(":11:00"), "high"].iloc[0])


def test_asof_timestamp_aligns_to_naive_daily_index():
    index = pd.date_range("2023-01-01", periods=2, freq="D")
    aware = pd.Timestamp("2023-01-02 09:05", tz="Asia/Seoul")
    aligned = asof_5m_models._align_daily_date(index, aware)
    assert aligned.tzinfo is None
    assert aligned == pd.Timestamp("2023-01-02")


def test_late_completed_five_minute_boundary_is_valid():
    ts = pd.date_range("2023-01-30 09:01", "2023-01-30 15:25", freq="min", tz="Asia/Seoul")
    frame = pd.DataFrame({"timestamp": ts.astype(str), "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0})
    assert asof_5m_models.build_partial_daily(frame, "2023-01-30", "15:25")["close"] == 100.0


def test_full_session_loader_rejects_probe_and_uses_canonical_path(tmp_path, monkeypatch):
    path = tmp_path / "data" / "toss_intraday_1m" / "069500" / "2023-01-31.csv"
    path.parent.mkdir(parents=True)
    ts = pd.date_range("2023-01-31 09:01", periods=390, freq="min", tz="Asia/Seoul")
    frame = pd.DataFrame({"timestamp": ts.astype(str), "symbol": "069500", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 1.0})
    frame.to_csv(path, index=False)
    monkeypatch.setattr(asof_5m_models, "_cache_path", lambda root, symbol, session: path)
    loaded_path, loaded = asof_5m_models._load_full_session_cache(tmp_path, "069500", "2023-01-31")
    assert loaded_path == path
    assert loaded is not None and len(loaded) == 390
    frame.iloc[:384].to_csv(path, index=False)
    _, rejected = asof_5m_models._load_full_session_cache(tmp_path, "069500", "2023-01-31")
    assert rejected is None


def test_full_session_has_78_bars_but_only_77_executable_buckets():
    ts = pd.date_range("2023-01-31 09:01", periods=390, freq="min", tz="Asia/Seoul")
    frame = pd.DataFrame({"timestamp": ts.astype(str), "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 1.0})
    from quant_harness.open_5m_execution_validation import aggregate_regular_five_minute
    grouped = aggregate_regular_five_minute(frame, "2023-01-31")
    assert len(grouped) == 78
    assert sum(pd.to_datetime(grouped["bucket"]).dt.strftime("%H:%M") <= "15:25") == 77
