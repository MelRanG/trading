"""Safe MOCK or conditional REAL_READ_ONLY Toss account snapshot runner."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import os
from urllib.parse import parse_qsl, urlparse
import uuid
from typing import Any, Callable

from quant_harness.toss_runtime_store import digest, fingerprint, initialize, save_snapshot
from quant_harness.v72_integration_ready.live_safety import (
    CURRENT_RELEASE_LIVE_AUTHORITY,
    LIVE_BUILD_CAPABILITY,
)
from quant_harness.v72_integration_ready.toss_openapi import TossApiError, TossOpenApiClient
from quant_harness.v72_integration_ready.toss_read_only import MockReadOnlySchema, TossReadOnlyAdapter


REQUIRED_REAL_ENV = (
    "TOSS_CLIENT_ID",
    "TOSS_CLIENT_SECRET",
)
OFFICIAL_TOSS_API_BASE_URL = "https://openapi.tossinvest.com"
DEFAULT_READ_ONLY_TIMEOUT_SECONDS = 15.0
KNOWN_ORDER_STATUSES = {
    "NEW", "ACCEPTED", "PARTIALLY_FILLED", "FILLED", "CANCELED", "REJECTED",
    "OPEN", "CLOSED", "PENDING", "PENDING_CANCEL", "PENDING_REPLACE", "PARTIAL_FILLED",
    "CANCEL_REJECTED", "REPLACE_REJECTED", "REPLACED",
}

# The stored order status remains the broker's exact enum.  This map is used
# only for the internal safety decision, and follows the existing v72 contract
# (ACCEPTED/CANCELED spellings) where it has no separate canonical state.
OFFICIAL_ORDER_STATUS_TO_CANONICAL = {
    "PENDING": "ACCEPTED",
    "PENDING_CANCEL": "ACCEPTED",
    "PENDING_REPLACE": "ACCEPTED",
    "PARTIAL_FILLED": "PARTIALLY_FILLED",
    "PARTIALLY_FILLED": "PARTIALLY_FILLED",
    "FILLED": "FILLED",
    "CANCELED": "CANCELED",
    "CANCELLED": "CANCELED",  # unambiguous spelling alias only
    "REJECTED": "REJECTED",
    "NEW": "NEW",
    "OPEN": "OPEN",
    "CLOSED": "CLOSED",
}


def canonical_order_status(value: Any) -> str:
    """Return the existing internal status or UNKNOWN, fail-closed."""
    text = str(value or "").strip().upper().replace("-", "_").replace(" ", "_")
    return OFFICIAL_ORDER_STATUS_TO_CANONICAL.get(text, "UNKNOWN")


def _receipt_endpoint(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path
    if path.startswith("/api/v1/orders/"):
        return "/api/v1/orders/{orderId}"
    allowed_query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key in {"currency", "status", "limit", "cursor"}
    ]
    if not allowed_query:
        return path
    query = "&".join(f"{key}={value}" for key, value in sorted(allowed_query))
    return f"{path}?{query}"


def _decimal_value(value: Any, *, field: str) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise TossApiError(f"{field} is not numeric") from exc
    if not amount.is_finite():
        raise TossApiError(f"{field} is not finite")
    return amount


class SafeRecordingTransport:
    def __init__(self, delegate: Callable[..., Any]) -> None:
        self.delegate = delegate
        self.calls: list[tuple[str, str, str]] = []
        self.mutation_calls = 0

    def __call__(self, request, timeout):
        method = request.get_method().upper()
        path = urlparse(request.full_url).path
        endpoint = _receipt_endpoint(request.full_url)
        if method == "POST" and path == "/oauth2/token":
            pass
        elif method != "GET":
            self.mutation_calls += 1
            raise TossApiError("broker mutation blocked before network")
        self.calls.append((method, endpoint, fingerprint(request.full_url)))
        return self.delegate(request, timeout)


class MockTransport:
    """Local fixture only; never performs a network request."""
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []
        self.mutation_calls = 0

    def __call__(self, request, timeout):
        method = request.get_method().upper()
        path = urlparse(request.full_url).path
        endpoint = _receipt_endpoint(request.full_url)
        if method == "POST" and path == "/oauth2/token":
            self.calls.append((method, endpoint, fingerprint(request.full_url)))
            return 200, {}, b'{"access_token":"MOCK_TOKEN","expires_in":300}'
        if method != "GET":
            self.mutation_calls += 1
            raise TossApiError("MOCK broker mutation blocked")
        self.calls.append((method, endpoint, fingerprint(request.full_url)))
        query = request.full_url
        if path == "/api/v1/accounts":
            body = {"result": [{"accountNo": "MOCK-0000-1234", "accountSeq": 1, "accountType": "BROKERAGE"}]}
        elif path == "/api/v1/holdings":
            body = {"result": {"items": []}}
        elif path == "/api/v1/buying-power":
            body = {
                "result": {
                    "currency": "USD" if "currency=USD" in query else "KRW",
                    "cashBuyingPower": "100",
                }
            }
        elif path.startswith("/api/v1/orders/"):
            body = {
                "result": {
                    "orderId": "mock-order-1", "symbol": "005930", "side": "BUY",
                    "orderType": "LIMIT", "status": "FILLED", "price": "100",
                    "quantity": "1", "orderedAt": "2026-07-30T09:00:00+09:00",
                    "execution": {"filledQuantity": "1", "filledAt": "2026-07-30T09:01:00+09:00"},
                }
            }
        else:
            body = {
                "result": {
                    "orders": [{
                        "orderId": "mock-order-1", "symbol": "005930", "side": "BUY",
                        "orderType": "LIMIT", "status": "FILLED", "price": "100",
                        "quantity": "1", "orderedAt": "2026-07-30T09:00:00+09:00",
                    }]
                }
            }
        return 200, {}, json.dumps(body).encode("utf-8")


def _strict_snapshot(
    adapter: TossReadOnlyAdapter,
    *,
    allowlist: set[str],
    client: TossOpenApiClient,
) -> tuple[dict[str, Any], bool]:
    accounts = adapter.get_account_basics()["raw"]
    account_rows = [row for row in accounts if isinstance(row, dict)]
    selected = (
        [row for row in account_rows if str(row.get("accountNo", "")) in allowlist]
        if allowlist
        else account_rows
    )
    if len(selected) != 1:
        raise TossApiError("account allowlist must match exactly one account")
    account_no = str(selected[0].get("accountNo") or "")
    account_seq = selected[0].get("accountSeq")
    if not account_no or account_seq in (None, ""):
        raise TossApiError("selected account schema is incomplete")
    client.account_id = str(account_seq)
    holdings_payload = adapter.get_holdings()["raw"]
    if not isinstance(holdings_payload, dict) or not isinstance(holdings_payload.get("items"), list):
        raise TossApiError("holdings schema mismatch")
    krw = adapter.get_buying_power(currency="KRW")["raw"]
    usd = adapter.get_buying_power(currency="USD")["raw"]
    for currency, payload in (("KRW", krw), ("USD", usd)):
        if (
            not isinstance(payload, dict)
            or payload.get("currency") != currency
            or payload.get("cashBuyingPower") is None
        ):
            raise TossApiError("buying-power schema mismatch")
        _decimal_value(payload["cashBuyingPower"], field="buying-power amount")
    open_orders = adapter.list_orders(status="OPEN", limit=100)
    closed_orders = adapter.list_orders(status="CLOSED", limit=100)
    orders: list[dict[str, Any]] = []
    unknown = False
    seen: set[str] = set()
    for row in [*open_orders, *closed_orders]:
        order_id = str(row.get("orderId") or "")
        if not order_id or order_id in seen:
            continue
        seen.add(order_id)
        detail = adapter.get_order(order_id)["raw"]
        required = {"orderId", "symbol", "side", "orderType", "status", "quantity"}
        if not isinstance(detail, dict) or not required.issubset(detail):
            raise TossApiError("order detail schema mismatch")
        status = str(detail["status"]).strip().upper()
        unknown = unknown or canonical_order_status(status) == "UNKNOWN"
        execution = detail.get("execution") if isinstance(detail.get("execution"), dict) else {}
        requested = _decimal_value(detail["quantity"], field="order quantity")
        filled = _decimal_value(execution.get("filledQuantity", 0), field="filled quantity")
        orders.append(
            {
                "provider_order_id": fingerprint(str(detail["orderId"])),
                "symbol": str(detail["symbol"]).zfill(6),
                "side": str(detail["side"]).upper(),
                "order_type": str(detail["orderType"]).upper(),
                "requested_quantity": requested,
                "executed_quantity": filled,
                "remaining_quantity": max(Decimal("0"), requested - filled),
                "limit_price": (
                    _decimal_value(detail["price"], field="order price")
                    if detail.get("price") is not None else None
                ),
                "status": status,
                "submitted_at": detail.get("orderedAt"),
                "updated_at": execution.get("filledAt") or detail.get("updatedAt"),
                "source_status": "REAL_READ_ONLY",
            }
        )
    now = datetime.now(timezone.utc)
    holdings = []
    for row in holdings_payload["items"]:
        if not isinstance(row, dict) or not {"symbol", "quantity"}.issubset(row):
            raise TossApiError("holding row schema mismatch")
        market_value = row.get("marketValue")
        if market_value is not None:
            if not isinstance(market_value, dict) or "amount" not in market_value:
                raise TossApiError("holding marketValue schema mismatch")
            market_value_amount = _decimal_value(
                market_value["amount"], field="holding marketValue.amount"
            )
        else:
            market_value_amount = None
        holdings.append(
            {
                "symbol": str(row["symbol"]).zfill(6),
                "quantity": _decimal_value(row["quantity"], field="holding quantity"),
                "available_quantity": (
                    _decimal_value(row["availableQuantity"], field="holding available quantity")
                    if row.get("availableQuantity") is not None else None
                ),
                "average_price": (
                    _decimal_value(row["averagePurchasePrice"], field="holding average purchase price")
                    if row.get("averagePurchasePrice") is not None else None
                ),
                "market_value": market_value_amount,
                "currency": str(row.get("currency") or "KRW"),
                "observed_at": now,
                "source_status": "REAL_READ_ONLY",
            }
        )
    return {
        "account_fingerprint": fingerprint(account_no),
        "cash": [
            {"currency": "KRW", "buying_power": _decimal_value(krw["cashBuyingPower"], field="KRW buying-power"), "observed_at": now, "source_status": "REAL_READ_ONLY"},
            {"currency": "USD", "buying_power": _decimal_value(usd["cashBuyingPower"], field="USD buying-power"), "observed_at": now, "source_status": "REAL_READ_ONLY"},
        ],
        "holdings": holdings,
        "orders": orders,
    }, unknown


def _adapter_for(
    mode: str,
    env: dict[str, str],
    transport: Any | None,
) -> tuple[TossOpenApiClient, TossReadOnlyAdapter, Any, set[str]]:
    schema = MockReadOnlySchema(
        buying_power_amount="cashBuyingPower",
        holdings_list="items",
        orders_list="orders",
    )
    if mode == "mock":
        recorder = transport or MockTransport()
        client = TossOpenApiClient(
            client_id="mock", client_secret="mock", base_url="https://mock.invalid",
            timeout_seconds=1, transport=recorder,
        )
        return client, TossReadOnlyAdapter(client, mock_schema=schema), recorder, {"MOCK-0000-1234"}
    timeout = float(env.get("TOSS_READ_ONLY_TIMEOUT_SECONDS") or DEFAULT_READ_ONLY_TIMEOUT_SECONDS)
    if not 0 < timeout <= 60:
        raise TossApiError("read-only timeout must be between 0 and 60 seconds")
    base_url = (env.get("TOSS_API_BASE_URL") or OFFICIAL_TOSS_API_BASE_URL).rstrip("/")
    if urlparse(base_url).scheme != "https":
        raise TossApiError("real read-only base URL must use HTTPS")
    delegate = transport or TossOpenApiClient._default_transport
    recorder = SafeRecordingTransport(delegate)
    client = TossOpenApiClient(
        client_id=env["TOSS_CLIENT_ID"],
        client_secret=env["TOSS_CLIENT_SECRET"],
        base_url=base_url,
        timeout_seconds=timeout,
        transport=recorder,
    )
    allowlist = {
        x.strip()
        for x in (env.get("TOSS_ACCOUNT_ALLOWLIST") or "").split(",")
        if x.strip()
    }
    return client, TossReadOnlyAdapter(client, mock_schema=schema), recorder, allowlist


def run_toss_snapshot(
    *,
    database_url: str,
    mode: str,
    env: dict[str, str] | None = None,
    transport: Any | None = None,
) -> dict[str, Any]:
    if mode not in {"mock", "real-read-only"}:
        raise TossApiError("snapshot mode must be mock or real-read-only")
    if LIVE_BUILD_CAPABILITY or CURRENT_RELEASE_LIVE_AUTHORITY:
        raise TossApiError("Live hardlock could not be verified")
    values = dict(os.environ if env is None else env)
    if mode == "real-read-only":
        missing = [key for key in REQUIRED_REAL_ENV if not values.get(key)]
        if missing:
            return {
                "status": "SKIPPED_NOT_CONFIGURED",
                "missing_variable_names": missing,
                "observation_status": "NOT_CONFIGURED",
                "mutation_calls": 0,
                "live_execution_allowed": False,
            }
    initialize(database_url)
    try:
        client, adapter, recorder, allowlist = _adapter_for(mode, values, transport)
        canonical, unknown_order = _strict_snapshot(
            adapter, allowlist=allowlist, client=client
        )
        now = datetime.now(timezone.utc)
        source_status = "MOCK" if mode == "mock" else "REAL_READ_ONLY"
        if mode == "mock":
            for row in canonical["cash"]:
                row["source_status"] = "MOCK"
            for row in canonical["orders"]:
                row["source_status"] = "MOCK"
        receipts = []
        unique_calls = list(dict.fromkeys(recorder.calls))
        for method, path, request_url_fingerprint in unique_calls:
            receipts.append(
                {
                    "endpoint": path,
                    "method": method,
                    "request_fingerprint": fingerprint(f"{method}:{request_url_fingerprint}"),
                    "started_at": now,
                    "completed_at": now,
                    "status_category": source_status,
                    "pagination_count": 1,
                    "result_status": "PASSED",
                    "response_digest": fingerprint(f"{source_status}:{path}"),
                    "error_category": None,
                }
            )
        snapshot = {
            "session_id": f"{source_status}-{uuid.uuid4()}",
            "mode": source_status,
            "provider": "TOSS_OPENAPI",
            "contract_version": "1.2.5",
            "started_at": now,
            "completed_at": now,
            **canonical,
            "receipts": receipts,
        }
        snapshot["snapshot_hash"] = digest(
            {k: v for k, v in snapshot.items() if k not in {"session_id", "snapshot_hash"}}
        )
        outcome = save_snapshot(database_url, snapshot)
        return {
            "status": outcome,
            "observation_status": "UNKNOWN_ORDER" if unknown_order else "PASSED",
            "mode": source_status,
            "account_fingerprint_suffix": canonical["account_fingerprint"][-8:],
            "holding_count": len(canonical["holdings"]),
            "order_count": len(canonical["orders"]),
            "cash_currencies": sorted(row["currency"] for row in canonical["cash"]),
            "business_methods": sorted(
                {method for method, path, _ in recorder.calls if path != "/oauth2/token"}
            ),
            "oauth_posts": sum(
                method == "POST" and path == "/oauth2/token"
                for method, path, _ in recorder.calls
            ),
            "mutation_calls": recorder.mutation_calls,
            "live_execution_allowed": False,
        }
    except TossApiError as exc:
        message = str(exc)
        last_endpoint = (
            recorder.calls[-1][1]
            if "recorder" in locals() and getattr(recorder, "calls", None)
            else "PRE_NETWORK"
        )
        if last_endpoint == "/oauth2/token":
            category = (
                "OAUTH_AUTHORIZATION_FAILED"
                if "status 401" in message or "status 403" in message
                else "OAUTH_REQUEST_FAILED"
            )
        elif "status 401" in message or "status 403" in message:
            category = "AUTHORIZATION_FAILED"
        elif "allowlist" in message or "exactly one account" in message:
            category = "ACCOUNT_SELECTION_FAILED"
        elif "schema" in message or "configured list" in message:
            category = "READ_ONLY_SCHEMA_FAILED"
        elif "connection failed" in message or "timed out" in message:
            category = "READ_ONLY_TRANSPORT_FAILED"
        else:
            category = "READ_ONLY_CONTRACT_FAILED"
        return {
            "status": "FAILED",
            "observation_status": "FAILED",
            "failure_category": category,
            "failure_stage": last_endpoint,
            "mutation_calls": getattr(locals().get("recorder"), "mutation_calls", 0),
            "live_execution_allowed": False,
        }
