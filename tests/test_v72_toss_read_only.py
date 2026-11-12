from __future__ import annotations

from datetime import datetime, timezone

import pytest

from quant_harness.v72_integration_ready.toss_openapi import TossApiError, TossOpenApiClient
from quant_harness.v72_integration_ready.toss_read_only import MockReadOnlySchema, TossReadOnlyAdapter
from quant_harness.toss_snapshot_runtime import canonical_order_status


class MockTransport:
    """MOCK fixture transport; its payloads are not claimed to be Toss responses."""
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, request, timeout):
        self.calls.append((request.get_method(), request.full_url, dict(request.header_items())))
        if request.get_method() == "POST":
            return 200, {}, b'{"access_token":"MOCK-TOKEN-SECRET","expires_in":300}'
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


def _adapter(responses):
    transport = MockTransport(responses)
    client = TossOpenApiClient(client_id="mock-id", client_secret="mock-secret", account_id="12345678", base_url="https://mock.invalid", transport=transport)
    return TossReadOnlyAdapter(client, mock_schema=MockReadOnlySchema(buying_power_amount="cashBuyingPower", holdings_list="items", orders_list="orders", next_cursor="nextCursor", cursor_query="cursor")), transport


def test_read_only_surface_exposes_no_mutations_and_all_business_calls_are_get():
    adapter, transport = _adapter([
        (200, {}, b'{"result":[]}'), (200, {}, b'{"result":{"cashBuyingPower":"1"}}'),
            (200, {}, b'{"result":{"items":[]}}'), (200, {}, b'{"result":{"orders":[]}}'),
    ])
    assert not hasattr(adapter, "create_order")
    assert not hasattr(adapter, "cancel_order")
    adapter.get_account_basics(); adapter.get_buying_power(currency="KRW"); adapter.get_holdings(); adapter.list_orders(status="OPEN")
    assert [method for method, _, _ in transport.calls] == ["POST", "GET", "GET", "GET", "GET"]
    assert all(method == "GET" for method, _, _ in transport.calls[1:])
    account_headers = dict(transport.calls[1][2])
    assert "X-tossinvest-account" not in {key.lower() for key in account_headers}


def test_mock_schema_is_fail_closed_and_unknown_order_status_is_preserved():
    adapter, _ = _adapter([(200, {}, b'{"result":{"orders":[{"status":"MYSTERY"}]}}')])
    assert adapter.list_orders(status="OPEN") == [{"status": "MYSTERY"}]
    malformed, _ = _adapter([(200, {}, b'{"result":{"orders":"not-a-list"}}')])
    with pytest.raises(TossApiError, match="configured list"):
        malformed.list_orders(status="OPEN")


def test_official_order_statuses_map_to_existing_contract_and_unregistered_stays_unknown():
    assert canonical_order_status("PENDING") == "ACCEPTED"
    assert canonical_order_status("PENDING_CANCEL") == "ACCEPTED"
    assert canonical_order_status("PARTIAL_FILLED") == "PARTIALLY_FILLED"
    assert canonical_order_status("CANCELED") == "CANCELED"
    assert canonical_order_status("CANCELLED") == "CANCELED"
    assert canonical_order_status("REPLACED") == "UNKNOWN"
    assert canonical_order_status("NOT_A_TOSS_STATUS") == "UNKNOWN"


def test_mock_pagination_combines_pages_and_snapshot_masks_account():
    adapter, transport = _adapter([
        (200, {}, b'{"result":{"orders":[{"id":"1"}],"nextCursor":"next"}}'),
        (200, {}, b'{"result":{"orders":[{"id":"2"}]}}'),
        (200, {}, b'{"result":{"cashBuyingPower":"1234"}}'),
        (200, {}, b'{"result":{"items":[{"symbol":"005930"}]}}'),
    ])
    assert adapter.list_orders(status="CLOSED", limit=10) == [{"id":"1"}, {"id":"2"}]
    assert "cursor=next" in transport.calls[-1][1]
    snapshot = adapter.canonical_snapshot(observed_at=datetime.now(timezone.utc), timezone_name="Asia/Seoul")
    assert snapshot.account_id_masked == "****5678"
    assert str(snapshot.cash_or_buying_power) == "1234"
    assert snapshot.source_status == "MOCK_SCHEMA_ONLY"


def test_timeout_rate_limit_and_unconfirmed_executions_fail_closed(monkeypatch):
    adapter, _ = _adapter([TimeoutError("network timeout")])
    with pytest.raises(TossApiError, match="UNKNOWN"):
        adapter.get_account_basics()
    rate_limited, transport = _adapter([(429, {"Retry-After":"0"}, b'{"error":{"code":"rate-limit-exceeded"}}'), (200, {}, b'{"result":[]}')])
    monkeypatch.setattr("quant_harness.v72_integration_ready.toss_openapi.time.sleep", lambda _: None)
    rate_limited.get_account_basics()
    assert len(transport.calls) == 3  # one OAuth POST, then rate-limit retry
    with pytest.raises(TossApiError, match="not officially confirmed"):
        rate_limited.list_executions()


def test_transient_get_transport_failure_is_bounded_and_retried(monkeypatch):
    adapter, transport = _adapter([
        TossApiError("Toss API connection failed: temporary"),
        (200, {}, b'{"result":[]}'),
    ])
    monkeypatch.setattr("quant_harness.v72_integration_ready.toss_openapi.time.sleep", lambda _: None)
    assert adapter.get_account_basics()["raw"] == []
    assert len(transport.calls) == 3  # OAuth POST, failed GET, bounded GET retry


def test_market_indicator_catalog_and_daily_candles_are_get_only():
    transport = MockTransport([
        (200, {}, b'{"result":[{"symbol":"KOSPI","timestamp":null,"lastPrice":"6595.45"}]}'),
        (200, {}, b'{"result":{"candles":[{"timestamp":"2026-07-31T00:00:00.000+09:00","openPrice":"5657.79","highPrice":"6630.77","lowPrice":"5629.76","closePrice":"6595.45","volume":"434445000"}],"nextBefore":"2026-07-30T00:00:00.000+09:00"}}'),
    ])
    client = TossOpenApiClient(client_id="mock-id", client_secret="mock-secret", base_url="https://mock.invalid", transport=transport)
    prices = client.get_market_indicator_prices(["KOSPI", "KOSDAQ"])
    candles, next_before = client.get_market_indicator_candles_page("KOSPI", interval="1d", count=200, before="2026-07-31T23:59:59+09:00")
    assert prices[0]["symbol"] == "KOSPI"
    assert candles[0]["close"] == "6595.45"
    assert next_before.startswith("2026-07-30")
    assert [method for method, _, _ in transport.calls] == ["POST", "GET", "GET"]


def test_official_market_calendar_snapshot_schema_is_normalized_get_only():
    transport = MockTransport([
        (200, {}, b'{"result":{"previousBusinessDay":{"date":"2026-10-02","integrated":{"regularMarket":{"endTime":"15:30:00"}}},"today":{"date":"2026-10-04"},"nextBusinessDay":{"date":"2026-10-06","integrated":{"regularMarket":{"endTime":"15:30:00"}}}}}'),
    ])
    client = TossOpenApiClient(client_id="mock-id", client_secret="mock-secret", base_url="https://mock.invalid", transport=transport)
    rows = client.get_market_calendar(market="KR", start_date="2026-10-01", end_date="2026-10-06")
    assert [(row["date"], row["is_open"]) for row in rows] == [
        ("2026-10-02", True), ("2026-10-04", False), ("2026-10-06", True),
    ]
    assert rows[0]["regular_market_end"] == "15:30:00"
    assert [method for method, _, _ in transport.calls] == ["POST", "GET"]


def test_errors_and_transport_records_do_not_expose_token_or_full_account(capsys):
    adapter, transport = _adapter([(400, {}, b'{"error":{"message":"MOCK-TOKEN-SECRET 12345678"}}')])
    with pytest.raises(TossApiError):
        adapter.get_account_basics()
    captured = capsys.readouterr().out + capsys.readouterr().err
    assert "MOCK-TOKEN-SECRET" not in captured and "12345678" not in captured
    assert all("MOCK-TOKEN-SECRET" not in url for _, url, _ in transport.calls)
