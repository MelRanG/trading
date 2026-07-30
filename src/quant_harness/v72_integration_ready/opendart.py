from __future__ import annotations

import io
import json
import os
import zipfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class OpenDartError(RuntimeError):
    pass


@dataclass(frozen=True)
class Disclosure:
    corp_code: str
    stock_code: str
    corp_name: str
    report_name: str
    receipt_no: str
    receipt_date: str
    disclosure_type: str | None = None


class OpenDartClient:
    BASE_URL = 'https://opendart.fss.or.kr/api'

    def __init__(
        self,
        *,
        api_key: str | None = None,
        timeout_seconds: float = 15.0,
        transport: Callable[[Request, float], tuple[int, dict[str, str], bytes]] | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv('OPENDART_API_KEY')
        self.timeout_seconds = timeout_seconds
        self.transport = transport or self._default_transport

    @staticmethod
    def _default_transport(request: Request, timeout: float) -> tuple[int, dict[str, str], bytes]:
        try:
            with urlopen(request, timeout=timeout) as response:
                return response.status, dict(response.headers.items()), response.read()
        except HTTPError as exc:
            body = exc.read() if exc.fp else b''
            raise OpenDartError(f'OpenDART HTTP {exc.code}: {body[:500]!r}') from exc
        except URLError as exc:
            raise OpenDartError(f'OpenDART connection failed: {exc.reason}') from exc

    def _request(self, endpoint: str, params: dict[str, Any], *, binary: bool = False) -> Any:
        if not self.api_key:
            raise OpenDartError('OPENDART_API_KEY is required.')
        query = {'crtfc_key': self.api_key, **{k: v for k, v in params.items() if v is not None}}
        url = f'{self.BASE_URL}/{endpoint}?{urlencode(query)}'
        status, _, raw = self.transport(Request(url, headers={'User-Agent': 'quant-harness-v72/1.0'}), self.timeout_seconds)
        if status < 200 or status >= 300:
            raise OpenDartError(f'OpenDART returned status {status}')
        if binary:
            return raw
        try:
            payload = json.loads(raw.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OpenDartError('OpenDART returned invalid JSON') from exc
        code = str(payload.get('status', '000'))
        if code not in {'000', '013'}:
            raise OpenDartError(f"OpenDART error {code}: {payload.get('message', '')}")
        return payload

    def search_disclosures(
        self,
        *,
        corp_code: str | None = None,
        start_date: str | date | None = None,
        end_date: str | date | None = None,
        disclosure_type: str | None = None,
        page_count: int = 100,
    ) -> list[Disclosure]:
        def fmt(value: str | date | None) -> str | None:
            if value is None:
                return None
            return value.strftime('%Y%m%d') if isinstance(value, date) else str(value).replace('-', '')

        count = min(max(int(page_count), 1), 100)
        results: list[Disclosure] = []
        page_no = 1
        while True:
            payload = self._request('list.json', {
                'corp_code': corp_code,
                'bgn_de': fmt(start_date),
                'end_de': fmt(end_date),
                'pblntf_ty': disclosure_type,
                'page_no': page_no,
                'page_count': count,
                'sort': 'date',
                'sort_mth': 'desc',
            })
            rows = payload.get('list', []) or []
            results.extend(Disclosure(
                corp_code=str(row.get('corp_code', '')),
                stock_code=str(row.get('stock_code', '')),
                corp_name=str(row.get('corp_name', '')),
                report_name=str(row.get('report_nm', '')),
                receipt_no=str(row.get('rcept_no', '')),
                receipt_date=str(row.get('rcept_dt', '')),
                disclosure_type=disclosure_type,
            ) for row in rows)
            total_page = int(payload.get('total_page') or payload.get('totalPage') or 1)
            if not rows or page_no >= total_page:
                break
            page_no += 1
            if page_no > 1000:
                raise OpenDartError('OpenDART pagination exceeded safety limit')
        return results

    def get_key_accounts(self, *, corp_code: str, business_year: int, report_code: str = '11011') -> list[dict[str, Any]]:
        payload = self._request('fnlttSinglAcnt.json', {
            'corp_code': corp_code,
            'bsns_year': str(business_year),
            'reprt_code': report_code,
        })
        return list(payload.get('list', []))

    def download_corp_codes(self) -> list[dict[str, str]]:
        raw = self._request('corpCode.xml', {}, binary=True)
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                xml = archive.read('CORPCODE.xml').decode('utf-8')
        except (zipfile.BadZipFile, KeyError, UnicodeDecodeError) as exc:
            raise OpenDartError('Invalid corpCode ZIP payload') from exc
        import xml.etree.ElementTree as ET
        root = ET.fromstring(xml)
        rows: list[dict[str, str]] = []
        for item in root.findall('list'):
            rows.append({child.tag: (child.text or '').strip() for child in item})
        return rows

    def write_disclosure_snapshot(self, path: Path | str, disclosures: list[Disclosure]) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps([d.__dict__ for d in disclosures], ensure_ascii=False, indent=2), encoding='utf-8')
        return target
