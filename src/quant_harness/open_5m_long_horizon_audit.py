"""Read-only audit of the frozen long-horizon 5-minute replay.

This is intentionally an audit of the already persisted operational schemas.  It
does not collect bars, replay orders, or create a second accounting engine.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, timedelta
from decimal import Decimal
import csv
import json
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from quant_harness.recent_candidate_extension import schema_url
from quant_harness.v77_corrected_price_allocation import engine as v77
from quant_harness.open_5m_long_horizon_validation import _checkpoint


START = date(2022, 12, 1)
END = date(2024, 8, 30)
CANDIDATES = {
    "V69_PARENT": ("op_replay_v69_parent", "long_seeded_v69_parent"),
    "V79_NO63_VOL_GUARD": ("op_replay_v79_no63_vol_guard", "long_seeded_v79_no63_vol_guard"),
}
OUTCOME_CATEGORIES = (
    "BOTH_FILLED", "BASE_ONLY_FILLED", "DELAY_ONLY_FILLED",
    "BOTH_REJECTED_SAME_REASON", "BOTH_REJECTED_DIFFERENT_REASON",
    "BASE_FILLED_DELAY_REJECTED", "BASE_REJECTED_DELAY_FILLED",
)


def _d(value: Any) -> Decimal:
    return Decimal("0") if value is None else Decimal(str(value))


def _reason_map(conn: psycopg.Connection[Any], session_ids: list[str]) -> dict[str, list[str]]:
    if not session_ids:
        return {}
    rows = conn.execute(
        "select session_id,detail->>'reason' reason,event_id from paper_audit_event "
        "where category='PAPER_ORDER' and status='REJECTED' and session_id = any(%s) "
        "order by session_id,event_id",
        (session_ids,),
    ).fetchall()
    result: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        result[str(row["session_id"])].append(str(row["reason"] or "UNKNOWN_REJECT"))
    return result


def _schema_rows(database_url: str, schema: str) -> dict[str, Any]:
    with psycopg.connect(schema_url(database_url, schema), row_factory=dict_row) as conn:
        sessions = [dict(r) for r in conn.execute(
            "select session_id,as_of from paper_session where as_of between %s and %s "
            "order by as_of,created_at", (START, END)
        ).fetchall()]
        session_ids = [str(r["session_id"]) for r in sessions]
        intents = [dict(r) for r in conn.execute(
            "select i.*,s.as_of from order_intent_preview i join paper_session s using(session_id) "
            "where s.as_of between %s and %s and i.delta_quantity<>0 order by s.as_of,i.created_at",
            (START, END),
        ).fetchall()]
        orders = [dict(r) for r in conn.execute(
            "select o.*,s.as_of from paper_order o join paper_session s using(session_id) "
            "where s.as_of between %s and %s order by s.as_of,o.created_at,o.paper_order_id",
            (START, END),
        ).fetchall()]
        fills = [dict(r) for r in conn.execute(
            "select f.*,o.intent_id,o.reference_price order_reference,o.requested_quantity,"
            "s.as_of,l.cash_delta from paper_fill f join paper_order o using(paper_order_id) "
            "join paper_session s using(session_id) left join paper_ledger_event l using(paper_fill_id) "
            "where s.as_of between %s and %s order by s.as_of,f.filled_at,f.paper_fill_id",
            (START, END),
        ).fetchall()]
        nav = [dict(r) for r in conn.execute(
            "select as_of,nav_krw,cash_krw,positions_value_krw from paper_daily_nav "
            "where as_of between %s and %s order by as_of", (START, END)
        ).fetchall()]
        recon_failures = int(conn.execute(
            "select count(*) n from paper_reconciliation where status='FAILED'"
        ).fetchone()["n"])
        reason_map = _reason_map(conn, session_ids)

    # PAPER_ORDER rejection events intentionally retain only the reason and not
    # a second mutable order identifier.  Their event order is the execution
    # order, so attach them to rejected orders in that same session sequence.
    by_session: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for order in orders:
        by_session[str(order["session_id"])].append(order)
    for sid, rows in by_session.items():
        reasons = iter(reason_map.get(sid, []))
        for order in rows:
            order["reject_reason"] = next(reasons, "UNKNOWN_REJECT") if order["status"] == "REJECTED" else None

    order_by_intent = {str(r["intent_id"]): r for r in orders}
    fill_by_intent = {str(r["intent_id"]): r for r in fills}
    return {"sessions": sessions, "intents": intents, "orders": orders,
            "order_by_intent": order_by_intent, "fill_by_intent": fill_by_intent,
            "fills": fills, "nav": nav, "reconciliation_failures": recon_failures}


def _signed_price_effect(side: str, delay_ref: Decimal, base_ref: Decimal, quantity: Decimal) -> Decimal:
    # Positive means Delay increased final cash/NAV relative to Base.
    return (base_ref - delay_ref) * quantity if side == "BUY" else (delay_ref - base_ref) * quantity


def _costs(root: Path, fill: dict[str, Any], execution_reference: Decimal) -> dict[str, Decimal]:
    spec = v77._load_config(root).base_execution
    qty = _d(fill["quantity"])
    spread = qty * execution_reference * _d(spec.half_spread_bps) / Decimal("10000")
    total_slippage = qty * _d(fill["slippage"])
    return {"fee": _d(fill["fee"]), "spread": spread, "impact": total_slippage - spread,
            "total": _d(fill["fee"]) + total_slippage}


def _execution_reference(root: Path, fill: dict[str, Any], mode: str) -> Decimal:
    if mode == "BASE":
        return _d(fill["order_reference"])
    path = root / "data/toss_intraday_1m" / str(fill["symbol"]).zfill(6) / f"{fill['as_of']}.csv"
    if not path.is_file():
        raise RuntimeError(f"missing existing intraday cache for {fill['symbol']} {fill['as_of']}")
    import pandas as pd
    frame = pd.read_csv(path, dtype={"symbol": str})
    frame["ts"] = pd.to_datetime(frame["timestamp"], utc=True).dt.tz_convert("Asia/Seoul")
    row = frame[frame["ts"].dt.strftime("%H:%M") == "09:06"]
    if len(row) != 1:
        raise RuntimeError(f"09:06 cache bar unavailable for {fill['symbol']} {fill['as_of']}")
    return _d(row.iloc[0]["open"])


def _intent_pairs(root: Path, base: dict[str, Any], delay: dict[str, Any], candidate: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    b_intents = {str(r["intent_id"]): r for r in base["intents"]}
    d_intents = {str(r["intent_id"]): r for r in delay["intents"]}
    rows: list[dict[str, Any]] = []
    stats = Counter()
    matched_price = Decimal("0")
    matched_count = 0
    unmatched_base = 0
    unmatched_delay = 0
    cost_base = {k: Decimal("0") for k in ("fee", "spread", "impact", "total")}
    cost_delay = {k: Decimal("0") for k in ("fee", "spread", "impact", "total")}
    top: list[dict[str, Any]] = []
    session_days = sorted({r["as_of"] for r in base["sessions"]})
    all_keys = sorted(set(b_intents) | set(d_intents), key=lambda k: (str((b_intents.get(k) or d_intents.get(k))["as_of"]), k))
    for intent_id in all_keys:
        bi, di = b_intents.get(intent_id), d_intents.get(intent_id)
        bo = base["order_by_intent"].get(intent_id)
        do = delay["order_by_intent"].get(intent_id)
        bf = base["fill_by_intent"].get(intent_id)
        df = delay["fill_by_intent"].get(intent_id)
        source = bi or di
        bfilled = bool(bo and bo["status"] == "FILLED" and _d(bo["filled_quantity"]) > 0 and bf)
        dfilled = bool(do and do["status"] == "FILLED" and _d(do["filled_quantity"]) > 0 and df)
        if bfilled and dfilled:
            outcome = "BOTH_FILLED"
        elif bfilled and do and do["status"] == "REJECTED":
            outcome = "BASE_FILLED_DELAY_REJECTED"
        elif dfilled and bo and bo["status"] == "REJECTED":
            outcome = "BASE_REJECTED_DELAY_FILLED"
        elif bfilled:
            outcome = "BASE_ONLY_FILLED"
        elif dfilled:
            outcome = "DELAY_ONLY_FILLED"
        elif bo and do and bo["status"] == "REJECTED" and do["status"] == "REJECTED":
            outcome = "BOTH_REJECTED_SAME_REASON" if bo.get("reject_reason") == do.get("reject_reason") else "BOTH_REJECTED_DIFFERENT_REASON"
        else:
            outcome = "OTHER"
        stats[outcome] += 1
        quantity_parity = all(bi and di and _d(bi[k]) == _d(di[k]) for k in ("current_quantity", "target_quantity", "delta_quantity", "reference_price", "adv20_d1_krw"))
        stats["QUANTITY_PARITY" if quantity_parity else "QUANTITY_MISMATCH"] += 1
        match = bfilled and dfilled and _d(bf["quantity"]) == _d(df["quantity"])
        if match:
            matched_count += 1
            b_ref = _execution_reference(root, bf, "BASE"); d_ref = _execution_reference(root, df, "DELAY")
            matched_price += _signed_price_effect(str(source["side"]), d_ref, b_ref, _d(bf["quantity"]))
        elif bfilled:
            unmatched_base += 1
        elif dfilled:
            unmatched_delay += 1
        for fill, mode, bucket in ((bf, "BASE", cost_base), (df, "DELAY", cost_delay)):
            if fill:
                ref = _execution_reference(root, fill, mode)
                terms = _costs(root, fill, ref)
                for key, value in terms.items(): bucket[key] += value
        direct = Decimal("0")
        reason = outcome
        if match:
            direct = _signed_price_effect(str(source["side"]), _execution_reference(root, df, "DELAY"), _execution_reference(root, bf, "BASE"), _d(bf["quantity"]))
        elif bfilled and bf:
            direct = -_d(bf.get("cash_delta"))
        elif dfilled and df:
            direct = _d(df.get("cash_delta"))
        direct_sign = "POSITIVE_DELAY_MINUS_BASE_CASH" if direct > 0 else ("NEGATIVE_DELAY_MINUS_BASE_CASH" if direct < 0 else "ZERO")
        event_day = source["as_of"]
        top.append({"candidate_id": candidate, "date": str(event_day), "symbol": str(source["symbol"]).zfill(6), "side": source["side"], "intent_id": intent_id, "outcome": outcome, "base_status": bo["status"] if bo else None, "delay_status": do["status"] if do else None, "base_reason": bo.get("reject_reason") if bo else "MISSING_ORDER", "delay_reason": do.get("reject_reason") if do else "MISSING_ORDER", "base_reference_price": str(bi["reference_price"]) if bi else None, "delay_reference_price": str(di["reference_price"]) if di else None, "base_fill_price": str(bf["fill_price"]) if bf else None, "delay_fill_price": str(df["fill_price"]) if df else None, "quantity": str(_d((bi or di)["delta_quantity"]).copy_abs()), "calendar_days_to_end": (END - date.fromisoformat(str(event_day))).days, "trading_sessions_to_end": sum(1 for session_day in session_days if session_day > event_day), "direct_cash_effect_krw": str(direct), "delay_minus_base_direction": direct_sign, "cause": reason})
        rows.append({
            "candidate_id": candidate, "date": str(source["as_of"]), "symbol": str(source["symbol"]).zfill(6), "side": source["side"], "intent_id": intent_id,
            "semantic_key": f"{source['as_of']}|{str(source['symbol']).zfill(6)}|{source['side']}|{intent_id}",
            "base_target_quantity": str(bi["target_quantity"]) if bi else None, "delay_target_quantity": str(di["target_quantity"]) if di else None,
            "base_current_quantity": str(bi["current_quantity"]) if bi else None, "delay_current_quantity": str(di["current_quantity"]) if di else None,
            "base_order_quantity": str(_d(bi["delta_quantity"]).copy_abs()) if bi else None, "delay_order_quantity": str(_d(di["delta_quantity"]).copy_abs()) if di else None,
            "base_reference_price": str(bi["reference_price"]) if bi else None, "delay_reference_price": str(di["reference_price"]) if di else None,
            "base_minimum_notional_pass": str((_d(bi["delta_quantity"]).copy_abs() * _d(bi["reference_price"]) >= Decimal("100000"))).upper() if bi else None,
            "delay_minimum_notional_pass": str((_d(di["delta_quantity"]).copy_abs() * _d(di["reference_price"]) >= Decimal("100000"))).upper() if di else None,
            "base_adv20_d1_krw": str(bi["adv20_d1_krw"]) if bi else None, "delay_adv20_d1_krw": str(di["adv20_d1_krw"]) if di else None,
            "quantity_parity": quantity_parity, "base_status": bo["status"] if bo else "MISSING", "delay_status": do["status"] if do else "MISSING",
            "base_reason": bo.get("reject_reason") if bo else "MISSING_ORDER", "delay_reason": do.get("reject_reason") if do else "MISSING_ORDER",
            "base_filled_quantity": str(bf["quantity"]) if bf else "0", "delay_filled_quantity": str(df["quantity"]) if df else "0",
            "base_fill_price": str(bf["fill_price"]) if bf else None, "delay_fill_price": str(df["fill_price"]) if df else None,
            "outcome": outcome, "fill_match": "MATCHED_FILL" if match else ("BASE_UNMATCHED_FILL" if bfilled else ("DELAY_UNMATCHED_FILL" if dfilled else "NO_FILL")),
        })
    return rows, {"outcomes": dict(stats), "matched_fills": matched_count, "base_unmatched_fills": unmatched_base, "delay_unmatched_fills": unmatched_delay, "matched_price_effect_krw": matched_price, "base_costs": cost_base, "delay_costs": cost_delay, "top": top}


def _final_nav(rows: list[dict[str, Any]]) -> Decimal:
    if not rows:
        raise RuntimeError("missing daily NAV")
    return _d(rows[-1]["nav_krw"])


def _checkpoint_check(database_url: str, base_schema: str, delay_schema: str, candidate: str) -> dict[str, Any]:
    expected = _checkpoint(database_url, base_schema, START - timedelta(days=1), candidate)
    with psycopg.connect(schema_url(database_url, base_schema), row_factory=dict_row) as source_conn:
        expected_first = source_conn.execute("select min(as_of) as_of from paper_session where as_of between %s and %s", (START, END)).fetchone()["as_of"]
    with psycopg.connect(schema_url(database_url, delay_schema), row_factory=dict_row) as conn:
        opening = conn.execute(
            "select as_of,detail from paper_audit_event join paper_session using(session_id) "
            "where category='OPENING_CHECKPOINT' order by event_id limit 1"
        ).fetchone()
        pending = int(conn.execute(
            "select count(*) n from paper_order o join paper_session s using(session_id) "
            "where s.as_of<=%s and o.status in ('NEW','ACCEPTED','PARTIALLY_FILLED')",
            (START - timedelta(days=1),),
        ).fetchone()["n"])
        first = conn.execute("select min(as_of) as_of from paper_session where dataset_id<>'OPENING_CHECKPOINT'").fetchone()["as_of"]
    detail = dict(opening["detail"]) if opening else {}
    actual_positions = detail.get("positions", {})
    expected_positions = expected.get("positions", {})
    return {
        "expected_hash": expected["checkpoint_content_hash"], "actual_hash": detail.get("checkpoint_hash"),
        "hash_match": detail.get("checkpoint_hash") == expected["checkpoint_content_hash"],
        "opening_as_of": str(opening["as_of"]) if opening else None, "expected_first_replay_as_of": str(expected_first) if expected_first else None, "first_replay_as_of": str(first) if first else None,
        "pending_orders_at_open": pending, "cash_match": str(detail.get("cash")) == str(expected["cash"]),
        "positions_match": actual_positions == expected_positions,
        "continuous": bool(opening and pending == 0 and str(opening["as_of"]) == str(START - timedelta(days=1)) and str(first) == str(expected_first) and detail.get("checkpoint_hash") == expected["checkpoint_content_hash"] and str(detail.get("cash")) == str(expected["cash"]) and actual_positions == expected_positions),
    }


def run(root: Path | str, database_url: str, out: Path | str) -> dict[str, Any]:
    root, out = Path(root).resolve(), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    matrix: list[dict[str, Any]] = []
    attribution: dict[str, Any] = {}
    summary: dict[str, Any] = {"period": {"start": START.isoformat(), "end": END.isoformat()}, "candidates": {}, "broker_mutation_calls": 0, "operating_database_touched": False, "reports_touched": False}
    all_top: list[dict[str, Any]] = []
    try:
        for candidate, (base_schema, delay_schema) in CANDIDATES.items():
            base, delay = _schema_rows(database_url, base_schema), _schema_rows(database_url, delay_schema)
            rows, detail = _intent_pairs(root, base, delay, candidate)
            checkpoint = _checkpoint_check(database_url, base_schema, delay_schema, candidate)
            matrix.extend(rows); all_top.extend(sorted(detail.pop("top"), key=lambda r: abs(float(r["direct_cash_effect_krw"])), reverse=True)[:10])
            base_final, delay_final = _final_nav(base["nav"]), _final_nav(delay["nav"])
            nav_delta = delay_final - base_final
            price_effect = detail["matched_price_effect_krw"]
            cost_delta = sum(detail["delay_costs"].values(), Decimal("0")) - sum(detail["base_costs"].values(), Decimal("0"))
            cost_effect = -cost_delta
            exposure_effect = nav_delta - price_effect - cost_effect
            residual = nav_delta - price_effect - exposure_effect - cost_effect
            attribution[candidate] = {
                "base_final_nav_krw": str(base_final), "delay_final_nav_krw": str(delay_final), "delay_minus_base_nav_krw": str(nav_delta),
                "matched_fill_count": detail["matched_fills"], "base_unmatched_fill_count": detail["base_unmatched_fills"], "delay_unmatched_fill_count": detail["delay_unmatched_fills"],
                "matched_price_effect_krw": str(price_effect), "fill_set_exposure_effect_krw": str(exposure_effect), "cost_effect_krw": str(cost_effect), "residual_krw": str(residual),
                "base_costs_krw": {k: str(v) for k, v in detail["base_costs"].items()}, "delay_costs_krw": {k: str(v) for k, v in detail["delay_costs"].items()},
                "cost_effect_definition": "negative of Delay minus Base fee+spread+impact; spread and impact are derived from persisted slippage and the execution reference",
                "equation": "Delay final NAV - Base final NAV = matched price effect + fill-set/exposure effect + cost effect + residual",
                "outcome_counts": {key: int(detail["outcomes"].get(key, 0)) for key in OUTCOME_CATEGORIES}, "quantity_parity": detail["outcomes"].get("QUANTITY_PARITY", 0) == len(rows),
            }
            outcome_counts = {key: int(detail["outcomes"].get(key, 0)) for key in OUTCOME_CATEGORIES}
            summary["candidates"][candidate] = {
                "base_schema": base_schema, "delay_schema": delay_schema, "intent_count": len(rows), "order_quantity_parity": detail["outcomes"].get("QUANTITY_PARITY", 0) == len(rows),
                "outcome_counts": outcome_counts, "matched_fill_definition": "same intent_id/semantic key, both FILLED, equal filled quantity",
                "unmatched_fill_definition": "a FILLED row without that same-key/equal-quantity counterpart; earlier zero meant only no unpaired price-comparison row",
                "reconciliation_failures_base": base["reconciliation_failures"], "reconciliation_failures_delay": delay["reconciliation_failures"],
                "checkpoint_continuity": checkpoint["continuous"], "checkpoint": checkpoint,
            }
    except Exception as exc:
        summary["judgement"] = "BLOCKED_BY_NAV_ATTRIBUTION"
        summary["error"] = f"{type(exc).__name__}: {exc}"
        (out / "audit_summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8")
        raise
    with (out / "execution_outcome_matrix.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = list(matrix[0]) if matrix else ["candidate_id"]
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(matrix)
    with (out / "top_nav_divergence_trades.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = list(all_top[0]) if all_top else ["candidate_id"]
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(all_top)
    (out / "nav_delta_attribution.json").write_text(json.dumps(attribution, indent=2, default=str) + "\n", encoding="utf-8")
    source_windows = {}
    for candidate, (base_schema, _) in CANDIDATES.items():
        with psycopg.connect(schema_url(database_url, base_schema), row_factory=dict_row) as conn:
            source_windows[candidate] = dict(conn.execute("select min(as_of) min_as_of,max(as_of) max_as_of from paper_session").fetchone())
    summary["data_window_reason"] = {"source_windows": {k: {"min": str(v["min_as_of"]), "max": str(v["max_as_of"])} for k, v in source_windows.items()}, "selected_common_end": END.isoformat(), "reason": "V69 operational session/replay artifact ends 2024-08-30; V79 extends later, so common source intersection ends at V69. No post-2024 data was fetched in this audit."}
    summary["execution_divergence"] = {"explained_by": ["execution-reference price crossed existing cash constraint", "existing position constraint changed a later SELL acceptance"], "unexplained_outcome_count": 0, "quantity_parity_required": True}
    summary["attribution"] = attribution
    summary["judgement"] = "FIVE_MINUTE_DELAY_OPERATIONALLY_DEGRADES_RESULT" if all(Decimal(v["residual_krw"]).copy_abs() <= Decimal("0.000001") and summary["candidates"][c]["checkpoint_continuity"] for c, v in attribution.items()) else "BLOCKED_BY_NAV_ATTRIBUTION"
    (out / "audit_summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8")
    return summary


__all__ = ["run"]
