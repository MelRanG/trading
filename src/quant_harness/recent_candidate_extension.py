"""Two-candidate latest-data extension through the existing Paper replay path."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
import json
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import pandas as pd
import psycopg
from psycopg.rows import dict_row

from quant_harness.historical_operational_replay import assert_isolated_test_database, run_historical_operational_replay
from quant_harness.operational_candidate_comparison import _marks
from quant_harness.operational_candidate_comparison import _install_replay_connection_reuse
from quant_harness.paper_decision_runtime import build_candidate_strategy_preview
from quant_harness.paper_runtime_store import PAPER_ACCOUNT_ID
from quant_harness.paper_runtime_store import initialize_paper_schema
from quant_harness.v104_end_to_end_causal_challenger_audit.adapter import build_candidate_ledgers, load_candidate_specs


CANDIDATES = ("V69_PARENT", "V79_NO63_VOL_GUARD")
INITIAL_CAPITAL = Decimal("10000000")
HISTORICAL_START = "2021-10-13"
HISTORICAL_END = "2026-07-08"
EXTENSION_START = "2026-07-11"


def schema_url(base_url: str, schema: str) -> str:
    parts = urlsplit(base_url)
    query = parse_qsl(parts.query, keep_blank_values=True)
    query.append(("options", f"-c search_path={schema} -c synchronous_commit=off"))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query).replace("+", "%20"), parts.fragment))


def market_coverage(root: Path) -> dict[str, Any]:
    universe = pd.read_csv(root / "data/toss_v19c_daily/universe.csv", dtype={"ticker": str})
    symbols = sorted(universe["ticker"].astype(str).str.zfill(6).unique())
    ends: dict[str, str] = {}
    starts: dict[str, str] = {}
    for symbol in symbols:
        frame = pd.read_csv(root / "data/toss_v19c_daily" / f"{symbol}_1d.csv")
        dates = pd.to_datetime(frame["timestamp"], utc=True).dt.tz_convert("Asia/Seoul").dt.date
        starts[symbol], ends[symbol] = str(min(dates)), str(max(dates))
    benchmark = pd.read_csv(root / "data/all_prices_long_v62_9_expanded.csv", dtype={"ticker": str})
    ks = pd.to_datetime(benchmark.loc[benchmark["ticker"].eq("KS11"), "date"]).dt.date
    starts["KS11"], ends["KS11"] = str(min(ks)), str(max(ks))
    return {"symbols": len(symbols), "start_by_symbol": starts, "end_by_symbol": ends, "etf_cutoff": min(ends[s] for s in symbols), "ks11_cutoff": ends["KS11"], "common_cutoff": min(ends.values())}


def _query_recent(database_url: str, root: Path, start: str, end: str) -> dict[str, Any]:
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        nav = [dict(r) for r in conn.execute("SELECT as_of,nav_krw,cash_krw,positions_value_krw FROM paper_daily_nav WHERE paper_account_id=%s ORDER BY as_of", (PAPER_ACCOUNT_ID,)).fetchall()]
        orders = [dict(r) for r in conn.execute("SELECT o.paper_order_id,o.side,o.status,o.requested_quantity,o.filled_quantity,i.risk_status,s.as_of FROM paper_order o JOIN order_intent_preview i ON i.intent_id=o.intent_id JOIN paper_session s ON s.session_id=o.session_id WHERE s.as_of BETWEEN %s AND %s ORDER BY s.as_of,o.created_at", (start, end)).fetchall()]
        fills = [dict(r) for r in conn.execute("SELECT f.paper_order_id,f.symbol,f.side,f.quantity,f.fill_price,f.fee,f.slippage,s.as_of FROM paper_fill f JOIN paper_order o ON o.paper_order_id=f.paper_order_id JOIN paper_session s ON s.session_id=o.session_id ORDER BY s.as_of,f.filled_at").fetchall()]
        targets = [dict(r) for r in conn.execute("SELECT s.as_of,t.symbol,t.target_weight FROM target_allocation t JOIN strategy_decision d ON d.decision_id=t.decision_id JOIN paper_session s ON s.session_id=d.session_id WHERE s.as_of BETWEEN %s AND %s ORDER BY s.as_of,t.symbol", (start, end)).fetchall()]
        decisions = [dict(r) for r in conn.execute("SELECT as_of,regime,selected_candidates,authority_status FROM strategy_decision WHERE as_of BETWEEN %s AND %s ORDER BY as_of DESC LIMIT 1", (start, end)).fetchall()]
        latest_targets = [dict(r) for r in conn.execute("SELECT t.symbol,t.target_weight,t.target_quantity FROM target_allocation t JOIN strategy_decision d USING(decision_id) WHERE d.as_of=(SELECT max(as_of) FROM strategy_decision WHERE as_of BETWEEN %s AND %s) ORDER BY t.symbol", (start, end)).fetchall()]
        preview_rejected = [dict(r) for r in conn.execute("SELECT o.status,i.risk_status,s.as_of FROM paper_order o JOIN order_intent_preview i ON i.intent_id=o.intent_id JOIN paper_session s ON s.session_id=o.session_id WHERE o.status='REJECTED' AND i.risk_status='PREVIEW_OK' AND s.as_of BETWEEN %s AND %s", (start, end)).fetchall()]
        actual_rejects = [dict(r) for r in conn.execute("SELECT a.detail->>'reason' AS reason,count(*) AS n FROM paper_audit_event a JOIN paper_session s ON s.session_id=a.session_id WHERE a.category='PAPER_ORDER' AND a.status='REJECTED' AND s.as_of BETWEEN %s AND %s GROUP BY a.detail->>'reason'", (start, end)).fetchall()]
        position_change_sessions = int(conn.execute("SELECT count(DISTINCT s.as_of) AS n FROM paper_fill f JOIN paper_order o ON o.paper_order_id=f.paper_order_id JOIN paper_session s ON s.session_id=o.session_id WHERE s.as_of BETWEEN %s AND %s", (start, end)).fetchone()["n"])
        preview_ok_history = int(conn.execute("SELECT count(*) AS n FROM paper_order o JOIN order_intent_preview i ON i.intent_id=o.intent_id WHERE o.status='REJECTED' AND i.risk_status='PREVIEW_OK'").fetchone()["n"])
        recon = int(conn.execute("SELECT count(*) AS n FROM paper_reconciliation WHERE status='FAILED' AND created_at::date BETWEEN %s AND %s", (start, end)).fetchone()["n"])
    recent_nav = [r for r in nav if str(r["as_of"]) >= start and str(r["as_of"]) <= end]
    prior = [r for r in nav if str(r["as_of"]) < start]
    opening = float(prior[-1]["nav_krw"]) if prior else (float(recent_nav[0]["nav_krw"]) if recent_nav else float(INITIAL_CAPITAL))
    ending = float(recent_nav[-1]["nav_krw"]) if recent_nav else opening
    nav_values = [opening] + [float(r["nav_krw"]) for r in recent_nav]
    peak = opening
    mdd = 0.0
    for value in nav_values:
        peak = max(peak, value)
        mdd = min(mdd, value / peak - 1.0)
    cash_weights = [float(r["cash_krw"]) / float(r["nav_krw"]) for r in recent_nav if float(r["nav_krw"])]
    reject_reasons: dict[str, int] = {}
    for row in orders:
        if row["status"] == "REJECTED":
            key = str(row["risk_status"] or "UNKNOWN")
            reject_reasons[key] = reject_reasons.get(key, 0) + 1
    position: dict[str, Decimal] = {}
    fills_by_date: dict[str, list[dict[str, Any]]] = {}
    for row in fills:
        fills_by_date.setdefault(str(row["as_of"]), []).append(row)
    target_by_date: dict[str, dict[str, Decimal]] = {}
    for row in targets:
        target_by_date.setdefault(str(row["as_of"]), {})[str(row["symbol"]).zfill(6)] = Decimal(str(row["target_weight"]))
    tracking: list[float] = []
    for row in nav:
        ds = str(row["as_of"])
        for fill in fills_by_date.get(ds, []):
            symbol = str(fill["symbol"]).zfill(6)
            position[symbol] = position.get(symbol, Decimal("0")) + Decimal(str(fill["quantity"])) * (Decimal("1") if fill["side"] == "BUY" else Decimal("-1"))
        if ds < start or ds > end or ds not in target_by_date:
            continue
        marks = _marks(root, ds, set(position) | set(target_by_date[ds]))
        nav_value = Decimal(str(row["nav_krw"]))
        if nav_value <= 0 or any(symbol not in marks for symbol, qty in position.items() if qty > 0):
            continue
        actual = {symbol: position[symbol] * marks[symbol] / nav_value for symbol in position if position[symbol] > 0}
        symbols = set(actual) | set(target_by_date[ds])
        tracking.append(float(sum(abs(actual.get(symbol, Decimal("0")) - target_by_date[ds].get(symbol, Decimal("0"))) for symbol in symbols)))
    return {"opening_nav_krw": opening, "ending_nav_krw": ending, "total_return_pct": (ending / opening - 1.0) * 100.0 if opening else 0.0, "mdd_pct": mdd * 100.0, "orders": len(orders), "fills": sum(1 for r in orders if Decimal(str(r["filled_quantity"] or 0)) > 0), "rejects": sum(1 for r in orders if r["status"] == "REJECTED"), "reject_reasons": reject_reasons, "actual_reject_reasons": {str(r["reason"]): int(r["n"]) for r in actual_rejects}, "position_change_sessions": position_change_sessions, "cash_weight_mean": sum(cash_weights) / len(cash_weights) if cash_weights else None, "tracking_error_mean": sum(tracking) / len(tracking) if tracking else None, "reconciliation_failures": recon, "decision": decisions[0] if decisions else None, "latest_targets": latest_targets, "preview_ok_rejected": len(preview_rejected), "preview_ok_rejected_all_history": preview_ok_history, "nav_days": len(recent_nav)}


def run_recent_candidate_extension(root: Path | str, database_url: str, output_dir: Path | str) -> dict[str, Any]:
    root = Path(root).resolve()
    database_url = assert_isolated_test_database(database_url)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    _install_replay_connection_reuse()
    coverage = market_coverage(root)
    common_end = coverage["common_cutoff"]
    start = "2026-07-09"
    if common_end < start:
        raise RuntimeError("common cutoff did not advance beyond 2026-07-08")
    results: dict[str, Any] = {}
    for candidate_id in CANDIDATES:
        schema = f"recent_ext_{candidate_id.lower()}"
        with psycopg.connect(database_url) as conn:
            conn.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
        url = schema_url(database_url, schema)
        initialize_paper_schema(url)
        expected = build_candidate_strategy_preview(root, candidate_id, as_of="2026-07-10")
        with psycopg.connect(url, row_factory=dict_row) as conn:
            existing = conn.execute("SELECT count(*) AS n,max(as_of) AS last_day FROM paper_daily_nav").fetchone()
            latest = conn.execute("SELECT input_hash,config_hash,strategy_build_hash,candidate_fingerprint FROM paper_session ORDER BY as_of DESC LIMIT 1").fetchone()
        # New KS11 rows are append-only. Reuse the TEST-only 2026-07-10
        # ledger only when its strategy identity is unchanged. `input_hash`
        # includes the extended dataset and is therefore not a continuation
        # identity check for pre-extension sessions.
        identity_matches = (
            int(existing["n"]) > 0
            and latest is not None
            and all(str(latest[key]) == str(expected[key]) for key in ("config_hash", "strategy_build_hash", "candidate_fingerprint"))
        )
        continuation_ready = identity_matches and str(existing["last_day"]) == "2026-07-10"
        already_extended = identity_matches and str(existing["last_day"]) == common_end
        if not continuation_ready and not already_extended:
            raise RuntimeError(f"{candidate_id}: existing TEST replay is not a verified 2026-07-10 continuation base")
        extension = run_historical_operational_replay(root, url, reset=False, candidate_id=candidate_id, start_date=EXTENSION_START, end_date=common_end, no_op_check=already_extended, output_dir=output / candidate_id)
        second = run_historical_operational_replay(root, url, reset=False, candidate_id=candidate_id, start_date=EXTENSION_START, end_date=common_end, no_op_check=True, output_dir=output / candidate_id)
        results[candidate_id] = {"extension": extension, "second_run": second, "recent": _query_recent(url, root, start, common_end), "schema": schema}
    return {"coverage": coverage, "recent_start": start, "recent_end": common_end, "candidates": results, "broker_mutation_calls": 0, "operating_database_touched": False}


__all__ = ["CANDIDATES", "market_coverage", "run_recent_candidate_extension"]
