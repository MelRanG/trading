from __future__ import annotations

import json
import os
import time
import threading
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .contracts import BrokerAccount, BrokerHolding, BrokerOrder, BrokerQuote, Side
from .live_safety import current_release_live_order_decision


class TossApiError(RuntimeError):
    pass


@dataclass(frozen=True)
class TossEndpointMap:
    token_path: str = '/oauth2/token'
    quote_path: str = '/api/v1/prices'
    candles_path: str = '/api/v1/candles'
    account_path: str | None = None
    holdings_path: str | None = None
    order_create_path: str | None = None
    order_cancel_path: str | None = None
    order_list_path: str | None = None
    market_calendar_path: str | None = None

    @classmethod
    def from_json(cls, path: Path | str | None) -> 'TossEndpointMap':
        if path is None:
            return cls()
        raw = json.loads(Path(path).read_text(encoding='utf-8'))
        allowed = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in raw.items() if k in allowed})


@dataclass(frozen=True)
class TossFieldMap:
    quote_price: str = 'price'
    quote_symbol: str = 'symbol'
    quote_timestamp: str = 'timestamp'
    account_cash: str = 'cash'
    account_equity: str = 'totalEquity'
    holdings_list: str = 'holdings'
    holding_symbol: str = 'symbol'
    holding_quantity: str = 'quantity'
    holding_average_price: str = 'averagePrice'
    holding_current_price: str = 'currentPrice'
    order_id: str = 'orderId'
    order_status: str = 'status'
    order_filled_quantity: str = 'filledQuantity'
    order_average_fill_price: str = 'averageFillPrice'
    candles_list: str = 'candles'
    candle_date: str = 'date'
    candle_open: str = 'open'
    candle_high: str = 'high'
    candle_low: str = 'low'
    candle_close: str = 'close'
    candle_volume: str = 'volume'
    candle_value: str = 'value'
    calendar_list: str = 'sessions'
    calendar_date: str = 'date'
    calendar_is_open: str = 'isOpen'

    @classmethod
    def from_json(cls, path: Path | str | None) -> 'TossFieldMap':
        if path is None:
            return cls()
        raw = json.loads(Path(path).read_text(encoding='utf-8'))
        allowed = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in raw.items() if k in allowed})


def _dig(data: Any, dotted: str, default: Any = None) -> Any:
    cur = data
    for part in dotted.split('.'):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return default
    return cur


def _normalize_order_status(value: Any) -> str:
    text = str(value or '').strip().upper().replace('-', '_').replace(' ', '_')
    aliases = {
        'PENDING': 'ACCEPTED', 'SUBMITTED': 'ACCEPTED', 'RECEIVED': 'ACCEPTED',
        'PARTIAL': 'PARTIALLY_FILLED', 'PARTIALLYFILLED': 'PARTIALLY_FILLED',
        'COMPLETED': 'FILLED', 'DONE': 'FILLED',
        'CANCELLED': 'CANCELED', 'CANCEL': 'CANCELED',
        'FAILED': 'REJECTED',
    }
    normalized = aliases.get(text, text)
    allowed = {'NEW', 'ACCEPTED', 'PARTIALLY_FILLED', 'FILLED', 'CANCELED', 'REJECTED'}
    if normalized not in allowed:
        raise TossApiError(f'Unknown Toss order status: {value!r}')
    return normalized


class TossOpenApiClient:
    """Fail-closed client for the official Toss Securities Open API.

    Exact account/order paths and response fields are loaded from JSON because the
    official OpenAPI document is the source of truth and may evolve. Market-data
    defaults follow the official public endpoint summary. Live mutations are
    structurally disabled in this release; environment variables cannot enable them.
    """

    _FIXED_TOKEN_PATH = '/oauth2/token'

    def __init__(
        self,
        *,
        client_id: str | None = None,
        client_secret: str | None = None,
        account_id: str | None = None,
        base_url: str = 'https://openapi.tossinvest.com',
        endpoint_map: TossEndpointMap | None = None,
        field_map: TossFieldMap | None = None,
        timeout_seconds: float = 15.0,
        transport: Callable[[Request, float], tuple[int, dict[str, str], bytes]] | None = None,
    ) -> None:
        self.client_id = client_id or os.getenv('TOSS_CLIENT_ID')
        self.client_secret = client_secret or os.getenv('TOSS_CLIENT_SECRET')
        self.account_id = account_id or os.getenv('TOSS_ACCOUNT_ID')
        self.base_url = base_url.rstrip('/')
        self.endpoint_map = endpoint_map or TossEndpointMap.from_json(os.getenv('TOSS_ENDPOINT_MAP'))
        if self.endpoint_map.token_path != self._FIXED_TOKEN_PATH:
            raise TossApiError(
                f'Toss OAuth token path is fixed to {self._FIXED_TOKEN_PATH}; '
                'endpoint configuration cannot change it.'
            )
        self.field_map = field_map or TossFieldMap.from_json(os.getenv('TOSS_FIELD_MAP'))
        self.timeout_seconds = timeout_seconds
        # The injectable transport is test plumbing, not part of the client API.
        self.__transport = transport or self._default_transport
        self._access_token: str | None = None
        self._token_expires_at = 0.0
        self._token_lock = threading.Lock()
        self.allow_live_orders = False

    def _require_live_order_authority(self, *, idempotency_key: str | None = None) -> None:
        decision = current_release_live_order_decision(
            account_id=self.account_id,
            idempotency_key=idempotency_key,
        )
        if not decision.allowed:
            raise TossApiError(
                'Live broker mutations are structurally disabled in this release: '
                + ', '.join(decision.blockers)
            )

    @staticmethod
    def _default_transport(request: Request, timeout: float) -> tuple[int, dict[str, str], bytes]:
        try:
            with urlopen(request, timeout=timeout) as response:
                return response.status, dict(response.headers.items()), response.read()
        except HTTPError as exc:
            body = exc.read() if exc.fp else b''
            return int(exc.code), dict(exc.headers.items()) if exc.headers else {}, body
        except URLError as exc:
            raise TossApiError(f'Toss API connection failed: {exc.reason}') from exc

    def _send(self, request: Request) -> tuple[int, dict[str, str], bytes]:
        """Issue an internally constructed request through the injected test transport."""
        return self.__transport(request, self.timeout_seconds)

    def _request(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        account_required: bool = False,
        authenticated: bool = True,
    ) -> dict[str, Any]:
        if method.upper() != 'GET':
            raise TossApiError(
                'Live broker mutations are structurally disabled in this release; '
                'only the fixed OAuth token POST is permitted.'
            )
        if not path:
            raise TossApiError('Toss endpoint is not configured. Run contract discovery and set TOSS_ENDPOINT_MAP.')
        url = f'{self.base_url}{path}'
        if query:
            url += '?' + urlencode({k: v for k, v in query.items() if v is not None})
        headers = {'Accept': 'application/json', 'User-Agent': 'quant-harness-v72/1.0'}
        if authenticated:
            headers['Authorization'] = f'Bearer {self._token()}'
        if account_required:
            if not self.account_id:
                raise TossApiError('TOSS_ACCOUNT_ID is required for account/order operations.')
            headers['X-Tossinvest-Account'] = self.account_id
        payload = None
        if body is not None:
            headers['Content-Type'] = 'application/json'
            payload = json.dumps(body, ensure_ascii=False).encode('utf-8')
        attempts = 4 if method.upper() == 'GET' else 1
        status = 0
        response_headers: dict[str, str] = {}
        raw = b''
        for attempt in range(attempts):
            status, response_headers, raw = self._send(Request(url, data=payload, headers=headers, method=method))
            if 200 <= status < 300:
                break
            if method.upper() != 'GET' or status not in {429, 500, 502, 503, 504} or attempt == attempts - 1:
                raise TossApiError(f'Toss API returned status {status}: {raw[:500]!r}')
            retry_after = response_headers.get('Retry-After') or response_headers.get('retry-after')
            try:
                wait = float(retry_after) if retry_after is not None else (2 ** attempt)
            except ValueError:
                wait = 2 ** attempt
            time.sleep(min(wait + random.uniform(0, 0.25), 8.0))
        if not raw:
            return {}
        try:
            return json.loads(raw.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TossApiError('Toss API returned invalid JSON') from exc

    def _token(self) -> str:
        with self._token_lock:
            if self._access_token and time.time() < self._token_expires_at - 30:
                return self._access_token
            if not self.client_id or not self.client_secret:
                raise TossApiError('TOSS_CLIENT_ID and TOSS_CLIENT_SECRET are required.')
            body = urlencode({
                'grant_type': 'client_credentials',
                'client_id': self.client_id,
                'client_secret': self.client_secret,
            }).encode('utf-8')
            headers = {'Content-Type': 'application/x-www-form-urlencoded', 'Accept': 'application/json'}
            status, _, raw = self._send(
                Request(f'{self.base_url}{self._FIXED_TOKEN_PATH}', data=body, headers=headers, method='POST')
            )
            if status < 200 or status >= 300:
                raise TossApiError(f'Token request failed with status {status}')
            try:
                data = json.loads(raw.decode('utf-8'))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise TossApiError('Token endpoint returned invalid JSON') from exc
            token = data.get('access_token') or data.get('accessToken')
            if not token:
                raise TossApiError('Token response did not contain access_token.')
            self._access_token = str(token)
            self._token_expires_at = time.time() + float(data.get('expires_in') or data.get('expiresIn') or 300)
            return self._access_token

    def health_check(self) -> dict[str, Any]:
        checks = {
            'credentials_present': bool(self.client_id and self.client_secret),
            'account_present': bool(self.account_id),
            'quote_endpoint_configured': bool(self.endpoint_map.quote_path),
            'candles_endpoint_configured': bool(self.endpoint_map.candles_path),
            'market_calendar_endpoint_configured': bool(self.endpoint_map.market_calendar_path),
            'account_endpoint_configured': bool(self.endpoint_map.account_path),
            'holdings_endpoint_configured': bool(self.endpoint_map.holdings_path),
            'order_create_endpoint_configured': bool(self.endpoint_map.order_create_path),
            'order_cancel_endpoint_configured': bool(self.endpoint_map.order_cancel_path),
            'order_list_endpoint_configured': bool(self.endpoint_map.order_list_path),
            'live_orders_enabled': self.allow_live_orders,
        }
        read_keys = {'credentials_present', 'quote_endpoint_configured', 'candles_endpoint_configured'}
        live_keys = set(checks)
        return {
            'ok_for_read': all(checks[key] for key in read_keys),
            'ok_for_live_contract': all(checks[key] for key in live_keys - {'live_orders_enabled'}),
            'ok_for_live': all(checks.values()),
            'checks': checks,
        }

    def get_quote(self, symbol: str) -> BrokerQuote:
        data = self._request('GET', self.endpoint_map.quote_path, query={'symbol': symbol})
        payload = data.get('data', data)
        price = _dig(payload, self.field_map.quote_price)
        if price is None:
            raise TossApiError(f'Quote response did not contain {self.field_map.quote_price}')
        timestamp_raw = _dig(payload, self.field_map.quote_timestamp)
        if not timestamp_raw:
            raise TossApiError(f'Quote response did not contain {self.field_map.quote_timestamp}')
        try:
            as_of = datetime.fromisoformat(str(timestamp_raw).replace('Z', '+00:00'))
        except ValueError as exc:
            raise TossApiError(f'Invalid quote timestamp: {timestamp_raw!r}') from exc
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise TossApiError('Quote timestamp must include a timezone offset')
        return BrokerQuote(
            symbol=str(_dig(payload, self.field_map.quote_symbol, symbol)),
            price=Decimal(str(price)), as_of=as_of, source='TOSS_OPEN_API',
        )


    def get_daily_candles(self, symbol: str, *, start_date: str, end_date: str) -> list[dict[str, Any]]:
        data = self._request('GET', self.endpoint_map.candles_path, query={
            'symbol': symbol, 'interval': '1d', 'startDate': start_date, 'endDate': end_date,
        })
        payload = data.get('data', data)
        rows = _dig(payload, self.field_map.candles_list, payload if isinstance(payload, list) else [])
        result: list[dict[str, Any]] = []
        for row in rows or []:
            close = _dig(row, self.field_map.candle_close)
            volume = _dig(row, self.field_map.candle_volume, 0)
            if close is None:
                continue
            value = _dig(row, self.field_map.candle_value)
            candle_date = _dig(row, self.field_map.candle_date)
            if not candle_date:
                raise TossApiError(f'Candle row did not contain {self.field_map.candle_date}')
            result.append({
                'date': str(candle_date)[:10],
                'ticker': str(symbol).zfill(6) if str(symbol).isdigit() else str(symbol),
                'open': float(_dig(row, self.field_map.candle_open, close)),
                'high': float(_dig(row, self.field_map.candle_high, close)),
                'low': float(_dig(row, self.field_map.candle_low, close)),
                'adj_close': float(close),
                'volume': float(volume or 0),
                'value_approx': float(value) if value is not None else float(close) * float(volume or 0),
                'source': 'TOSS_OPEN_API',
            })
        return result


    def get_market_calendar(self, *, market: str, start_date: str, end_date: str) -> list[dict[str, Any]]:
        path = (self.endpoint_map.market_calendar_path or '').replace('{market}', market)
        data = self._request('GET', path, query={'startDate': start_date, 'endDate': end_date})
        payload = data.get('data', data)
        rows = _dig(payload, self.field_map.calendar_list, payload if isinstance(payload, list) else [])
        result: list[dict[str, Any]] = []
        for row in rows or []:
            session = str(_dig(row, self.field_map.calendar_date, ''))[:10]
            if not session:
                continue
            raw_open = _dig(row, self.field_map.calendar_is_open, True)
            is_open = raw_open if isinstance(raw_open, bool) else str(raw_open).lower() in {'true', '1', 'y', 'yes', 'open'}
            result.append({'date': session, 'is_open': is_open, 'raw': row})
        return result

    def next_trading_session(self, *, market: str, after_date: str, search_days: int = 14) -> str:
        from datetime import date, timedelta
        start = date.fromisoformat(after_date) + timedelta(days=1)
        end = start + timedelta(days=max(1, int(search_days)))
        rows = self.get_market_calendar(market=market, start_date=start.isoformat(), end_date=end.isoformat())
        sessions = sorted(row['date'] for row in rows if row['is_open'] and row['date'] > after_date)
        if not sessions:
            raise TossApiError(f'No open {market} session found after {after_date}')
        return sessions[0]

    def get_account(self) -> BrokerAccount:
        account_data = self._request('GET', self.endpoint_map.account_path or '', account_required=True)
        holdings_data = self._request('GET', self.endpoint_map.holdings_path or '', account_required=True)
        account_payload = account_data.get('data', account_data)
        holdings_payload = holdings_data.get('data', holdings_data)
        rows = _dig(holdings_payload, self.field_map.holdings_list, holdings_payload if isinstance(holdings_payload, list) else [])
        cash_raw = _dig(account_payload, self.field_map.account_cash)
        equity_raw = _dig(account_payload, self.field_map.account_equity)
        if cash_raw is None or equity_raw is None:
            raise TossApiError('Account response is missing configured cash/equity fields')
        if not isinstance(rows, list):
            raise TossApiError('Holdings response is not a list at the configured field path')
        holdings: list[BrokerHolding] = []
        for row in rows or []:
            symbol_raw = _dig(row, self.field_map.holding_symbol)
            quantity_raw = _dig(row, self.field_map.holding_quantity)
            average_raw = _dig(row, self.field_map.holding_average_price)
            if symbol_raw in (None, '') or quantity_raw is None or average_raw is None:
                raise TossApiError('Holding row is missing symbol, quantity, or average price')
            quantity = Decimal(str(quantity_raw))
            avg = Decimal(str(average_raw))
            current_raw = _dig(row, self.field_map.holding_current_price)
            current = Decimal(str(current_raw)) if current_raw is not None else None
            holdings.append(BrokerHolding(
                symbol=str(symbol_raw).zfill(6) if str(symbol_raw).isdigit() else str(symbol_raw),
                quantity=quantity, average_price=avg, current_price=current,
                market_value=(quantity * current if current is not None else None),
            ))
        return BrokerAccount(
            account_id=self.account_id or '',
            cash=Decimal(str(cash_raw)),
            total_equity=Decimal(str(equity_raw)),
            holdings=tuple(holdings), as_of=datetime.now(timezone.utc),
        )

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
    ) -> BrokerOrder:
        if quantity <= 0 or quantity != quantity.to_integral_value():
            raise TossApiError('KR live orders require a positive integer quantity.')
        if dry_run:
            return BrokerOrder(
                client_order_id=client_order_id, symbol=symbol, side=side, quantity=quantity,
                order_type=order_type, limit_price=limit_price, status='NEW', reason=reason,
                created_at=datetime.now(timezone.utc), raw={'dry_run': True},
            )
        self._require_live_order_authority(idempotency_key=client_order_id)
        payload: dict[str, Any] = {
            'clientOrderId': client_order_id,
            'symbol': symbol,
            'side': side,
            'quantity': str(quantity),
            'orderType': order_type,
        }
        if limit_price is not None:
            payload['price'] = str(limit_price)
        data = self._request('POST', self.endpoint_map.order_create_path or '', body=payload, account_required=True)
        result = data.get('data', data)
        broker_id = _dig(result, self.field_map.order_id)
        if not broker_id:
            raise TossApiError('Create-order response did not contain an order id.')
        return BrokerOrder(
            client_order_id=client_order_id, broker_order_id=str(broker_id), symbol=symbol,
            side=side, quantity=quantity, order_type=order_type,
            status=_normalize_order_status(_dig(result, self.field_map.order_status, 'ACCEPTED')),
            filled_quantity=Decimal(str(_dig(result, self.field_map.order_filled_quantity, 0))),
            average_fill_price=(Decimal(str(_dig(result, self.field_map.order_average_fill_price)))
                                if _dig(result, self.field_map.order_average_fill_price) is not None else None),
            reason=reason, created_at=datetime.now(timezone.utc), raw=result,
        )

    def list_orders(self, *, start_date: str | None = None, end_date: str | None = None) -> list[BrokerOrder]:
        data = self._request('GET', self.endpoint_map.order_list_path or '',
                             query={'startDate': start_date, 'endDate': end_date}, account_required=True)
        rows = data.get('data', data)
        if isinstance(rows, dict):
            rows = rows.get('orders', [])
        result: list[BrokerOrder] = []
        for row in rows or []:
            result.append(BrokerOrder(
                client_order_id=str(row.get('clientOrderId', '')),
                broker_order_id=str(_dig(row, self.field_map.order_id, '')) or None,
                symbol=str(row.get('symbol', '')),
                side=str(row.get('side', 'BUY')).upper(),
                quantity=Decimal(str(row.get('quantity', 0))),
                order_type=str(row.get('orderType', 'MARKET')),
                status=_normalize_order_status(_dig(row, self.field_map.order_status, 'ACCEPTED')),
                filled_quantity=Decimal(str(_dig(row, self.field_map.order_filled_quantity, 0))),
                average_fill_price=(Decimal(str(_dig(row, self.field_map.order_average_fill_price)))
                                    if _dig(row, self.field_map.order_average_fill_price) is not None else None),
                raw=row,
            ))
        return result

    def cancel_order(self, broker_order_id: str) -> BrokerOrder:
        self._require_live_order_authority()
        path = (self.endpoint_map.order_cancel_path or '').replace('{order_id}', broker_order_id)
        data = self._request('POST', path, body={}, account_required=True)
        result = data.get('data', data)
        return BrokerOrder(
            client_order_id=str(result.get('clientOrderId', '')),
            broker_order_id=broker_order_id, symbol=str(result.get('symbol', '')),
            side=str(result.get('side', 'BUY')).upper(), quantity=Decimal(str(result.get('quantity', 0))),
            order_type=str(result.get('orderType', 'MARKET')),
            status=_normalize_order_status(_dig(result, self.field_map.order_status, 'CANCELED')), raw=result,
        )
