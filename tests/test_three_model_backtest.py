from __future__ import annotations

from pathlib import Path

from quant_harness.three_model_backtest import fetch_intraday_session


class FakeClient:
    def __init__(self) -> None:
        self.calls = 0

    def get_intraday_candles_page(self, symbol: str, *, before: str, interval: str = "1m", count: int = 200):
        self.calls += 1
        start = 200 if self.calls == 1 else 0
        total = 200 if self.calls == 1 else 190
        rows = []
        for i in range(total):
            minute = start + i
            hour, rem = divmod(minute, 60)
            rows.append({
                "timestamp": f"2026-07-31T{9 + hour:02d}:{rem:02d}:00+09:00",
                "symbol": symbol,
                "open": 100,
                "high": 101,
                "low": 99,
                "close": 100,
                "volume": 1,
            })
        return rows, "2026-07-31T12:10:00+09:00" if self.calls == 1 else None


def test_intraday_pagination_and_cache_reuse(tmp_path: Path) -> None:
    client = FakeClient()
    first = fetch_intraday_session(client, tmp_path, "069500", "2026-07-31")
    assert first["bars"] == 390
    assert first["cache_hit"] is False
    calls = client.calls
    second = fetch_intraday_session(client, tmp_path, "069500", "2026-07-31")
    assert second["bars"] == 390
    assert second["cache_hit"] is True
    assert client.calls == calls


def test_intraday_cache_is_session_scoped(tmp_path: Path) -> None:
    client = FakeClient()
    fetch_intraday_session(client, tmp_path, "069500", "2026-07-31")
    other = fetch_intraday_session(client, tmp_path, "395160", "2026-07-31")
    assert other["cache_hit"] is False
    assert (tmp_path / "data/toss_intraday_1m/395160/2026-07-31.csv").is_file()
