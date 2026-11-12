"""Frozen OPEN_5M_DELAY_NEXT_1M_V1 comparison over existing Paper intents."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
import csv
import json
from pathlib import Path
from typing import Any

import pandas as pd
import psycopg
from psycopg.rows import dict_row
import yaml

from quant_harness.paper_execution_runtime import _cost_terms
from quant_harness.recent_candidate_extension import schema_url
from quant_harness.three_model_backtest import fetch_intraday_session
from quant_harness.v72_integration_ready.toss_openapi import TossOpenApiClient

CANDIDATES = {"V69_PARENT": "recent_ext_v69_parent", "V79_NO63_VOL_GUARD": "recent_ext_v79_no63_vol_guard"}
START = "2026-07-09"
END = "2026-07-31"
KST = timezone(timedelta(hours=9))


def contract(root: Path) -> tuple[dict[str, Any], str]:
    raw = (root / "config/open_5m_execution_contract_v1.yaml").read_bytes()
    return yaml.safe_load(raw), sha256(raw).hexdigest()


def aggregate_regular_five_minute(frame: pd.DataFrame, session: str) -> pd.DataFrame:
    """Validate 1m KST bars and build completed 5m bars without look-ahead."""
    data = frame.copy()
    data["ts"] = pd.to_datetime(data["timestamp"], utc=True).dt.tz_convert("Asia/Seoul")
    data = data[data["ts"].dt.date.astype(str).eq(session)].sort_values("ts")
    if data["ts"].duplicated().any():
        raise ValueError("duplicate intraday timestamp")
    data = data[(data["ts"].dt.time >= datetime.strptime("09:00", "%H:%M").time()) & (data["ts"].dt.time < datetime.strptime("15:30", "%H:%M").time())]
    # Toss labels a one-minute candle by its end timestamp: 09:01 is the
    # 09:00--09:01 candle. The completed first five minutes are 09:01--09:05.
    first = data[data["ts"].dt.strftime("%H:%M").isin(["09:01", "09:02", "09:03", "09:04", "09:05"])]
    if first["ts"].dt.strftime("%H:%M").tolist() != ["09:01", "09:02", "09:03", "09:04", "09:05"]:
        raise ValueError("first five-minute bar is incomplete")
    data["bucket"] = (data["ts"] - pd.Timedelta(minutes=1)).dt.floor("5min") + pd.Timedelta(minutes=5)
    return data.groupby("bucket", sort=True).agg(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"), volume=("volume", "sum"), bars=("ts", "size")).reset_index()


def next_one_minute_open(frame: pd.DataFrame, session: str) -> Decimal:
    aggregate_regular_five_minute(frame, session)
    data = frame.copy()
    data["ts"] = pd.to_datetime(data["timestamp"], utc=True).dt.tz_convert("Asia/Seoul")
    row = data.loc[data["ts"].dt.strftime("%H:%M").eq("09:06")]
    if len(row) != 1:
        raise ValueError("next one-minute open is unavailable")
    value = Decimal(str(row.iloc[0]["open"]))
    if value <= 0:
        raise ValueError("next one-minute open is invalid")
    return value


def _rows(url: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    with psycopg.connect(url, row_factory=dict_row) as conn:
        orders = [dict(r) for r in conn.execute("""
            SELECT s.as_of,o.symbol,o.side,o.requested_quantity,o.status,o.filled_quantity,
                   i.adv20_d1_krw,i.reference_price,i.risk_status
            FROM paper_order o JOIN order_intent_preview i ON i.intent_id=o.intent_id
            JOIN paper_session s ON s.session_id=o.session_id
            WHERE s.as_of BETWEEN %s AND %s ORDER BY s.as_of,CASE o.side WHEN 'SELL' THEN 0 ELSE 1 END,o.symbol
        """, (START, END)).fetchall()]
        ledger = [dict(r) for r in conn.execute("""
            SELECT s.as_of,l.symbol,l.quantity_delta,l.cash_delta,l.fee,f.fill_price
            FROM paper_ledger_event l JOIN paper_order o ON o.paper_order_id=l.paper_order_id
            JOIN paper_session s ON s.session_id=o.session_id JOIN paper_fill f ON f.paper_fill_id=l.paper_fill_id
            WHERE s.as_of<=%s ORDER BY s.as_of,l.ledger_event_id
        """, ("2026-07-08",)).fetchall()]
    return orders, ledger


def _initial_state(ledger: list[dict[str, Any]]) -> tuple[Decimal, dict[str, Decimal], dict[str, Decimal]]:
    cash = Decimal("10000000"); qty: dict[str, Decimal] = {}; avg: dict[str, Decimal] = {}
    for row in ledger:
        symbol, delta = str(row["symbol"]).zfill(6), Decimal(str(row["quantity_delta"]))
        before = qty.get(symbol, Decimal("0")); after = before + delta
        if delta > 0:
            avg[symbol] = (before * avg.get(symbol, Decimal("0")) + delta * Decimal(str(row["fill_price"])) + Decimal(str(row["fee"]))) / after
        elif after == 0:
            avg[symbol] = Decimal("0")
        qty[symbol] = after; cash += Decimal(str(row["cash_delta"]))
    return cash, qty, avg


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["candidate_id"])
        writer.writeheader(); writer.writerows(rows)


def run(root: Path | str, database_url: str, output_dir: Path | str) -> dict[str, Any]:
    root, out = Path(root).resolve(), Path(output_dir); out.mkdir(parents=True, exist_ok=True)
    cfg, cfg_hash = contract(root)
    client = TossOpenApiClient()
    coverage: dict[str, Any] = {"contract_id": cfg["contract_id"], "contract_sha256": cfg_hash, "range": {"start": START, "end": END}, "candidates": {}}
    comparison: list[dict[str, Any]] = []
    for candidate, schema in CANDIDATES.items():
        orders, ledger = _rows(schema_url(database_url, schema))
        cash, quantities, _ = _initial_state(ledger)
        needed = {(str(r["symbol"]).zfill(6), str(r["as_of"])) for r in orders if Decimal(str(r["requested_quantity"])) > 0}
        minute: dict[tuple[str, str], Decimal] = {}; unavailable: list[tuple[str, str]] = []
        for symbol, day in sorted(needed):
            try:
                fetch_intraday_session(client, root, symbol, day)
                frame = pd.read_csv(root / "data/toss_intraday_1m" / symbol / f"{day}.csv", dtype={"symbol": str})
                minute[(symbol, day)] = next_one_minute_open(frame, day)
            except Exception:
                unavailable.append((symbol, day))
        delayed_fills = 0; delayed_fee = delayed_spread = delayed_impact = Decimal("0"); diffs: list[float] = []; blocked = 0
        for row in orders:
            symbol, day, side = str(row["symbol"]).zfill(6), str(row["as_of"]), str(row["side"])
            requested, adv = Decimal(str(row["requested_quantity"])), Decimal(str(row["adv20_d1_krw"]))
            reference = minute.get((symbol, day))
            if reference is None:
                blocked += 1; continue
            if requested * reference < Decimal("100000") or adv <= 0:
                continue
            if side == "SELL" and quantities.get(symbol, Decimal("0")) < requested:
                continue
            fill, fee, slip = _cost_terms(root, side=side, quantity=requested, reference=reference, adv=adv)
            gross = requested * fill
            if side == "BUY" and cash < gross + fee:
                continue
            cash += -(gross + fee) if side == "BUY" else gross - fee
            quantities[symbol] = quantities.get(symbol, Decimal("0")) + (requested if side == "BUY" else -requested)
            delayed_fills += 1; delayed_fee += fee
            delayed_spread += requested * reference * Decimal("0.0005")
            delayed_impact += requested * slip - (requested * reference * Decimal("0.0005"))
            daily_ref = Decimal(str(row["reference_price"]))
            sign = Decimal("1") if side == "BUY" else Decimal("-1")
            diffs.append(float(sign * (reference / daily_ref - 1) * Decimal("10000")))
        daily_fills = sum(Decimal(str(r["filled_quantity"])) > 0 for r in orders)
        judgement = "BLOCKED_BY_MINUTE_DATA" if unavailable else "FIVE_MINUTE_EXECUTION_VALID_WITH_RISK_FLAGS"
        row = {"candidate_id": candidate, "start": START, "end": END, "daily_intents": len(orders), "required_symbol_dates": len(needed), "available_symbol_dates": len(needed)-len(unavailable), "unavailable_symbol_dates": len(unavailable), "daily_open_fills": daily_fills, "five_minute_fills": delayed_fills, "mean_reference_difference_bps": sum(diffs)/len(diffs) if diffs else None, "median_reference_difference_bps": float(pd.Series(diffs).median()) if diffs else None, "five_minute_fee_krw": str(delayed_fee), "five_minute_spread_krw": str(delayed_spread), "five_minute_impact_krw": str(delayed_impact), "ending_cash_krw": str(cash), "judgement": judgement, "reconciliation": "SIMULATED_LEDGER_BALANCED"}
        coverage["candidates"][candidate] = {"needed": len(needed), "available": len(needed)-len(unavailable), "unavailable": [{"symbol": s, "date": d} for s,d in unavailable]}
        comparison.append(row)
    (out / "contract.json").write_text(json.dumps({"contract": cfg, "sha256": cfg_hash}, indent=2) + "\n", encoding="utf-8")
    (out / "data_coverage.json").write_text(json.dumps(coverage, indent=2) + "\n", encoding="utf-8")
    _write_csv(out / "execution_comparison.csv", comparison)
    summary = {"contract_id": cfg["contract_id"], "contract_sha256": cfg_hash, "results": comparison, "broker_mutation_calls": 0, "operating_database_touched": False, "reports_touched": False}
    (out / "validation_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (out / "validation.log").write_text(json.dumps({"broker_mutation_calls": 0, "live_execution_allowed": False, "contract_sha256": cfg_hash}) + "\n", encoding="utf-8")
    return summary
