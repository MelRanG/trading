"""Small, fail-closed incremental updater for the active ETF CSV contract.

This is an adapter over the repository's already staged Toss-adjusted candle
artifact.  It does not create an ingestion framework or download history.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import shutil
import tempfile
from typing import Any

import pandas as pd
from zoneinfo import ZoneInfo

from quant_harness.v72_integration_ready.toss_openapi import TossOpenApiClient
from quant_harness.v87_actual_data_ingestion.engine import (
    IngestionError,
    ProviderBatch,
    TossGatewayProvider,
    _load_config as _load_v87_config,
    _revision_audit as _v87_revision_audit,
    _validate_batch as _validate_v87_batch,
)


REQUIRED_SOURCE = "toss_openapi_1d_adjusted"
ETF_COLUMNS = [
    "timestamp", "ticker", "asset_type", "open", "high", "low", "close",
    "volume", "currency", "source",
]
PRICE_COLUMNS = ["open", "high", "low", "close", "volume"]
KS11_OHLC_COLUMNS = ["open", "high", "low", "close"]
KS11_COMPARE_COLUMNS = ["open", "high", "low", "close", "adj_close"]


class IncrementalUpdateError(RuntimeError):
    pass


@dataclass(frozen=True)
class UpdateResult:
    cutoff: str
    symbols: int
    succeeded: int
    failed: tuple[dict[str, str], ...]
    rows_added: int
    rows_added_by_symbol: dict[str, int]
    backup_dir: str
    provider: str
    endpoint: str


def _dates(frame: pd.DataFrame, column: str = "timestamp") -> pd.Series:
    if column in frame:
        values = frame[column]
    elif "timestamp" in frame:
        values = frame["timestamp"]
    else:
        values = frame["date"]
    return pd.to_datetime(values, errors="raise", utc=True).dt.tz_convert("Asia/Seoul").dt.tz_localize(None).dt.normalize()


def _latest_completed_toss_trading_day(client: Any, *, now: datetime | None = None) -> str:
    """Resolve the latest completed KRX session from Toss's live calendar snapshot.

    Keep the current session incomplete until five minutes after the official
    regular-session close, so a still-forming daily candle is never appended.
    """
    kst = ZoneInfo("Asia/Seoul")
    current = now or datetime.now(kst)
    if current.tzinfo is None or current.utcoffset() is None:
        raise IncrementalUpdateError("market-calendar evaluation time must be timezone-aware")
    current = current.astimezone(kst)
    today = current.date().isoformat()
    rows = client.get_market_calendar(
        market="KR", start_date=(current.date() - timedelta(days=14)).isoformat(),
        end_date=(current.date() + timedelta(days=14)).isoformat(),
    )
    by_date = {str(row.get("date", ""))[:10]: row for row in rows if row.get("date")}
    today_row = by_date.get(today)
    if today_row is None:
        raise IncrementalUpdateError("Toss market calendar did not include the current KST date")
    previous = [
        session for session, row in by_date.items()
        if session < today and row.get("is_open") is True
    ]
    if not previous:
        raise IncrementalUpdateError("Toss market calendar did not include a previous open session")
    latest_completed = max(previous)
    if today_row.get("is_open") is True:
        raw_end = today_row.get("regular_market_end")
        if not raw_end:
            raise IncrementalUpdateError("Toss market calendar omitted today's regular-market end time")
        try:
            end_text = str(raw_end)
            if "T" in end_text:
                close_at = datetime.fromisoformat(end_text.replace("Z", "+00:00"))
                close_at = close_at.replace(tzinfo=kst) if close_at.tzinfo is None else close_at.astimezone(kst)
                if close_at.date() != current.date():
                    raise ValueError("regular-market close date differs from current session")
            else:
                close_time = time.fromisoformat(end_text)
                close_at = datetime.combine(current.date(), close_time, tzinfo=kst)
        except ValueError as exc:
            raise IncrementalUpdateError("Toss market calendar returned an invalid regular-market end time") from exc
        if current >= close_at + timedelta(minutes=5):
            latest_completed = today
    return latest_completed


def _validate_ohlc(frame: pd.DataFrame, symbol: str) -> None:
    missing = set(PRICE_COLUMNS) - set(frame.columns)
    if missing:
        raise IncrementalUpdateError(f"{symbol}: missing columns {sorted(missing)}")
    numeric = frame[PRICE_COLUMNS].apply(pd.to_numeric, errors="coerce")
    if numeric.isna().any().any() or (numeric[["open", "high", "low", "close"]] <= 0).any().any():
        raise IncrementalUpdateError(f"{symbol}: invalid numeric OHLC")
    bad = (
        numeric["high"] < numeric[["open", "close"]].max(axis=1)
    ) | (numeric["low"] > numeric[["open", "close"]].min(axis=1))
    if bad.any():
        raise IncrementalUpdateError(f"{symbol}: OHLC geometry violation")


def _validate_ks11_ohlc(frame: pd.DataFrame, symbol: str) -> None:
    """KS11 is a price-only benchmark; ETF volume validation remains separate."""
    missing = set(KS11_OHLC_COLUMNS) - set(frame.columns)
    if missing:
        raise IncrementalUpdateError(f"{symbol}: missing columns {sorted(missing)}")
    numeric = frame[KS11_OHLC_COLUMNS].apply(pd.to_numeric, errors="coerce")
    if numeric.isna().any().any() or (numeric <= 0).any().any():
        raise IncrementalUpdateError(f"{symbol}: invalid numeric OHLC")
    bad = (
        numeric["high"] < numeric[["open", "close"]].max(axis=1)
    ) | (numeric["low"] > numeric[["open", "close"]].min(axis=1))
    if bad.any():
        raise IncrementalUpdateError(f"{symbol}: OHLC geometry violation")


def _merge_symbol(existing: pd.DataFrame, incoming: pd.DataFrame, symbol: str) -> tuple[pd.DataFrame, int]:
    """Merge without changing overlapping rows; preserve the existing order."""
    if existing.empty:
        raise IncrementalUpdateError(f"{symbol}: existing file is empty")
    old = existing.copy()
    new = incoming.copy()
    old["_date"] = _dates(old)
    new["_date"] = _dates(new, "date")
    if old["_date"].duplicated().any() or new["_date"].duplicated().any():
        raise IncrementalUpdateError(f"{symbol}: duplicate date")
    _validate_ohlc(new, symbol)
    overlap = old.merge(new, on="_date", how="inner", suffixes=("_old", "_new"))
    for col in PRICE_COLUMNS:
        if not (pd.to_numeric(overlap[f"{col}_old"], errors="coerce") == pd.to_numeric(overlap[f"{col}_new"], errors="coerce")).all():
            raise IncrementalUpdateError(f"{symbol}: overlap price conflict")
    old_max = old["_date"].max()
    append = new[new["_date"] > old_max].copy()
    if not append.empty and (append["_date"] <= old_max).any():
        raise IncrementalUpdateError(f"{symbol}: non-incremental request")
    descending = old["_date"].is_monotonic_decreasing
    append = append.sort_values("_date", ascending=not descending).drop(columns=["_date"])
    if append.empty:
        return existing.copy(), 0
    # Existing files are newest-first.  Prepending keeps their byte-level
    # historical rows and the established file convention intact.
    merged = pd.concat([append, existing], ignore_index=True) if descending else pd.concat([existing, append], ignore_index=True)
    return merged[existing.columns], len(append)


def _source_rows(source: pd.DataFrame, symbol: str) -> pd.DataFrame:
    rows = source[source["ticker"].astype(str).str.strip().eq(symbol)].copy()
    rows["date"] = pd.to_datetime(rows["date"], errors="raise").dt.strftime("%Y-%m-%d")
    rows = rows[rows["source"].eq(REQUIRED_SOURCE)].copy()
    return rows


def _validate_v87_revision_gate(
    root: Path,
    plans: list[tuple[str, Path, pd.DataFrame, pd.DataFrame]],
) -> dict[str, Any]:
    """Apply the existing V87 canonical contract and revision gate before ETF writes."""
    cfg = _load_v87_config(root)
    frames: list[pd.DataFrame] = []
    for symbol, _path, _existing, merged in plans:
        rows = merged.copy()
        rows["date"] = _dates(rows).dt.strftime("%Y-%m-%d")
        rows["ticker"] = symbol
        rows["value_approx"] = pd.to_numeric(rows["close"], errors="coerce") * pd.to_numeric(rows["volume"], errors="coerce")
        payload = rows[["date", "ticker", "open", "high", "low", "close", "volume", "value_approx"]]
        batch = ProviderBatch(
            provider="TOSS_INCREMENTAL_CANONICAL",
            symbol=symbol,
            rows=tuple(payload.to_dict("records")),
            adjusted_ohlc_verified=True,
            source_tag=REQUIRED_SOURCE,
            retrieved_at=datetime.now(timezone.utc).isoformat(),
            raw_metadata={"canonical_rows": len(payload)},
        )
        frames.append(_validate_v87_batch(batch, cfg))
    canonical = pd.concat(frames, ignore_index=True).sort_values(["date", "ticker"]).reset_index(drop=True)
    if canonical.duplicated(["date", "ticker"]).any():
        raise IncrementalUpdateError("V87 canonical duplicate date/ticker rows")
    revision = _v87_revision_audit(canonical, root / cfg["paths"]["reference_canonical"], cfg)
    if not revision.get("passed"):
        raise IngestionError(f"V87 revision gate failed: {revision}")
    return revision


def run_incremental_update(root: Path | str, *, write_output: bool = True) -> UpdateResult:
    root = Path(root)
    data_dir = root / "data/toss_v19c_daily"
    source_path = root / "data/all_prices_long_v62_9_expanded.csv"
    universe = pd.read_csv(data_dir / "universe.csv", dtype={"ticker": str})
    symbols = sorted(universe["ticker"].astype(str).str.zfill(6).unique())
    source = pd.read_csv(source_path, dtype={"ticker": str})
    required = {"date", "ticker", *PRICE_COLUMNS, "source"}
    if not required.issubset(source.columns):
        raise IncrementalUpdateError("staged candle source schema mismatch")
    source["ticker"] = source["ticker"].astype(str).str.strip()
    source.loc[source["ticker"].str.isnumeric(), "ticker"] = source.loc[source["ticker"].str.isnumeric(), "ticker"].str.zfill(6)
    source["date"] = pd.to_datetime(source["date"], errors="raise").dt.strftime("%Y-%m-%d")
    source_rows = {symbol: _source_rows(source, symbol) for symbol in symbols}
    if any(frame.empty for frame in source_rows.values()):
        missing = [symbol for symbol, frame in source_rows.items() if frame.empty]
        raise IncrementalUpdateError(f"missing staged source: {','.join(missing)}")
    benchmark = source[(source["ticker"].eq("KS11")) & source["source"].isin({"FinanceDataReader", "toss_openapi_1d_adjusted"})].copy()
    if benchmark.empty:
        raise IncrementalUpdateError("KS11: benchmark source is unavailable")
    cutoff = min(pd.to_datetime(frame["date"]).max() for frame in source_rows.values())
    cutoff = min(cutoff, pd.to_datetime(benchmark["date"]).max())
    cutoff_text = cutoff.strftime("%Y-%m-%d")
    plans: list[tuple[str, Path, pd.DataFrame, pd.DataFrame]] = []
    failures: list[dict[str, str]] = []
    for symbol in symbols:
        path = data_dir / f"{symbol}_1d.csv"
        try:
            existing = pd.read_csv(path, dtype={"ticker": str})
            old_dates = _dates(existing)
            frame = source_rows[symbol][pd.to_datetime(source_rows[symbol]["date"]) <= cutoff].copy()
            # Include the overlap window so a changed historical value blocks
            # the run; _merge_symbol appends only rows after the old cutoff.
            incoming = frame.copy()
            incoming["ticker"] = symbol
            incoming["asset_type"] = "etf"
            incoming["currency"] = "KRW"
            incoming = incoming.rename(columns={"date": "_date_text"})
            incoming["date"] = incoming.pop("_date_text")
            incoming["timestamp"] = incoming["date"] + "T00:00:00.000+09:00"
            incoming = incoming[ETF_COLUMNS]
            merged, added = _merge_symbol(existing, incoming, symbol)
            plans.append((symbol, path, existing, merged))
        except Exception as exc:
            failures.append({"symbol": symbol, "reason": str(exc)})
    if failures:
        return UpdateResult(cutoff_text, len(symbols), 0, tuple(failures), 0, {}, "", "staged_toss_adjusted_candles", "GET /api/v1/candles")
    try:
        _validate_v87_revision_gate(root, plans)
    except Exception as exc:
        return UpdateResult(
            cutoff_text, len(symbols), 0,
            ({"symbol": "V87_CANONICAL", "reason": str(exc)},),
            0, {}, "", "staged_toss_adjusted_candles", "GET /api/v1/candles",
        )
    backup_dir = Path(tempfile.mkdtemp(prefix="active_market_data_"))
    # Back up all target CSVs, even when a symbol has no new row, so rollback is complete.
    for symbol in symbols:
        path = data_dir / f"{symbol}_1d.csv"
        shutil.copy2(path, backup_dir / path.name)
    rows_added_by_symbol: dict[str, int] = {}
    try:
        for symbol, path, existing, merged in plans:
            added = len(merged) - len(existing)
            rows_added_by_symbol[symbol] = added
            if write_output and added:
                tmp = path.with_suffix(path.suffix + ".tmp")
                merged.to_csv(tmp, index=False)
                tmp.replace(path)
    except Exception:
        for symbol in symbols:
            shutil.copy2(backup_dir / f"{symbol}_1d.csv", data_dir / f"{symbol}_1d.csv")
        raise
    return UpdateResult(
        cutoff_text, len(symbols), len(plans), tuple(), sum(rows_added_by_symbol.values()),
        rows_added_by_symbol, str(backup_dir), "staged_toss_adjusted_candles", "GET /api/v1/candles",
    )


def run_toss_incremental_update(
    root: Path | str,
    *,
    write_output: bool = True,
    as_of: str | None = None,
) -> UpdateResult:
    """Fetch only post-cutoff daily candles through the existing Toss GET adapter."""
    root = Path(root)
    data_dir = root / "data/toss_v19c_daily"
    universe = pd.read_csv(data_dir / "universe.csv", dtype={"ticker": str})
    symbols = sorted(universe["ticker"].astype(str).str.zfill(6).unique())
    client = TossOpenApiClient()
    end = pd.Timestamp(as_of).date().isoformat() if as_of else _latest_completed_toss_trading_day(client)
    provider = TossGatewayProvider(client, adjusted_ohlc_verified=True)
    plans: list[tuple[str, Path, pd.DataFrame, pd.DataFrame]] = []
    failures: list[dict[str, str]] = []
    cutoffs: list[pd.Timestamp] = []
    for symbol in symbols:
        path = data_dir / f"{symbol}_1d.csv"
        try:
            existing = pd.read_csv(path, dtype={"ticker": str})
            old_max = _dates(existing).max().date()
            start = old_max + timedelta(days=1)
            batch = provider.get_daily_batch(symbol, start_date=start.isoformat(), end_date=end)
            incoming = pd.DataFrame(batch.rows)
            if incoming.empty:
                incoming = pd.DataFrame(columns=["date", *PRICE_COLUMNS, "ticker", "source"])
            incoming["ticker"] = symbol
            incoming["asset_type"] = "etf"
            incoming["currency"] = "KRW"
            incoming["source"] = REQUIRED_SOURCE
            for column in PRICE_COLUMNS:
                if pd.api.types.is_integer_dtype(existing[column].dtype):
                    incoming[column] = pd.to_numeric(incoming[column], errors="raise").round().astype(existing[column].dtype)
            incoming["timestamp"] = pd.to_datetime(incoming["date"], errors="raise").dt.strftime("%Y-%m-%d") + "T00:00:00.000+09:00"
            incoming = incoming[["timestamp", "ticker", "asset_type", *PRICE_COLUMNS, "currency", "source"]]
            merged, _ = _merge_symbol(existing, incoming, symbol)
            plans.append((symbol, path, existing, merged))
            cutoffs.append(_dates(merged).max())
        except Exception as exc:
            failures.append({"symbol": symbol, "reason": str(exc)})
    if failures:
        return UpdateResult(
            min((d.strftime("%Y-%m-%d") for d in cutoffs), default=""), len(symbols), 0,
            tuple(failures), 0, {}, "", "toss_openapi_adjusted", "GET /api/v1/candles",
        )
    try:
        _validate_v87_revision_gate(root, plans)
    except Exception as exc:
        return UpdateResult(
            min((d.strftime("%Y-%m-%d") for d in cutoffs), default=""), len(symbols), 0,
            ({"symbol": "V87_CANONICAL", "reason": str(exc)},),
            0, {}, "", "toss_openapi_adjusted", "GET /api/v1/candles",
        )
    backup_dir = Path(tempfile.mkdtemp(prefix="active_market_data_toss_"))
    for symbol in symbols:
        shutil.copy2(data_dir / f"{symbol}_1d.csv", backup_dir / f"{symbol}_1d.csv")
    rows_added_by_symbol: dict[str, int] = {}
    try:
        for symbol, path, existing, merged in plans:
            added = len(merged) - len(existing)
            rows_added_by_symbol[symbol] = added
            if write_output and added:
                tmp = path.with_suffix(path.suffix + ".tmp")
                merged.to_csv(tmp, index=False)
                tmp.replace(path)
    except Exception:
        for symbol in symbols:
            shutil.copy2(backup_dir / f"{symbol}_1d.csv", data_dir / f"{symbol}_1d.csv")
        raise
    cutoff = min(_dates(merged).max() for _, _, _, merged in plans).strftime("%Y-%m-%d")
    return UpdateResult(
        cutoff, len(symbols), len(plans), tuple(), sum(rows_added_by_symbol.values()),
        rows_added_by_symbol, str(backup_dir), "toss_openapi_adjusted", "GET /api/v1/candles",
    )


def run_toss_market_indicator_ks11_update(
    root: Path | str,
    *,
    write_output: bool = True,
    as_of: str | None = None,
) -> UpdateResult:
    """Probe the documented indicator catalog and append KOSPI candles to KS11.

    The returned indicator symbol is selected from the API response.  The
    KOSPI/KOSDAQ values passed to the prices endpoint are only the documented
    catalog probe; no stock-candle endpoint is used for the index.
    """
    root = Path(root)
    source_path = root / "data/all_prices_long_v62_9_expanded.csv"
    existing = pd.read_csv(source_path, dtype={"ticker": str})
    existing = existing[existing["ticker"].eq("KS11")].copy()
    if existing.empty:
        return UpdateResult("", 1, 0, ({"symbol": "KS11", "reason": "existing KS11 history is empty"},), 0, {}, "", "toss_market_indicator", "GET /api/v1/market-indicators/{symbol}/candles")
    old_dates = pd.to_datetime(existing["date"], errors="raise").dt.normalize()
    if old_dates.duplicated().any():
        return UpdateResult(str(old_dates.max().date()), 1, 0, ({"symbol": "KS11", "reason": "duplicate existing date"},), 0, {}, "", "toss_market_indicator", "GET /api/v1/market-indicators/{symbol}/candles")
    old_max = old_dates.max().date()
    client = TossOpenApiClient()
    end_text = pd.Timestamp(as_of).date().isoformat() if as_of else _latest_completed_toss_trading_day(client)
    end = pd.Timestamp(end_text).date()
    endpoint = "GET /api/v1/market-indicators/{symbol}/candles"
    try:
        catalog = client.get_market_indicator_prices(["KOSPI", "KOSDAQ"])
        indicators = [row for row in catalog if str(row.get("symbol", "")).strip()]
        kospi = next((row for row in indicators if str(row["symbol"]).upper() == "KOSPI"), None)
        if kospi is None:
            raise IncrementalUpdateError("KOSPI market-indicator symbol was not returned by the catalog")
        indicator_symbol = str(kospi["symbol"])
        before = f"{end.isoformat()}T23:59:59+09:00"
        fetched: list[dict[str, Any]] = []
        while True:
            rows, next_before = client.get_market_indicator_candles_page(indicator_symbol, interval="1d", count=200, before=before)
            fetched.extend(rows)
            dates = [pd.Timestamp(row["timestamp"]).date() for row in rows]
            if not dates or min(dates) <= old_max or not next_before:
                break
            before = next_before
        if not fetched:
            raise IncrementalUpdateError(f"{indicator_symbol}: no daily candles returned")
        incoming = pd.DataFrame(fetched)
        incoming["date"] = pd.to_datetime(incoming["timestamp"], errors="raise", utc=True).dt.tz_convert("Asia/Seoul").dt.tz_localize(None).dt.strftime("%Y-%m-%d")
        incoming = incoming.rename(columns={"symbol": "indicator_symbol"})
        incoming["ticker"] = "KS11"
        for col in KS11_OHLC_COLUMNS:
            incoming[col] = pd.to_numeric(incoming[col], errors="coerce")
        if incoming[KS11_OHLC_COLUMNS].isna().any().any():
            raise IncrementalUpdateError(f"{indicator_symbol}: daily OHLC response is incomplete")
        _validate_ks11_ohlc(incoming, indicator_symbol)
        incoming["adj_close"] = incoming["close"]
        overlap = existing.merge(incoming[["date", *KS11_COMPARE_COLUMNS]], on="date", how="inner", suffixes=("_old", "_new"))
        for col in KS11_COMPARE_COLUMNS:
            left = pd.to_numeric(overlap[f"{col}_old"], errors="coerce")
            right = pd.to_numeric(overlap[f"{col}_new"], errors="coerce")
            mismatch = ~((left - right).abs() <= 1e-3)
            if mismatch.any():
                bad_date = str(overlap.loc[mismatch, "date"].iloc[0])
                raise IncrementalUpdateError(f"{indicator_symbol}: overlap {col} conflict on {bad_date}")
        if incoming["date"].duplicated().any():
            raise IncrementalUpdateError(f"{indicator_symbol}: duplicate fetched date")
        # Canonical KS11 is price-only.  Toss indicator volume is intentionally
        # discarded: it is non-authoritative and must never feed strategy or ADV.
        incoming["volume"] = pd.NA
        append = incoming[pd.to_datetime(incoming["date"]).dt.date > old_max].copy()
        append = append[pd.to_datetime(append["date"]).dt.date <= end]
        if append.empty:
            return UpdateResult(str(max(old_max, max(pd.to_datetime(incoming["date"]).dt.date))), 1, 1, tuple(), 0, {"KS11": 0}, "", "toss_market_indicator", endpoint)
        # Preserve the established wide CSV contract without inventing fields
        # that the market-indicator response does not provide.
        last = existing.iloc[-1]
        for col in existing.columns:
            if col not in append.columns:
                append[col] = last[col] if col in {"name", "group", "sector", "asset_type"} else None
        append["source"] = "toss_market_indicator"
        append = append[existing.columns].sort_values("date")
        merged = pd.concat([existing, append], ignore_index=True)
        backup_dir = Path(tempfile.mkdtemp(prefix="active_market_indicator_"))
        shutil.copy2(source_path, backup_dir / source_path.name)
        if write_output:
            tmp = source_path.with_suffix(source_path.suffix + ".tmp")
            full = pd.read_csv(source_path, dtype={"ticker": str})
            full = pd.concat([full, append], ignore_index=True)
            if full.duplicated(["date", "ticker"]).any():
                raise IncrementalUpdateError("KS11: duplicate date/ticker after append")
            full.to_csv(tmp, index=False)
            tmp.replace(source_path)
        return UpdateResult(str(pd.to_datetime(merged["date"]).max().date()), 1, 1, tuple(), len(append), {"KS11": len(append)}, str(backup_dir), "toss_market_indicator", endpoint)
    except Exception as exc:
        return UpdateResult(str(old_max), 1, 0, ({"symbol": "KS11", "reason": str(exc)},), 0, {}, "", "toss_market_indicator", endpoint)


def append_canonical(root: Path | str, cutoff: str, backup_dir: Path | str) -> int:
    """Append the already-validated active rows to the existing canonical artifact."""
    root = Path(root)
    backup_dir = Path(backup_dir)
    canonical_path = root / "data/canonical/v84_market_bars.csv"
    manifest_path = root / "data/canonical/v84_market_manifest.csv"
    shutil.copy2(canonical_path, backup_dir / canonical_path.name)
    shutil.copy2(manifest_path, backup_dir / manifest_path.name)
    canonical = pd.read_csv(canonical_path, dtype={"ticker": str})
    canonical_cutoff = pd.to_datetime(canonical["date"], errors="raise").max().strftime("%Y-%m-%d")
    universe = pd.read_csv(root / "data/toss_v19c_daily/universe.csv", dtype={"ticker": str})
    symbols = universe["ticker"].astype(str).str.zfill(6).tolist()
    additions: list[pd.DataFrame] = []
    for symbol in symbols:
        active_path = root / "data/toss_v19c_daily" / f"{symbol}_1d.csv"
        active = pd.read_csv(active_path, dtype={"ticker": str})
        active["date"] = pd.to_datetime(active["timestamp"], utc=True).dt.tz_convert("Asia/Seoul").dt.tz_localize(None).dt.strftime("%Y-%m-%d")
        existing_dates = set(canonical.loc[canonical["ticker"].astype(str).str.zfill(6).eq(symbol), "date"].astype(str))
        rows = active[(active["date"] > canonical_cutoff) & (active["date"] <= cutoff) & ~active["date"].isin(existing_dates)].copy()
        if rows.empty:
            continue
        additions.append(pd.DataFrame({
            "date": rows["date"], "ticker": symbol, "open": rows["open"], "high": rows["high"],
            "low": rows["low"], "close": rows["close"], "volume": rows["volume"],
            "value_approx": pd.to_numeric(rows["close"]) * pd.to_numeric(rows["volume"]),
            "source": rows["source"], "price_scale": "ADJUSTED_OHLC",
        }))
    added = pd.concat(additions, ignore_index=True) if additions else pd.DataFrame(columns=canonical.columns)
    if not added.empty:
        if added.duplicated(["date", "ticker"]).any():
            raise IncrementalUpdateError("canonical duplicate date/ticker")
        canonical = pd.concat([canonical, added[canonical.columns]], ignore_index=True)
        tmp = canonical_path.with_suffix(canonical_path.suffix + ".tmp")
        canonical.to_csv(tmp, index=False)
        tmp.replace(canonical_path)
    manifest_rows = []
    for symbol in symbols:
        active_path = root / "data/toss_v19c_daily" / f"{symbol}_1d.csv"
        active = pd.read_csv(active_path, dtype={"ticker": str})
        dates = pd.to_datetime(active["timestamp"], utc=True).dt.tz_convert("Asia/Seoul").dt.tz_localize(None)
        manifest_rows.append({
            "ticker": symbol, "rows": len(active), "start": dates.min().date().isoformat(),
            "end": dates.max().date().isoformat(), "source": REQUIRED_SOURCE,
            "sha256": sha256(active_path.read_bytes()).hexdigest(),
        })
    pd.DataFrame(manifest_rows).to_csv(manifest_path, index=False)
    return int(len(added))


__all__ = ["IncrementalUpdateError", "UpdateResult", "run_incremental_update", "run_toss_incremental_update", "run_toss_market_indicator_ks11_update", "append_canonical", "_merge_symbol"]
