from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Protocol

from .toss_openapi import TossApiError, TossOpenApiClient, _dig


class TossReadOnly(Protocol):
    """Intentionally contains no order creation, modification, or cancellation."""
    def get_account_basics(self) -> dict[str, Any]: ...
    def get_buying_power(self, *, currency: str) -> dict[str, Any]: ...
    def get_holdings(self, *, symbol: str | None = None) -> dict[str, Any]: ...
    def list_orders(self, *, status: str, limit: int | None = None, cursor: str | None = None, symbol: str | None = None, from_date: str | None = None, to_date: str | None = None) -> list[dict[str, Any]]: ...
    def get_order(self, order_id: str) -> dict[str, Any]: ...
    def list_executions(self) -> list[dict[str, Any]]: ...


@dataclass(frozen=True)
class MockReadOnlySchema:
    """Test-only response mapping. It is not a claim about a Toss response schema."""
    account_list: str | None = None
    buying_power_amount: str | None = None
    holdings_list: str | None = None
    orders_list: str | None = None
    next_cursor: str | None = None
    cursor_query: str | None = None


@dataclass(frozen=True)
class CanonicalAccountSnapshot:
    account_id_masked: str
    cash_or_buying_power: Decimal
    holdings: tuple[dict[str, Any], ...]
    observed_at: datetime
    timezone: str
    source_status: str


def mask_account_id(value: str | None) -> str:
    text = str(value or "")
    if len(text) <= 4:
        return "****"
    return "*" * (len(text) - 4) + text[-4:]


class TossReadOnlyAdapter:
    """GET-only account inspection adapter; all fixtures are explicitly MOCK."""
    def __init__(self, client: TossOpenApiClient, *, mock_schema: MockReadOnlySchema | None = None) -> None:
        self.__client = client
        self.__schema = mock_schema

    @staticmethod
    def _result(data: dict[str, Any]) -> Any:
        if not isinstance(data, dict):
            raise TossApiError("read-only response must be a JSON object")
        return data.get("result", data.get("data", data))

    def _get(self, path: str, *, query: dict[str, Any] | None = None, account_required: bool = True) -> Any:
        try:
            return self._result(self.__client._request("GET", path, query=query, account_required=account_required))
        except TimeoutError as exc:
            raise TossApiError("read-only request timed out; state is UNKNOWN") from exc

    def get_account_basics(self) -> dict[str, Any]:
        # The accounts entrypoint is OAuth-only; accountSeq is discovered here.
        result = self._get("/api/v1/accounts", account_required=False)
        if not isinstance(result, (dict, list)):
            raise TossApiError("accounts response has an unsupported schema")
        if not isinstance(result, list):
            raise TossApiError("accounts result must be an array")
        return {"source": "TOSS_OPENAPI_V1_2_5_FIXTURE", "raw": result}

    def get_buying_power(self, *, currency: str) -> dict[str, Any]:
        if currency not in {"KRW", "USD"}:
            raise TossApiError("currency must be KRW or USD")
        result = self._get("/api/v1/buying-power", query={"currency": currency})
        if not isinstance(result, dict):
            raise TossApiError("buying-power response has an unsupported schema")
        return {"source": "TOSS_MOCK_OR_UNVERIFIED", "raw": result}

    def get_holdings(self, *, symbol: str | None = None) -> dict[str, Any]:
        result = self._get("/api/v1/holdings", query={"symbol": symbol})
        if not isinstance(result, (dict, list)):
            raise TossApiError("holdings response has an unsupported schema")
        return {"source": "TOSS_MOCK_OR_UNVERIFIED", "raw": result}

    def list_orders(self, *, status: str, limit: int | None = None, cursor: str | None = None, symbol: str | None = None, from_date: str | None = None, to_date: str | None = None) -> list[dict[str, Any]]:
        if status not in {"OPEN", "CLOSED"}:
            raise TossApiError("status must be OPEN or CLOSED")
        if limit is not None and not 1 <= limit <= 100:
            raise TossApiError("limit must be between 1 and 100")
        schema = self.__schema
        query: dict[str, Any] = {"status": status, "limit": limit, "cursor": cursor, "symbol": symbol, "from": from_date, "to": to_date}
        rows: list[dict[str, Any]] = []
        while True:
            result = self._get("/api/v1/orders", query=query)
            page = _dig(result, schema.orders_list) if schema and schema.orders_list else result
            if not isinstance(page, list) or not all(isinstance(row, dict) for row in page):
                raise TossApiError("orders response is not a configured list")
            rows.extend(page)
            cursor = _dig(result, schema.next_cursor) if schema and schema.next_cursor else None
            if cursor is None:
                return rows
            if not schema or not schema.cursor_query or not isinstance(cursor, str) or not cursor:
                raise TossApiError("orders pagination cursor is unverified or malformed")
            query[schema.cursor_query] = cursor

    def get_order(self, order_id: str) -> dict[str, Any]:
        if not order_id:
            raise TossApiError("order_id is required")
        result = self._get(f"/api/v1/orders/{order_id}")
        if not isinstance(result, dict):
            raise TossApiError("order detail result must be an object")
        return {"source": "TOSS_OPENAPI_V1_2_5_FIXTURE", "raw": result}

    def list_executions(self) -> list[dict[str, Any]]:
        raise TossApiError("execution-history endpoint/schema is not officially confirmed; fail closed")

    def canonical_snapshot(self, *, observed_at: datetime, timezone_name: str) -> CanonicalAccountSnapshot:
        schema = self.__schema
        if not schema or not schema.buying_power_amount or not schema.holdings_list:
            raise TossApiError("canonical snapshot requires a verified response field map")
        power = self.get_buying_power(currency="KRW")["raw"]
        holdings = self.get_holdings()["raw"]
        amount = _dig(power, schema.buying_power_amount)
        rows = _dig(holdings, schema.holdings_list)
        if amount is None or not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
            raise TossApiError("canonical snapshot response is malformed")
        try:
            cash = Decimal(str(amount))
        except Exception as exc:
            raise TossApiError("buying-power amount is not numeric") from exc
        if observed_at.tzinfo is None or observed_at.utcoffset() is None or not timezone_name:
            raise TossApiError("snapshot timestamp must be timezone-aware")
        return CanonicalAccountSnapshot(mask_account_id(self.__client.account_id), cash, tuple(rows), observed_at, timezone_name, "MOCK_SCHEMA_ONLY")
