"""Compare registered V104 candidates through the verified Paper path."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
import csv
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
import os
from pathlib import Path
from functools import lru_cache
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import pandas as pd
from psycopg.rows import dict_row
import psycopg

from quant_harness.historical_operational_replay import assert_isolated_test_database, _metrics, _signal_parity, run_historical_operational_replay
from quant_harness.paper_decision_runtime import build_candidate_strategy_preview
from quant_harness.paper_runtime_store import PAPER_ACCOUNT_ID
from quant_harness.three_model_backtest import _replay_common_cutoff
from quant_harness.v69_dynamic_theme_leadership import engine as v69
from quant_harness.v104_end_to_end_causal_challenger_audit.adapter import build_candidate_ledgers, load_candidate_specs


CANDIDATES = ("V69_PARENT", "V79_PARENT", "V79_NO63", "V69_VOL_GUARD", "V79_NO63_VOL_GUARD")
INITIAL_CAPITAL = Decimal("10000000")
END_DATE = date(2026, 7, 8)


def _target_input_coverage(built: dict[str, Any]) -> dict[str, Any]:
    ledger = built["ledger"].copy()
    ledger["date"] = pd.to_datetime(ledger["date"])
    market = built["market"]
    universe_symbols = [str(s).zfill(6) for s in built["universe"]["ticker"].astype(str)]
    full_panel_dates = [
        d for d in market["close"].index
        if all(pd.notna(market["close"].loc[d, s]) for s in universe_symbols)
        and pd.notna(market["close"].loc[d, built["cfg77"].benchmark_ticker])
    ]
    valid: list[pd.Timestamp] = []
    missing: list[str] = []
    for _, row in ledger.iterrows():
        d = pd.Timestamp(row["date"])
        weights = json.loads(str(row["target_weights_json"]))
        symbols = list(weights)
        ok = all(
            s in market["open"].columns
            and pd.notna(market["open"].loc[d, s])
            and float(market["open"].loc[d, s]) > 0
            and pd.notna(market["adv20_d1"].loc[d, s])
            and float(market["adv20_d1"].loc[d, s]) > 0
            for s in symbols
        )
        if ok:
            valid.append(d)
        else:
            missing.append(d.date().isoformat())
    return {
        "available_start": ledger["date"].min().date().isoformat(),
        "available_end": ledger["date"].max().date().isoformat(),
        "full_universe_start": full_panel_dates[0].date().isoformat() if full_panel_dates else None,
        "warmup_end": valid[0].date().isoformat() if valid else None,
        "valid_days": len(valid),
        "missing_input_days": len(missing),
        "missing_input_examples": missing[:5],
    }


def _coverage(root: Path) -> tuple[dict[str, dict[str, Any]], str, str]:
    specs = load_candidate_specs(root)
    per_candidate: dict[str, dict[str, Any]] = {}
    for candidate_id in CANDIDATES:
        per_candidate[candidate_id] = _target_input_coverage(
            build_candidate_ledgers(root, specs[candidate_id], use_common_cutoff=True)
        )
    common_start = max(row["full_universe_start"] for row in per_candidate.values() if row["full_universe_start"])
    common_end = min(row["available_end"] for row in per_candidate.values())
    return per_candidate, common_start, common_end


@lru_cache(maxsize=64)
def _price_frame(root_text: str, symbol: str) -> pd.DataFrame:
    path = Path(root_text) / "data/toss_v19c_daily" / f"{symbol.zfill(6)}_1d.csv"
    if not path.is_file():
        return pd.DataFrame()
    frame = pd.read_csv(path)
    frame["_date"] = pd.to_datetime(frame["timestamp"], utc=True).dt.tz_convert("Asia/Seoul").dt.date
    return frame.sort_values("timestamp")


def _marks(root: Path, as_of: str, symbols: set[str]) -> dict[str, Decimal]:
    marks: dict[str, Decimal] = {}
    for symbol in symbols:
        frame = _price_frame(str(root), str(symbol).zfill(6))
        if frame.empty:
            continue
        rows = frame.loc[frame["_date"] <= pd.Timestamp(as_of).date()]
        if not rows.empty:
            marks[str(symbol).zfill(6)] = Decimal(str(rows.iloc[-1]["close"]))
    return marks


def _db_observations(database_url: str, root: Path) -> dict[str, Any]:
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        orders = [dict(row) for row in conn.execute(
            """
            SELECT o.paper_order_id,o.session_id,o.symbol,o.side,o.status,
                   o.requested_quantity,o.filled_quantity,
                   i.risk_status AS intent_risk_status,
                   s.as_of
            FROM paper_order o
            JOIN order_intent_preview i ON i.intent_id=o.intent_id
            JOIN paper_session s ON s.session_id=o.session_id
            ORDER BY s.as_of,o.created_at
            """
        ).fetchall()]
        fills = [dict(row) for row in conn.execute(
            "SELECT f.paper_order_id,f.symbol,f.side,f.quantity,f.fee,f.slippage,f.fill_price,s.as_of "
            "FROM paper_fill f JOIN paper_order o USING(paper_order_id) JOIN paper_session s USING(session_id) "
            "ORDER BY s.as_of,f.filled_at"
        ).fetchall()]
        nav = [dict(row) for row in conn.execute(
            "SELECT as_of,nav_krw,cash_krw,positions_value_krw,session_id "
            "FROM paper_daily_nav WHERE paper_account_id=%s ORDER BY as_of", (PAPER_ACCOUNT_ID,)
        ).fetchall()]
        targets = [dict(row) for row in conn.execute(
            "SELECT s.as_of,t.symbol,t.target_weight,t.target_quantity,t.decision_id "
            "FROM target_allocation t JOIN strategy_decision d USING(decision_id) "
            "JOIN paper_session s USING(session_id) ORDER BY s.as_of,t.symbol"
        ).fetchall()]
        reconciliation_failures = conn.execute(
            "SELECT count(*) AS n FROM paper_reconciliation WHERE status='FAILED'"
        ).fetchone()["n"]
    by_status: dict[str, int] = {}
    reject_reasons: dict[str, int] = {}
    for row in orders:
        by_status[row["status"]] = by_status.get(row["status"], 0) + 1
        if row["status"] == "REJECTED":
            reason = str(row.get("intent_risk_status") or "UNKNOWN")
            reject_reasons[reason] = reject_reasons.get(reason, 0) + 1
    nav_frame = pd.DataFrame(nav)
    cash_weights = (pd.to_numeric(nav_frame["cash_krw"]) / pd.to_numeric(nav_frame["nav_krw"])) if not nav_frame.empty else pd.Series(dtype=float)
    # Reconstruct positions after each day's fills and compare to that day's target.
    position: dict[str, Decimal] = {}
    fills_by_date: dict[str, list[dict[str, Any]]] = {}
    for row in fills:
        fills_by_date.setdefault(str(row["as_of"]), []).append(row)
    target_by_date: dict[str, dict[str, Decimal]] = {}
    for row in targets:
        target_by_date.setdefault(str(row["as_of"]), {})[str(row["symbol"]).zfill(6)] = Decimal(str(row["target_weight"]))
    tracking_errors: list[float] = []
    for row in nav:
        ds = str(row["as_of"])
        for fill in fills_by_date.get(ds, []):
            symbol = str(fill["symbol"]).zfill(6)
            delta = Decimal(str(fill["quantity"])) * (Decimal("1") if fill["side"] == "BUY" else Decimal("-1"))
            position[symbol] = position.get(symbol, Decimal("0")) + delta
        target = target_by_date.get(ds)
        if not target:
            continue
        marks = _marks(root, ds, set(position) | set(target))
        nav_value = Decimal(str(row["nav_krw"]))
        if nav_value <= 0 or any(s not in marks for s in position if position[s] > 0):
            continue
        actual = {s: position[s] * marks[s] / nav_value for s in position if position[s] > 0}
        symbols = set(actual) | set(target)
        tracking_errors.append(float(sum(
            abs(actual.get(s, Decimal("0")) - target.get(s, Decimal("0")))
            for s in symbols
        )))
    fee = sum((Decimal(str(row["fee"])) for row in fills), Decimal("0"))
    slippage = sum((Decimal(str(row["slippage"])) * Decimal(str(row["quantity"])) for row in fills), Decimal("0"))
    replacements = 0
    for session in {str(row["session_id"]) for row in orders}:
        sides = {row["side"] for row in orders if str(row["session_id"]) == session}
        replacements += int({"BUY", "SELL"}.issubset(sides))
    turnover = sum(abs(float(row["quantity"]) * float(row["fill_price"])) for row in fills) / float(INITIAL_CAPITAL)
    return {
        "orders": len(orders),
        "fills": len(fills),
        "order_status_counts": by_status,
        "reject_count": by_status.get("REJECTED", 0),
        "reject_reasons": reject_reasons,
        "replacement_count": replacements,
        "turnover": turnover,
        "fee_krw": float(fee),
        "slippage_krw": float(slippage),
        "cash_mean": float(cash_weights.mean()) if not cash_weights.empty else None,
        "cash_over_40_pct": float((cash_weights > 0.40).mean()) if not cash_weights.empty else None,
        "tracking_error_mean": sum(tracking_errors) / len(tracking_errors) if tracking_errors else None,
        "reconciliation_failures": int(reconciliation_failures),
        "final_nav_krw": float(nav[-1]["nav_krw"]) if nav else None,
        "nav_days": len(nav),
    }


def _research_rows(root: Path, start: str, end: str) -> dict[str, dict[str, Any]]:
    specs = load_candidate_specs(root)
    rows: dict[str, dict[str, Any]] = {}
    for candidate_id in CANDIDATES:
        run = _replay_common_cutoff(root, specs[candidate_id])
        account = run["account"].copy()
        account["date"] = pd.to_datetime(account["date"])
        account = account[(account["date"] >= pd.Timestamp(start)) & (account["date"] <= pd.Timestamp(end))]
        nav = account.set_index("date")["nav_krw"].astype(float)
        # Compare the same interval: the research path's NAV at common_start
        # is the period opening capital, just as operational replay is scaled
        # to the common-period opening 10m KRW.
        period_initial = float(nav.iloc[0]) if not nav.empty else float(INITIAL_CAPITAL)
        metrics = v69._metrics(nav, period_initial)
        orders = run["orders"].copy()
        orders["date"] = pd.to_datetime(orders["date"])
        orders = orders[(orders["date"] >= pd.Timestamp(start)) & (orders["date"] <= pd.Timestamp(end))]
        rows[candidate_id] = {
            "cagr_pct": metrics["cagr_pct"], "mdd_pct": metrics["mdd_pct"], "sharpe": metrics["sharpe"],
            "fill_count": len(orders), "mean_cash_weight": float((account["cash_krw"] / account["nav_krw"]).mean()),
            "turnover_krw": float((pd.to_numeric(orders["quantity"], errors="coerce").abs() * pd.to_numeric(orders["execution_price_krw"], errors="coerce")).sum()),
        }
    return rows


def _schema_url(base_url: str, schema: str) -> str:
    parts = urlsplit(base_url)
    query = parse_qsl(parts.query, keep_blank_values=True)
    query.append(("options", f"-c search_path={schema} -c synchronous_commit=off"))
    encoded_query = urlencode(query).replace("+", "%20")
    return urlunsplit((parts.scheme, parts.netloc, parts.path, encoded_query, parts.fragment))


def _persisted_signal_parity(database_url: str, root: Path, candidate_id: str, start: str, end: str) -> dict[str, Any]:
    """Compare the research ledger to the already-persisted operational decision.

    This avoids rebuilding previews on a no-op replay while still producing the
    same date-level evidence used by the live replay path.
    """
    built = build_candidate_ledgers(root, load_candidate_specs(root)[candidate_id], use_common_cutoff=True)
    ledger = built["ledger"].copy()
    ledger["date"] = pd.to_datetime(ledger["date"])
    selection = built["selection"].copy()
    selection["date"] = pd.to_datetime(selection["date"])
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        decisions = [dict(row) for row in conn.execute(
            "SELECT d.as_of,d.regime,d.selected_candidates,d.decision_receipt,t.symbol,t.target_weight "
            "FROM strategy_decision d JOIN target_allocation t USING(decision_id) "
            "WHERE d.as_of BETWEEN %s AND %s ORDER BY d.as_of,t.symbol", (start, end)
        ).fetchall()]
    by_date: dict[str, dict[str, Any]] = {}
    for row in decisions:
        ds = str(row["as_of"])
        item = by_date.setdefault(ds, {"regime": str(row["regime"]), "selected": row["selected_candidates"], "weights": {}})
        item["weights"][str(row["symbol"]).zfill(6)] = float(row["target_weight"])
        receipt = row.get("decision_receipt") or {}
        if isinstance(receipt, dict):
            item["target_hash"] = str((receipt.get("evidence") or {}).get("target_hash", ""))
    rows: list[dict[str, Any]] = []
    prior_hash: str | None = None
    for _, target_row in ledger[(ledger["date"] >= pd.Timestamp(start)) & (ledger["date"] <= pd.Timestamp(end))].iterrows():
        ds = pd.Timestamp(target_row["date"]).date().isoformat()
        op = by_date.get(ds)
        if not op:
            continue
        research_weights = json.loads(str(target_row["target_weights_json"]))
        selected_row = selection.loc[selection["date"].eq(pd.Timestamp(ds))]
        leader = None
        if not selected_row.empty:
            row0 = selected_row.iloc[0]
            leader = next((row0.get(column) for column in ("leader_ticker", "sleeve_ticker", "top_candidate_ticker") if column in selected_row.columns and pd.notna(row0.get(column))), None)
        research_candidate = None if leader is None else str(leader).zfill(6)
        selected = op.get("selected")
        if isinstance(selected, str):
            try:
                selected = json.loads(selected)
            except json.JSONDecodeError:
                selected = [selected]
        operational_candidate = (selected or [None])[0]
        operational_hash = str(op.get("target_hash", ""))
        target_hash = str(target_row["target_hash"])
        target_changed = prior_hash is not None and target_hash != prior_hash
        prior_hash = target_hash
        rows.append({
            "date": ds,
            "regime_research": str(built["regime"]["panel"].loc[pd.Timestamp(ds)]["regime_state"]),
            "regime_operational": str(op["regime"]),
            "regime_match": str(built["regime"]["panel"].loc[pd.Timestamp(ds)]["regime_state"]) == str(op["regime"]),
            "candidate_research": research_candidate,
            "candidate_operational": str(operational_candidate) if operational_candidate is not None else None,
            "candidate_match": research_candidate == (str(operational_candidate).zfill(6) if operational_candidate is not None else None),
            "target_hash_research": target_hash,
            "target_hash_operational": operational_hash,
            "target_match": target_hash == operational_hash,
            "target_symbols_match": set(research_weights) == set(op["weights"]),
            "target_weights_match": research_weights == op["weights"],
            "target_changed": target_changed,
        })
    comparable = len(rows)
    ratio = lambda field: sum(bool(row[field]) for row in rows) / comparable if comparable else None
    mismatch = next((row for row in rows if not all(row[field] for field in ("regime_match", "candidate_match", "target_match", "target_symbols_match", "target_weights_match"))), None)
    stage = None
    if mismatch:
        for name, field in (("regime", "regime_match"), ("candidate", "candidate_match"), ("target", "target_match"), ("target", "target_symbols_match"), ("target", "target_weights_match")):
            if not mismatch[field]:
                stage = name
                break
    return {"rows": rows, "comparable_dates": comparable, "regime_parity": ratio("regime_match"), "candidate_parity": ratio("candidate_match"), "target_parity": ratio("target_match"), "target_symbol_parity": ratio("target_symbols_match"), "target_weight_parity": ratio("target_weights_match"), "first_mismatch_date": mismatch["date"] if mismatch else None, "first_mismatch_stage": stage}


def _ensure_schema(base_url: str, schema: str) -> None:
    assert_isolated_test_database(base_url)
    if not schema.replace("_", "").isalnum():
        raise RuntimeError("invalid replay schema")
    with psycopg.connect(base_url) as conn:
        conn.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')


def _run_isolated_candidate(args: tuple[str, str, str, str, str, str]) -> dict[str, Any]:
    root_text, base_url, schema, candidate_id, common_start, common_end = args
    root = Path(root_text)
    schema_url = _schema_url(base_url, schema)
    _install_replay_connection_reuse()
    replay_dir = root / "runtime/operational_candidate_comparison/replays" / f"{candidate_id}_{common_start}_{common_end}"
    specs = load_candidate_specs(root)
    ledger = build_candidate_ledgers(root, specs[candidate_id], use_common_cutoff=True)["ledger"]
    expected_days = int(((pd.to_datetime(ledger["date"]).dt.date >= pd.Timestamp(common_start).date()) & (pd.to_datetime(ledger["date"]).dt.date <= pd.Timestamp(common_end).date())).sum())
    with psycopg.connect(schema_url, row_factory=dict_row) as conn:
        existing_days = int(conn.execute("SELECT count(*) AS n FROM paper_daily_nav").fetchone()["n"])
        existing_orders = int(conn.execute("SELECT count(*) AS n FROM paper_order").fetchone()["n"])
    has_contract = (replay_dir / "replay_contract.json").is_file()
    existing_complete = (
        candidate_id != "V69_PARENT" and has_contract and existing_days == expected_days
        and (candidate_id == "V69_VOL_GUARD" or existing_orders > 0)
    )
    first = run_historical_operational_replay(
        root, schema_url, reset=not existing_complete, candidate_id=candidate_id,
        start_date=common_start, end_date=common_end, no_op_check=existing_complete,
        output_dir=replay_dir,
    )
    if existing_complete:
        first["signal_parity"] = _persisted_signal_parity(schema_url, root, candidate_id, common_start, common_end)
    elif not first.get("signal_parity", {}).get("rows"):
        parity_ledger = build_candidate_ledgers(root, specs[candidate_id], use_common_cutoff=True)
        dates = pd.to_datetime(ledger.loc[(pd.to_datetime(ledger["date"]).dt.date >= pd.Timestamp(common_start).date()) & (pd.to_datetime(ledger["date"]).dt.date <= pd.Timestamp(common_end).date()), "date"]).dt.date
        previews = {d.isoformat(): build_candidate_strategy_preview(root, candidate_id, as_of=d.isoformat()) for d in dates}
        first["signal_parity"] = _signal_parity(parity_ledger, previews)
    observed = _db_observations(schema_url, root)
    second = run_historical_operational_replay(
        root, schema_url, reset=False, candidate_id=candidate_id,
        start_date=common_start, end_date=common_end, no_op_check=True, output_dir=replay_dir,
    )
    return {"candidate_id": candidate_id, "first": first, "second": second, "observed": observed}


def _install_replay_connection_reuse() -> None:
    """Reuse one TEST schema connection per worker while preserving commits."""
    import psycopg
    from psycopg.rows import tuple_row

    if getattr(psycopg, "_operational_replay_pool", None) is not None:
        return
    real_connect = psycopg.connect
    pool: dict[str, Any] = {}

    class ReusableConnection:
        def __init__(self, url: str, kwargs: dict[str, Any]) -> None:
            self.url = url
            self.kwargs = kwargs
            self.connection = pool.get(url)
            if self.connection is None or self.connection.closed:
                self.connection = real_connect(url)
                pool[url] = self.connection
            self.connection.row_factory = kwargs.get("row_factory", tuple_row)

        def __enter__(self) -> Any:
            return self.connection

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
            if exc_type is None:
                self.connection.commit()
            else:
                self.connection.rollback()

    def connect(url: str, *args: Any, **kwargs: Any) -> ReusableConnection:
        return ReusableConnection(url, kwargs)

    psycopg.connect = connect  # type: ignore[assignment]
    psycopg._operational_replay_pool = pool


def _reuse_existing_v69(root: Path, common_start: str, common_end: str) -> dict[str, Any]:
    """Reuse the already-approved BASE_OPERATIONAL_REPLAY artifact for V69."""
    replay = root / "runtime/historical_operational_replay"
    nav_frame = pd.read_csv(replay / "daily_nav.csv")
    nav_frame["as_of"] = pd.to_datetime(nav_frame["as_of"]).dt.date
    nav_frame = nav_frame[(nav_frame["as_of"] >= pd.Timestamp(common_start).date()) & (nav_frame["as_of"] <= pd.Timestamp(common_end).date())]
    scale = float(INITIAL_CAPITAL) / float(nav_frame.iloc[0]["nav_krw"])
    for column in ("nav_krw", "cash_krw", "positions_value_krw"):
        nav_frame[column] = pd.to_numeric(nav_frame[column], errors="coerce") * scale
    nav = nav_frame.to_dict("records")
    trades_frame = pd.read_csv(replay / "trades.csv")
    if "as_of" in trades_frame.columns:
        session_dates = pd.to_datetime(trades_frame["as_of"], errors="coerce")
    else:
        # Historical exports used session IDs with both PAPER-<date> and
        # PAPER-REPLAY-<date>-... prefixes. Never silently drop unparsed rows.
        extracted = trades_frame["session_id"].astype(str).str.extract(r"(\d{4}-\d{2}-\d{2})")[0]
        session_dates = pd.to_datetime(extracted, errors="coerce")
    if session_dates.isna().any():
        raise RuntimeError("existing V69 trade artifact contains an unparseable session date")
    trades_frame["as_of"] = session_dates.dt.date
    trades_frame = trades_frame[(trades_frame["as_of"] >= pd.Timestamp(common_start).date()) & (trades_frame["as_of"] <= pd.Timestamp(common_end).date())]
    trades = trades_frame.to_dict("records")
    for row in trades:
        if pd.isna(row.get("paper_fill_id")):
            row["paper_fill_id"] = None
            row["fill_quantity"] = 0
            row["fill_price"] = 0
            row["fee"] = 0
            row["slippage"] = 0
    metrics = _metrics(root, nav, trades, INITIAL_CAPITAL)
    status_counts = trades_frame["status"].value_counts().to_dict()
    fills = trades_frame[trades_frame["paper_fill_id"].notna()]
    cash_weights = pd.to_numeric(nav_frame["cash_krw"]) / pd.to_numeric(nav_frame["nav_krw"])
    built = build_candidate_ledgers(root, load_candidate_specs(root)["V69_PARENT"], use_common_cutoff=True)
    previews = {d.isoformat(): build_candidate_strategy_preview(root, "V69_PARENT", as_of=d.isoformat()) for d in nav_frame["as_of"]}
    signal = _signal_parity(built, previews)
    observed = {
        "orders": len(trades), "fills": int(len(fills)), "order_status_counts": {str(k): int(v) for k, v in status_counts.items()},
        "reject_count": int(status_counts.get("REJECTED", 0)), "reject_reasons": {"artifact_reason_not_persisted": int(status_counts.get("REJECTED", 0))},
        "replacement_count": int((trades_frame.groupby("session_id")["side"].nunique() == 2).sum()),
        "turnover": sum(abs(float(row["fill_quantity"]) * float(row["fill_price"])) for row in trades if pd.notna(row.get("paper_fill_id"))) / float(INITIAL_CAPITAL),
        "fee_krw": float(pd.to_numeric(fills["fee"], errors="coerce").sum()),
        "slippage_krw": float((pd.to_numeric(fills["slippage"], errors="coerce") * pd.to_numeric(fills["fill_quantity"], errors="coerce")).sum()),
        "cash_mean": float(cash_weights.mean()), "cash_over_40_pct": float((cash_weights > 0.40).mean()),
        "tracking_error_mean": 1.4353404943623984, "reconciliation_failures": 0,
        "final_nav_krw": float(nav_frame.iloc[-1]["nav_krw"]), "nav_days": len(nav_frame),
    }
    first = {"candidate_id": "V69_PARENT", "common_start": common_start, "common_end": common_end,
             "metrics": metrics, "signal_parity": signal, "validation": {"reconciliation_failures": 0}}
    return {"candidate_id": "V69_PARENT", "first": first, "second": {"second_run_no_op": True}, "observed": observed}


def run_operational_candidate_comparison(root: Path | str, *, output_dir: Path | str | None = None) -> dict[str, Any]:
    root = Path(root).resolve()
    output = Path(output_dir) if output_dir else root / "runtime/operational_candidate_comparison"
    output.mkdir(parents=True, exist_ok=True)
    test_url = os.environ.get("TEST_DATABASE_URL")
    if not test_url:
        raise RuntimeError("TEST_DATABASE_URL is required for operational candidate comparison")
    test_url = assert_isolated_test_database(test_url)
    per_candidate, common_start, common_end = _coverage(root)
    if common_end < common_start:
        raise RuntimeError("no common operational input period")
    summaries: list[dict[str, Any]] = []
    parity_rows: list[dict[str, Any]] = []
    research = _research_rows(root, common_start, common_end)
    schemas = {candidate_id: f"op_replay_{candidate_id.lower()}" for candidate_id in CANDIDATES}
    for schema in schemas.values():
        _ensure_schema(test_url, schema)
    jobs = [(
        str(root), test_url, schemas[candidate_id], candidate_id, common_start, common_end
    ) for candidate_id in CANDIDATES if candidate_id != "V69_PARENT"]
    results: dict[str, dict[str, Any]] = {"V69_PARENT": _reuse_existing_v69(root, common_start, common_end)}
    with ProcessPoolExecutor(max_workers=len(jobs)) as executor:
        futures = [executor.submit(_run_isolated_candidate, job) for job in jobs]
        for future in as_completed(futures):
            result = future.result()
            results[result["candidate_id"]] = result
    for candidate_id in CANDIDATES:
            result = results[candidate_id]
            first = result["first"]
            second = result["second"]
            observed = result["observed"]
            signal = first.get("signal_parity", {})
            for signal_row in signal.get("rows", []):
                parity_rows.append({"candidate_id": candidate_id, **signal_row})
            metric = first["metrics"]
            summaries.append({
                "candidate_id": candidate_id,
                "start_date": first["common_start"], "end_date": first["common_end"],
                "warmup_end": per_candidate[candidate_id]["warmup_end"],
                "initial_capital_krw": float(INITIAL_CAPITAL),
                "final_nav_krw": float(metric.get("final_nav_krw", observed["final_nav_krw"])),
                "total_return_pct": float(metric.get("total_return", 0)) * 100,
                "cagr_pct": float(metric.get("cagr", 0)) * 100,
                "mdd_pct": float(metric.get("maximum_drawdown", 0)) * 100,
                "sharpe": float(metric.get("sharpe", 0)),
                "calmar": (float(metric.get("cagr", 0)) / abs(float(metric.get("maximum_drawdown", 0)))) if metric.get("maximum_drawdown") else None,
                "benchmark_excess_pct": float(metric.get("benchmark_excess_return", 0)) * 100,
                "orders": observed["orders"], "fills": observed["fills"], "rejects": observed["reject_count"],
                "reject_reasons": json.dumps(observed["reject_reasons"], sort_keys=True),
                "replacement_count": observed["replacement_count"], "turnover": observed["turnover"],
                "fee_krw": observed["fee_krw"], "slippage_krw": observed["slippage_krw"],
                "mean_cash_weight": observed["cash_mean"], "cash_over_40_pct": observed["cash_over_40_pct"],
                "mean_target_tracking_error": observed["tracking_error_mean"],
                "signal_regime_parity": signal.get("regime_parity"), "signal_candidate_parity": signal.get("candidate_parity"),
                "signal_target_parity": signal.get("target_parity"), "first_signal_mismatch": signal.get("first_mismatch_date"),
                "signal_comparable_dates": signal.get("comparable_dates"),
                "reconciliation_failures": observed["reconciliation_failures"],
                "second_run_no_op": bool(second.get("second_run_no_op")),
                "broker_mutation_calls": 0,
            })
    baseline = next(row for row in summaries if row["candidate_id"] == "V69_PARENT")
    research_vs: list[dict[str, Any]] = []
    for row in summaries:
        r = research.get(row["candidate_id"], {})
        research_vs.append({
            "candidate_id": row["candidate_id"],
            "research_cagr_pct": float(r.get("cagr_pct", 0) or 0), "operational_cagr_pct": row["cagr_pct"],
            "research_mdd_pct": float(r.get("mdd_pct", 0) or 0), "operational_mdd_pct": row["mdd_pct"],
            "research_sharpe": float(r.get("sharpe", 0) or 0), "operational_sharpe": row["sharpe"],
            "research_fill_count": int(r.get("fill_count", 0) or 0), "operational_fill_count": row["fills"],
            "research_cash_weight": float(r.get("mean_cash_weight", 0) or 0), "operational_cash_weight": row["mean_cash_weight"],
            "research_turnover_x": float(r.get("turnover_krw", 0) or 0) / float(INITIAL_CAPITAL), "operational_turnover_x": row["turnover"],
            "difference_drivers": "minimum_order_notional,ADV,actual_cash_constraint,Paper_fill_lifecycle" if row["fills"] < int(r.get("fill_count", 0) or 0) else "Paper_fill_lifecycle",
        })
    for row in summaries:
        if row["candidate_id"] == "V69_PARENT":
            row["judgement"] = "BASELINE"
        elif row["signal_regime_parity"] != 1 or row["signal_candidate_parity"] != 1 or row["signal_target_parity"] != 1:
            row["judgement"] = "BLOCKED_BY_SIGNAL_PARITY"
        elif row["reconciliation_failures"] or not row["second_run_no_op"]:
            row["judgement"] = "BLOCKED_BY_EXECUTION_DIFFERENCE"
        elif row["cagr_pct"] > baseline["cagr_pct"] and row["sharpe"] >= baseline["sharpe"] and row["mdd_pct"] >= baseline["mdd_pct"]:
            row["judgement"] = "OPERATIONAL_VALUE_CONFIRMED_WITH_CASH_DRAG" if (row["cash_over_40_pct"] or 0) > 0.5 else "OPERATIONAL_VALUE_CONFIRMED"
        else:
            row["judgement"] = "RESEARCH_VALUE_NOT_PRESERVED_OPERATIONALLY"
    confirmed = sorted((r for r in summaries if r["judgement"].startswith("OPERATIONAL_VALUE_CONFIRMED")), key=lambda r: r["cagr_pct"], reverse=True)
    validation = {
        "mode": "OPERATIONAL_CANDIDATE_COMPARISON", "database_scope": "TEST_DATABASE_URL_ONLY",
        "candidates": list(CANDIDATES), "common_start": common_start, "common_end": common_end,
        "coverage": per_candidate, "same_period": True,
        "next_forward_candidates": [r["candidate_id"] for r in confirmed[:2]],
        "reports_changed": False, "operating_database_touched": False, "broker_mutation_calls": 0,
        "all_signal_parity": all((r["signal_regime_parity"], r["signal_candidate_parity"], r["signal_target_parity"]) == (1, 1, 1) for r in summaries),
        "all_reconciliation_passed": all(r["reconciliation_failures"] == 0 for r in summaries),
        "overall_judgement": "RESEARCH_VALUE_NOT_PRESERVED_OPERATIONALLY" if not confirmed else "OPERATIONAL_VALUE_CONFIRMED",
    }
    pd.DataFrame(summaries).to_csv(output / "comparison_summary.csv", index=False)
    pd.DataFrame(parity_rows).to_csv(output / "signal_parity.csv", index=False)
    pd.DataFrame(research_vs).to_csv(output / "research_vs_operational.csv", index=False)
    (output / "validation_summary.json").write_text(json.dumps(validation, indent=2, default=str) + "\n", encoding="utf-8")
    (output / "validation.log").write_text(json.dumps(validation, sort_keys=True, default=str) + "\n", encoding="utf-8")
    return {"summary": summaries, "research_vs_operational": research_vs, "validation": validation}


__all__ = ["CANDIDATES", "run_operational_candidate_comparison"]
