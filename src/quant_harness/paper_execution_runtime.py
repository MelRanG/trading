"""Minimal deterministic Paper-only order and synthetic-fill lifecycle."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_FLOOR
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from quant_harness.paper_runtime_store import (
    PAPER_ACCOUNT_ID,
    initialize_paper_schema,
    load_paper_account,
)
from quant_harness.v72_integration_ready.live_safety import (
    CURRENT_RELEASE_LIVE_AUTHORITY,
    LIVE_BUILD_CAPABILITY,
)
from quant_harness.v77_corrected_price_allocation import engine as v77
from quant_harness.v101_risk_execution_agent import engine as v101
from quant_harness.v104_end_to_end_causal_challenger_audit.adapter import load_candidate_specs


EXECUTION_SCOPE = "PAPER_ONLY"
PAPER_TEST_EXECUTION = "ALLOWED"
OPERATIONAL_AUTHORITY = "HOLD_ONLY"
PAPER_STATUSES = {"NEW", "ACCEPTED", "PARTIALLY_FILLED", "FILLED", "CANCELED", "REJECTED"}


class PaperExecutionError(RuntimeError):
    pass


def _id(prefix: str, value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    return f"{prefix}-{sha256(encoded.encode()).hexdigest()[:32]}"


def _decimal(value: Any, field: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise PaperExecutionError(f"{field} is not numeric") from exc
    if not result.is_finite():
        raise PaperExecutionError(f"{field} is not finite")
    return result


def _partition_executable_intents(intents: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Fail closed: only explicitly authorized preview intents may reach Paper orders."""
    executable: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for intent in intents:
        if intent.get("authority_status") == "PREVIEW_ONLY":
            executable.append(intent)
        else:
            blocked.append({
                "intent_id": intent.get("intent_id"),
                "symbol": intent.get("symbol"),
                "reason": "INTENT_AUTHORITY_NOT_PREVIEW_ONLY",
                "authority_status": intent.get("authority_status"),
                "risk_status": intent.get("risk_status"),
            })
    return executable, blocked


def _require_paper_intent_authority(intent: dict[str, Any]) -> None:
    if intent.get("authority_status") != "PREVIEW_ONLY":
        raise PaperExecutionError("intent authority is not PREVIEW_ONLY")


def _order_intents_by_registered_priority(
    root: Path,
    intents: list[dict[str, Any]],
    targets: list[dict[str, Any]],
    candidate_fingerprint: str,
) -> list[dict[str, Any]]:
    specs = load_candidate_specs(root)
    spec = next((item for item in specs.values() if item.fingerprint == candidate_fingerprint), None)
    if spec is None:
        raise PaperExecutionError("candidate execution policy fingerprint is not registered")
    policy = v101._policy(root, spec.execution_policy)
    strategy = spec.strategy
    priority = policy.v69_buy_priority if strategy == "V69" else policy.v79_buy_priority
    core_ticker = str(v77._load_config(root).core_ticker).zfill(6)
    target_weights = {str(row["symbol"]).zfill(6): float(row["target_weight"]) for row in targets}
    desired = {str(row["symbol"]).zfill(6): int(Decimal(row["target_quantity"])) for row in targets}
    current = {str(row["symbol"]).zfill(6): int(Decimal(row["current_quantity"])) for row in intents}
    buy_symbols = v101._buy_order(target_weights, desired, current, priority, core_ticker)
    buy_rank = {symbol: index for index, symbol in enumerate(buy_symbols)}
    return sorted(
        intents,
        key=lambda row: (
            0 if row["side"] == "SELL" else 1,
            str(row["symbol"]).zfill(6) if row["side"] == "SELL" else buy_rank.get(str(row["symbol"]).zfill(6), len(buy_rank)),
        ),
    )


def _adv_participation_cap_quantity(
    *, adv_krw: Decimal, reference_price: Decimal, participation: Decimal
) -> int:
    if adv_krw <= 0 or reference_price <= 0 or participation <= 0:
        return 0
    return int((adv_krw * participation / reference_price).to_integral_value(rounding=ROUND_FLOOR))


def _plan_v101_executable_intents(
    root: Path,
    database_url: str,
    intents: list[dict[str, Any]],
    targets: list[dict[str, Any]],
    candidate_fingerprint: str,
    *,
    cash_krw: Decimal,
    positions: dict[str, Decimal],
    execution_references: dict[str, Decimal] | None,
) -> tuple[list[tuple[dict[str, Any], int]], list[dict[str, Any]]]:
    """Apply the registered V101 ADV/cash/minimum gates before Paper orders.

    The preview intent keeps the full target delta.  The Paper order quantity
    is the executable quantity after SELL-first proceeds, the D-1 ADV cap,
    minimum notional, and fee-inclusive cash affordability have been applied.
    """
    specs = load_candidate_specs(root)
    spec = next((item for item in specs.values() if item.fingerprint == candidate_fingerprint), None)
    if spec is None:
        raise PaperExecutionError("candidate execution policy fingerprint is not registered")
    policy = v101._policy(root, spec.execution_policy)
    execution = v77._load_config(root).base_execution
    targets_by_symbol = {str(row["symbol"]).zfill(6): row for row in targets}
    # Target rows provide pre-open marks for holdings which do not need an
    # order. Intent-specific execution references override those marks when
    # available. This keeps dynamic-NAV policies valid for no-op/held symbols.
    references: dict[str, Decimal] = {}
    if execution_references is not None:
        references.update({
            str(key).zfill(6): _decimal(value, "symbol execution mark")
            for key, value in execution_references.items()
            if str(key).isdigit() and len(str(key)) <= 6
        })
    for row in targets:
        symbol = str(row["symbol"]).zfill(6)
        price = _decimal(row.get("reference_price"), "target reference")
        if price <= 0:
            raise PaperExecutionError(f"missing target reference for {symbol}")
        references.setdefault(symbol, price)
    for intent in intents:
        symbol = str(intent["symbol"]).zfill(6)
        intent_id = str(intent["intent_id"])
        if execution_references is not None and intent_id not in execution_references:
            raise PaperExecutionError(f"missing executable open for {symbol}")
        raw = (execution_references or {}).get(intent_id, intent["reference_price"])
        price = _decimal(raw, "execution reference")
        if price <= 0:
            raise PaperExecutionError(f"missing executable open for {symbol}")
        references[symbol] = price
    missing_marks = sorted(
        symbol for symbol, quantity in positions.items()
        if quantity > 0 and str(symbol).zfill(6) not in references
    )
    if missing_marks:
        raise PaperExecutionError(f"cannot compute Paper NAV without held-symbol marks: {missing_marks}")
    opening_nav = cash_krw + sum(
        (quantity * references[symbol] for symbol, quantity in positions.items() if symbol in references),
        Decimal("0"),
    )
    threshold = max(
        Decimal(str(policy.minimum_order_notional_krw)),
        opening_nav * Decimal(str(policy.dynamic_min_order_nav_fraction)),
    )
    participation = Decimal(str(execution.max_participation_of_d1_adv))
    planned: list[tuple[dict[str, Any], int]] = []
    blocked: list[dict[str, Any]] = []
    cash = cash_krw
    held = dict(positions)
    for intent in intents:
        symbol = str(intent["symbol"]).zfill(6)
        side = str(intent["side"])
        request = int(abs(_decimal(intent["delta_quantity"], "intent quantity")))
        raw = references[symbol]
        target = targets_by_symbol.get(symbol, {})
        adv_raw = intent.get("adv20_d1_krw")
        if adv_raw is None:
            adv_raw = target.get("adv20_d1_krw")
        adv = _decimal(adv_raw, "D-1 ADV") if adv_raw is not None else Decimal("0")
        cap = _adv_participation_cap_quantity(adv_krw=adv, reference_price=raw, participation=participation)
        quantity = min(request, cap)
        reason = None
        if cap <= 0:
            reason = "MISSING_OR_ZERO_D1_ADV"
        elif side == "SELL":
            quantity = min(quantity, int(held.get(symbol, Decimal("0"))))
            if quantity < request:
                reason = "PARTICIPATION_LIMITED_PENDING"
            if quantity > 0 and Decimal(quantity) * raw < threshold:
                quantity = 0
                reason = (
                    "BELOW_MIN_ORDER_THRESHOLD_PENDING"
                    if policy.deferred_min_order_sets_pending
                    else "BELOW_MIN_ORDER_THRESHOLD"
                )
            if quantity > 0:
                fill_price, fee, _ = _cost_terms(root, side=side, quantity=Decimal(quantity), reference=raw, adv=adv)
                cash += Decimal(quantity) * fill_price - fee
                held[symbol] = held.get(symbol, Decimal("0")) - Decimal(quantity)
        else:
            if quantity < request:
                reason = "PARTICIPATION_LIMITED_PENDING"
            if quantity > 0:
                fill_quantity, _, _, _, _ = v77._buy_fill_terms(
                    cash=float(cash), max_quantity=quantity, raw_open=float(raw), adv=float(adv), spec=execution
                )
                if fill_quantity < quantity:
                    reason = "PAPER_CASH_POLICY_BLOCK" if fill_quantity == 0 else "PARTICIPATION_LIMITED_PENDING"
                quantity = int(fill_quantity)
                while quantity > 0:
                    affordable_price, affordable_fee, _ = _cost_terms(
                        root, side=side, quantity=Decimal(quantity), reference=raw, adv=adv
                    )
                    if Decimal(quantity) * affordable_price + affordable_fee <= cash:
                        break
                    quantity -= 1
                    reason = "PARTICIPATION_LIMITED_PENDING"
                if quantity > 0 and Decimal(quantity) * raw < threshold:
                    quantity = 0
                    reason = (
                        "BELOW_MIN_ORDER_THRESHOLD_PENDING"
                        if policy.deferred_min_order_sets_pending
                        else "BELOW_MIN_ORDER_THRESHOLD"
                    )
                if quantity > 0:
                    fill_price, fee, _ = _cost_terms(root, side=side, quantity=Decimal(quantity), reference=raw, adv=adv)
                    cash -= Decimal(quantity) * fill_price + fee
                    held[symbol] = held.get(symbol, Decimal("0")) + Decimal(quantity)
        if quantity <= 0:
            if side == "SELL" and request > 0 and reason is None:
                reason = "INSUFFICIENT_POSITION"
            final_reason = reason or "BELOW_MIN_ORDER_THRESHOLD"
            with psycopg.connect(database_url) as conn:
                conn.execute(
                    "UPDATE order_intent_preview SET risk_status=%s WHERE intent_id=%s",
                    (final_reason, intent["intent_id"]),
                )
            blocked.append({"intent_id": intent["intent_id"], "symbol": symbol, "reason": final_reason})
            continue
        if quantity < request and reason is None:
            reason = "PARTICIPATION_LIMITED_PENDING"
        if reason:
            with psycopg.connect(database_url) as conn:
                conn.execute("UPDATE order_intent_preview SET risk_status=%s WHERE intent_id=%s", (reason, intent["intent_id"]))
        signed_quantity = Decimal(quantity) if side == "BUY" else Decimal(-quantity)
        planned.append(({**intent, "delta_quantity": signed_quantity}, quantity))
    return planned, blocked


def _cost_terms(root: Path, *, side: str, quantity: Decimal, reference: Decimal, adv: Decimal) -> tuple[Decimal, Decimal, Decimal]:
    if adv <= 0:
        raise PaperExecutionError("missing executable D1 ADV")
    cfg = v77._load_config(root)
    spec = cfg.base_execution
    notional = quantity * reference
    impact_bps = Decimal(str(v77._impact_bps(float(notional), float(adv), spec)))
    half_spread = Decimal(str(spec.half_spread_bps))
    bps = half_spread + impact_bps
    direction = Decimal("1") if side == "BUY" else Decimal("-1")
    fill_price = reference * (Decimal("1") + direction * bps / Decimal("10000"))
    fee_bps = Decimal(str(spec.buy_fee_bps if side == "BUY" else spec.sell_fee_bps))
    fee = quantity * fill_price * fee_bps / Decimal("10000")
    slippage = abs(fill_price - reference)
    return fill_price, fee, slippage


def _reject_order(conn: psycopg.Connection[Any], order_id: str, reason: str) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    conn.execute("UPDATE paper_order SET status='REJECTED',updated_at=%s WHERE paper_order_id=%s", (now, order_id))
    conn.execute(
        "INSERT INTO paper_audit_event(session_id,paper_account_id,category,status,detail) "
        "SELECT session_id,paper_account_id,'PAPER_ORDER','REJECTED',%s::jsonb FROM paper_order WHERE paper_order_id=%s",
        (json.dumps({"reason": reason}), order_id),
    )
    return {"paper_order_id": order_id, "status": "REJECTED", "reason": reason, "filled_quantity": Decimal("0")}


def execute_paper_order(
    database_url: str,
    root: Path | str,
    intent: dict[str, Any],
    *,
    fill_quantity: Decimal | int | None = None,
    execution_reference: Decimal | int | float | None = None,
) -> dict[str, Any]:
    """Create one deterministic Paper order and apply one synthetic fill."""
    if LIVE_BUILD_CAPABILITY or CURRENT_RELEASE_LIVE_AUTHORITY:
        raise PaperExecutionError("Live hardlock verification failed")
    _require_paper_intent_authority(intent)
    root = Path(root)
    if intent.get("paper_account_id") != PAPER_ACCOUNT_ID or intent.get("side") not in {"BUY", "SELL"}:
        raise PaperExecutionError("intent is not a Paper order intent")
    symbol = str(intent["symbol"]).zfill(6)
    requested = _decimal(intent.get("delta_quantity"), "requested quantity").copy_abs()
    reference = _decimal(intent.get("reference_price"), "reference price")
    if requested <= 0:
        raise PaperExecutionError("zero quantity intent is not executable")
    if reference <= 0:
        raise PaperExecutionError("reference price is not executable")
    session_id = str(intent["session_id"])
    intent_id = str(intent["intent_id"])
    client_order_id = _id("PAPER-CLIENT", {"session_id": session_id, "intent_id": intent_id})
    paper_order_id = _id("PAPER-ORDER", client_order_id)
    fill_qty = requested if fill_quantity is None else _decimal(fill_quantity, "fill quantity")
    if fill_qty <= 0 or fill_qty > requested:
        raise PaperExecutionError("fill quantity must be within requested quantity")
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        existing = conn.execute("SELECT * FROM paper_order WHERE client_order_id=%s FOR UPDATE", (client_order_id,)).fetchone()
        if existing:
            for key, expected in (("session_id", session_id), ("intent_id", intent_id), ("symbol", symbol), ("side", intent["side"]), ("reference_price", reference)):
                if str(existing[key]) != str(expected):
                    raise PaperExecutionError("client_order_id payload conflict")
            if existing["status"] in {"FILLED", "CANCELED", "REJECTED"}:
                return {"paper_order_id": existing["paper_order_id"], "client_order_id": client_order_id, "status": existing["status"], "idempotent": True, "filled_quantity": Decimal(existing["filled_quantity"])}
            paper_order_id = existing["paper_order_id"]
            remaining = Decimal(existing["remaining_quantity"])
            fill_qty = min(fill_qty, remaining)
            if fill_qty <= 0:
                return {"paper_order_id": paper_order_id, "client_order_id": client_order_id, "status": existing["status"], "idempotent": True, "filled_quantity": Decimal(existing["filled_quantity"])}
        else:
            conn.execute(
                "INSERT INTO paper_order(paper_order_id,client_order_id,session_id,intent_id,paper_account_id,symbol,side,requested_quantity,filled_quantity,remaining_quantity,reference_price,status,execution_scope,live_authority) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,0,%s,%s,'NEW','PAPER_ONLY',false)",
                (paper_order_id, client_order_id, session_id, intent_id, PAPER_ACCOUNT_ID, symbol, intent["side"], requested, requested, reference),
            )
            conn.execute("UPDATE paper_order SET status='ACCEPTED',updated_at=now() WHERE paper_order_id=%s", (paper_order_id,))
            remaining = requested
        target = conn.execute(
            "SELECT reference_price,adv20_d1_krw FROM target_allocation WHERE decision_id=(SELECT decision_id FROM strategy_decision WHERE session_id=%s) AND symbol=%s",
            (session_id, symbol),
        ).fetchone()
        if target and _decimal(target["reference_price"], "target reference price") != reference:
            return _reject_order(conn, paper_order_id, "REFERENCE_PRICE_MISMATCH")
        adv_value = target["adv20_d1_krw"] if target and target["adv20_d1_krw"] is not None else intent.get("adv20_d1_krw")
        adv = _decimal(adv_value, "D1 ADV") if adv_value is not None else Decimal("0")
        executable_reference = reference if execution_reference is None else _decimal(execution_reference, "execution reference")
        if executable_reference <= 0:
            return _reject_order(conn, paper_order_id, "INTRADAY_DATA_UNAVAILABLE")
        if fill_qty * executable_reference < Decimal(str(v101._policy(root, "PARENT_EXECUTION_CONTRACT").minimum_order_notional_krw)):
            return _reject_order(conn, paper_order_id, "MINIMUM_NOTIONAL")
        if adv <= 0:
            return _reject_order(conn, paper_order_id, "MISSING_D1_ADV")
        participation = Decimal(str(v77._load_config(root).base_execution.max_participation_of_d1_adv))
        adv_cap_quantity = _adv_participation_cap_quantity(
            adv_krw=adv,
            reference_price=executable_reference,
            participation=participation,
        )
        if fill_qty > adv_cap_quantity:
            return _reject_order(conn, paper_order_id, "ADV_PARTICIPATION_LIMIT")
        account = conn.execute("SELECT status FROM paper_account WHERE paper_account_id=%s FOR UPDATE", (PAPER_ACCOUNT_ID,)).fetchone()
        if not account or account["status"] != "ACTIVE":
            return _reject_order(conn, paper_order_id, "PAPER_ACCOUNT_NOT_ACTIVE")
        cash_row = conn.execute("SELECT amount FROM paper_cash WHERE paper_account_id=%s AND currency='KRW' FOR UPDATE", (PAPER_ACCOUNT_ID,)).fetchone()
        position = conn.execute("SELECT quantity,average_price FROM paper_position WHERE paper_account_id=%s AND symbol=%s FOR UPDATE", (PAPER_ACCOUNT_ID, symbol)).fetchone()
        quantity_before = Decimal(position["quantity"]) if position else Decimal("0")
        average_before = Decimal(position["average_price"]) if position else Decimal("0")
        fill_price, fee, slippage = _cost_terms(root, side=str(intent["side"]), quantity=fill_qty, reference=executable_reference, adv=adv)
        gross = fill_qty * fill_price
        cash_before = Decimal(cash_row["amount"])
        if intent["side"] == "BUY" and cash_before < gross + fee:
            return _reject_order(conn, paper_order_id, "INSUFFICIENT_CASH")
        if intent["side"] == "SELL" and quantity_before < fill_qty:
            return _reject_order(conn, paper_order_id, "INSUFFICIENT_POSITION")
        fill_id = _id("PAPER-FILL", {"paper_order_id": paper_order_id, "sequence": str(Decimal(existing["filled_quantity"]) if existing else 0), "quantity": str(fill_qty)})
        if conn.execute("SELECT 1 FROM paper_fill WHERE paper_fill_id=%s", (fill_id,)).fetchone():
            return {"paper_order_id": paper_order_id, "client_order_id": client_order_id, "status": "FILLED", "idempotent": True, "filled_quantity": fill_qty}
        now = datetime.now(timezone.utc)
        conn.execute("INSERT INTO paper_fill(paper_fill_id,paper_order_id,symbol,side,quantity,fill_price,fee,slippage,filled_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)", (fill_id, paper_order_id, symbol, intent["side"], fill_qty, fill_price, fee, slippage, now))
        if intent["side"] == "BUY":
            cash_delta = -(gross + fee)
            quantity_after = quantity_before + fill_qty
            average_after = ((quantity_before * average_before) + gross + fee) / quantity_after
        else:
            cash_delta = gross - fee
            quantity_after = quantity_before - fill_qty
            average_after = average_before
        cash_after = cash_before + cash_delta
        if cash_after < 0 or quantity_after < 0:
            raise PaperExecutionError("negative Paper balance prevented")
        conn.execute("UPDATE paper_cash SET amount=%s,updated_at=%s WHERE paper_account_id=%s AND currency='KRW'", (cash_after, now, PAPER_ACCOUNT_ID))
        if position:
            conn.execute("UPDATE paper_position SET quantity=%s,average_price=%s,updated_at=%s WHERE paper_account_id=%s AND symbol=%s", (quantity_after, average_after, now, PAPER_ACCOUNT_ID, symbol))
        elif quantity_after > 0:
            conn.execute("INSERT INTO paper_position(paper_account_id,symbol,quantity,average_price) VALUES (%s,%s,%s,%s)", (PAPER_ACCOUNT_ID, symbol, quantity_after, average_after))
        conn.execute("INSERT INTO paper_ledger_event(ledger_event_id,paper_fill_id,paper_order_id,paper_account_id,symbol,side,quantity_delta,cash_delta,fee) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)", (_id("PAPER-LEDGER", fill_id), fill_id, paper_order_id, PAPER_ACCOUNT_ID, symbol, intent["side"], fill_qty if intent["side"] == "BUY" else -fill_qty, cash_delta, fee))
        filled_after = requested - remaining + fill_qty
        remaining_after = requested - filled_after
        status = "FILLED" if remaining_after == 0 else "PARTIALLY_FILLED"
        conn.execute("UPDATE paper_order SET filled_quantity=%s,remaining_quantity=%s,status=%s,updated_at=%s WHERE paper_order_id=%s", (filled_after, remaining_after, status, now, paper_order_id))
        conn.execute("INSERT INTO paper_audit_event(session_id,paper_account_id,category,status,detail) VALUES (%s,%s,'PAPER_FILL',%s,%s::jsonb)", (session_id, PAPER_ACCOUNT_ID, status, json.dumps({"paper_order_id": paper_order_id, "fill_id": fill_id, "execution_scope": EXECUTION_SCOPE})))
        return {"paper_order_id": paper_order_id, "client_order_id": client_order_id, "status": status, "idempotent": False, "filled_quantity": filled_after, "fill_id": fill_id, "fill_price": fill_price, "fee": fee}


def cancel_paper_order(database_url: str, client_order_id: str) -> dict[str, Any]:
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        row = conn.execute("SELECT * FROM paper_order WHERE client_order_id=%s FOR UPDATE", (client_order_id,)).fetchone()
        if not row:
            raise PaperExecutionError("Paper order not found")
        if row["status"] in {"FILLED", "CANCELED", "REJECTED"}:
            return {"client_order_id": client_order_id, "status": row["status"], "idempotent": True}
        conn.execute("UPDATE paper_order SET status='CANCELED',updated_at=now() WHERE client_order_id=%s", (client_order_id,))
        return {"client_order_id": client_order_id, "status": "CANCELED", "idempotent": False}


def reconcile_paper(database_url: str) -> dict[str, Any]:
    initialize_paper_schema(database_url)
    errors: list[str] = []
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        orders = conn.execute("SELECT * FROM paper_order ORDER BY created_at").fetchall()
        fills = conn.execute("SELECT * FROM paper_fill").fetchall()
        ledger = conn.execute("SELECT * FROM paper_ledger_event").fetchall()
        fill_by_order: dict[str, Decimal] = {}
        for fill in fills:
            fill_by_order[fill["paper_order_id"]] = fill_by_order.get(fill["paper_order_id"], Decimal("0")) + Decimal(fill["quantity"])
        for order in orders:
            filled = Decimal(order["filled_quantity"])
            if filled != fill_by_order.get(order["paper_order_id"], Decimal("0")):
                errors.append(f"filled mismatch:{order['paper_order_id']}")
            if Decimal(order["remaining_quantity"]) != Decimal(order["requested_quantity"]) - filled:
                errors.append(f"remaining mismatch:{order['paper_order_id']}")
            if order["status"] == "FILLED" and Decimal(order["remaining_quantity"]) != 0:
                errors.append(f"terminal remaining:{order['paper_order_id']}")
        cash = Decimal(conn.execute("SELECT amount FROM paper_cash WHERE paper_account_id=%s AND currency='KRW'", (PAPER_ACCOUNT_ID,)).fetchone()["amount"])
        initial = Decimal(conn.execute("SELECT initial_capital_krw FROM paper_account WHERE paper_account_id=%s", (PAPER_ACCOUNT_ID,)).fetchone()["initial_capital_krw"])
        opening = conn.execute("SELECT detail FROM paper_audit_event WHERE category='OPENING_CHECKPOINT' AND paper_account_id=%s ORDER BY created_at LIMIT 1", (PAPER_ACCOUNT_ID,)).fetchone()
        opening_detail = opening["detail"] if opening else {}
        opening_cash = Decimal(str(opening_detail.get("cash", initial)))
        ledger_cash = sum((Decimal(row["cash_delta"]) for row in ledger), Decimal("0"))
        # PostgreSQL numeric values retain the deterministic fill decimals, but
        # repeated BUY/SELL arithmetic can leave a sub-nanowon Decimal residue.
        # Treat only that representation residue as equal; real cash drift still
        # fails closed.
        if abs(cash - (opening_cash + ledger_cash)) > Decimal("0.000000001") or cash < 0:
            errors.append("cash ledger mismatch")
        positions = {(r["symbol"]): r for r in conn.execute("SELECT symbol,quantity FROM paper_position WHERE paper_account_id=%s", (PAPER_ACCOUNT_ID,)).fetchall()}
        symbols = set(positions) | {e["symbol"] for e in ledger}
        opening_positions = (opening_detail.get("positions", {}) if opening else {})
        for symbol in symbols:
            delta = sum((Decimal(e["quantity_delta"]) for e in ledger if e["symbol"] == symbol), Decimal("0"))
            held = Decimal(positions[symbol]["quantity"]) if symbol in positions else Decimal("0")
            baseline = Decimal(str(opening_positions.get(symbol, {}).get("quantity", "0")))
            if delta + baseline != held or held < 0:
                errors.append(f"position ledger mismatch:{symbol}")
        status = "FAILED" if errors else "PASSED"
        if errors:
            conn.execute("UPDATE paper_account SET status='HOLD_ONLY',updated_at=now() WHERE paper_account_id=%s", (PAPER_ACCOUNT_ID,))
        conn.execute("INSERT INTO paper_reconciliation(reconciliation_id,paper_account_id,status,detail) VALUES (%s,%s,%s,%s::jsonb)", (_id("PAPER-RECON", datetime.now(timezone.utc).isoformat()), PAPER_ACCOUNT_ID, status, json.dumps({"errors": errors})))
    return {"status": status, "errors": errors}


def run_paper_execution_cycle(database_url: str, root: Path | str, *, mode: str = "historical-development", execution_references: dict[str, Decimal] | None = None) -> dict[str, Any]:
    if mode != "historical-development":
        raise PaperExecutionError("only historical-development Paper execution is allowed")
    if LIVE_BUILD_CAPABILITY or CURRENT_RELEASE_LIVE_AUTHORITY:
        raise PaperExecutionError("Live hardlock verification failed")
    initialize_paper_schema(database_url)
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        row = conn.execute("SELECT s.*,d.decision_id FROM paper_session s JOIN strategy_decision d USING(session_id) WHERE s.completed_at IS NOT NULL ORDER BY s.created_at DESC LIMIT 1").fetchone()
        if not row:
            raise PaperExecutionError("no Paper decision preview exists")
        # The parent execution contract permits same-session rebalancing.  Apply
        # already-held SELL deltas before BUY deltas so a lexical symbol order
        # cannot manufacture an otherwise unavailable cash rejection.
        all_intents = conn.execute("SELECT * FROM order_intent_preview WHERE session_id=%s", (row["session_id"],)).fetchall()
        target_rows = conn.execute(
            "SELECT symbol,target_weight,target_quantity,reference_price,adv20_d1_krw FROM target_allocation WHERE decision_id=%s",
            (row["decision_id"],),
        ).fetchall()
    intents, blocked_intents = _partition_executable_intents([dict(intent) for intent in all_intents])
    registered_spec = next(
        (item for item in load_candidate_specs(Path(root)).values() if item.fingerprint == str(row["candidate_fingerprint"])),
        None,
    )
    if registered_spec is None:
        raise PaperExecutionError("candidate execution policy fingerprint is not registered")
    registered_policy = v101._policy(Path(root), registered_spec.execution_policy)
    if registered_policy.deferred_min_order_sets_pending:
        for blocked in blocked_intents:
            if blocked.get("risk_status") == "BELOW_MIN_ORDER_THRESHOLD":
                with psycopg.connect(database_url) as conn:
                    conn.execute(
                        "UPDATE order_intent_preview SET risk_status='BELOW_MIN_ORDER_THRESHOLD_PENDING' WHERE intent_id=%s",
                        (blocked["intent_id"],),
                    )
    intents = _order_intents_by_registered_priority(
        Path(root), intents, [dict(target) for target in target_rows], str(row["candidate_fingerprint"])
    )
    account = load_paper_account(database_url)
    plan, deferred_intents = _plan_v101_executable_intents(
        Path(root), database_url, intents, [dict(target) for target in target_rows],
        str(row["candidate_fingerprint"]), cash_krw=account["cash_krw"],
        positions=account["positions"], execution_references=execution_references,
    )
    results = []
    for executable_intent, quantity in plan:
        intent_id = str(executable_intent["intent_id"])
        result = execute_paper_order(
            database_url, root, executable_intent,
            execution_reference=(None if execution_references is None else execution_references.get(intent_id, Decimal("0"))),
        )
        result["v101_executable_quantity"] = quantity
        results.append(result)
        if result.get("status") == "REJECTED":
            blocked_intents.append({"intent_id": intent_id, "symbol": executable_intent["symbol"], "reason": result.get("reason")})
    blocked_intents.extend(deferred_intents)
    reconciliation = reconcile_paper(database_url)
    return {
        "status": "COMPLETED" if reconciliation["status"] == "PASSED" and not blocked_intents else "HOLD_ONLY",
        "execution_scope": EXECUTION_SCOPE,
        "live_authority": False,
        "data_mode": "HISTORICAL_DEVELOPMENT",
        "operational_authority": OPERATIONAL_AUTHORITY,
        "paper_test_execution": PAPER_TEST_EXECUTION,
        "session_id": row["session_id"],
        "as_of": str(row["as_of"]),
        "orders": results,
        "blocked_intents": blocked_intents,
        "reconciliation": reconciliation,
        "broker_mutation_calls": 0,
        "live_execution_allowed": False,
    }


__all__ = ["PaperExecutionError", "execute_paper_order", "cancel_paper_order", "reconcile_paper", "run_paper_execution_cycle"]
