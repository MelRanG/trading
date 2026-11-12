from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from datetime import datetime
from zoneinfo import ZoneInfo

from quant_harness.active_market_data_update import (
    IncrementalUpdateError,
    _latest_completed_toss_trading_day,
    _merge_symbol,
    run_toss_incremental_update,
    run_toss_market_indicator_ks11_update,
)


def _row(date: str, close: float) -> dict[str, object]:
    return {
        "timestamp": f"{date}T00:00:00.000+09:00", "ticker": "091170", "asset_type": "etf",
        "open": close - 10, "high": close + 10, "low": close - 20, "close": close,
        "volume": 100, "currency": "KRW", "source": "toss_openapi_1d_adjusted",
    }


def test_incremental_merge_appends_only_after_last_date_and_preserves_order():
    existing = pd.DataFrame([_row("2026-07-03", 100), _row("2026-07-02", 90)])
    incoming = pd.DataFrame([_row("2026-07-04", 110)])
    merged, added = _merge_symbol(existing, incoming, "091170")
    assert added == 1
    assert merged.timestamp.iloc[0].startswith("2026-07-04")
    assert merged.timestamp.iloc[1].startswith("2026-07-03")


def test_overlap_price_conflict_fails_closed_without_mutating_input():
    existing = pd.DataFrame([_row("2026-07-03", 100)])
    incoming = pd.DataFrame([_row("2026-07-03", 101)])
    with pytest.raises(IncrementalUpdateError, match="overlap price conflict"):
        _merge_symbol(existing, incoming, "091170")
    assert existing.iloc[0]["close"] == 100


def test_multiple_incremental_rows_preserve_existing_descending_order():
    existing = pd.DataFrame([_row("2026-07-03", 100), _row("2026-07-02", 90)])
    incoming = pd.DataFrame([_row("2026-07-08", 150), _row("2026-07-06", 130), _row("2026-07-07", 140)])
    merged, added = _merge_symbol(existing, incoming, "091170")
    assert added == 3
    assert merged["timestamp"].str[:10].tolist() == ["2026-07-08", "2026-07-07", "2026-07-06", "2026-07-03", "2026-07-02"]


def test_official_calendar_prevents_holiday_from_becoming_latest_completed_day():
    class FakeClient:
        def get_market_calendar(self, *, market, start_date, end_date):
            assert market == "KR"
            return [
                {"date": "2026-10-02", "is_open": True, "regular_market_end": "15:30:00"},
                {"date": "2026-10-04", "is_open": False, "regular_market_end": None},
                {"date": "2026-10-06", "is_open": True, "regular_market_end": "15:30:00"},
            ]

    now = datetime(2026, 10, 4, 12, 0, tzinfo=ZoneInfo("Asia/Seoul"))
    assert _latest_completed_toss_trading_day(FakeClient(), now=now) == "2026-10-02"


def test_official_calendar_does_not_mark_intraday_session_complete():
    class FakeClient:
        def get_market_calendar(self, *, market, start_date, end_date):
            return [
                {"date": "2026-10-05", "is_open": True, "regular_market_end": "2026-10-05T15:30:00.000+09:00"},
                {"date": "2026-10-02", "is_open": True, "regular_market_end": "15:30:00"},
            ]

    now = datetime(2026, 10, 5, 11, 0, tzinfo=ZoneInfo("Asia/Seoul"))
    assert _latest_completed_toss_trading_day(FakeClient(), now=now) == "2026-10-02"


def test_official_calendar_marks_regular_day_complete_only_after_close_grace():
    class FakeClient:
        def get_market_calendar(self, *, market, start_date, end_date):
            return [
                {"date": "2026-10-05", "is_open": True, "regular_market_end": "2026-10-05T15:30:00.000+09:00"},
                {"date": "2026-10-02", "is_open": True, "regular_market_end": "15:30:00"},
            ]

    now = datetime(2026, 10, 5, 15, 36, tzinfo=ZoneInfo("Asia/Seoul"))
    assert _latest_completed_toss_trading_day(FakeClient(), now=now) == "2026-10-05"


def test_market_indicator_ohlc_overlap_conflict_fails_closed_without_append(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    path = data / "all_prices_long_v62_9_expanded.csv"
    columns = ["date", "ticker", "yf_symbol", "name", "group", "sector", "asset_type", "source", "open", "high", "low", "close", "adj_close", "volume", "value_approx", "change", "UpDown", "Comp", "Amount", "MarCap", "dividends", "stock_splits", "Capital Gains"]
    rows = [{"date": "2026-07-03", "ticker": "KS11", "name": "KOSPI", "sector": "broad_equity", "asset_type": "index", "open": 100, "high": 110, "low": 90, "close": 105, "adj_close": 105, "volume": 1000, "source": "WEB_VERIFIED"}]
    pd.DataFrame(rows).reindex(columns=columns).to_csv(path, index=False)

    class FakeClient:
        def get_market_indicator_prices(self, symbols):
            return [{"symbol": "KOSPI", "timestamp": None, "last_price": "105"}]

        def get_market_indicator_candles_page(self, symbol, *, interval, count, before):
            return ([{"timestamp": "2026-07-03T00:00:00+09:00", "symbol": "KOSPI", "open": "101", "high": "110", "low": "90", "close": "105", "volume": "1001"}], None)

    monkeypatch.setattr("quant_harness.active_market_data_update.TossOpenApiClient", FakeClient)
    result = run_toss_market_indicator_ks11_update(tmp_path, as_of="2026-07-04")
    assert result.succeeded == 0
    assert result.rows_added == 0
    assert "overlap open conflict" in result.failed[0]["reason"]
    assert len(pd.read_csv(path)) == 1


def test_market_indicator_ignores_volume_and_appends_price_only_ks11_row(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    path = data / "all_prices_long_v62_9_expanded.csv"
    columns = ["date", "ticker", "yf_symbol", "name", "group", "sector", "asset_type", "source", "open", "high", "low", "close", "adj_close", "volume", "value_approx", "change", "UpDown", "Comp", "Amount", "MarCap", "dividends", "stock_splits", "Capital Gains"]
    rows = [{"date": "2026-07-03", "ticker": "KS11", "name": "KOSPI", "sector": "broad_equity", "asset_type": "index", "open": 100, "high": 110, "low": 90, "close": 105, "adj_close": 105, "volume": 1000, "source": "WEB_VERIFIED"}]
    pd.DataFrame(rows).reindex(columns=columns).to_csv(path, index=False)

    class FakeClient:
        def get_market_indicator_prices(self, symbols):
            return [{"symbol": "KOSPI", "timestamp": None, "last_price": "105"}]

        def get_market_indicator_candles_page(self, symbol, *, interval, count, before):
            return ([
                {"timestamp": "2026-07-04T00:00:00+09:00", "symbol": "KOSPI", "open": "106", "high": "111", "low": "101", "close": "108", "volume": "2000000"},
                {"timestamp": "2026-07-03T00:00:00+09:00", "symbol": "KOSPI", "open": "100", "high": "110", "low": "90", "close": "105", "volume": "1000000"},
            ], None)

    monkeypatch.setattr("quant_harness.active_market_data_update.TossOpenApiClient", FakeClient)
    result = run_toss_market_indicator_ks11_update(tmp_path, as_of="2026-07-04")
    assert result.succeeded == 1 and result.rows_added == 1
    out = pd.read_csv(path)
    assert out.iloc[-1]["date"] == "2026-07-04"
    assert pd.isna(out.iloc[-1]["volume"])
    assert out.iloc[-1]["ticker"] == "KS11"
    assert out.iloc[-1]["close"] == 108


@pytest.mark.parametrize(("reference_close", "expected_success"), [(100.0, 1), (50.0, 0)])
def test_toss_etf_update_runs_v87_revision_gate_before_write(tmp_path, monkeypatch, reference_close, expected_success):
    daily = tmp_path / "data" / "toss_v19c_daily"
    canonical = tmp_path / "data" / "canonical"
    config_dir = tmp_path / "config"
    daily.mkdir(parents=True)
    canonical.mkdir(parents=True)
    config_dir.mkdir(parents=True)
    source_config = Path(__file__).resolve().parents[1] / "config" / "v87_actual_data_ingestion.yaml"
    (config_dir / source_config.name).write_text(source_config.read_text(encoding="utf-8"), encoding="utf-8")
    pd.DataFrame([{"ticker": "091170"}]).to_csv(daily / "universe.csv", index=False)
    existing = pd.DataFrame([_row("2026-07-03", 100)])
    path = daily / "091170_1d.csv"
    existing.to_csv(path, index=False)
    old_bytes = path.read_bytes()
    pd.DataFrame([{
        "date": "2026-07-03", "ticker": "091170", "open": 90,
        "high": 110, "low": 80, "close": reference_close, "volume": 1000,
        "value_approx": reference_close * 1000,
    }]).to_csv(canonical / "v84_market_bars.csv", index=False)

    class FakeClient:
        def get_daily_candles(self, symbol, *, start_date, end_date):
            return [{"date": "2026-07-06", "ticker": symbol, "open": 101,
                     "high": 111, "low": 91, "close": 105, "volume": 1000}]

        def health_check(self):
            return {"status": "OK"}

    monkeypatch.setattr("quant_harness.active_market_data_update.TossOpenApiClient", FakeClient)
    result = run_toss_incremental_update(tmp_path, as_of="2026-07-06", write_output=True)

    assert result.succeeded == expected_success
    if expected_success:
        assert result.rows_added == 1
        assert len(pd.read_csv(path)) == 2
    else:
        assert result.rows_added == 0
        assert "V87 revision gate failed" in result.failed[0]["reason"]
        assert path.read_bytes() == old_bytes
