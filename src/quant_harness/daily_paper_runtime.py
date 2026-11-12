"""Minimal single-command daily Paper cycle with a fail-closed freshness gate."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from contextlib import contextmanager
from datetime import date, timedelta
from decimal import Decimal
import json
import os
from pathlib import Path
import threading
from typing import Any

import pandas as pd
import yaml

from quant_harness.active_market_data_update import (
    append_canonical,
    _latest_completed_toss_trading_day,
    run_toss_incremental_update,
    run_toss_market_indicator_ks11_update,
)
from quant_harness.paper_decision_runtime import build_strategy_preview, run_paper_decision_preview
from quant_harness.paper_execution_runtime import run_paper_execution_cycle
from quant_harness.paper_runtime_store import (
    ensure_paper_account,
    initialize_paper_schema,
    load_paper_account,
    save_daily_nav,
)
from quant_harness.v72_integration_ready.live_safety import (
    CURRENT_RELEASE_LIVE_AUTHORITY,
    LIVE_BUILD_CAPABILITY,
)
from quant_harness.v72_integration_ready.toss_openapi import TossOpenApiClient


FRESHNESS_STATES = frozenset({"FRESH", "STALE", "INCOMPLETE", "FAILED"})
REQUIRED_SOURCE = "toss_openapi_1d_adjusted"
_DAILY_CYCLE_PROCESS_LOCK = threading.Lock()


@contextmanager
def _daily_cycle_lock(root: Path | str):
    """Non-blocking process and OS file lock for a single daily cycle per workspace."""
    if not _DAILY_CYCLE_PROCESS_LOCK.acquire(blocking=False):
        yield "ALREADY_RUNNING"
        return

    lock_file = None
    lock_kind: str | None = None
    try:
        try:
            lock_path = Path(root).resolve() / "runtime" / "daily_paper_cycle.lock"
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            lock_file = lock_path.open("a+b")
            lock_file.seek(0, os.SEEK_END)
            if lock_file.tell() == 0:
                lock_file.write(b"\0")
                lock_file.flush()
            lock_file.seek(0)

            if os.name == "nt":
                import msvcrt

                try:
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                except OSError:
                    yield "ALREADY_RUNNING"
                    return
                lock_kind = "windows"
            else:
                import fcntl

                try:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    yield "ALREADY_RUNNING"
                    return
                lock_kind = "posix"
        except OSError:
            yield "LOCK_UNAVAILABLE"
            return
        yield "ACQUIRED"
    finally:
        try:
            if lock_file is not None:
                try:
                    if lock_kind == "windows":
                        import msvcrt

                        lock_file.seek(0)
                        msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                    elif lock_kind == "posix":
                        import fcntl

                        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                finally:
                    lock_file.close()
        finally:
            _DAILY_CYCLE_PROCESS_LOCK.release()


@dataclass(frozen=True)
class FreshnessResult:
    status: str
    cutoff: str | None
    symbol_count: int
    failures: tuple[str, ...]
    benchmark: str
    structural_completeness: str = "UNKNOWN"
    temporal_freshness: str = "UNKNOWN"
    latest_completed_date: str | None = None

    def __post_init__(self) -> None:
        if self.status not in FRESHNESS_STATES:
            raise ValueError(f"invalid freshness state: {self.status}")
        if self.structural_completeness == "UNKNOWN" and self.status in {"FRESH", "STALE"}:
            object.__setattr__(self, "structural_completeness", "PASSED")
        if self.temporal_freshness == "UNKNOWN" and self.status in {"FRESH", "STALE"}:
            object.__setattr__(self, "temporal_freshness", self.status)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_freshness_records(
    records: dict[str, dict[str, Any]],
    benchmark: dict[str, Any],
    *,
    expected_symbols: int = 26,
    run_date: date | None = None,
    latest_completed_date: str | None = None,
) -> FreshnessResult:
    failures: list[str] = []
    if len(records) != expected_symbols:
        failures.append(f"ETF_COUNT:{len(records)}/{expected_symbols}")
    for symbol, record in sorted(records.items()):
        if not record.get("valid", False):
            failures.append(f"ETF:{symbol}")
        if not record.get("last_date"):
            failures.append(f"ETF_MISSING_DATE:{symbol}")
    if not benchmark.get("valid", False):
        failures.append("KS11")
    if not benchmark.get("last_date"):
        failures.append("KS11_MISSING_DATE")
    if failures:
        state = "INCOMPLETE" if any("MISSING" in item or "COUNT" in item for item in failures) else "FAILED"
        structural = "INCOMPLETE" if state == "INCOMPLETE" else "FAILED"
        return FreshnessResult(state, None, len(records), tuple(failures), "KS11", structural, "UNKNOWN", None)
    cutoff = min([str(row["last_date"]) for row in records.values()] + [str(benchmark["last_date"])])
    latest = latest_completed_date or _latest_completed_business_day(run_date or date.today()).isoformat()
    temporal = "FRESH" if cutoff >= latest else "STALE"
    return FreshnessResult(temporal, cutoff, len(records), tuple(), "KS11", "PASSED", temporal, latest)


def _latest_completed_business_day(run_date: date) -> date:
    candidate = run_date - timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate -= timedelta(days=1)
    return candidate


def _parse_dates(values: pd.Series) -> pd.Series:
    return pd.to_datetime(values, errors="raise", utc=True).dt.tz_convert("Asia/Seoul").dt.tz_localize(None).dt.normalize()


def _valid_ohlc(frame: pd.DataFrame) -> bool:
    required = {"open", "high", "low", "close"}
    if not required.issubset(frame.columns) or frame.empty:
        return False
    numeric = frame[list(required)].apply(pd.to_numeric, errors="coerce")
    if numeric.isna().any().any() or (numeric <= 0).any().any():
        return False
    return bool(
        not (
            (numeric["high"] < numeric[["open", "close"]].max(axis=1))
            | (numeric["low"] > numeric[["open", "close"]].min(axis=1))
        ).any()
    )


def validate_market_freshness(
    root: Path | str, *, run_date: date | None = None, latest_completed_date: str | None = None,
) -> FreshnessResult:
    root = Path(root)
    if not latest_completed_date:
        return FreshnessResult(
            "FAILED", None, 0, ("OFFICIAL_MARKET_CALENDAR_CUTOFF_REQUIRED",),
            "KS11", "UNKNOWN", "UNKNOWN", None,
        )
    data_dir = root / "data/toss_v19c_daily"
    try:
        universe = pd.read_csv(data_dir / "universe.csv", dtype={"ticker": str})
    except Exception as exc:
        return FreshnessResult("INCOMPLETE", None, 0, (f"UNIVERSE:{type(exc).__name__}",), "KS11")
    symbols = sorted(universe["ticker"].astype(str).str.zfill(6).unique())
    records: dict[str, dict[str, Any]] = {}
    failures: list[str] = []
    for symbol in symbols:
        path = data_dir / f"{symbol}_1d.csv"
        if not path.is_file():
            records[symbol] = {"valid": False}
            continue
        try:
            frame = pd.read_csv(path, dtype={"ticker": str})
            dates = _parse_dates(frame["timestamp"])
            duplicate = bool(dates.duplicated().any())
            ordered = bool(dates.is_monotonic_increasing or dates.is_monotonic_decreasing)
            source_ok = set(frame.get("source", pd.Series(dtype=str)).dropna().astype(str).unique()) == {REQUIRED_SOURCE}
            valid = bool(not duplicate and ordered and source_ok and _valid_ohlc(frame))
            records[symbol] = {"valid": valid, "last_date": dates.max().date().isoformat()}
            if duplicate:
                failures.append(f"ETF_DUPLICATE:{symbol}")
            if not ordered:
                failures.append(f"ETF_ORDER:{symbol}")
            if not source_ok:
                failures.append(f"ETF_SOURCE:{symbol}")
            if not _valid_ohlc(frame):
                failures.append(f"ETF_OHLC:{symbol}")
        except Exception as exc:
            records[symbol] = {"valid": False}
            failures.append(f"ETF:{symbol}:{type(exc).__name__}")

    benchmark_path = root / "data/all_prices_long_v62_9_expanded.csv"
    benchmark_record: dict[str, Any]
    try:
        benchmark = pd.read_csv(benchmark_path, dtype={"ticker": str})
        benchmark = benchmark[benchmark["ticker"].astype(str).str.strip().eq("KS11")].copy()
        benchmark["date"] = pd.to_datetime(benchmark["date"], errors="raise")
        duplicate = bool(benchmark["date"].duplicated().any())
        benchmark_record = {
            "valid": bool(not duplicate and _valid_ohlc(benchmark)),
            "last_date": benchmark["date"].max().date().isoformat() if not benchmark.empty else None,
        }
        if duplicate:
            failures.append("KS11_DUPLICATE")
        if not _valid_ohlc(benchmark):
            failures.append("KS11_OHLC")
    except Exception as exc:
        benchmark_record = {"valid": False}
        failures.append(f"KS11:{type(exc).__name__}")

    result = validate_freshness_records(
        records, benchmark_record, expected_symbols=26, run_date=run_date,
        latest_completed_date=latest_completed_date,
    )
    if failures:
        state = "INCOMPLETE" if any("MISSING" in item or "COUNT" in item for item in result.failures + tuple(failures)) else "FAILED"
        structural = "INCOMPLETE" if state == "INCOMPLETE" else "FAILED"
        return FreshnessResult(state, result.cutoff, len(records), tuple(sorted(set(result.failures + tuple(failures)))), "KS11", structural, "UNKNOWN", result.latest_completed_date)
    return result


def _field(value: Any, name: str, default: Any = None) -> Any:
    return getattr(value, name, default) if not isinstance(value, dict) else value.get(name, default)


def _require_isolated_test_database(
    database_url: str | None,
    *,
    test_database_url: str | None,
    operational_database_url: str | None,
) -> str:
    if not test_database_url or not database_url or database_url != test_database_url:
        raise RuntimeError("Forward Paper requires TEST_DATABASE_URL exactly; no operational fallback is allowed")
    if operational_database_url and test_database_url == operational_database_url:
        raise RuntimeError("Forward Paper TEST_DATABASE_URL must be distinct from DATABASE_URL")
    return test_database_url


def _run_toss_market_update(root: Path | str) -> dict[str, Any]:
    """Refresh active ETF and KS11 data through the existing Toss GET adapters."""
    latest_completed = _latest_completed_toss_trading_day(TossOpenApiClient())
    etf = run_toss_incremental_update(root, write_output=True, as_of=latest_completed)
    benchmark = run_toss_market_indicator_ks11_update(root, write_output=True, as_of=latest_completed)
    failures = tuple(
        [dict(row) for row in etf.failed]
        + [dict(row) for row in benchmark.failed]
    )
    cutoffs = [str(result.cutoff) for result in (etf, benchmark) if result.cutoff]
    return {
        "cutoff": min(cutoffs) if cutoffs else None,
        "latest_completed_date": latest_completed,
        "symbols": int(etf.symbols) + int(benchmark.symbols),
        "succeeded": int(etf.succeeded) + int(benchmark.succeeded),
        "failed": failures,
        "rows_added": int(etf.rows_added) + int(benchmark.rows_added),
        "backup_dir": etf.backup_dir if not failures else "",
        "provider": f"{etf.provider}+{benchmark.provider}",
        "endpoint": f"{etf.endpoint}; {benchmark.endpoint}",
    }


def _latest_mark(root: Path, symbol: str, cutoff: str | None) -> Decimal:
    path = root / "data/toss_v19c_daily" / f"{symbol}_1d.csv"
    if not path.is_file():
        return Decimal("0")
    frame = pd.read_csv(path, dtype={"ticker": str})
    dates = _parse_dates(frame["timestamp"])
    frame = frame.assign(_date=dates)
    if cutoff:
        frame = frame[frame["_date"] <= pd.Timestamp(cutoff)]
    if frame.empty:
        return Decimal("0")
    row = frame.sort_values("_date").iloc[-1]
    return Decimal(str(row["close"]))


def _paper_nav_components(
    *, cash: Decimal, positions: dict[str, Decimal], marks: dict[str, Decimal]
) -> tuple[Decimal, Decimal]:
    missing = sorted(symbol for symbol in positions if symbol not in marks or marks[symbol] <= 0)
    if missing:
        raise ValueError(f"missing or invalid valuation marks: {','.join(missing)}")
    positions_value = sum((positions[symbol] * marks[symbol] for symbol in positions), Decimal("0"))
    nav = cash + positions_value
    if nav <= 0:
        raise ValueError("Paper NAV is not positive")
    return positions_value, nav


def _save_nav(database_url: str, root: Path, freshness: FreshnessResult, *, session_id: str | None, authority: str) -> dict[str, Any]:
    account = load_paper_account(database_url)
    cutoff = freshness.cutoff or date.today().isoformat()
    marks = {symbol: _latest_mark(root, symbol, freshness.cutoff) for symbol in account["positions"]}
    missing_marks = sorted(symbol for symbol, mark in marks.items() if mark <= 0)
    positions_value, nav = _paper_nav_components(
        cash=account["cash_krw"], positions=account["positions"], marks=marks
    )
    return save_daily_nav(
        database_url,
        as_of=cutoff,
        session_id=session_id,
        nav_krw=nav,
        cash_krw=account["cash_krw"],
        positions_value_krw=positions_value,
        freshness_status=freshness.status,
        authority_status=authority,
        detail={
            "failures": list(freshness.failures),
            "benchmark": freshness.benchmark,
            "structural_completeness": freshness.structural_completeness,
            "temporal_freshness": freshness.temporal_freshness,
            "latest_completed_date": freshness.latest_completed_date,
            "missing_evaluation_prices": missing_marks,
        },
    )


def _run_daily_paper_cycle_locked(
    database_url: str,
    root: Path | str,
    *,
    snapshot_mode: str = "real-read-only",
) -> dict[str, Any]:
    root = Path(root)
    initial_cfg = yaml.safe_load((root / "config/v85_operations.yaml").read_text(encoding="utf-8"))
    initialize_paper_schema(database_url)
    ensure_paper_account(database_url, Decimal(str(initial_cfg["initial_capital_krw"])), "config/v85_operations.yaml:initial_capital_krw")
    update_error: str | None = None
    update: Any = None
    try:
        update = _run_toss_market_update(root)
        failed = tuple(_field(update, "failed", ()))
        if failed:
            freshness = FreshnessResult("FAILED", _field(update, "cutoff"), _field(update, "symbols", 0), tuple(str(row) for row in failed), "KS11")
        else:
            backup_dir = _field(update, "backup_dir")
            if backup_dir:
                append_canonical(root, str(_field(update, "cutoff")), backup_dir)
            latest_completed = _field(update, "latest_completed_date")
            if not latest_completed:
                raise RuntimeError("official market-calendar cutoff is missing; fail closed")
            freshness = validate_market_freshness(root, latest_completed_date=str(latest_completed))
    except Exception as exc:
        update_error = f"{type(exc).__name__}:{exc}"
        freshness = FreshnessResult("FAILED", _field(update, "cutoff") if update is not None else None, _field(update, "symbols", 0) if update is not None else 0, (update_error,), "KS11")

    base = {
        "data_mode": "HISTORICAL_DEVELOPMENT",
        "operational_authority": "HOLD_ONLY",
        "paper_test_execution": "ALLOWED",
        "live_execution_allowed": False,
        "broker_mutation_calls": 0,
        "freshness": freshness.as_dict(),
        "update": {
            "cutoff": _field(update, "cutoff"),
            "rows_added": _field(update, "rows_added", 0),
            "failed": list(_field(update, "failed", ())),
            "provider": _field(update, "provider"),
            "endpoint": _field(update, "endpoint"),
        },
        "orders": [],
        "preview": None,
        "reconciliation": None,
    }
    if freshness.status != "FRESH":
        base["status"] = "HOLD_ONLY"
        base["nav"] = _save_nav(database_url, root, freshness, session_id=None, authority="HOLD_ONLY")
        return base
    try:
        preflight = build_strategy_preview(root)
        if pd.Timestamp(preflight["as_of"]).date().isoformat() != freshness.cutoff:
            freshness = FreshnessResult("STALE", freshness.cutoff, freshness.symbol_count, (f"STRATEGY_CUTOFF:{preflight['as_of']}",), "KS11")
            base["freshness"] = freshness.as_dict()
            base["status"] = "HOLD_ONLY"
            base["nav"] = _save_nav(database_url, root, freshness, session_id=None, authority="HOLD_ONLY")
            return base
        preview = run_paper_decision_preview(root, database_url=database_url, mode=snapshot_mode)
        base["preview"] = preview
        snapshot = preview.get("read_only_snapshot") or {}
        if preview.get("authority_status") != "PREVIEW_ONLY" or snapshot.get("status") != "SAVED" or snapshot.get("mutation_calls", 0) != 0:
            base["status"] = "HOLD_ONLY"
            base["nav"] = _save_nav(database_url, root, freshness, session_id=preview.get("decision", {}).get("session_id"), authority="HOLD_ONLY")
            return base
        execution = run_paper_execution_cycle(
            database_url,
            root,
            mode="historical-development",
            execution_references=preview.get("execution_references"),
        )
        base["orders"] = execution.get("orders", [])
        base["reconciliation"] = execution.get("reconciliation")
        base["broker_mutation_calls"] = execution.get("broker_mutation_calls", 0)
        base["status"] = "COMPLETED" if execution.get("status") == "COMPLETED" else "HOLD_ONLY"
        base["nav"] = _save_nav(database_url, root, freshness, session_id=execution.get("session_id"), authority="HOLD_ONLY")
        return base
    except Exception as exc:
        base["status"] = "HOLD_ONLY"
        base["failure"] = f"{type(exc).__name__}:{exc}"
        base["nav"] = _save_nav(database_url, root, freshness, session_id=None, authority="HOLD_ONLY")
        return base


def run_daily_paper_cycle(
    database_url: str,
    root: Path | str,
    *,
    snapshot_mode: str = "real-read-only",
) -> dict[str, Any]:
    database_url = _require_isolated_test_database(
        database_url,
        test_database_url=os.environ.get("TEST_DATABASE_URL"),
        operational_database_url=os.environ.get("DATABASE_URL"),
    )
    if LIVE_BUILD_CAPABILITY or CURRENT_RELEASE_LIVE_AUTHORITY:
        raise RuntimeError("Live hardlock verification failed")
    root = Path(root)
    with _daily_cycle_lock(root) as lock_status:
        if lock_status != "ACQUIRED":
            return {
                "status": "HOLD_ONLY",
                "operational_authority": "HOLD_ONLY",
                "failure": f"DAILY_CYCLE_{lock_status}",
                "orders": [],
                "live_execution_allowed": False,
                "broker_mutation_calls": 0,
            }
        return _run_daily_paper_cycle_locked(
            database_url, root, snapshot_mode=snapshot_mode
        )


__all__ = ["FreshnessResult", "validate_freshness_records", "validate_market_freshness", "run_daily_paper_cycle"]
