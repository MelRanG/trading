from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal, Protocol

Side = Literal['BUY', 'SELL']
OrderStatus = Literal['NEW', 'ACCEPTED', 'PARTIALLY_FILLED', 'FILLED', 'CANCELED', 'REJECTED']


@dataclass(frozen=True)
class BrokerQuote:
    symbol: str
    price: Decimal
    as_of: datetime
    currency: str = 'KRW'
    source: str = 'UNKNOWN'


@dataclass(frozen=True)
class BrokerHolding:
    symbol: str
    quantity: Decimal
    average_price: Decimal
    current_price: Decimal | None = None
    market_value: Decimal | None = None
    unrealized_pnl: Decimal | None = None


@dataclass(frozen=True)
class BrokerAccount:
    account_id: str
    cash: Decimal
    total_equity: Decimal
    currency: str = 'KRW'
    holdings: tuple[BrokerHolding, ...] = field(default_factory=tuple)
    as_of: datetime | None = None


@dataclass(frozen=True)
class BrokerOrder:
    client_order_id: str
    symbol: str
    side: Side
    quantity: Decimal
    order_type: str
    status: OrderStatus
    broker_order_id: str | None = None
    limit_price: Decimal | None = None
    average_fill_price: Decimal | None = None
    filled_quantity: Decimal = Decimal('0')
    reason: str = ''
    created_at: datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class BrokerGateway(Protocol):
    def health_check(self) -> dict[str, Any]: ...
    def get_quote(self, symbol: str) -> BrokerQuote: ...
    def get_account(self) -> BrokerAccount: ...
    def list_orders(self, *, start_date: str | None = None, end_date: str | None = None) -> list[BrokerOrder]: ...
    def create_order(
        self,
        *,
        client_order_id: str,
        symbol: str,
        side: Side,
        quantity: Decimal,
        order_type: str = 'MARKET',
        limit_price: Decimal | None = None,
        reason: str = '',
        dry_run: bool = True,
    ) -> BrokerOrder: ...
    def cancel_order(self, broker_order_id: str) -> BrokerOrder: ...
