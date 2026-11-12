from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from quant_harness import asof_5m_collection as collector
from quant_harness.three_model_backtest import _cache_path
from quant_harness.v72_integration_ready.toss_openapi import TossApiError


def _frame(session: str = "2023-01-30", bars: int = 390) -> pd.DataFrame:
    ts = pd.date_range(f"{session} 09:01", periods=bars, freq="min", tz="Asia/Seoul")
    return pd.DataFrame({
        "timestamp": ts.astype(str), "symbol": "069500", "open": 100.0,
        "high": 101.0, "low": 99.0, "close": 100.0, "volume": 1.0,
    })


def test_complete_cache_is_valid_and_partial_is_not():
    complete = collector.validate_complete_session(_frame(), "2023-01-30")
    partial = collector.validate_complete_session(_frame(bars=20), "2023-01-30")
    assert complete["ok"] is True
    assert complete["five_minute_bars"] == 78
    assert partial["ok"] is False


def test_resume_skips_complete_cache_and_reprocesses_partial(tmp_path, monkeypatch):
    required = [("069500", "2023-01-30"), ("069500", "2023-01-31")]
    monkeypatch.setattr(collector, "required_symbol_dates", lambda root: required)
    complete_path = tmp_path / _cache_path(tmp_path, *required[0]).relative_to(tmp_path)
    complete_path.parent.mkdir(parents=True, exist_ok=True)
    _frame().to_csv(complete_path, index=False)
    called: list[tuple[str, str]] = []

    def fake_fetch(client, root, symbol, session):
        called.append((symbol, session))
        frame = _frame(session)
        path = root / _cache_path(root, symbol, session).relative_to(root)
        collector._atomic_csv(path, frame)
        return frame, {"api_pages": 1, "bar_count": 390, "validation": {"ok": True}}

    monkeypatch.setattr(collector, "_fetch_atomic", fake_fetch)
    result = collector.collect(tmp_path, resume=True)
    assert called == [("069500", "2023-01-31")]
    assert result["sessions"]["069500:2023-01-30"]["status"] == "COMPLETE"
    assert result["sessions"]["069500:2023-01-31"]["status"] == "COMPLETE"


def test_manifest_persisted_after_session_and_interrupt(tmp_path, monkeypatch):
    required = [("069500", "2023-01-30")]
    monkeypatch.setattr(collector, "required_symbol_dates", lambda root: required)
    persisted: list[dict] = []
    original = collector._atomic_json
    monkeypatch.setattr(collector, "_atomic_json", lambda path, payload: (persisted.append(json.loads(json.dumps(payload))), original(path, payload))[1])

    def fake_fetch(client, root, symbol, session):
        frame = _frame(session)
        collector._atomic_csv(root / _cache_path(root, symbol, session).relative_to(root), frame)
        return frame, {"api_pages": 1, "bar_count": 390, "validation": {"ok": True}}

    monkeypatch.setattr(collector, "_fetch_atomic", fake_fetch)
    result = collector.collect(tmp_path)
    assert any(p["sessions"]["069500:2023-01-30"]["status"] == "COMPLETE" for p in persisted)
    assert (tmp_path / collector.MANIFEST).is_file()
    assert result["status"] == "MINUTE_DATA_COLLECTION_COMPLETE"

    complete_path = tmp_path / _cache_path(tmp_path, *required[0]).relative_to(tmp_path)
    complete_path.unlink()

    def interrupt(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(collector, "_fetch_atomic", interrupt)
    result = collector.collect(tmp_path, resume=True)
    assert result["status"] == "MINUTE_DATA_COLLECTION_IN_PROGRESS"
    assert result["sessions"]["069500:2023-01-30"]["status"] == "PARTIAL"


def test_atomic_csv_leaves_no_temporary_file(tmp_path):
    path = tmp_path / "nested" / "session.csv"
    collector._atomic_csv(path, _frame())
    assert path.is_file()
    assert not list(path.parent.glob("*.tmp"))


def test_pagination_cursor_must_progress(tmp_path):
    class Client:
        def get_intraday_candles_page(self, *args, **kwargs):
            return ([{"timestamp": "2023-01-30T00:01:00+00:00", "open": 1, "high": 1, "low": 1, "close": 1}], "same")

    with pytest.raises(TossApiError, match="pagination cursor did not progress"):
        collector._fetch_atomic(Client(), tmp_path, "069500", "2023-01-30")
