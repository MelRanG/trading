"""Historical replay using the existing Paper operational path.

This module deliberately has no strategy or broker implementation.  It walks
the already-built V69 parent ledger through the same decision, intent, Paper
execution, reconciliation, and NAV functions used by the daily runtime.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_FLOOR
import csv
from hashlib import sha256
import inspect
import json
import math
import os
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, parse_qsl, urlsplit

import pandas as pd
import psycopg
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row
import yaml

from quant_harness.daily_paper_runtime import FreshnessResult, _save_nav
from quant_harness.paper_decision_runtime import (
    PREOPEN_EXECUTION_CONTRACT as REPLAY_EXECUTION_CONTRACT,
    PREOPEN_EXECUTION_CONTRACT_HASH as REPLAY_EXECUTION_CONTRACT_HASH,
    _unselected_target_exceeds_cap,
    apply_replay_preopen_sizing,
    build_intent_previews,
    build_candidate_strategy_preview,
    save_paper_preview,
)
from quant_harness.paper_execution_runtime import _adv_participation_cap_quantity, _cost_terms, run_paper_execution_cycle
from quant_harness.paper_runtime_store import (
    PAPER_ACCOUNT_ID,
    ensure_paper_account,
    initialize_paper_schema,
    load_paper_account,
)
from quant_harness.v104_end_to_end_causal_challenger_audit.adapter import (
    _input_hash,
    build_candidate_ledgers,
    load_candidate_specs,
)
from quant_harness.v101_risk_execution_agent import engine as v101
from quant_harness.v77_corrected_price_allocation import engine as v77


MODE = "HISTORICAL_REPLAY"
INITIAL_CAPITAL = Decimal("10000000")
ACCOUNT_SOURCE = "config/v85_operations.yaml:initial_capital_krw"
DEFAULT_END = date(2026, 7, 8)
REPLAY_CODE_FILES = (
    "src/quant_harness/historical_operational_replay.py",
    "src/quant_harness/paper_decision_runtime.py",
    "src/quant_harness/paper_execution_runtime.py",
    "src/quant_harness/paper_runtime_store.py",
    "src/quant_harness/daily_paper_runtime.py",
    "src/quant_harness/v104_end_to_end_causal_challenger_audit/adapter.py",
    "src/quant_harness/v69_dynamic_theme_leadership/engine.py",
    "src/quant_harness/v77_corrected_price_allocation/engine.py",
    "src/quant_harness/v79_generic_trend_sleeve/engine.py",
    "src/quant_harness/v94_universe_agent/engine.py",
    "src/quant_harness/v94_universe_agent/policy.py",
    "src/quant_harness/v95_market_regime_agent/engine.py",
    "src/quant_harness/v95_market_regime_agent/policy.py",
    "src/quant_harness/v100_strategy_agent/engine.py",
    "src/quant_harness/v100_strategy_agent/policy.py",
    "src/quant_harness/v101_risk_execution_agent/engine.py",
    "src/quant_harness/v101_risk_execution_agent/policy.py",
    "src/quant_harness/v102_market_evidence_agent/policy.py",
    "src/quant_harness/v102_market_evidence_agent/engine.py",
    "src/quant_harness/v98_candidate_selection_agent/engine.py",
    "src/quant_harness/v98_candidate_selection_agent/policy.py",
)
REPLAY_INPUT_FILES = (
    "config/active_strategy.yaml",
    "config/strategy_registry_v84.yaml",
    "config/v69_dynamic_theme_leadership.yaml",
    "config/v77_corrected_price_allocation.yaml",
    "config/v79_generic_trend_sleeve.yaml",
    "config/v85_operations.yaml",
    "config/v94_universe_agent.yaml",
    "config/v95_market_regime_agent.yaml",
    "config/v98_candidate_selection_agent.yaml",
    "config/v100_strategy_agent.yaml",
    "config/v101_risk_execution_agent.yaml",
    "config/v102_market_evidence_contract.yaml",
    "config/v104_end_to_end_causal_challenger_audit.yaml",
    "data/canonical/v84_market_manifest.csv",
    "data/agent_ready_v62_16/agent_etf_to_stock_mapping_v62_16.csv",
)
OUTPUT_FILES = ("replay_summary.json", "daily_nav.csv", "trades.csv", "parity_summary.json", "validation.log", "replay_contract.json")


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _hash_files(root: Path, relative_paths: tuple[str, ...]) -> str:
    digest = sha256()
    for relative in relative_paths:
        path = root / relative
        if not path.is_file():
            raise RuntimeError(f"required replay input missing: {relative}")
        digest.update(relative.replace("\\", "/").encode("utf-8"))
        digest.update(b"\0")
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        digest.update(b"\0")
    return digest.hexdigest()


def _database_scope_hash(database_url: str) -> str:
    parsed = urlsplit(database_url)
    scope = {
        "scheme": parsed.scheme,
        "host": parsed.hostname,
        "port": parsed.port,
        "database": parsed.path,
        "search_path": parse_qs(parsed.query).get("options", []),
    }
    return sha256(json.dumps(scope, sort_keys=True).encode("utf-8")).hexdigest()


def _database_identity(database_url: str) -> tuple[Any, ...]:
    try:
        options = conninfo_to_dict(database_url)
    except Exception as exc:
        raise RuntimeError("database URL could not be resolved for test isolation") from exc
    user = options.get("user") or os.environ.get("PGUSER") or os.environ.get("USERNAME") or os.environ.get("USER")
    database = options.get("dbname") or os.environ.get("PGDATABASE") or user
    host = options.get("host") or options.get("hostaddr") or os.environ.get("PGHOST") or "localhost"
    port = options.get("port") or os.environ.get("PGPORT") or "5432"
    # Destination query parameters (dbname/host/port) are interpreted by
    # libpq, so compare the resolved values rather than URI path text.
    return (str(host).lower(), str(port), str(database))


def assert_isolated_test_database(database_url: str) -> str:
    """Reject operational DB destinations even when a TEST alias is configured."""
    test_url = _database_url_from_test_env(database_url)
    operational_url = os.environ.get("DATABASE_URL")
    if operational_url and _database_identity(test_url) == _database_identity(operational_url):
        raise RuntimeError("TEST_DATABASE_URL resolves to the operational database; refusing replay mutation")
    return test_url


def _intraday_cache_hash(root: Path, start: date, end: date) -> str:
    """Fingerprint only cached 1m sessions that can affect this replay window."""
    base = root / "data/toss_intraday_1m"
    digest = sha256()
    if not base.exists():
        return digest.hexdigest()
    paths: list[Path] = []
    for path in base.glob("*/*.csv"):
        try:
            day = date.fromisoformat(path.stem)
        except ValueError:
            continue
        if start <= day <= end:
            paths.append(path)
    for path in sorted(paths, key=lambda item: item.as_posix()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        digest.update(b"\0")
    return digest.hexdigest()


def _paper_state_hash(database_url: str) -> str:
    # Hash exact canonical rows, not aggregates: equal-total edits to fills,
    # individual NAVs or audit records must invalidate a resume checkpoint.
    tables = (
        "paper_account", "paper_cash", "paper_position", "paper_session",
        "strategy_decision", "target_allocation", "order_intent_preview",
        "paper_order", "paper_fill", "paper_ledger_event", "paper_reconciliation",
        "paper_daily_nav", "paper_audit_event",
    )
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        body = {}
        for table in tables:
            rows = conn.execute(
                f"SELECT to_jsonb(t)::text AS row FROM {table} AS t ORDER BY to_jsonb(t)::text"
            ).fetchall()
            body[table] = [row["row"] for row in rows]
    return sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _resolver_fingerprint(resolver: Any) -> str:
    if resolver is None:
        return REPLAY_EXECUTION_CONTRACT_HASH
    if getattr(resolver, "__code__", None) is None:
        raise RuntimeError("custom execution resolver has no inspectable code; refusing unversioned replay")
    digest = sha256()
    closure = []
    for cell in getattr(resolver, "__closure__", ()) or ():
        try:
            closure.append(repr(cell.cell_contents))
        except ValueError:
            closure.append("<empty>")
    pending = [resolver]
    seen: set[tuple[str, str]] = set()
    while pending:
        function = pending.pop()
        key = (str(getattr(function, "__module__", "")), str(getattr(function, "__qualname__", "")))
        if key in seen:
            continue
        seen.add(key)
        code = getattr(function, "__code__", None)
        if code is None:
            raise RuntimeError("custom execution resolver dependency is not inspectable")
        module = inspect.getmodule(function)
        source_file = Path(module.__file__).resolve() if module and module.__file__ else None
        if source_file is None or not source_file.is_file():
            raise RuntimeError("custom execution resolver source is unavailable; refusing unversioned replay")
        digest.update(key[0].encode("utf-8"))
        digest.update(key[1].encode("utf-8"))
        digest.update(source_file.read_bytes())
        digest.update(code.co_code)
        digest.update(repr(tuple(value for value in code.co_consts if not inspect.iscode(value))).encode("utf-8"))
        digest.update(repr(code.co_names).encode("utf-8"))
        for name in code.co_names:
            dependency = getattr(function, "__globals__", {}).get(name)
            if inspect.isfunction(dependency) and getattr(dependency, "__code__", None) is not None:
                pending.append(dependency)
    digest.update(json.dumps(closure, sort_keys=True).encode("utf-8"))
    return digest.hexdigest()


def _replay_fingerprint(
    root: Path,
    *,
    candidate_id: str,
    candidate_fingerprint: str,
    input_hash: str,
    start: date,
    end: date,
    database_url: str,
    execution_contract_name: str,
    execution_contract_hash: str,
    execution_resolver_hash: str,
    execution_data_hash: str,
) -> dict[str, Any]:
    body = {
        "schema_version": "HISTORICAL_REPLAY_CONTRACT_V3",
        "mode": MODE,
        "candidate_id": candidate_id,
        "candidate_fingerprint": candidate_fingerprint,
        "data_input_hash": input_hash,
        "code_hash": _hash_files(root, REPLAY_CODE_FILES),
        "configuration_and_manifest_hash": _hash_files(root, REPLAY_INPUT_FILES),
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "initial_capital_krw": str(INITIAL_CAPITAL),
        "execution_contract": {"name": execution_contract_name, "hash": execution_contract_hash},
        "execution_resolver_hash": execution_resolver_hash,
        "execution_data_hash": execution_data_hash,
        "database_scope_hash": _database_scope_hash(database_url),
    }
    fingerprint = sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {**body, "fingerprint": fingerprint}


def _check_or_start_replay_contract(
    path: Path,
    contract: dict[str, Any],
    *,
    reset: bool,
    existing_dates: set[date],
    database_url: str | None = None,
) -> dict[str, Any]:
    if reset:
        state = {"contract": contract, "status": "RUNNING", "completed_dates": [], "last_completed_date": None}
        _atomic_json(path, state)
        return state
    if not path.is_file():
        if existing_dates:
            raise RuntimeError("existing Paper NAV has no matching replay contract; refusing unsafe resume")
        state = {"contract": contract, "status": "RUNNING", "completed_dates": [], "last_completed_date": None}
        _atomic_json(path, state)
        return state
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("replay contract is unreadable; refusing resume") from exc
    if state.get("contract", {}).get("fingerprint") != contract["fingerprint"]:
        raise RuntimeError("replay input/code/config fingerprint changed; refusing unsafe resume")
    recorded = {date.fromisoformat(value) for value in state.get("completed_dates", [])}
    if recorded != existing_dates:
        raise RuntimeError("replay checkpoint and Paper NAV dates disagree; refusing unsafe resume")
    if recorded:
        if database_url is None or state.get("last_state_hash") != _paper_state_hash(database_url):
            raise RuntimeError("Paper account/ledger state differs from replay checkpoint; refusing unsafe resume")
    return state


def _market_prices_for_session(market: dict[str, Any], session: str | date, symbols: set[str]) -> tuple[str, dict[str, Decimal], dict[str, Decimal]]:
    """Return prior-close sizing prices and current-session open execution prices."""
    close = market["close"]
    open_prices = market["open"]
    session_date = pd.Timestamp(session).date()

    def local_dates(index: Any) -> pd.DatetimeIndex:
        parsed = pd.DatetimeIndex(pd.to_datetime(index))
        if parsed.tz is not None:
            parsed = parsed.tz_convert("Asia/Seoul").tz_localize(None)
        return parsed.normalize()

    close_dates = local_dates(close.index)
    open_dates = local_dates(open_prices.index)
    prior_positions = [i for i, value in enumerate(close_dates) if value.date() < session_date]
    session_positions = [i for i, value in enumerate(open_dates) if value.date() == session_date]
    if not prior_positions or len(session_positions) != 1:
        raise RuntimeError(f"missing prior close or unique D open for replay session {session_date}")
    prior_position = prior_positions[-1]
    open_position = session_positions[0]
    prior_date = close_dates[prior_position].date().isoformat()
    sizing: dict[str, Decimal] = {}
    executable: dict[str, Decimal] = {}
    for symbol in sorted(symbols):
        if symbol not in close.columns or symbol not in open_prices.columns:
            raise RuntimeError(f"required market price column is missing: {symbol}")
        before = close.iloc[prior_position][symbol]
        at_open = open_prices.iloc[open_position][symbol]
        for label, value in (("prior close", before), ("session open", at_open)):
            if pd.isna(value) or not math.isfinite(float(value)) or float(value) <= 0:
                raise RuntimeError(f"invalid {label} for {symbol} on replay session {session_date}")
        sizing[symbol] = Decimal(str(before))
        executable[symbol] = Decimal(str(at_open))
    return prior_date, sizing, executable


def _database_url_from_test_env(database_url: str | None) -> str:
    configured = os.environ.get("TEST_DATABASE_URL")
    if not configured:
        raise RuntimeError("TEST_DATABASE_URL is required for HISTORICAL_REPLAY")
    if database_url != configured:
        expected = urlsplit(configured)
        supplied = urlsplit(database_url or "")
        expected_base = (expected.scheme, expected.username, expected.password, expected.hostname, expected.port, expected.path, expected.fragment)
        supplied_base = (supplied.scheme, supplied.username, supplied.password, supplied.hostname, supplied.port, supplied.path, supplied.fragment)
        expected_query = parse_qsl(expected.query, keep_blank_values=True)
        supplied_query = parse_qsl(supplied.query, keep_blank_values=True)
        remainder = list(supplied_query)
        for pair in expected_query:
            try:
                remainder.remove(pair)
            except ValueError:
                remainder = [("__invalid__", "")]
                break
        allowed_options = False
        if len(remainder) == 1 and remainder[0][0] == "options":
            import re
            allowed_options = bool(re.fullmatch(
                r"-c search_path=[A-Za-z_][A-Za-z0-9_]*(?: -c synchronous_commit=off)?",
                remainder[0][1],
            ))
        if expected_base != supplied_base or not allowed_options:
            raise RuntimeError("HISTORICAL_REPLAY accepts TEST_DATABASE_URL only")
    if database_url is None:
        raise RuntimeError("HISTORICAL_REPLAY accepts TEST_DATABASE_URL only")
    return database_url


def _truncate_paper_tables(database_url: str) -> None:
    tables = (
        "paper_daily_nav", "paper_reconciliation", "paper_ledger_event", "paper_fill",
        "paper_order", "paper_audit_event", "order_intent_preview", "target_allocation",
        "strategy_decision", "paper_session", "paper_position", "paper_cash", "paper_account",
    )
    with psycopg.connect(database_url) as conn:
        conn.execute("TRUNCATE " + ",".join(tables) + " CASCADE")


def _freshness_for_replay(as_of: str) -> FreshnessResult:
    d = str(pd.Timestamp(as_of).date())
    return FreshnessResult("FRESH", d, 26, tuple(), "KS11", "PASSED", "FRESH", d)


def _replay_hold_reason(preview: dict[str, Any]) -> str:
    if _unselected_target_exceeds_cap(preview):
        fallback = preview.get("targets", [])
        if fallback and all(row.get("reason") == "NO_LEADER_CORE_FALLBACK" for row in fallback):
            return "NO_LEADER_CORE_FALLBACK_EXCEEDS_90_PERCENT_SINGLE_SYMBOL_CAP"
        return "NO_SELECTED_TARGET_EXCEEDS_90_PERCENT_SINGLE_SYMBOL_CAP"
    return str(preview.get("hold_reason") or preview.get("authority_status") or "NO_SELECTED_CANDIDATE")


def _is_unselected_over_cap_hold(preview: dict[str, Any]) -> bool:
    return _unselected_target_exceeds_cap(preview)


def _nav_rows(database_url: str) -> list[dict[str, Any]]:
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        return [dict(r) for r in conn.execute(
            "SELECT as_of,nav_krw,cash_krw,positions_value_krw,freshness_status,authority_status "
            "FROM paper_daily_nav WHERE paper_account_id=%s ORDER BY as_of", (PAPER_ACCOUNT_ID,)
        ).fetchall()]


def _trade_rows(database_url: str) -> list[dict[str, Any]]:
    query = """
    SELECT o.paper_order_id,o.client_order_id,o.session_id,s.as_of,o.symbol,o.side,
           o.requested_quantity,o.filled_quantity,o.reference_price,o.status,
           f.paper_fill_id,f.quantity AS fill_quantity,f.fill_price,f.fee,f.slippage,
           l.cash_delta,l.quantity_delta,l.created_at
    FROM paper_order o
    JOIN paper_session s ON s.session_id=o.session_id
    LEFT JOIN paper_fill f ON f.paper_order_id=o.paper_order_id
    LEFT JOIN paper_ledger_event l ON l.paper_fill_id=f.paper_fill_id
    ORDER BY o.created_at,f.filled_at
    """
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        return [dict(r) for r in conn.execute(query).fetchall()]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("\n", encoding="utf-8")
        return
    keys = list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in row.items()})


def _json_obj(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _parity(root: Path, previews: dict[str, dict[str, Any]], *, candidate_id: str = "V69_PARENT") -> dict[str, Any]:
    """Compare only a model-matched legacy reference, never an independent oracle.

    The original V79 artifact does not freeze NO63/vol-guard semantics, so it
    must not stand in for that challenger. Legacy regime differences remain
    visible; same-builder wiring parity is a separate check below.
    """
    if any(p.get("candidate_id", candidate_id) != candidate_id for p in previews.values()):
        raise ValueError("parity candidate identity differs from requested model")
    base = {"candidate_id": candidate_id, "comparable_dates": 0, "exact_dates": 0,
            "parity_ratio": None, "first_mismatch_date": None, "first_mismatch_stage": None,
            "mismatch_counts": {}, "artifact": None, "uncompared_dates": sorted(previews),
            "independent_strategy_validation": False, "target_candidate_parity_ratio": None,
            "legacy_regime_mismatch_dates": [], "regime_comparable_dates": 0,
            "regime_uncompared_dates": sorted(previews), "legacy_regime_parity_ratio": None}
    if candidate_id != "V69_PARENT":
        return {**base, "status": "NOT_AVAILABLE", "reason": "NO_MODEL_MATCHED_INDEPENDENT_REFERENCE"}
    artifact_path = root / "reports/v100_strategy_agent/v100_target_ledger_v69_FIXED_PARENT_ALLOCATIONS.csv"
    if not artifact_path.is_file():
        return {**base, "status": "NOT_AVAILABLE", "reason": "REFERENCE_MISSING", "first_mismatch_stage": "artifact_missing"}
    artifact = pd.read_csv(artifact_path, dtype=str)
    required = {"date", "target_hash", "target_weights_json", "leader_ticker"}
    if not required.issubset(artifact.columns):
        raise ValueError("parity reference missing required columns")
    if artifact["date"].isna().any() or artifact["date"].duplicated().any():
        raise ValueError("parity reference invalid or duplicate dates")
    artifact = artifact.set_index("date")
    regime_path = root / "reports/v90_trade_attribution/v90_regime_d1.csv"
    regimes = pd.read_csv(regime_path, dtype=str).set_index("date") if regime_path.is_file() else pd.DataFrame()
    if not regimes.empty and (not regimes.index.is_unique or "regime_d1" not in regimes):
        raise ValueError("legacy regime reference duplicate dates or missing regime column")
    comparable = sorted(set(previews) & set(artifact.index))
    mismatches: list[tuple[str, str]] = []
    counts: dict[str, int] = {}
    target_candidate_mismatches = 0
    legacy_regime_mismatch_dates: list[str] = []
    regime_compared_dates: list[str] = []
    regime_map = {"RANGE_RISK": "RISK_OFF", "SHOCK_RISK": "RISK_OFF", "NARROW_BULL": "RISK_ON", "BROAD_BULL": "RISK_ON"}
    for d in comparable:
        p = previews[d]
        a = artifact.loc[d]
        stages: list[str] = []
        if str(p.get("target_hash")) != str(a.get("target_hash")):
            stages.append("target")
        if _json_obj(p.get("target_weights")) != _json_obj(a.get("target_weights_json")):
            stages.append("target")
        if (p.get("selected_candidates") or [None])[0] != (None if pd.isna(a.get("leader_ticker")) else a.get("leader_ticker")):
            stages.append("candidate")
        if stages:
            target_candidate_mismatches += 1
        if not regimes.empty and d in regimes.index:
            regime_compared_dates.append(d)
            expected = regime_map.get(str(regimes.loc[d, "regime_d1"]), str(regimes.loc[d, "regime_d1"]))
            if str(p.get("regime")) != expected:
                stages.append("regime")
                legacy_regime_mismatch_dates.append(d)
        if stages:
            stage = stages[0]
            mismatches.append((d, stage))
            counts[stage] = counts.get(stage, 0) + 1
    exact = len(comparable) - len(mismatches)
    return {
        **base,
        "status": ("LEGACY_REFERENCE_COMPARISON" if len(regime_compared_dates) == len(comparable)
                   else "INCOMPLETE_LEGACY_REGIME_REFERENCE") if comparable else "NO_COMPARABLE_DATES",
        "comparison_scope": "LEGACY_TARGET_CANDIDATE_AND_LEGACY_REGIME_NOT_SAME_CONTRACT",
        "comparable_dates": len(comparable),
        "exact_dates": exact,
        "parity_ratio": (exact / len(comparable)) if comparable and len(regime_compared_dates) == len(comparable) else None,
        "first_mismatch_date": mismatches[0][0] if mismatches else None,
        "first_mismatch_stage": mismatches[0][1] if mismatches else None,
        "mismatch_counts": counts,
        "artifact": str(artifact_path.relative_to(root)),
        "uncompared_dates": sorted(set(previews) - set(comparable)),
        "target_candidate_parity_ratio": (1 - target_candidate_mismatches / len(comparable)) if comparable else None,
        "legacy_regime_mismatch_dates": legacy_regime_mismatch_dates,
        "regime_comparable_dates": len(regime_compared_dates),
        "regime_uncompared_dates": sorted(set(previews) - set(regime_compared_dates)),
        "legacy_regime_parity_ratio": (1 - len(legacy_regime_mismatch_dates) / len(regime_compared_dates)) if regime_compared_dates else None,
    }


def _costed_buy_hold_069500(
    root: Path, market: dict[str, Any], dates: pd.DatetimeIndex, initial: Decimal, execution_spec: Any
) -> dict[str, Any]:
    ticker = "069500"
    first = pd.Timestamp(dates[0])
    prior_dates = market["close"].index[market["close"].index < first]
    if not len(prior_dates) or ticker not in market["close"].columns or ticker not in market["open"].columns:
        return {"status": "BLOCKED_BY_BUY_HOLD_INPUT", "reason": "missing prior close or open"}
    prior_close = Decimal(str(market["close"].loc[prior_dates[-1], ticker]))
    raw_open = Decimal(str(market["open"].loc[first, ticker]))
    adv_value = market["adv20_d1"].loc[first, ticker] if ticker in market["adv20_d1"].columns else None
    if adv_value is None or pd.isna(adv_value) or prior_close <= 0 or raw_open <= 0:
        return {"status": "BLOCKED_BY_BUY_HOLD_INPUT", "reason": "missing valid D-1 ADV or price"}
    adv = Decimal(str(adv_value))
    desired = int((initial / prior_close).to_integral_value(rounding=ROUND_FLOOR))
    cap = _adv_participation_cap_quantity(
        adv_krw=adv,
        reference_price=raw_open,
        participation=Decimal(str(execution_spec.max_participation_of_d1_adv)),
    )
    allowed = min(desired, cap)
    fee = spread_cost = impact_cost = Decimal("0")
    shares = 0
    cash = initial
    fill_price = Decimal("0")
    shares = allowed
    while shares > 0:
        fill_price, fee, _ = _cost_terms(
            root, side="BUY", quantity=Decimal(shares), reference=raw_open, adv=adv
        )
        if Decimal(shares) * fill_price + fee <= initial:
            break
        shares -= 1
    minimum_notional = Decimal(str(v101._policy(root, v101.ACTIVE_POLICY).minimum_order_notional_krw))
    if shares > 0 and Decimal(shares) * raw_open < minimum_notional:
        shares = 0
    if shares > 0:
        impact_bps = Decimal(str(v77._impact_bps(float(Decimal(shares) * raw_open), float(adv), execution_spec)))
        fill_price, fee, _ = _cost_terms(
            root, side="BUY", quantity=Decimal(shares), reference=raw_open, adv=adv
        )
        spread_cost = Decimal(shares) * raw_open * Decimal(str(execution_spec.half_spread_bps)) / Decimal("10000")
        impact_cost = Decimal(shares) * raw_open * impact_bps / Decimal("10000")
        cash -= Decimal(shares) * fill_price + fee
    closes = market["close"].reindex(dates)[ticker]
    if closes.isna().any():
        return {"status": "BLOCKED_BY_BUY_HOLD_INPUT", "reason": "missing daily close in replay period"}
    path = [initial] + [cash + Decimal(shares) * Decimal(str(value)) for value in closes.tolist()]
    peak = path[0]
    mdd = Decimal("0")
    for value in path:
        peak = max(peak, value)
        if peak > 0:
            mdd = min(mdd, value / peak - 1)
    return {
        "status": "EXECUTED" if shares else "NO_FILL",
        "ticker": ticker,
        "start_date": first.date().isoformat(),
        "end_date": pd.Timestamp(dates[-1]).date().isoformat(),
        "initial_nav_krw": str(initial),
        "final_nav_krw": str(path[-1]),
        "total_return": float(path[-1] / initial - 1),
        "maximum_drawdown": float(mdd),
        "shares": shares,
        "residual_cash_krw": str(cash),
        "sizing_price_d_minus_1_close": str(prior_close),
        "execution_price_d_open": str(fill_price) if shares else None,
        "fee_krw": str(fee),
        "spread_cost_krw": str(spread_cost),
        "impact_cost_krw": str(impact_cost),
        "final_liquidation": False,
        "execution_contract": "D_MINUS_1_NAV_SIZE_D_OPEN_V101_COST_ADV_1PCT_V1",
    }


def _metrics(
    root: Path, nav: list[dict[str, Any]], trades: list[dict[str, Any]], initial: Decimal,
    *, market: dict[str, Any] | None = None, execution_spec: Any = None,
) -> dict[str, Any]:
    if not nav:
        return {"start_date": None, "end_date": None, "total_trading_days": 0, "initial_capital_krw": str(initial)}
    values = pd.Series([float(r["nav_krw"]) for r in nav], index=pd.to_datetime([r["as_of"] for r in nav]))
    daily = values.pct_change()
    if len(daily):
        daily.iloc[0] = float(values.iloc[0] / float(initial) - 1.0)
    daily = daily.dropna()
    path_with_opening = pd.concat([pd.Series([float(initial)], index=[values.index[0] - pd.Timedelta(days=1)]), values])
    running = path_with_opening.cummax()
    mdd = float((path_with_opening / running - 1).min()) if len(path_with_opening) else 0.0
    # Return starts with opening capital immediately before the first session.
    elapsed = max((values.index[-1] - values.index[0]).days + 1, 1)
    final = Decimal(str(nav[-1]["nav_krw"]))
    total_return = final / initial - 1
    cagr = (float(final / initial) ** (365.25 / elapsed) - 1) if final > 0 else -1.0
    vol = float(daily.std(ddof=0) * (252 ** 0.5)) if len(daily) else 0.0
    sharpe = float(daily.mean() / daily.std(ddof=0) * (252 ** 0.5)) if len(daily) and daily.std(ddof=0) else 0.0
    benchmark = pd.read_csv(root / "data/all_prices_long_v62_9_expanded.csv", dtype={"ticker": str})
    benchmark = benchmark[benchmark["ticker"].astype(str).eq("KS11")].copy()
    benchmark["date"] = pd.to_datetime(benchmark["date"])
    benchmark = benchmark.set_index("date")["close"].sort_index()
    benchmark_before = benchmark.loc[benchmark.index < values.index[0]].dropna()
    benchmark_end = benchmark.reindex(values.index)
    benchmark_missing_dates = [str(d.date()) for d, value in benchmark_end.items() if pd.isna(value)]
    benchmark_return = None
    if len(benchmark_before) and len(benchmark_end) and not benchmark_missing_dates:
        benchmark_return = float(benchmark_end.iloc[-1] / benchmark_before.iloc[-1] - 1)
    core_path = root / "data/toss_v19c_daily/069500_1d.csv"
    core_return = None
    core_missing_dates = [str(d.date()) for d in values.index]
    if core_path.is_file():
        core = pd.read_csv(core_path)
        if {"timestamp", "close"}.issubset(core.columns):
            core_dates = pd.to_datetime(core["timestamp"], utc=True, errors="raise").dt.tz_convert("Asia/Seoul").dt.tz_localize(None).dt.normalize()
            core_series = pd.Series(pd.to_numeric(core["close"], errors="coerce").to_numpy(), index=core_dates).sort_index()
            core_before = core_series.loc[core_series.index < values.index[0]].dropna()
            core_end = core_series.reindex(values.index)
            core_missing_dates = [str(d.date()) for d, value in core_end.items() if pd.isna(value)]
            if len(core_before) and len(core_end) and not core_missing_dates:
                core_return = float(core_end.iloc[-1] / core_before.iloc[-1] - 1)
        else:
            core_missing_dates = [str(d.date()) for d in values.index]
    else:
        core_missing_dates = [str(d.date()) for d in values.index]
    fills = [r for r in trades if r.get("paper_fill_id")]
    buy = sum(1 for r in fills if r["side"] == "BUY")
    sell = sum(1 for r in fills if r["side"] == "SELL")
    orders_by_session: dict[str, dict[str, set[str]]] = {}
    for row in trades:
        bucket = orders_by_session.setdefault(str(row["session_id"]), {"BUY": set(), "SELL": set()})
        bucket[str(row["side"])].add(str(row["symbol"]))
    replacements = sum(1 for bucket in orders_by_session.values() if bucket["BUY"] and bucket["SELL"])
    turnover = sum(abs(float(r["fill_quantity"]) * float(r["fill_price"])) for r in fills) / float(initial)
    investable_buy_hold = None
    if market is not None and execution_spec is not None:
        investable_buy_hold = _costed_buy_hold_069500(root, market, values.index, initial, execution_spec)
        if investable_buy_hold.get("status") != "EXECUTED":
            raise RuntimeError(f"costed 069500 comparison is not executable: {investable_buy_hold}")
    return {
        "start_date": str(values.index[0].date()), "end_date": str(values.index[-1].date()),
        "total_trading_days": len(values), "initial_capital_krw": str(initial), "final_nav_krw": str(final),
        "total_return": float(total_return), "cagr": cagr, "maximum_drawdown": mdd,
        "daily_volatility": vol, "sharpe": sharpe, "benchmark_total_return": benchmark_return,
        "benchmark_excess_return": (float(total_return) - benchmark_return) if benchmark_return is not None else None,
        "benchmark_symbol": "KS11",
        "benchmark_complete_daily_coverage": not benchmark_missing_dates,
        "benchmark_missing_dates": benchmark_missing_dates,
        "069500_adjusted_close_reference_return": core_return,
        "069500_reference_missing_dates": core_missing_dates,
        "069500_reference_is_execution_adjusted": False,
        "069500_investable_buy_and_hold": investable_buy_hold,
        "return_definition": "first_replay_session_close_nav_vs_configured_initial_capital_then_daily_nav_returns",
        "drawdown_includes_opening_initial_capital": True,
        "total_orders": len({r["paper_order_id"] for r in trades}),
        "buy_orders": sum(1 for r in trades if r["side"] == "BUY"),
        "sell_orders": sum(1 for r in trades if r["side"] == "SELL"),
        "buy_fills": buy, "sell_fills": sell, "replacement_count": replacements,
        "turnover": turnover, "turnover_definition": "sum(abs(fill_quantity*fill_price))/initial_capital",
        "total_fee_krw": str(sum((Decimal(str(r["fee"])) for r in fills), Decimal("0"))),
        "total_slippage_krw": str(sum((Decimal(str(r["slippage"])) * Decimal(str(r["fill_quantity"])) for r in fills), Decimal("0"))),
        "worst_daily_return": float(daily.min()) if len(daily) else 0.0,
    }


def _validation(database_url: str, initial: Decimal) -> dict[str, Any]:
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        account = conn.execute("SELECT status,initial_capital_krw FROM paper_account WHERE paper_account_id=%s", (PAPER_ACCOUNT_ID,)).fetchone()
        cash = Decimal(conn.execute("SELECT amount FROM paper_cash WHERE paper_account_id=%s AND currency='KRW'", (PAPER_ACCOUNT_ID,)).fetchone()["amount"])
        positions = conn.execute("SELECT symbol,quantity FROM paper_position WHERE paper_account_id=%s", (PAPER_ACCOUNT_ID,)).fetchall()
        ledger_positions = conn.execute(
            "SELECT symbol,coalesce(sum(quantity_delta),0) AS quantity FROM paper_ledger_event WHERE paper_account_id=%s GROUP BY symbol",
            (PAPER_ACCOUNT_ID,),
        ).fetchall()
        fills = conn.execute("SELECT paper_order_id,quantity,fee,slippage FROM paper_fill").fetchall()
        orders = conn.execute("SELECT paper_order_id,filled_quantity FROM paper_order").fetchall()
        ledger = conn.execute("SELECT cash_delta,fee FROM paper_ledger_event").fetchall()
        recon_failed = conn.execute("SELECT count(*) AS n FROM paper_reconciliation WHERE status='FAILED'").fetchone()["n"]
        duplicate_nav = conn.execute("SELECT count(*)-count(DISTINCT as_of) AS n FROM paper_daily_nav WHERE paper_account_id=%s", (PAPER_ACCOUNT_ID,)).fetchone()["n"]
        nav_accounting_failures = conn.execute(
            "SELECT count(*) AS n FROM paper_daily_nav WHERE paper_account_id=%s AND abs(nav_krw-(cash_krw+positions_value_krw))>0.000000001",
            (PAPER_ACCOUNT_ID,),
        ).fetchone()["n"]
    fill_totals: dict[str, Decimal] = {}
    for row in fills:
        fill_totals[row["paper_order_id"]] = fill_totals.get(row["paper_order_id"], Decimal("0")) + Decimal(row["quantity"])
    order_match = all(Decimal(r["filled_quantity"]) == fill_totals.get(r["paper_order_id"], Decimal("0")) for r in orders)
    position_by_symbol = {str(row["symbol"]): Decimal(row["quantity"]) for row in positions}
    ledger_position_by_symbol = {str(row["symbol"]): Decimal(row["quantity"]) for row in ledger_positions}
    position_symbols = set(position_by_symbol) | set(ledger_position_by_symbol)
    position_ledger_match = all(
        position_by_symbol.get(symbol, Decimal("0")) == ledger_position_by_symbol.get(symbol, Decimal("0"))
        for symbol in position_symbols
    )
    ledger_fee = sum((Decimal(r["fee"]) for r in ledger), Decimal("0"))
    fill_fee = sum((Decimal(r["fee"]) for r in fills), Decimal("0"))
    # Slippage is stored on paper_fill as a per-share price delta, but the
    # cash ledger stores only cash_delta and fee. There is no slippage-ledger
    # column to reconcile, so do not report an unperformed check as passed.
    return {
        "final_cash_krw": str(cash), "negative_cash": cash < 0,
        "negative_position": any(Decimal(r["quantity"]) < 0 for r in positions),
        "position_ledger_matches": position_ledger_match,
        "nav_accounting_matches": int(nav_accounting_failures) == 0,
        "filled_quantity_matches_fills": order_match, "fee_ledger_matches_fills": ledger_fee == fill_fee,
        **_slippage_ledger_validation(),
        "reconciliation_failures": int(recon_failed),
        "daily_nav_duplicate_dates": int(duplicate_nav), "account_status": account["status"],
        "ledger_cash_plus_initial_matches_cash": abs(cash - (initial + sum((Decimal(r["cash_delta"]) for r in ledger), Decimal("0")))) <= Decimal("0.000000001"),
    }


def _slippage_ledger_validation() -> dict[str, Any]:
    """Describe the limit honestly: slippage is not a ledger field today."""
    return {
        "slippage_ledger_matches_fills": None,
        "slippage_ledger_validation": "NOT_TRACKED_IN_LEDGER",
    }


def _signal_parity(built: dict[str, Any], previews: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Compare research-ledger signals with the operational preview signals."""
    ledger = built["ledger"].copy()
    ledger["date"] = pd.to_datetime(ledger["date"])
    selection = built["selection"].copy()
    selection["date"] = pd.to_datetime(selection["date"])
    regime_panel = built["regime"]["panel"]
    rows: list[dict[str, Any]] = []
    for ds, preview in previews.items():
        d = pd.Timestamp(ds)
        target = ledger.loc[ledger["date"].eq(d)]
        selected = selection.loc[selection["date"].eq(d)]
        if target.empty or selected.empty or d not in regime_panel.index:
            continue
        target_row = target.iloc[0]
        leader = next((selected.iloc[0].get(column) for column in ("leader_ticker", "sleeve_ticker", "top_candidate_ticker") if column in selected.columns and pd.notna(selected.iloc[0].get(column))), None)
        research_candidate = None if pd.isna(leader) else str(leader).zfill(6)
        operational_candidate = (preview.get("selected_candidates") or [None])[0]
        research_weights = json.loads(str(target_row["target_weights_json"]))
        operational_weights = {str(k).zfill(6): float(v) for k, v in (preview.get("target_weights") or {}).items()}
        position = ledger.index[ledger["date"].eq(d)].tolist()[0]
        target_changed = position > 0 and str(target_row["target_hash"]) != str(ledger.iloc[position - 1]["target_hash"])
        rows.append({
            "date": d.date().isoformat(),
            "regime_research": str(regime_panel.loc[d]["regime_state"]),
            "regime_operational": str(preview.get("regime")),
            "regime_match": str(regime_panel.loc[d]["regime_state"]) == str(preview.get("regime")),
            "candidate_research": research_candidate,
            "candidate_operational": operational_candidate,
            "candidate_match": research_candidate == operational_candidate,
            "target_hash_research": str(target_row["target_hash"]),
            "target_hash_operational": str(preview.get("target_hash")),
            "target_match": str(target_row["target_hash"]) == str(preview.get("target_hash")),
            "target_symbols_match": set(research_weights) == set(operational_weights),
            "target_weights_match": research_weights == operational_weights,
            "target_changed": target_changed,
        })
    comparable = len(rows)
    def ratio(field: str) -> float | None:
        return sum(bool(row[field]) for row in rows) / comparable if comparable else None
    first_mismatch = next((row for row in rows if not all(row[k] for k in (
        "regime_match", "candidate_match", "target_match", "target_symbols_match", "target_weights_match",
    ))), None)
    first_stage = None
    if first_mismatch:
        for stage, field in (("regime", "regime_match"), ("candidate", "candidate_match"), ("target", "target_match"),
                             ("target", "target_symbols_match"), ("target", "target_weights_match")):
            if not first_mismatch[field]:
                first_stage = stage
                break
    return {
        "rows": rows,
        "comparison_scope": "SHARED_BUILDER_WIRING_CHECK",
        "independent_strategy_validation": False,
        "comparable_dates": comparable,
        "regime_parity": ratio("regime_match"),
        "candidate_parity": ratio("candidate_match"),
        "target_parity": ratio("target_match"),
        "target_symbol_parity": ratio("target_symbols_match"),
        "target_weight_parity": ratio("target_weights_match"),
        "first_mismatch_date": first_mismatch["date"] if first_mismatch else None,
        "first_mismatch_stage": first_stage,
    }


def run_historical_operational_replay(
    root: Path | str,
    database_url: str | None = None,
    *, reset: bool = False, candidate_id: str | None = None,
    start_date: str | None = None, end_date: str | None = None,
    no_op_check: bool = False,
    output_dir: Path | str | None = None,
    execution_reference_resolver: Any = None,
    execution_contract_name: str | None = None,
    execution_contract_hash: str | None = None,
    execution_price_contract: str = "D adjusted open",
) -> dict[str, Any]:
    root = Path(root).resolve()
    database_url = assert_isolated_test_database(database_url or os.environ.get("TEST_DATABASE_URL", ""))
    if execution_reference_resolver is not None and (not execution_contract_hash or not execution_contract_name):
        raise RuntimeError("custom execution reference resolver requires a frozen execution contract name and hash")
    execution_contract_name = execution_contract_name or str(REPLAY_EXECUTION_CONTRACT["name"])
    execution_contract_hash = execution_contract_hash or REPLAY_EXECUTION_CONTRACT_HASH
    if len(execution_contract_hash) != 64 or any(ch not in "0123456789abcdef" for ch in execution_contract_hash.lower()):
        raise RuntimeError("execution contract hash must be a SHA-256 digest")
    execution_resolver_hash = _resolver_fingerprint(execution_reference_resolver)
    out = Path(output_dir) if output_dir else root / "runtime/historical_operational_replay"
    out.mkdir(parents=True, exist_ok=True)
    initialize_paper_schema(database_url)

    replay_candidate_id = candidate_id or "V69_PARENT"
    operations_config = yaml.safe_load((root / "config/v85_operations.yaml").read_text(encoding="utf-8"))
    if Decimal(str(operations_config["initial_capital_krw"])) != INITIAL_CAPITAL:
        raise RuntimeError("historical replay initial capital differs from the Paper operations contract")
    specs = load_candidate_specs(root)
    if replay_candidate_id not in specs:
        raise RuntimeError(f"unknown replay candidate: {replay_candidate_id}")
    built = build_candidate_ledgers(root, specs[replay_candidate_id], use_common_cutoff=True)
    ledger = built["ledger"].copy()
    ledger["date"] = pd.to_datetime(ledger["date"]).dt.date
    lower = pd.Timestamp(start_date).date() if start_date else None
    upper = pd.Timestamp(end_date).date() if end_date else DEFAULT_END
    dates = sorted(d for d in ledger["date"].tolist() if (lower is None or d >= lower) and d <= upper)
    if not dates:
        raise RuntimeError(f"candidate has no replay dates: {replay_candidate_id}")
    execution_data_hash = _intraday_cache_hash(root, dates[0], dates[-1]) if execution_reference_resolver else "NOT_APPLICABLE"
    if reset:
        _truncate_paper_tables(database_url)
    ensure_paper_account(database_url, INITIAL_CAPITAL, ACCOUNT_SOURCE)
    existing = {pd.Timestamp(r["as_of"]).date() for r in _nav_rows(database_url)}
    if existing - set(dates):
        raise RuntimeError("Paper account contains NAV outside this replay period; use an isolated TEST schema")
    replay_contract = _replay_fingerprint(
        root,
        candidate_id=replay_candidate_id,
        candidate_fingerprint=str(specs[replay_candidate_id].fingerprint),
        input_hash=str(built.get("input_hash", "")),
        start=dates[0],
        end=dates[-1],
        database_url=database_url,
        execution_contract_name=execution_contract_name,
        execution_contract_hash=execution_contract_hash,
        execution_resolver_hash=execution_resolver_hash,
        execution_data_hash=execution_data_hash,
    )
    contract_path = out / "replay_contract.json"
    replay_state = _check_or_start_replay_contract(
        contract_path, replay_contract, reset=reset, existing_dates=existing, database_url=database_url
    )
    if not existing and not replay_state.get("completed_dates"):
        opening = load_paper_account(database_url)
        if opening["cash_krw"] != INITIAL_CAPITAL or opening["positions"]:
            raise RuntimeError("fresh replay requires exactly the configured opening cash and no positions")
    artifacts_ready = all((out / name).is_file() for name in OUTPUT_FILES if name != "replay_contract.json")
    if no_op_check and artifacts_ready and set(dates).issubset(existing) and replay_state.get("status") == "COMPLETED":
        nav = _nav_rows(database_url)
        trades = _trade_rows(database_url)
        metrics = _metrics(root, nav, trades, INITIAL_CAPITAL, market=built["market"], execution_spec=built["cfg77"].base_execution)
        validation = _validation(database_url, INITIAL_CAPITAL)
        validation["broker_mutation_calls"] = 0
        return {
            "mode": MODE, "candidate_id": replay_candidate_id,
            "database_scope": "TEST_DATABASE_URL_ONLY", "common_start": str(dates[0]),
            "common_end": str(dates[-1]), "processed_dates": 0,
            "skipped_existing_dates": len(dates), "second_run_no_op": True,
            "metrics": metrics, "parity": {"comparable_dates": 0},
            "signal_parity": {"comparable_dates": 0}, "validation": validation,
            "output_files": list(OUTPUT_FILES),
            "live_hardlock": {"broker_mutation_calls": 0, "live_execution_allowed": False},
        }
    replay_state["status"] = "RUNNING"
    replay_state.pop("failure_type", None)
    _atomic_json(contract_path, replay_state)
    previews: dict[str, dict[str, Any]] = {}
    hold_only_dates: list[dict[str, Any]] = []
    processed = 0
    skipped = 0
    validation_lines: list[str] = [f"mode={MODE}", f"database=TEST_DATABASE_URL", f"range={dates[0]}..{dates[-1]}"]
    try:
        for d in dates:
            ds = d.isoformat()
            preview = build_candidate_strategy_preview(root, replay_candidate_id, as_of=ds)
            previews[ds] = preview
            if d in existing:
                skipped += 1
                if _is_unselected_over_cap_hold(preview):
                    hold_only_dates.append({
                        "date": ds,
                        "reason": _replay_hold_reason(preview),
                        "target_hash": preview.get("target_hash"),
                        "target_weights": preview.get("target_weights", {}),
                        "orders_created": 0,
                    })
                continue
            # The replay label and the invoked model must be the same explicit
            # candidate; falling back to active_strategy.yaml made the default
            # V69_PARENT replay silently execute whichever model was active.
            account = load_paper_account(database_url)
            if _is_unselected_over_cap_hold(preview):
                _save_nav(database_url, root, _freshness_for_replay(ds), session_id=None, authority="HOLD_ONLY")
                hold_only_dates.append({
                    "date": ds,
                    "reason": _replay_hold_reason(preview),
                    "target_hash": preview.get("target_hash"),
                    "target_weights": preview.get("target_weights", {}),
                    "orders_created": 0,
                })
                processed += 1
            else:
                symbols = {str(row["symbol"]).zfill(6) for row in preview.get("targets", [])}
                symbols.update(str(symbol).zfill(6) for symbol in account.get("positions", {}))
                prior_date, sizing_prices, execution_prices = _market_prices_for_session(built["market"], d, symbols)
                sizing_nav = Decimal(account["cash_krw"]) + sum(
                    (
                        Decimal(quantity) * sizing_prices[str(symbol).zfill(6)]
                        for symbol, quantity in account.get("positions", {}).items()
                    ),
                    Decimal("0"),
                )
                preview = apply_replay_preopen_sizing(
                    preview,
                    prior_session=prior_date,
                    sizing_prices=sizing_prices,
                    sizing_nav_krw=sizing_nav,
                    execution_contract_hash=execution_contract_hash,
                    execution_contract_name=execution_contract_name,
                    execution_price_contract=execution_price_contract,
                )
                previews[ds] = preview
                intents = build_intent_previews(
                    preview,
                    account,
                    position_reference_resolver=lambda symbol, prices=sizing_prices: prices[str(symbol).zfill(6)],
                    rebalance_reference_prices=execution_prices,
                )
                save_paper_preview(database_url, preview, intents)
                # Supply D-open marks for all target/held symbols independently
                # of whether they have an order. A custom execution resolver
                # may override only the order-specific reference.
                references = {
                    str(symbol).zfill(6): execution_prices[str(symbol).zfill(6)]
                    for symbol in symbols
                }
                if execution_reference_resolver:
                    references.update(execution_reference_resolver(preview, intents))
                else:
                    references.update({
                        str(intent["intent_id"]): execution_prices[str(intent["symbol"]).zfill(6)]
                        for intent in intents
                    })
                execution = run_paper_execution_cycle(database_url, root, mode="historical-development", execution_references=references)
                if execution.get("broker_mutation_calls") != 0 or execution.get("reconciliation", {}).get("status") != "PASSED":
                    raise RuntimeError(f"Paper replay execution validation failed on {ds}")
                if execution.get("status") == "HOLD_ONLY" or execution.get("blocked_intents"):
                    blocked = execution.get("blocked_intents", [])
                    hold_only_dates.append({
                        "date": ds,
                        "reason": "BLOCKED_INTENTS_OR_EXECUTION_HOLD",
                        "target_hash": preview.get("target_hash"),
                        "target_weights": preview.get("target_weights", {}),
                        "intent_count": len(intents),
                        "blocked_intent_count": len(blocked),
                        "blocked_reasons": sorted({str(item.get("reason") or item.get("risk_status") or "UNKNOWN") for item in blocked}),
                        "order_count": len(execution.get("orders", [])),
                    })
                _save_nav(database_url, root, _freshness_for_replay(ds), session_id=execution.get("session_id"), authority="HOLD_ONLY")
                processed += 1
            existing.add(d)
            replay_state["completed_dates"] = sorted(value.isoformat() for value in existing)
            replay_state["last_completed_date"] = ds
            replay_state["last_state_hash"] = _paper_state_hash(database_url)
            _atomic_json(contract_path, replay_state)
    except BaseException as exc:
        replay_state["status"] = "INTERRUPTED" if isinstance(exc, KeyboardInterrupt) else "FAILED"
        replay_state["failure_type"] = type(exc).__name__
        _atomic_json(contract_path, replay_state)
        raise
    nav = _nav_rows(database_url)
    trades = _trade_rows(database_url)
    parity = _parity(root, previews, candidate_id=replay_candidate_id)
    signal_parity = _signal_parity(built, previews)
    metrics = _metrics(root, nav, trades, INITIAL_CAPITAL, market=built["market"], execution_spec=built["cfg77"].base_execution)
    validation = _validation(database_url, INITIAL_CAPITAL)
    validation["broker_mutation_calls"] = 0
    validation["hold_only_dates"] = hold_only_dates
    validation["hold_only_date_count"] = len(hold_only_dates)
    validation["point_in_time"] = all(not bool(ledger.loc[ledger["date"] == d, "decision_uses_same_day_close"].iloc[0]) for d in dates)
    validation["d_minus_1_contract"] = bool((ledger["information_cutoff"].isna() | (pd.to_datetime(ledger["information_cutoff"]) < pd.to_datetime(ledger["date"]))).all())
    validation["same_date_duplicate_processing"] = skipped == 0 if reset else True
    validation["replay_fingerprint"] = replay_contract["fingerprint"]
    validation["execution_contract_hash"] = execution_contract_hash
    if _input_hash(root) != replay_contract["data_input_hash"]:
        replay_state["status"] = "INVALIDATED_INPUT_CHANGED_DURING_REPLAY"
        _atomic_json(contract_path, replay_state)
        raise RuntimeError("replay input data changed while replay was running")
    if _hash_files(root, REPLAY_CODE_FILES) != replay_contract["code_hash"]:
        replay_state["status"] = "INVALIDATED_CODE_CHANGED_DURING_REPLAY"
        _atomic_json(contract_path, replay_state)
        raise RuntimeError("replay code changed while replay was running")
    if _hash_files(root, REPLAY_INPUT_FILES) != replay_contract["configuration_and_manifest_hash"]:
        replay_state["status"] = "INVALIDATED_CONFIG_OR_MANIFEST_CHANGED_DURING_REPLAY"
        _atomic_json(contract_path, replay_state)
        raise RuntimeError("replay configuration/manifest changed while replay was running")
    if execution_reference_resolver and _intraday_cache_hash(root, dates[0], dates[-1]) != replay_contract["execution_data_hash"]:
        replay_state["status"] = "INVALIDATED_EXECUTION_DATA_CHANGED_DURING_REPLAY"
        _atomic_json(contract_path, replay_state)
        raise RuntimeError("intraday execution data changed while replay was running")
    expected_dates = set(dates)
    actual_nav_dates = {pd.Timestamp(row["as_of"]).date() for row in nav}
    validation["daily_nav_matches_replay_dates"] = actual_nav_dates == expected_dates
    validation["point_in_time"] = bool(validation.get("point_in_time"))
    validation["d_minus_1_contract"] = bool(validation.get("d_minus_1_contract"))
    required_true = (
        "filled_quantity_matches_fills",
        "fee_ledger_matches_fills", "position_ledger_matches", "nav_accounting_matches",
        "daily_nav_matches_replay_dates",
        "ledger_cash_plus_initial_matches_cash", "point_in_time", "d_minus_1_contract",
    )
    failed_checks = [name for name in required_true if validation.get(name) is not True]
    failed_checks.extend(name for name in ("negative_cash", "negative_position") if validation.get(name) is not False)
    if validation.get("reconciliation_failures") != 0:
        failed_checks.append("reconciliation_failures")
    if validation.get("daily_nav_duplicate_dates") != 0:
        failed_checks.append("daily_nav_duplicate_dates")
    if validation.get("broker_mutation_calls") != 0:
        failed_checks.append("broker_mutation_calls")
    if failed_checks:
        replay_state["status"] = "FAILED_FINAL_VALIDATION"
        replay_state["validation_failures"] = failed_checks
        _atomic_json(contract_path, replay_state)
        raise RuntimeError(f"replay final validation failed: {failed_checks}")
    validation_lines += [f"candidate_id={replay_candidate_id}", f"processed_dates={processed}", f"skipped_existing_dates={skipped}", f"parity={parity}", f"signal_parity={signal_parity}", f"validation={validation}"]
    (out / "validation.log").write_text("\n".join(validation_lines) + "\n", encoding="utf-8")
    _write_csv(out / "daily_nav.csv", nav)
    _write_csv(out / "trades.csv", trades)
    (out / "parity_summary.json").write_text(json.dumps(parity, indent=2, default=str) + "\n", encoding="utf-8")
    summary = {
        "mode": MODE, "candidate_id": replay_candidate_id, "database_scope": "TEST_DATABASE_URL_ONLY", "common_start": str(dates[0]),
        "common_end": str(dates[-1]), "processed_dates": processed, "skipped_existing_dates": skipped,
        "second_run_no_op": skipped == len(dates) and processed == 0,
        "metrics": metrics, "parity": parity,
        "signal_parity": signal_parity,
        "hold_only_dates": hold_only_dates,
        "validation": validation,
        "replay_fingerprint": replay_contract["fingerprint"],
        "execution_contract": {
            **REPLAY_EXECUTION_CONTRACT,
            "name": execution_contract_name,
            "hash": execution_contract_hash,
            "execution_price": execution_price_contract,
        },
        "output_files": list(OUTPUT_FILES), "live_hardlock": {"broker_mutation_calls": 0, "live_execution_allowed": False},
    }
    (out / "replay_summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8")
    replay_state["status"] = "COMPLETED"
    replay_state["completed_dates"] = sorted(value.isoformat() for value in existing)
    replay_state["last_completed_date"] = max(existing).isoformat() if existing else None
    _atomic_json(contract_path, replay_state)
    return summary


__all__ = ["MODE", "run_historical_operational_replay"]
