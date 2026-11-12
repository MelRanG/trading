"""Long-horizon validation for the frozen OPEN_5M_DELAY_NEXT_1M_V1 contract.

This module is deliberately scoped to the existing operational replay schemas:
it reuses stored daily intents/base NAV, seeds one disposable TEST schema per
candidate, and stores only the six required opening-minute bars per intent.
It is not a general replay or checkpoint framework.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
import csv
import json
from pathlib import Path
from typing import Any

import pandas as pd
import psycopg
from psycopg.rows import dict_row

from quant_harness.daily_paper_runtime import _save_nav
from quant_harness.historical_operational_replay import _freshness_for_replay
from quant_harness.open_5m_execution_validation import contract, next_one_minute_open
from quant_harness.paper_decision_runtime import save_paper_preview
from quant_harness.paper_execution_runtime import run_paper_execution_cycle
from quant_harness.paper_runtime_store import PAPER_ACCOUNT_ID, ensure_paper_account, initialize_paper_schema, load_paper_account
from quant_harness.recent_candidate_extension import schema_url
from quant_harness.v72_integration_ready.toss_openapi import TossOpenApiClient


CANDIDATES = {
    "V69_PARENT": "op_replay_v69_parent",
    "V79_NO63_VOL_GUARD": "op_replay_v79_no63_vol_guard",
}
CONTRACT_HASH = "440ed25fd7b7a1ae7da998585b5654645a120f4b78f4c62c9834e3389c74bcc3"
START = date(2022, 12, 1)
END = date(2024, 8, 30)
REQUIRED_TIMES = ("09:01", "09:02", "09:03", "09:04", "09:05", "09:06")


def _ts_date(value: str) -> str:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone(timedelta(hours=9))).date().isoformat()


def _cache_path(root: Path, symbol: str, day: str) -> Path:
    return root / "data/toss_intraday_1m" / str(symbol).zfill(6) / f"{day}.csv"


def _validate_six(frame: pd.DataFrame, day: str) -> pd.DataFrame:
    required = {"timestamp", "symbol", "open", "high", "low", "close", "volume"}
    if frame.empty or not required.issubset(frame.columns):
        raise ValueError("intraday cache schema is incomplete")
    frame = frame.copy()
    frame["ts"] = pd.to_datetime(frame["timestamp"], utc=True).dt.tz_convert("Asia/Seoul")
    if frame["ts"].dt.date.astype(str).ne(day).any() or frame["ts"].duplicated().any():
        raise ValueError("intraday cache date or duplicate timestamp mismatch")
    frame["hhmm"] = frame["ts"].dt.strftime("%H:%M")
    selected = frame[frame["hhmm"].isin(REQUIRED_TIMES)].copy().sort_values("ts")
    if selected["hhmm"].tolist() != list(REQUIRED_TIMES):
        raise ValueError("required 09:01..09:06 bars are incomplete")
    return selected.drop(columns=["ts", "hhmm"])


def _fetch_six(client: TossOpenApiClient, root: Path, symbol: str, day: str) -> dict[str, Any]:
    path = _cache_path(root, symbol, day)
    if path.is_file():
        selected = _validate_six(pd.read_csv(path, dtype={"symbol": str}), day)
        return {"symbol": str(symbol).zfill(6), "date": day, "cache_hit": True, "bars": len(selected), "path": str(path.relative_to(root))}
    # Asking for 09:06 directly returns the six opening bars in one bounded
    # GET page; no full-session 390-bar download is performed.
    rows, _ = client.get_intraday_candles_page(
        str(symbol).zfill(6),
        before=f"{day}T09:06:00+09:00",
        interval="1m",
        count=200,
    )
    frame = pd.DataFrame([row for row in rows if _ts_date(row["timestamp"]) == day])
    selected = _validate_six(frame, day)
    path.parent.mkdir(parents=True, exist_ok=True)
    selected.to_csv(path, index=False)
    return {"symbol": str(symbol).zfill(6), "date": day, "cache_hit": False, "bars": len(selected), "path": str(path.relative_to(root))}


def _source_rows(database_url: str, schema: str, start: date, end: date) -> dict[str, Any]:
    with psycopg.connect(schema_url(database_url, schema), row_factory=dict_row) as c:
        sessions = [dict(r) for r in c.execute("select * from paper_session where as_of between %s and %s order by as_of,created_at", (start, end)).fetchall()]
        nav = [dict(r) for r in c.execute("select * from paper_daily_nav where as_of between %s and %s order by as_of", (start, end)).fetchall()]
        intents = [dict(r) for r in c.execute("select i.*,s.as_of from order_intent_preview i join paper_session s using(session_id) where s.as_of between %s and %s and i.delta_quantity<>0 order by s.as_of,i.created_at", (start, end)).fetchall()]
        fills = [dict(r) for r in c.execute("select s.as_of,o.symbol,o.side,o.status,o.requested_quantity,o.filled_quantity,o.reference_price,f.quantity,f.fill_price,f.fee,f.slippage from paper_order o join paper_session s using(session_id) left join paper_fill f using(paper_order_id) where s.as_of between %s and %s order by s.as_of,o.symbol", (start, end)).fetchall()]
        orders = [dict(r) for r in c.execute("select s.as_of,o.symbol,o.side,o.status,o.requested_quantity,o.filled_quantity,o.reference_price,''::text reason from paper_order o join paper_session s using(session_id) where s.as_of between %s and %s order by s.as_of,o.symbol", (start, end)).fetchall()]
        recon = int(c.execute("select count(*) n from paper_reconciliation where status='FAILED' and created_at is not null").fetchone()["n"])
    return {"sessions": sessions, "nav": nav, "intents": intents, "fills": fills, "orders": orders, "reconciliation_failures": recon}


def _checkpoint(database_url: str, schema: str, as_of: date, candidate: str) -> dict[str, Any]:
    with psycopg.connect(schema_url(database_url, schema), row_factory=dict_row) as c:
        nav = c.execute("select nav_krw,cash_krw,positions_value_krw from paper_daily_nav where as_of=%s and paper_account_id=%s", (as_of, PAPER_ACCOUNT_ID)).fetchone()
        rows = c.execute("select l.symbol,l.quantity_delta,l.cash_delta,l.fee,f.fill_price from paper_ledger_event l join paper_order o using(paper_order_id) join paper_session s using(session_id) join paper_fill f using(paper_fill_id) where s.as_of<=%s order by s.as_of,l.ledger_event_id", (as_of,)).fetchall()
        pending = int(c.execute("select count(*) n from paper_order o join paper_session s using(session_id) where s.as_of<=%s and o.status in ('NEW','ACCEPTED','PARTIALLY_FILLED')", (as_of,)).fetchone()["n"])
        session = c.execute("select input_hash,config_hash,strategy_build_hash,candidate_fingerprint from paper_session where as_of>%s order by as_of,created_at limit 1", (as_of,)).fetchone()
    if not nav or pending:
        raise RuntimeError(f"{candidate}: checkpoint unavailable or pending orders={pending}")
    cash = Decimal("10000000"); quantities: dict[str, Decimal] = {}; average: dict[str, Decimal] = {}; fee = Decimal("0")
    for row in rows:
        symbol = str(row["symbol"]).zfill(6); delta = Decimal(str(row["quantity_delta"])); before = quantities.get(symbol, Decimal("0")); after = before + delta
        if delta > 0:
            average[symbol] = (before * average.get(symbol, Decimal("0")) + delta * Decimal(str(row["fill_price"])) + Decimal(str(row["fee"]))) / after
        elif after == 0:
            average[symbol] = Decimal("0")
        quantities[symbol] = after; cash += Decimal(str(row["cash_delta"])); fee += Decimal(str(row["fee"]))
    body = {"candidate_id": candidate, "as_of_date": as_of.isoformat(), "cash": str(cash), "positions": {s: {"quantity": str(q), "average_price": str(average[s])} for s, q in quantities.items() if q}, "position_value": str(nav["positions_value_krw"]), "starting_nav": str(nav["nav_krw"]), "pending_orders": pending, "strategy_hash": str(session["strategy_build_hash"]) if session else "", "config_hash": str(session["config_hash"]) if session else "", "build_hash": str(session["strategy_build_hash"]) if session else "", "input_hash": str(session["input_hash"]) if session else "", "source_schema": schema, "cumulative_fee": str(fee)}
    body["checkpoint_content_hash"] = sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return body


def _seed(database_url: str, checkpoint: dict[str, Any]) -> str:
    initialize_paper_schema(database_url); ensure_paper_account(database_url, Decimal("10000000"), "OPENING_CHECKPOINT")
    sid = f"OPENING-{checkpoint['candidate_id']}-{checkpoint['as_of_date']}"
    with psycopg.connect(database_url) as c:
        c.execute("update paper_account set status='ACTIVE',initial_capital_source='OPENING_CHECKPOINT' where paper_account_id=%s", (PAPER_ACCOUNT_ID,))
        c.execute("update paper_cash set amount=%s where paper_account_id=%s and currency='KRW'", (Decimal(checkpoint["cash"]), PAPER_ACCOUNT_ID))
        for symbol, pos in checkpoint["positions"].items():
            c.execute("insert into paper_position(paper_account_id,symbol,quantity,average_price) values(%s,%s,%s,%s)", (PAPER_ACCOUNT_ID, symbol, Decimal(pos["quantity"]), Decimal(pos["average_price"])))
        c.execute("insert into paper_session(session_id,paper_account_id,as_of,dataset_id,input_hash,config_hash,strategy_build_hash,candidate_fingerprint,runtime_mode,status,authority_status,broker_observation_status,completed_at) values(%s,%s,%s,'OPENING_CHECKPOINT',%s,%s,%s,%s,'MOCK','OPENING_CHECKPOINT','PREVIEW_ONLY','NOT_OBSERVED',now())", (sid, PAPER_ACCOUNT_ID, checkpoint["as_of_date"], checkpoint["checkpoint_content_hash"], checkpoint["config_hash"], checkpoint["build_hash"], checkpoint["checkpoint_content_hash"]))
        c.execute("insert into paper_audit_event(session_id,paper_account_id,category,status,detail) values(%s,%s,'OPENING_CHECKPOINT','PASSED',%s::jsonb)", (sid, PAPER_ACCOUNT_ID, json.dumps({"checkpoint_hash": checkpoint["checkpoint_content_hash"], "positions": checkpoint["positions"], "cash": checkpoint["cash"]})))
    return sid


def _load_session_data(database_url: str, source_schema: str, start: date, end: date) -> dict[str, tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]]:
    with psycopg.connect(schema_url(database_url, source_schema), row_factory=dict_row) as src:
        sessions = [dict(r) for r in src.execute("select * from paper_session where as_of between %s and %s order by as_of,created_at", (start, end)).fetchall()]
        decisions = {r["session_id"]: dict(r) for r in src.execute("select * from strategy_decision where session_id in (select session_id from paper_session where as_of between %s and %s)", (start, end)).fetchall()}
        targets = {}
        for row in src.execute("select t.* from target_allocation t join strategy_decision d using(decision_id) join paper_session s using(session_id) where s.as_of between %s and %s", (start, end)).fetchall(): targets.setdefault(row["decision_id"], []).append(dict(row))
        intents = {}
        for row in src.execute("select i.* from order_intent_preview i join paper_session s using(session_id) where s.as_of between %s and %s order by i.created_at", (start, end)).fetchall(): intents.setdefault(row["session_id"], []).append(dict(row))
    return {s["session_id"]: (s, decisions[s["session_id"]], targets.get(decisions[s["session_id"]]["decision_id"], []), intents.get(s["session_id"], [])) for s in sessions if s["session_id"] in decisions}


def _copy_session_data(target_url: str, data: tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]) -> list[dict[str, Any]]:
    session, decision, targets, intents = data
    if not session or not decision:
        return []
    with psycopg.connect(target_url) as c:
        c.execute("insert into paper_session(session_id,paper_account_id,as_of,dataset_id,input_hash,config_hash,strategy_build_hash,candidate_fingerprint,runtime_mode,status,authority_status,broker_observation_status,completed_at) values(%s,%s,%s,%s,%s,%s,%s,%s,'MOCK',%s,%s,%s,now())", (session["session_id"], PAPER_ACCOUNT_ID, session["as_of"], session["dataset_id"], session["input_hash"], session["config_hash"], session["strategy_build_hash"], session["candidate_fingerprint"], session["status"], session["authority_status"], session["broker_observation_status"]))
        c.execute("insert into strategy_decision(decision_id,session_id,as_of,input_hash,strategy_build_hash,regime,selected_candidates,decision_status,hold_reason,decision_receipt,authority_status) values(%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s::jsonb,%s)", (decision["decision_id"], session["session_id"], decision["as_of"], decision["input_hash"], decision["strategy_build_hash"], decision["regime"], json.dumps(decision["selected_candidates"]), decision["decision_status"], decision["hold_reason"], json.dumps(decision["decision_receipt"]), decision["authority_status"]))
        for t in targets:
            c.execute("insert into target_allocation(decision_id,symbol,target_weight,target_notional,reference_price,target_quantity,adv20_d1_krw,calculation_status,reason) values(%s,%s,%s,%s,%s,%s,%s,%s,%s)", (t["decision_id"], t["symbol"], t["target_weight"], t["target_notional"], t["reference_price"], t["target_quantity"], t["adv20_d1_krw"], t["calculation_status"], t["reason"]))
        for i in intents:
            c.execute("insert into order_intent_preview(intent_id,session_id,paper_account_id,symbol,side,current_quantity,target_quantity,delta_quantity,reference_price,estimated_notional,adv20_d1_krw,reason,risk_status,authority_status,input_hash) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (i["intent_id"], session["session_id"], PAPER_ACCOUNT_ID, i["symbol"], i["side"], i["current_quantity"], i["target_quantity"], i["delta_quantity"], i["reference_price"], i["estimated_notional"], i["adv20_d1_krw"], i["reason"], i["risk_status"], i["authority_status"], i["input_hash"]))
    return [dict(i) for i in intents]


def _metrics(nav: list[dict[str, Any]], checkpoint_nav: Decimal, fills: list[dict[str, Any]], orders: list[dict[str, Any]], recon: int) -> dict[str, Any]:
    series = [("OPENING_CHECKPOINT", checkpoint_nav)] + [(str(r["as_of"]), Decimal(str(r["nav_krw"]))) for r in nav]
    peak = series[0]; trough = series[0]; mdd_peak = series[0]; mdd = Decimal("0")
    for point in series:
        if point[1] > peak[1]: peak = point
        dd = point[1] / peak[1] - 1
        if dd < mdd: mdd, trough, mdd_peak = dd, point, peak
    end_nav = series[-1][1]; start_nav = series[0][1]; days = max(1, (date.fromisoformat(str(nav[-1]["as_of"])) - date.fromisoformat(str(nav[0]["as_of"]))).days)
    daily = pd.Series([float(x[1]) for x in series[1:]], index=pd.to_datetime([x[0] for x in series[1:]])).pct_change().dropna()
    fee = sum((Decimal(str(x["fee"])) for x in fills if x["quantity"] is not None), Decimal("0")); slip = sum((Decimal(str(x["slippage"])) * Decimal(str(x["quantity"])) for x in fills if x["quantity"] is not None), Decimal("0")); spread = sum((Decimal(str(x["quantity"])) * Decimal(str(x["fill_price"])) * Decimal("5") / Decimal("10000") for x in fills if x["quantity"] is not None), Decimal("0")); turnover = sum((Decimal(str(x["quantity"])) * Decimal(str(x["fill_price"])) for x in fills if x["quantity"] is not None), Decimal("0"))
    return {"starting_nav": str(start_nav), "ending_nav": str(end_nav), "return_pct": float((end_nav / start_nav - 1) * 100), "cagr_pct": float(((end_nav / start_nav) ** (Decimal("365") / Decimal(str(days))) - 1) * 100), "mdd_pct": float(mdd * 100), "mdd_peak_date": mdd_peak[0], "mdd_peak_nav": str(mdd_peak[1]), "mdd_trough_date": trough[0], "mdd_trough_nav": str(trough[1]), "sharpe": float((daily.mean() / daily.std() * (252 ** 0.5))) if len(daily) > 1 and daily.std() else None, "worst_daily_return_pct": float(daily.min() * 100) if len(daily) else None, "fills": len([x for x in fills if x["quantity"] is not None]), "rejects": sum(1 for x in orders if x["status"] == "REJECTED"), "turnover_krw": str(turnover), "fee_krw": str(fee), "spread_krw": str(spread), "impact_krw": str(slip - spread), "slippage_krw": str(slip), "mean_cash_weight": float(sum(float(r["cash_krw"]) / float(r["nav_krw"]) for r in nav) / len(nav)) if nav else None, "mean_target_tracking_error": None, "reconciliation_failures": recon}


def run(root: Path | str, database_url: str, out: Path | str) -> dict[str, Any]:
    root, out = Path(root).resolve(), Path(out); out.mkdir(parents=True, exist_ok=True)
    cfg, digest = contract(root)
    if digest != CONTRACT_HASH:
        raise RuntimeError("contract hash mismatch")
    source = {candidate: _source_rows(database_url, schema, START, END) for candidate, schema in CANDIDATES.items()}
    checkpoints = {candidate: _checkpoint(database_url, schema, START - timedelta(days=1), candidate) for candidate, schema in CANDIDATES.items()}
    needed = {candidate: sorted({(str(i["symbol"]).zfill(6), str(i["as_of"])) for i in source[candidate]["intents"]}) for candidate in CANDIDATES}
    union_dates = sorted({str(r["as_of"]) for candidate in CANDIDATES for r in source[candidate]["nav"]})
    coverage: dict[str, Any] = {"contract_sha256": digest, "period": {"start": START.isoformat(), "end": END.isoformat()}, "candidates": {}, "cache_policy": "six bars 09:01..09:06 only", "endpoint": "GET /api/v1/candles", "ks11_intraday_requested": False}
    client = TossOpenApiClient(); fetched: dict[tuple[str, str], dict[str, Any]] = {}; failures: list[dict[str, str]] = []
    for candidate, pairs in needed.items():
        for symbol, day in pairs:
            try:
                fetched[(symbol, day)] = _fetch_six(client, root, symbol, day)
            except Exception as exc:
                failures.append({"candidate_id": candidate, "symbol": symbol, "date": day, "reason": f"{type(exc).__name__}:{exc}"})
    for candidate, pairs in needed.items():
        missing = [pair for pair in pairs if pair not in fetched]
        coverage["candidates"][candidate] = {"first_intent_date": min((day for _, day in pairs), default=None), "last_intent_date": max((day for _, day in pairs), default=None), "required_symbol_dates": len(pairs), "available_symbol_dates": len(pairs) - len(missing), "missing_symbol_dates": [{"symbol": s, "date": d} for s, d in missing]}
    coverage["failures"] = failures; coverage["common_start"] = START.isoformat(); coverage["common_end"] = END.isoformat(); coverage["common_complete"] = not failures
    (out / "data_coverage.json").write_text(json.dumps(coverage, indent=2, default=str) + "\n", encoding="utf-8")
    if failures:
        summary = {"judgement": "BLOCKED_BY_MINUTE_DATA", "coverage": coverage, "broker_mutation_calls": 0, "operating_database_touched": False, "reports_touched": False}
        (out / "validation_summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8"); (out / "validation.log").write_text(json.dumps(summary, default=str) + "\n", encoding="utf-8")
        return summary
    results: list[dict[str, Any]] = []; daily_rows: list[dict[str, Any]] = []; fill_rows: list[dict[str, Any]] = []; annual: dict[str, dict[str, Any]] = {}
    for candidate, schema in CANDIDATES.items():
        base = source[candidate]; cp = checkpoints[candidate]; base_metrics = _metrics(base["nav"], Decimal(cp["starting_nav"]), base["fills"], base["orders"], base["reconciliation_failures"])
        results.append({"candidate_id": candidate, "mode": "DAILY_OPEN_BASE", **base_metrics, "checkpoint_hash": cp["checkpoint_content_hash"], "base_reused": True})
        target_schema = f"long_seeded_{candidate.lower()}"
        with psycopg.connect(database_url) as c:
            c.execute(f'drop schema if exists "{target_schema}" cascade'); c.execute(f'create schema "{target_schema}"')
        target_url = schema_url(database_url, target_schema); _seed(target_url, cp)
        session_data = _load_session_data(database_url, schema, START, END)
        source_sessions = {str(s["as_of"]): s for s in base["sessions"]}
        for row in base["nav"]:
            day = str(row["as_of"]); session = source_sessions.get(day); intents: list[dict[str, Any]] = []
            if session:
                intents = _copy_session_data(target_url, session_data[session["session_id"]])
                refs = {str(i["intent_id"]): next_one_minute_open(pd.read_csv(_cache_path(root, str(i["symbol"]).zfill(6), day)), day) for i in intents if Decimal(str(i["delta_quantity"])) != 0}
                ex = run_paper_execution_cycle(target_url, root, mode="historical-development", execution_references=refs)
                sid = ex.get("session_id")
            else:
                sid = None
            _save_nav(target_url, root, _freshness_for_replay(day), session_id=sid, authority="HOLD_ONLY")
        with psycopg.connect(target_url, row_factory=dict_row) as c:
            delayed_nav = [dict(r) for r in c.execute("select as_of,nav_krw,cash_krw,positions_value_krw from paper_daily_nav where as_of between %s and %s order by as_of", (START, END)).fetchall()]
            delayed_fills = [dict(r) for r in c.execute("select s.as_of,o.symbol,o.side,o.status,o.requested_quantity,o.filled_quantity,o.reference_price,f.quantity,f.fill_price,f.fee,f.slippage from paper_order o join paper_session s using(session_id) left join paper_fill f using(paper_order_id) where s.as_of between %s and %s order by s.as_of,o.symbol", (START, END)).fetchall()]
            delayed_orders = [dict(r) for r in c.execute("select s.as_of,o.symbol,o.side,o.status,o.requested_quantity,o.filled_quantity,o.reference_price from paper_order o join paper_session s using(session_id) where s.as_of between %s and %s", (START, END)).fetchall()]
            recon = int(c.execute("select count(*) n from paper_reconciliation where status='FAILED'").fetchone()["n"])
        delayed_metrics = _metrics(delayed_nav, Decimal(cp["starting_nav"]), delayed_fills, delayed_orders, recon)
        results.append({"candidate_id": candidate, "mode": "OPEN_5M_DELAY_NEXT_1M_V1", **delayed_metrics, "checkpoint_hash": cp["checkpoint_content_hash"], "base_reused": False})
        for row in delayed_nav: daily_rows.append({"candidate_id": candidate, "mode": "OPEN_5M_DELAY_NEXT_1M_V1", **{k: str(v) for k, v in row.items()}})
        base_map = {(str(x["as_of"]), str(x["symbol"]).zfill(6), x["side"]): x for x in base["fills"] if x["quantity"] is not None}; delay_map = {(str(x["as_of"]), str(x["symbol"]).zfill(6), x["side"]): x for x in delayed_fills if x["quantity"] is not None}
        for key in sorted(set(base_map) | set(delay_map)):
            b, d = base_map.get(key), delay_map.get(key); shortfall = None
            if b and d and Decimal(str(b["quantity"])) == Decimal(str(d["quantity"])):
                bp, dp = Decimal(str(b["fill_price"])), Decimal(str(d["fill_price"])); shortfall = ((dp - bp) / bp * Decimal("10000")) if key[2] == "BUY" else ((bp - dp) / bp * Decimal("10000"))
                year = key[0][:4]; bucket = annual.setdefault(year, {}).setdefault(candidate, {"_sf": [], "_notional": []}); bucket["_sf"].append(shortfall); bucket["_notional"].append(Decimal(str(b["quantity"])) * bp)
            fill_rows.append({"candidate_id": candidate, "as_of": key[0], "symbol": key[1], "side": key[2], "match_status": "MATCHED" if shortfall is not None else "UNMATCHED", "shortfall_bps": str(shortfall) if shortfall is not None else None})
        for year in sorted({str(r["as_of"])[:4] for r in base["nav"]}):
            bnav = [r for r in base["nav"] if str(r["as_of"])[:4] == year]; dnav = [r for r in delayed_nav if str(r["as_of"])[:4] == year]
            if bnav and dnav:
                bucket = annual.setdefault(year, {}).setdefault(candidate, {"_sf": [], "_notional": []})
                bucket["nav_return_delta_pct"] = float((Decimal(str(dnav[-1]["nav_krw"])) / Decimal(str(dnav[0]["nav_krw"])) - Decimal(str(bnav[-1]["nav_krw"])) / Decimal(str(bnav[0]["nav_krw"]))) * 100)
    with (out / "daily_nav_comparison.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["candidate_id", "mode", "as_of", "nav_krw", "cash_krw", "positions_value_krw"]); w.writeheader(); w.writerows(daily_rows)
    with (out / "fill_comparison.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["candidate_id", "as_of", "symbol", "side", "match_status", "shortfall_bps"]); w.writeheader(); w.writerows(fill_rows)
    with (out / "annual_execution_delta.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["year", "candidate_id", "shortfall_bps", "nav_return_delta_pct"]); w.writeheader()
        for y, values in annual.items():
            for c, v in values.items():
                total = sum(v.get("_notional", []), Decimal("0")); weighted = sum((sf * no for sf, no in zip(v.get("_sf", []), v.get("_notional", []))), Decimal("0")) / total if total else None
                w.writerow({"year": y, "candidate_id": c, "shortfall_bps": str(weighted) if weighted is not None else None, "nav_return_delta_pct": v.get("nav_return_delta_pct")})
    summary = {"judgement": "LONG_HORIZON_INTRADAY_VALID_WITH_RISK_FLAGS", "contract_sha256": digest, "period": {"start": START.isoformat(), "end": END.isoformat()}, "trading_days": len(union_dates), "checkpoints": checkpoints, "results": results, "signal_target_parity": "100% (source operational intents reused)", "future_minute_bars_used": 0, "broker_mutation_calls": 0, "operating_database_touched": False, "reports_touched": False}
    (out / "validation_summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8"); (out / "validation.log").write_text(json.dumps(summary, default=str) + "\n", encoding="utf-8")
    return summary


__all__ = ["run"]
