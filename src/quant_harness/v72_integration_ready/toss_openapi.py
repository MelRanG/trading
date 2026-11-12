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
from urllib.parse import quote, urlencode
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
    market_calendar_path: str | None = '/api/v1/market-calendar/{market}'

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
        'PENDING_CANCEL': 'ACCEPTED', 'PENDING_REPLACE': 'ACCEPTED',
        'PARTIAL': 'PARTIALLY_FILLED', 'PARTIALLYFILLED': 'PARTIALLY_FILLED',
        'PARTIAL_FILLED': 'PARTIALLY_FILLED',
        'COMPLETED': 'FILLED', 'DONE': 'FILLED',
        'CANCELLED': 'CANCELED', 'CANCEL': 'CANCELED',
        'FAILED': 'REJECTED', 'REPLACED': 'CANCELED',
        'CANCEL_REJECTED': 'REJECTED', 'REPLACE_REJECTED': 'REJECTED',
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
            try:
                status, response_headers, raw = self._send(
                    Request(url, data=payload, headers=headers, method=method)
                )
            except TossApiError:
                if method.upper() != 'GET' or attempt == attempts - 1:
                    raise
                time.sleep(min((2 ** attempt) + random.uniform(0, 0.25), 8.0))
                continue
            if 200 <= status < 300:
                break
            if method.upper() != 'GET' or status not in {429, 500, 502, 503, 504} or attempt == attempts - 1:
                # Provider bodies may contain account-linked or other sensitive data.
                # Never include raw responses in exceptions that callers could log.
                raise TossApiError(f'Toss API returned status {status}')
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
            # Official v1.2 candle contract: bounded pages, inclusive `before`,
            # and adjusted OHLC.  The caller still supplies a date window; the
            # provider filters the returned page to that window below.
            'symbol': symbol, 'interval': '1d', 'count': 200,
            'before': f'{end_date}T23:59:59+09:00', 'adjusted': 'true',
        })
        payload = data.get('data', data)
        result_payload = _dig(payload, 'result', payload)
        rows = _dig(result_payload, self.field_map.candles_list, result_payload if isinstance(result_payload, list) else [])
        result: list[dict[str, Any]] = []
        for row in rows or []:
            close = _dig(row, self.field_map.candle_close)
            if close is None:
                close = row.get('closePrice') if isinstance(row, dict) else None
            volume = _dig(row, self.field_map.candle_volume, 0)
            if close is None:
                continue
            value = _dig(row, self.field_map.candle_value)
            candle_date = _dig(row, self.field_map.candle_date)
            if not candle_date and isinstance(row, dict):
                candle_date = row.get('timestamp')
            if not candle_date:
                raise TossApiError(f'Candle row did not contain {self.field_map.candle_date}')
            candle_date = str(candle_date)[:10]
            if candle_date < str(start_date) or candle_date > str(end_date):
                continue
            open_price = _dig(row, self.field_map.candle_open)
            high_price = _dig(row, self.field_map.candle_high)
            low_price = _dig(row, self.field_map.candle_low)
            if isinstance(row, dict):
                open_price = row.get('openPrice', open_price)
                high_price = row.get('highPrice', high_price)
                low_price = row.get('lowPrice', low_price)
            result.append({
                'date': candle_date,
                'ticker': str(symbol).zfill(6) if str(symbol).isdigit() else str(symbol),
                'open': float(open_price if open_price is not None else close),
                'high': float(high_price if high_price is not None else close),
                'low': float(low_price if low_price is not None else close),
                'adj_close': float(close),
                'volume': float(volume or 0),
                'value_approx': float(value) if value is not None else float(close) * float(volume or 0),
                'source': 'TOSS_OPEN_API',
            })
        return result

    def get_market_indicator_prices(self, symbols: list[str]) -> list[dict[str, Any]]:
        """Return the raw market-indicator price identity fields from Toss."""
        requested = [str(symbol).strip() for symbol in symbols if str(symbol).strip()]
        if not requested:
            raise TossApiError('Market-indicator price discovery requires a symbol catalog probe.')
        data = self._request('GET', '/api/v1/market-indicators/prices', query={'symbols': ','.join(requested)})
        payload = data.get('result', data.get('data', data))
        rows = payload if isinstance(payload, list) else _dig(payload, 'indicators', [])
        if not isinstance(rows, list):
            raise TossApiError('Market-indicator price response schema is not verified.')
        result: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict) or not row.get('symbol'):
                raise TossApiError('Market-indicator price row is malformed.')
            result.append({
                'symbol': str(row['symbol']),
                'name': row.get('name'),
                'timestamp': row.get('timestamp'),
                'last_price': row.get('lastPrice', row.get('last_price')),
            })
        return result

    def get_market_indicator_candles_page(
        self,
        symbol: str,
        *,
        interval: str = '1d',
        count: int = 200,
        before: str | None = None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Read one official market-indicator candle page (GET-only)."""
        if interval not in {'1m', '1d'} or not 1 <= int(count) <= 200:
            raise TossApiError('market-indicator candle contract requires interval=1m|1d and count<=200')
        query: dict[str, Any] = {'interval': interval, 'count': int(count)}
        if before is not None:
            query['before'] = before
        path = f'/api/v1/market-indicators/{quote(str(symbol), safe="")}/candles'
        data = self._request('GET', path, query=query)
        result = data.get('result', data.get('data', data))
        if not isinstance(result, dict) or not isinstance(result.get('candles'), list):
            raise TossApiError('market-indicator candle response schema is not verified.')
        rows: list[dict[str, Any]] = []
        for row in result['candles']:
            if not isinstance(row, dict) or not row.get('timestamp'):
                raise TossApiError('market-indicator candle row is malformed.')
            def field(name: str, fallback: str) -> Any:
                value = row.get(name)
                return row.get(fallback) if value is None else value
            rows.append({
                'timestamp': str(row['timestamp']),
                'symbol': str(symbol),
                'open': field('open', 'openPrice'),
                'high': field('high', 'highPrice'),
                'low': field('low', 'lowPrice'),
                'close': field('close', 'closePrice'),
                'volume': row.get('volume'),
            })
        next_before = result.get('nextBefore', result.get('next_before'))
        if next_before is not None and not isinstance(next_before, str):
            raise TossApiError('market-indicator nextBefore is not a string.')
        return rows, next_before

    def get_intraday_candles_page(
        self,
        symbol: str,
        *,
        before: str,
        interval: str = '1m',
        count: int = 200,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Read one official 1-minute candle page; this method is GET-only."""
        if interval != '1m' or not 1 <= int(count) <= 200:
            raise TossApiError('intraday candle contract requires interval=1m and count<=200')
        data = self._request('GET', self.endpoint_map.candles_path, query={
            'symbol': symbol, 'interval': interval, 'count': int(count),
            'before': before, 'adjusted': 'true',
        })
        result = data.get('result', data)
        if not isinstance(result, dict) or not isinstance(result.get('candles'), list):
            raise TossApiError('intraday candle response schema is not verified')
        rows: list[dict[str, Any]] = []
        for row in result['candles']:
            if not isinstance(row, dict) or not row.get('timestamp'):
                raise TossApiError('intraday candle row is malformed')
            def field(name: str, fallback: str) -> Any:
                value = row.get(name)
                return row.get(fallback) if value is None else value
            rows.append({
                'timestamp': str(row['timestamp']),
                'symbol': str(symbol).zfill(6) if str(symbol).isdigit() else str(symbol),
                'open': field('open', 'openPrice'),
                'high': field('high', 'highPrice'),
                'low': field('low', 'lowPrice'),
                'close': field('close', 'closePrice'),
                'volume': row.get('volume', 0),
                'adjusted_query': True,
                'source': 'TOSS_OPEN_API',
            })
        next_before = result.get('nextBefore')
        if next_before is not None and not isinstance(next_before, str):
            raise TossApiError('intraday nextBefore is not a string')
        return rows, next_before


    def get_market_calendar(self, *, market: str, start_date: str, end_date: str) -> list[dict[str, Any]]:
        path = (self.endpoint_map.market_calendar_path or '').replace('{market}', market)
        # The official endpoint returns a current snapshot (previous/today/next
        # business day), not a caller-selected date range.
        data = self._request('GET', path)
        payload = data.get('result', data.get('data', data))
        if isinstance(payload, dict) and {'previousBusinessDay', 'today', 'nextBusinessDay'}.issubset(payload):
            rows = []
            for key in ('previousBusinessDay', 'today', 'nextBusinessDay'):
                item = payload.get(key)
                if not isinstance(item, dict):
                    continue
                integrated = item.get('integrated')
                krx = item.get('krx')
                session_data = integrated if isinstance(integrated, dict) else krx if isinstance(krx, dict) else {}
                regular = session_data.get('regularMarket') if isinstance(session_data, dict) else None
                rows.append({
                    'date': str(item.get('date', ''))[:10],
                    'is_open': key != 'today' or isinstance(regular, dict),
                    'regular_market_end': regular.get('endTime') if isinstance(regular, dict) else None,
                    'raw': item,
                })
        else:
            rows = _dig(payload, self.field_map.calendar_list, payload if isinstance(payload, list) else [])
        result: list[dict[str, Any]] = []
        for row in rows or []:
            session = str(row.get('date') or _dig(row, self.field_map.calendar_date, ''))[:10]
            if not session:
                continue
            raw_open = row.get('is_open', _dig(row, self.field_map.calendar_is_open, True))
            is_open = raw_open if isinstance(raw_open, bool) else str(raw_open).lower() in {'true', '1', 'y', 'yes', 'open'}
            end_time = row.get('regular_market_end')
            if end_time is None:
                end_time = _dig(row, 'integrated.regularMarket.endTime') or _dig(row, 'krx.regularMarket.endTime')
            result.append({'date': session, 'is_open': is_open, 'regular_market_end': end_time, 'raw': row.get('raw', row)})
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
