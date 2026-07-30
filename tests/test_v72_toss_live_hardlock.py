from __future__ import annotations

from decimal import Decimal

import pytest

from quant_harness.v72_integration_ready.toss_openapi import (
    TossApiError,
    TossEndpointMap,
    TossOpenApiClient,
)
from quant_harness.v72_integration_ready.live_safety import (
    LiveOrderSafetyContext,
    evaluate_live_order_safety,
)


class RecordingTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def __call__(self, request, timeout: float) -> tuple[int, dict[str, str], bytes]:
        self.calls.append((request.get_method(), request.full_url))
        if request.full_url.endswith("/oauth2/token"):
            return 200, {}, b'{"access_token":"test-token","expires_in":300}'
        return 200, {}, b'{"orderId":"BROKER-1","status":"ACCEPTED"}'


def _client(transport: RecordingTransport) -> TossOpenApiClient:
    return TossOpenApiClient(
        client_id="test-client",
        client_secret="test-secret",
        account_id="TEST-ACCOUNT",
        base_url="https://broker.invalid",
        endpoint_map=TossEndpointMap(
            order_create_path="/orders",
            order_cancel_path="/orders/{order_id}",
        ),
        transport=transport,
    )


def test_environment_flag_cannot_enable_live_order(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TOSS_ALLOW_LIVE_ORDERS", "true")
    transport = RecordingTransport()
    client = _client(transport)

    with pytest.raises(TossApiError, match="structurally disabled"):
        client.create_order(
            client_order_id="LIVE-ENV-1",
            symbol="069500",
            side="BUY",
            quantity=Decimal("1"),
            dry_run=False,
        )

    assert transport.calls == []


def test_direct_non_dry_run_call_is_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TOSS_ALLOW_LIVE_ORDERS", raising=False)
    transport = RecordingTransport()
    client = _client(transport)

    with pytest.raises(TossApiError, match="structurally disabled"):
        client.create_order(
            client_order_id="LIVE-DIRECT-1",
            symbol="069500",
            side="BUY",
            quantity=Decimal("1"),
            dry_run=False,
        )

    assert transport.calls == []


def test_low_level_mutation_request_cannot_bypass_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TOSS_ALLOW_LIVE_ORDERS", "true")
    transport = RecordingTransport()
    client = _client(transport)

    with pytest.raises(TossApiError, match="structurally disabled"):
        client._request(
            "POST",
            "/orders",
            body={"symbol": "069500"},
            account_required=True,
            authenticated=False,
        )

    assert transport.calls == []


def test_constructor_rejects_order_path_as_token_endpoint() -> None:
    transport = RecordingTransport()

    with pytest.raises(TossApiError, match="token path is fixed"):
        TossOpenApiClient(
            base_url="https://broker.invalid",
            endpoint_map=TossEndpointMap(token_path="/orders"),
            transport=transport,
        )

    assert transport.calls == []


def test_token_post_uses_only_fixed_oauth_endpoint() -> None:
    transport = RecordingTransport()
    client = _client(transport)

    assert client._token() == "test-token"
    assert transport.calls == [("POST", "https://broker.invalid/oauth2/token")]
    assert not hasattr(client, "transport")


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_all_non_get_low_level_requests_are_blocked_before_transport(method: str) -> None:
    transport = RecordingTransport()
    client = _client(transport)

    with pytest.raises(TossApiError, match="structurally disabled"):
        client._request(method, "/orders", body={"symbol": "069500"}, authenticated=False)

    assert transport.calls == []


def test_credentials_do_not_enable_live_order(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TOSS_ALLOW_LIVE_ORDERS", "true")
    monkeypatch.setenv("TOSS_CLIENT_ID", "env-client")
    monkeypatch.setenv("TOSS_CLIENT_SECRET", "env-secret")
    monkeypatch.setenv("TOSS_ACCOUNT_ID", "ENV-ACCOUNT")
    transport = RecordingTransport()
    client = TossOpenApiClient(
        base_url="https://broker.invalid",
        endpoint_map=TossEndpointMap(order_create_path="/orders"),
        transport=transport,
    )

    with pytest.raises(TossApiError, match="structurally disabled"):
        client.create_order(
            client_order_id="LIVE-CREDENTIAL-1",
            symbol="069500",
            side="BUY",
            quantity=Decimal("1"),
            dry_run=False,
        )

    assert transport.calls == []


def test_paper_order_remains_local_and_does_not_call_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TOSS_ALLOW_LIVE_ORDERS", "true")
    transport = RecordingTransport()
    client = _client(transport)

    order = client.create_order(
        client_order_id="PAPER-1",
        symbol="069500",
        side="BUY",
        quantity=Decimal("1"),
        reason="paper regression",
        dry_run=True,
    )

    assert order.status == "NEW"
    assert order.raw == {"dry_run": True}
    assert transport.calls == []


def test_live_cancel_is_blocked_before_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TOSS_ALLOW_LIVE_ORDERS", "true")
    transport = RecordingTransport()
    client = _client(transport)

    with pytest.raises(TossApiError, match="structurally disabled"):
        client.cancel_order("BROKER-1")

    assert transport.calls == []


def test_all_runtime_gates_cannot_override_disabled_build_capability() -> None:
    decision = evaluate_live_order_safety(
        LiveOrderSafetyContext(
            broker_contract_verified=True,
            account_allowlisted=True,
            order_notional_within_limit=True,
            order_count_within_limit=True,
            reconciliation_normal=True,
            kill_switch_clear=True,
            explicit_approval=True,
            idempotency_key_present=True,
            paper_live_environment_separated=True,
        )
    )

    assert decision.allowed is False
    assert "LIVE_BUILD_CAPABILITY_DISABLED" in decision.blockers
    assert "CURRENT_RELEASE_LIVE_AUTHORITY_DISABLED" in decision.blockers
