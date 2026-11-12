"""Resumable, fail-closed collection of the frozen AS-OF 1-minute sessions.

This is deliberately a session collector, not a data platform.  It only
materializes the already frozen execution-safe symbol/date union and never
invokes a strategy or broker endpoint.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import tempfile
import time
from typing import Any

import pandas as pd
import yaml

from quant_harness.asof_5m_models import ASOF_CANDIDATES, BASE_CANDIDATES
from quant_harness.current_models_5m_validation import END, START, _run_daily
from quant_harness.three_model_backtest import _cache_path
from quant_harness.v104_end_to_end_causal_challenger_audit.adapter import build_candidate_ledgers, load_candidate_specs
from quant_harness.v72_integration_ready.toss_openapi import TossApiError, TossOpenApiClient
from quant_harness.open_5m_execution_validation import aggregate_regular_five_minute


KST = timezone(timedelta(hours=9))
OUTPUT = Path("runtime/asof_5m_models_validation")
MANIFEST = OUTPUT / "minute_collection_manifest.json"
STATUSES = {"COMPLETE", "PARTIAL", "FAILED_PERMANENT", "PENDING"}
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def target_set_hash(required: list[tuple[str, str]]) -> str:
    payload = "\n".join(f"{str(symbol).zfill(6)}:{session}" for symbol, session in sorted(required))
    return sha256(payload.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(tz=KST).isoformat()


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True, indent=2, default=str)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _atomic_csv(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            frame.to_csv(handle, index=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _session_key(symbol: str, session: str) -> str:
    return f"{str(symbol).zfill(6)}:{session}"


def _timestamp_series(frame: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(frame["timestamp"], utc=True).dt.tz_convert("Asia/Seoul")


def validate_complete_session(frame: pd.DataFrame, session: str) -> dict[str, Any]:
    """Validate the strict 390-row regular-session contract."""
    required = {"timestamp", "open", "high", "low", "close"}
    if not required.issubset(frame.columns):
        return {"ok": False, "reason": "INVALID_SCHEMA", "bar_count": 0}
    try:
        ts = _timestamp_series(frame)
    except Exception:
        return {"ok": False, "reason": "INVALID_TIMESTAMP", "bar_count": 0}
    expected = pd.date_range(f"{session} 09:01", f"{session} 15:30", freq="min", tz="Asia/Seoul")
    duplicate_count = int(ts.duplicated().sum())
    future_count = int((ts.dt.date > pd.Timestamp(session).date()).sum())
    numeric = frame[["open", "high", "low", "close"]].apply(pd.to_numeric, errors="coerce")
    positive = bool(numeric.notna().all().all() and (numeric > 0).all().all())
    ordered = bool(ts.is_monotonic_increasing)
    exact_timestamps = len(frame) == len(expected) and set(ts.tolist()) == set(expected.tolist())
    five_minute_ok = False
    if exact_timestamps and ordered and duplicate_count == 0:
        try:
            five_minute_ok = len(aggregate_regular_five_minute(frame, session)) == 78
        except Exception:
            five_minute_ok = False
    ok = bool(exact_timestamps and ordered and duplicate_count == 0 and future_count == 0 and positive and five_minute_ok)
    return {
        "ok": ok,
        "reason": None if ok else "SESSION_CONTRACT_FAILED",
        "bar_count": int(len(frame)),
        "first_timestamp": ts.iloc[0].isoformat() if len(ts) else None,
        "last_timestamp": ts.iloc[-1].isoformat() if len(ts) else None,
        "duplicate_timestamp": duplicate_count,
        "future_bars": future_count,
        "ordered": ordered,
        "price_fields_valid": positive,
        "five_minute_bars": 78 if five_minute_ok else 0,
    }


def _is_complete(path: Path, session: str) -> tuple[bool, dict[str, Any]]:
    if not path.is_file():
        return False, {"ok": False, "reason": "CACHE_MISSING"}
    try:
        frame = pd.read_csv(path, dtype={"symbol": str})
        result = validate_complete_session(frame, session)
        return bool(result["ok"]), result
    except Exception as exc:
        return False, {"ok": False, "reason": type(exc).__name__}


def required_symbol_dates(root: Path) -> list[tuple[str, str]]:
    """Build the execution-safe symbol/date Cartesian product offline."""
    specs = load_candidate_specs(root)
    symbols: set[str] = set()
    periods: list[pd.DatetimeIndex] = []
    for base_id in BASE_CANDIDATES:
        built = build_candidate_ledgers(root, specs[base_id], use_common_cutoff=True)
        period = built["market"]["close"].index
        period = period[(period >= START) & (period <= END)]
        periods.append(period)
        elig = built["f69"]["eligible"] if base_id.startswith("V69") else built["f79"]["eligible"]
        eligible = elig.reindex(period).fillna(False)
        symbols.update(str(symbol).zfill(6) for symbol in eligible.columns[eligible.any(axis=0)])
        symbols.add(str(built["cfg77"].core_ticker).zfill(6))
        ledger = built["ledger"].copy()
        ledger["date"] = pd.to_datetime(ledger["date"])
        ledger = ledger[ledger["date"].isin(period)]
        for raw in ledger["target_weights_json"]:
            symbols.update(str(symbol).zfill(6) for symbol in json.loads(str(raw)).keys())
    if not periods:
        return []
    common_period = periods[0]
    for period in periods[1:]:
        common_period = common_period.intersection(period)
    return sorted((symbol, session.date().isoformat()) for symbol in sorted(symbols) for session in common_period)


def _load_or_initialize(root: Path, required: list[tuple[str, str]], *, resume: bool) -> dict[str, Any]:
    path = root / MANIFEST
    prior_manifest: dict[str, Any] | None = None
    if resume and path.is_file():
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
            prior_manifest = manifest
            if int(manifest.get("target_count", -1)) == len(required):
                for entry in manifest.get("sessions", {}).values():
                    cache = root / _cache_path(root, entry["symbol"], entry["date"]).relative_to(root)
                    complete, validation = _is_complete(cache, entry["date"])
                    entry["status"] = "COMPLETE" if complete else ("PARTIAL" if cache.is_file() else "PENDING")
                    entry["bar_count"] = int(validation.get("bar_count", 0))
                    entry["validation"] = validation
                manifest["schema"] = "ASOF_5M_RESUMABLE_COLLECTION_V2_EXECUTION_SAFE"
                manifest["schema_version"] = manifest["schema"]
                manifest["target_set_hash"] = target_set_hash(required)
                return manifest
        except Exception:
            pass
    sessions: dict[str, dict[str, Any]] = {}
    for symbol, session in required:
        complete, validation = _is_complete(root / _cache_path(root, symbol, session).relative_to(root), session)
        sessions[_session_key(symbol, session)] = {
            "symbol": symbol,
            "date": session,
            "status": "COMPLETE" if complete else ("PARTIAL" if (root / _cache_path(root, symbol, session).relative_to(root)).is_file() else "PENDING"),
            "bar_count": validation.get("bar_count", 0),
            "validation": validation,
            "last_update": _now(),
        }
    manifest = {
        "schema": "ASOF_5M_RESUMABLE_COLLECTION_V2_EXECUTION_SAFE",
        "schema_version": "ASOF_5M_RESUMABLE_COLLECTION_V2_EXECUTION_SAFE",
        "scope": {"start": START.date().isoformat(), "end": END.date().isoformat(), "interval": "1m", "adjusted": True},
        "target_count": len(required),
        "target_set_hash": target_set_hash(required),
        "status": "MINUTE_DATA_COLLECTION_IN_PROGRESS",
        "sessions": sessions,
        "statistics": dict((prior_manifest or {}).get("statistics", {"total": 0, "GET": 0, "POST": 0, "status": {}, "rate_limit_429": 0, "retry": 0, "newly_completed": 0, "last_completed": None})),
        "started_at": _now(),
        "last_update": _now(),
    }
    if prior_manifest:
        manifest["started_at"] = prior_manifest.get("started_at", manifest["started_at"])
    return manifest


def _transport_counter(existing: dict[str, Any]):
    counts = existing

    def transport(request, timeout):
        method = request.get_method().upper()
        counts["total"] = int(counts.get("total", 0)) + 1
        counts[method] = int(counts.get(method, 0)) + 1
        status, headers, body = TossOpenApiClient._default_transport(request, timeout)
        status_map = counts.setdefault("status", {})
        status_map[str(status)] = int(status_map.get(str(status), 0)) + 1
        if status == 429:
            counts["rate_limit_429"] = int(counts.get("rate_limit_429", 0)) + 1
        if status in RETRYABLE_STATUS:
            counts["retry"] = int(counts.get("retry", 0)) + 1
        return status, headers, body

    return transport


def _permanent_error(exc: Exception) -> bool:
    match = re.search(r"status\s+(\d{3})", str(exc), flags=re.IGNORECASE)
    if not match:
        return False
    status = int(match.group(1))
    return 400 <= status < 500 and status != 429


def _fetch_atomic(client: TossOpenApiClient, root: Path, symbol: str, session: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    before = f"{session}T23:59:59+09:00"
    seen_before: set[str] = set()
    pages = 0
    while True:
        if before in seen_before:
            raise TossApiError("pagination cursor did not progress")
        seen_before.add(before)
        page, next_before = client.get_intraday_candles_page(symbol, before=before, interval="1m", count=200)
        pages += 1
        rows.extend(row for row in page if str(pd.to_datetime(row["timestamp"], utc=True).tz_convert("Asia/Seoul").date()) == session)
        if not page or not next_before:
            break
        page_dates = [str(pd.to_datetime(row["timestamp"], utc=True).tz_convert("Asia/Seoul").date()) for row in page]
        if min(page_dates) < session:
            break
        if str(next_before) == before:
            raise TossApiError("pagination cursor did not progress")
        before = str(next_before)
    unique = {str(row["timestamp"]): row for row in rows}
    if not unique:
        raise TossApiError(f"no 1m candle rows for {symbol} {session}")
    frame = pd.DataFrame(sorted(unique.values(), key=lambda row: str(row["timestamp"])))
    validation = validate_complete_session(frame, session)
    if not validation["ok"]:
        raise TossApiError(f"session contract failed: {validation.get('reason')}")
    path = root / _cache_path(root, symbol, session).relative_to(root)
    _atomic_csv(path, frame)
    return frame, {"api_pages": pages, "bar_count": len(frame), "validation": validation}


def _progress(manifest: dict[str, Any], started: float) -> str:
    rows = list(manifest["sessions"].values())
    counts = {status: sum(row.get("status") == status for row in rows) for status in STATUSES}
    total = len(rows)
    complete = counts["COMPLETE"]
    elapsed = max(0.0, time.monotonic() - started)
    return (f"target={total} COMPLETE={complete} PARTIAL={counts['PARTIAL']} "
            f"FAILED_PERMANENT={counts['FAILED_PERMANENT']} PENDING={counts['PENDING']} "
            f"coverage={complete / total:.4%} newly={manifest['statistics'].get('newly_completed', 0)} "
            f"GET={manifest['statistics'].get('GET', 0)} 429={manifest['statistics'].get('rate_limit_429', 0)} "
            f"retry={manifest['statistics'].get('retry', 0)} last={manifest['statistics'].get('last_completed')} "
            f"elapsed={elapsed / 60:.1f}m")


def collect(root: Path | str, *, resume: bool = False, max_sessions: int | None = None, max_runtime_minutes: float | None = None, stop_on_permanent_error: bool = False) -> dict[str, Any]:
    root = Path(root).resolve()
    try:
        from dotenv import load_dotenv
        load_dotenv(root / ".env")
    except Exception:
        pass
    existing_manifest = root / MANIFEST
    required = required_symbol_dates(root)
    manifest = _load_or_initialize(root, required, resume=True)
    started = time.monotonic()
    transport = _transport_counter(manifest["statistics"])
    client = TossOpenApiClient(transport=transport)
    processed = 0
    stop_reason = "COMPLETED"

    def persist() -> None:
        manifest["last_update"] = _now()
        rows = list(manifest["sessions"].values())
        manifest["status"] = "MINUTE_DATA_COLLECTION_COMPLETE" if all(row.get("status") == "COMPLETE" for row in rows) else "MINUTE_DATA_COLLECTION_IN_PROGRESS"
        _atomic_json(root / MANIFEST, manifest)
        print(_progress(manifest, started), flush=True)

    persist()
    try:
        for key, entry in manifest["sessions"].items():
            if entry.get("status") == "COMPLETE":
                continue
            if max_sessions is not None and processed >= max_sessions:
                stop_reason = "MAX_SESSIONS"
                break
            if max_runtime_minutes is not None and (time.monotonic() - started) >= max_runtime_minutes * 60:
                stop_reason = "MAX_RUNTIME"
                break
            processed += 1
            symbol, session = entry["symbol"], entry["date"]
            entry["status"] = "PENDING"
            entry["last_update"] = _now()
            try:
                _, meta = _fetch_atomic(client, root, symbol, session)
                entry.update(meta)
                entry["status"] = "COMPLETE"
                entry["last_update"] = _now()
                manifest["statistics"]["newly_completed"] = int(manifest["statistics"].get("newly_completed", 0)) + 1
                manifest["statistics"]["last_completed"] = key
            except KeyboardInterrupt:
                entry["status"] = "PARTIAL"
                stop_reason = "INTERRUPTED"
                raise
            except Exception as exc:
                entry["status"] = "FAILED_PERMANENT" if _permanent_error(exc) else "PARTIAL"
                entry["error"] = type(exc).__name__ + (f": {exc}" if _permanent_error(exc) else "")
                entry["last_update"] = _now()
                if stop_on_permanent_error and entry["status"] == "FAILED_PERMANENT":
                    stop_reason = "PERMANENT_ERROR"
                    persist()
                    break
            persist()
    except KeyboardInterrupt:
        stop_reason = "INTERRUPTED"
        persist()
    manifest["stop_reason"] = stop_reason
    persist()
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Resume frozen AS-OF 1m session collection")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--max-sessions", type=int, default=None)
    parser.add_argument("--max-runtime-minutes", type=float, default=None)
    parser.add_argument("--stop-on-permanent-error", action="store_true")
    args = parser.parse_args(argv)
    collect(Path(__file__).resolve().parents[2], resume=args.resume, max_sessions=args.max_sessions, max_runtime_minutes=args.max_runtime_minutes, stop_on_permanent_error=args.stop_on_permanent_error)
    return 0


__all__ = ["collect", "main", "validate_complete_session", "required_symbol_dates"]
