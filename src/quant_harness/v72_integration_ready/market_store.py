from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Iterable

import pandas as pd

REQUIRED_COLUMNS = ['date', 'ticker', 'open', 'high', 'low', 'adj_close', 'volume', 'value_approx', 'source']


def normalize_ticker(value: object) -> str:
    text = str(value).strip().replace('.0', '')
    return text.zfill(6) if text.isdigit() and len(text) <= 6 else text


@dataclass(frozen=True)
class MarketStoreResult:
    accepted_rows: int
    duplicate_rows_removed: int
    min_date: str | None
    max_date: str | None
    target: str


def validate_bars(frame: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise ValueError(f'missing market bar columns: {missing}')
    out = frame[REQUIRED_COLUMNS].copy()
    out['ticker'] = out['ticker'].map(normalize_ticker)
    out['date'] = pd.to_datetime(out['date'], errors='raise').dt.strftime('%Y-%m-%d')
    for col in ['open', 'high', 'low', 'adj_close', 'volume', 'value_approx']:
        out[col] = pd.to_numeric(out[col], errors='raise')
    if out[['open', 'high', 'low', 'adj_close']].le(0).any().any():
        raise ValueError('OHLC prices must be positive')
    if out[['volume', 'value_approx']].lt(0).any().any():
        raise ValueError('volume/value cannot be negative')
    if (out['high'] < out[['open', 'adj_close', 'low']].max(axis=1)).any():
        raise ValueError('high price is inconsistent')
    if (out['low'] > out[['open', 'adj_close', 'high']].min(axis=1)).any():
        raise ValueError('low price is inconsistent')
    if out[['date', 'ticker']].duplicated().any():
        raise ValueError('incoming bars contain duplicate date/ticker rows')
    return out.sort_values(['date', 'ticker']).reset_index(drop=True)


def _atomic_write_csv(frame: pd.DataFrame, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile('w', encoding='utf-8', newline='', delete=False, dir=target.parent, suffix='.tmp') as tmp:
        frame.to_csv(tmp.name, index=False)
        temp = Path(tmp.name)
    os.replace(temp, target)


def append_runtime_bars(target: Path | str, bars: pd.DataFrame | Iterable[dict]) -> MarketStoreResult:
    target = Path(target)
    incoming = validate_bars(pd.DataFrame(list(bars)) if not isinstance(bars, pd.DataFrame) else bars)
    if target.exists():
        existing = validate_bars(pd.read_csv(target))
        existing['_batch_priority'] = 0
        incoming = incoming.copy()
        incoming['_batch_priority'] = 1
        combined = pd.concat([existing, incoming], ignore_index=True)
    else:
        combined = incoming.copy()
        combined['_batch_priority'] = 1
    before = len(combined)
    # The newly validated batch always wins. Source names are audit metadata, not precedence rules.
    combined = (combined.sort_values(['date', 'ticker', '_batch_priority'])
                .drop_duplicates(['date', 'ticker'], keep='last'))
    removed = before - len(combined)
    _atomic_write_csv(combined[REQUIRED_COLUMNS], target)
    return MarketStoreResult(
        accepted_rows=len(incoming), duplicate_rows_removed=removed,
        min_date=str(combined['date'].min()) if len(combined) else None,
        max_date=str(combined['date'].max()) if len(combined) else None,
        target=str(target),
    )


def build_merged_market_file(*, historical_file: Path | str, runtime_file: Path | str, output_file: Path | str) -> MarketStoreResult:
    historical_file, runtime_file, output_file = Path(historical_file), Path(runtime_file), Path(output_file)
    hist = pd.read_csv(historical_file, low_memory=False)
    needed = ['date', 'ticker', 'open', 'adj_close', 'value_approx']
    missing = [c for c in needed if c not in hist.columns]
    if missing:
        raise ValueError(f'historical market file missing {missing}')
    hist = hist.copy()
    hist['ticker'] = hist['ticker'].map(normalize_ticker)
    hist['date'] = pd.to_datetime(hist['date']).dt.strftime('%Y-%m-%d')
    hist['source'] = hist.get('source', 'HISTORICAL_BASE')
    for c in ['high', 'low']:
        if c not in hist.columns:
            hist[c] = hist['adj_close']
    if 'volume' not in hist.columns:
        hist['volume'] = 0.0
    hist = validate_bars(hist[REQUIRED_COLUMNS])
    runtime = validate_bars(pd.read_csv(runtime_file)) if runtime_file.exists() else pd.DataFrame(columns=REQUIRED_COLUMNS)
    hist['_batch_priority'] = 0
    runtime = runtime.copy()
    runtime['_batch_priority'] = 1
    combined = pd.concat([hist, runtime], ignore_index=True)
    before = len(combined)
    combined = (combined.sort_values(['date', 'ticker', '_batch_priority'])
                .drop_duplicates(['date', 'ticker'], keep='last'))
    _atomic_write_csv(combined[REQUIRED_COLUMNS], output_file)
    return MarketStoreResult(
        accepted_rows=len(runtime), duplicate_rows_removed=before-len(combined),
        min_date=str(combined['date'].min()), max_date=str(combined['date'].max()), target=str(output_file),
    )
