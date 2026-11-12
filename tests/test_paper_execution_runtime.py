from __future__ import annotations

from decimal import Decimal
import os
from pathlib import Path

import psycopg
import pytest
from psycopg.rows import dict_row

from quant_harness.paper_execution_runtime import (
    PaperExecutionError,
    cancel_paper_order,
    execute_paper_order,
    reconcile_paper,
    run_paper_execution_cycle,
)
from quant_harness.paper_runtime_store import PAPER_ACCOUNT_ID, ensure_paper_account, initialize_paper_schema, load_paper_account
from quant_harness.v104_end_to_end_causal_challenger_audit.adapter import load_candidate_specs


ROOT = Path(__file__).resolve().parents[1]
URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="TEST_DATABASE_URL is required for PostgreSQL acceptance")


@pytest.fixture(autouse=True)
def clean_paper_execution_tables() -> None:
    initialize_paper_schema(URL)
    with psycopg.connect(URL) as conn:
        conn.execute("TRUNCATE paper_reconciliation,paper_ledger_event,paper_fill,paper_order,paper_audit_event,order_intent_preview,target_allocation,strategy_decision,paper_session,paper_position,paper_cash,paper_account CASCADE")
    ensure_paper_account(URL, Decimal("1000000"), "paper-execution-test")
    with psycopg.connect(URL) as conn:
        fingerprint = load_candidate_specs(ROOT)["V69_PARENT"].fingerprint
        conn.execute("INSERT INTO paper_session(session_id,paper_account_id,as_of,dataset_id,input_hash,config_hash,strategy_build_hash,candidate_fingerprint,runtime_mode,status,authority_status,broker_observation_status,completed_at) VALUES ('S-TEST',%s,'2026-07-08','d','h','c','s',%s,'MOCK','PREVIEW_ONLY','PREVIEW_ONLY','PASSED',now())", (PAPER_ACCOUNT_ID, fingerprint))
        conn.execute("INSERT INTO strategy_decision(decision_id,session_id,as_of,input_hash,strategy_build_hash,regime,selected_candidates,decision_status,decision_receipt,authority_status) VALUES ('D-TEST','S-TEST','2026-07-08','h','s','RISK_ON','[]','PREVIEW_ONLY','{}','PREVIEW_ONLY')")


def _intent(intent_id: str, symbol: str, side: str, quantity: int, price: int) -> dict[str, object]:
    with psycopg.connect(URL) as conn:
        conn.execute("INSERT INTO order_intent_preview(intent_id,session_id,paper_account_id,symbol,side,current_quantity,target_quantity,delta_quantity,reference_price,estimated_notional,reason,risk_status,authority_status,input_hash) VALUES (%s,'S-TEST',%s,%s,%s,0,%s,%s,%s,%s,'TEST','PAPER_RISK_PASS','PREVIEW_ONLY','h')", (intent_id, PAPER_ACCOUNT_ID, symbol, side, quantity, quantity if side == 'BUY' else -quantity, price, quantity * price))
        conn.execute("INSERT INTO target_allocation(decision_id,symbol,target_weight,target_notional,reference_price,target_quantity,adv20_d1_krw,calculation_status,reason) VALUES ('D-TEST',%s,1,%s,%s,%s,1000000000,'CALCULATED','TEST') ON CONFLICT (decision_id,symbol) DO UPDATE SET target_notional=EXCLUDED.target_notional,reference_price=EXCLUDED.reference_price,target_quantity=EXCLUDED.target_quantity,adv20_d1_krw=1000000000", (symbol, quantity * price, price, quantity))
    return {"intent_id": intent_id, "session_id": "S-TEST", "paper_account_id": PAPER_ACCOUNT_ID, "symbol": symbol, "side": side, "delta_quantity": Decimal(quantity if side == "BUY" else -quantity), "reference_price": Decimal(price), "authority_status": "PREVIEW_ONLY"}


def test_buy_fill_average_price_persistence_and_idempotency() -> None:
    intent = _intent("I-BUY", "069500", "BUY", 1000, 100)
    first = execute_paper_order(URL, ROOT, intent)
    second = execute_paper_order(URL, ROOT, intent)
    assert first["status"] == "FILLED" and second["idempotent"] is True
    account = load_paper_account(URL)
    assert account["positions"]["069500"] == Decimal("1000")
    assert account["cash_krw"] < Decimal("1000000")
    with psycopg.connect(URL, row_factory=dict_row) as conn:
        fill = conn.execute("SELECT quantity,fill_price,fee,slippage FROM paper_fill").fetchone()
        ledger = conn.execute("SELECT cash_delta FROM paper_ledger_event").fetchone()
    gross = Decimal(fill["quantity"]) * Decimal(fill["fill_price"])
    assert Decimal(ledger["cash_delta"]) == -(gross + Decimal(fill["fee"]))
    assert Decimal(fill["slippage"]) == abs(Decimal(fill["fill_price"]) - Decimal("100"))
    assert reconcile_paper(URL)["status"] == "PASSED"


def test_partial_fill_restart_then_sell_and_cancel() -> None:
    buy = _intent("I-BUY", "069500", "BUY", 2000, 100)
    execute_paper_order(URL, ROOT, buy)
    sell = _intent("I-SELL", "069500", "SELL", 2000, 110)
    partial = execute_paper_order(URL, ROOT, sell, fill_quantity=1000)
    resumed = execute_paper_order(URL, ROOT, sell)
    assert partial["status"] == "PARTIALLY_FILLED"
    assert resumed["status"] == "FILLED"
    assert load_paper_account(URL)["positions"].get("069500", Decimal("0")) == Decimal("0")
    with psycopg.connect(URL, row_factory=dict_row) as conn:
        sell_fill = conn.execute("SELECT quantity,fill_price,fee FROM paper_fill WHERE side='SELL'").fetchone()
        sell_ledger = conn.execute("SELECT cash_delta FROM paper_ledger_event WHERE side='SELL'").fetchone()
    assert Decimal(sell_ledger["cash_delta"]) == Decimal(sell_fill["quantity"]) * Decimal(sell_fill["fill_price"]) - Decimal(sell_fill["fee"])
    with psycopg.connect(URL) as conn:
        conn.execute("INSERT INTO order_intent_preview(intent_id,session_id,paper_account_id,symbol,side,current_quantity,target_quantity,delta_quantity,reference_price,estimated_notional,reason,risk_status,authority_status,input_hash) VALUES ('I-CANCEL','S-TEST',%s,'091160','BUY',0,1000,1000,100,100000,'TEST','PAPER_RISK_PASS','PREVIEW_ONLY','h')", (PAPER_ACCOUNT_ID,))
        conn.execute("INSERT INTO paper_order(paper_order_id,client_order_id,session_id,intent_id,paper_account_id,symbol,side,requested_quantity,filled_quantity,remaining_quantity,reference_price,status,execution_scope,live_authority) VALUES ('PO-CANCEL','CO-CANCEL','S-TEST','I-CANCEL',%s,'091160','BUY',1000,0,1000,100,'ACCEPTED','PAPER_ONLY',false)", (PAPER_ACCOUNT_ID,))
    assert cancel_paper_order(URL, "CO-CANCEL")["status"] == "CANCELED"


def test_rejections_and_reconciliation_hold_only() -> None:
    oversell = _intent("I-OVERSELL", "069500", "SELL", 1000, 100)
    rejected = execute_paper_order(URL, ROOT, oversell)
    assert rejected["status"] == "REJECTED"
    with pytest.raises(PaperExecutionError, match="zero quantity"):
        execute_paper_order(URL, ROOT, {**oversell, "intent_id": "I-ZERO", "delta_quantity": Decimal("0")})
    with psycopg.connect(URL) as conn:
        conn.execute("UPDATE paper_cash SET amount=1 WHERE paper_account_id=%s", (PAPER_ACCOUNT_ID,))
    result = reconcile_paper(URL)
    assert result["status"] == "FAILED"
    assert load_paper_account(URL)["status"] == "HOLD_ONLY"


def test_reference_price_scale_mismatch_is_rejected_without_fill() -> None:
    intent = _intent("I-SCALE", "069500", "BUY", 1000, 100)
    with psycopg.connect(URL) as conn:
        conn.execute("UPDATE target_allocation SET reference_price=101 WHERE decision_id='D-TEST' AND symbol='069500'")
    result = execute_paper_order(URL, ROOT, intent)
    assert result["status"] == "REJECTED"
    assert result["reason"] == "REFERENCE_PRICE_MISMATCH"
    with psycopg.connect(URL) as conn:
        assert conn.execute("SELECT count(*) FROM paper_fill").fetchone()[0] == 0


def test_d1_adv_participation_limit_is_enforced_before_fill() -> None:
    intent = _intent("I-ADV-CAP", "069500", "BUY", 1000, 100)
    with psycopg.connect(URL) as conn:
        conn.execute("UPDATE target_allocation SET adv20_d1_krw=100000 WHERE decision_id='D-TEST' AND symbol='069500'")

    result = execute_paper_order(URL, ROOT, intent)

    assert result["status"] == "REJECTED"
    assert result["reason"] == "ADV_PARTICIPATION_LIMIT"
    with psycopg.connect(URL) as conn:
        assert conn.execute("SELECT count(*) FROM paper_fill").fetchone()[0] == 0


def test_target_exit_uses_same_d1_adv_without_creating_a_zero_weight_target() -> None:
    with psycopg.connect(URL) as conn:
        conn.execute("INSERT INTO paper_position(paper_account_id,symbol,quantity,average_price) VALUES (%s,'091160',1000,100)", (PAPER_ACCOUNT_ID,))
        conn.execute("INSERT INTO order_intent_preview(intent_id,session_id,paper_account_id,symbol,side,current_quantity,target_quantity,delta_quantity,reference_price,estimated_notional,adv20_d1_krw,reason,risk_status,authority_status,input_hash) VALUES ('I-EXIT','S-TEST',%s,'091160','SELL',1000,0,-1000,100,100000,1000000000,'TARGET_EXIT','PREVIEW_OK','PREVIEW_ONLY','h')", (PAPER_ACCOUNT_ID,))
    result = execute_paper_order(URL, ROOT, {"intent_id": "I-EXIT", "session_id": "S-TEST", "paper_account_id": PAPER_ACCOUNT_ID, "symbol": "091160", "side": "SELL", "delta_quantity": Decimal("-1000"), "reference_price": Decimal("100"), "adv20_d1_krw": Decimal("1000000000"), "authority_status": "PREVIEW_ONLY"})
    assert result["status"] == "FILLED"


def test_same_session_sells_are_applied_before_buys() -> None:
    with psycopg.connect(URL) as conn:
        conn.execute("UPDATE paper_cash SET amount=1 WHERE paper_account_id=%s", (PAPER_ACCOUNT_ID,))
        conn.execute("INSERT INTO paper_position(paper_account_id,symbol,quantity,average_price) VALUES (%s,'000001',10000,100)", (PAPER_ACCOUNT_ID,))
        for intent_id, symbol, side, current, target, delta, price in [
            ('I-SELL-FIRST', '000001', 'SELL', 10000, 0, -10000, 100),
            ('I-BUY-SECOND', '999999', 'BUY', 0, 9000, 9000, 100),
        ]:
            conn.execute("INSERT INTO target_allocation(decision_id,symbol,target_weight,target_notional,reference_price,target_quantity,adv20_d1_krw,calculation_status,reason) VALUES ('D-TEST',%s,1,%s,%s,%s,1000000000,'CALCULATED','TEST')", (symbol, abs(delta) * price, price, target))
            conn.execute("INSERT INTO order_intent_preview(intent_id,session_id,paper_account_id,symbol,side,current_quantity,target_quantity,delta_quantity,reference_price,estimated_notional,adv20_d1_krw,reason,risk_status,authority_status,input_hash) VALUES (%s,'S-TEST',%s,%s,%s,%s,%s,%s,%s,%s,1000000000,'TEST','PREVIEW_OK','PREVIEW_ONLY','h')", (intent_id, PAPER_ACCOUNT_ID, symbol, side, current, target, delta, price, abs(delta) * price))
    result = run_paper_execution_cycle(URL, ROOT)
    assert [row["status"] for row in result["orders"]] == ["FILLED", "FILLED"]


def test_registered_v101_cash_capacity_is_applied_before_paper_order() -> None:
    intent = _intent("I-CASH-CAP", "069500", "BUY", 20000, 100)
    result = run_paper_execution_cycle(URL, ROOT)
    assert result["reconciliation"]["status"] == "PASSED"
    assert len(result["orders"]) == 1, result
    order = result["orders"][0]
    assert order["status"] == "FILLED"
    assert 0 < order["v101_executable_quantity"] < 20000
    assert load_paper_account(URL)["cash_krw"] >= 0
    with psycopg.connect(URL, row_factory=dict_row) as conn:
        stored = conn.execute("SELECT requested_quantity,filled_quantity,status FROM paper_order").fetchone()
        risk = conn.execute("SELECT risk_status FROM order_intent_preview WHERE intent_id='I-CASH-CAP'").fetchone()
    assert Decimal(stored["requested_quantity"]) == Decimal(stored["filled_quantity"])
    assert stored["status"] == "FILLED"
    assert risk["risk_status"] == "PARTICIPATION_LIMITED_PENDING"


def test_deferred_zero_quantity_minimum_order_remains_pending() -> None:
    _intent("I-MIN-DEFER", "069500", "BUY", 1, 100)
    result = run_paper_execution_cycle(URL, ROOT)
    assert result["orders"] == []
    assert result["blocked_intents"][0]["reason"] == "BELOW_MIN_ORDER_THRESHOLD_PENDING"
    assert load_paper_account(URL)["execution_pending"] is True
    with psycopg.connect(URL, row_factory=dict_row) as conn:
        risk = conn.execute("SELECT risk_status FROM order_intent_preview WHERE intent_id='I-MIN-DEFER'").fetchone()
    assert risk["risk_status"] == "BELOW_MIN_ORDER_THRESHOLD_PENDING"


def test_dynamic_min_policy_accepts_held_target_without_order(monkeypatch) -> None:
    from dataclasses import replace
    import quant_harness.paper_execution_runtime as paper_execution

    spec = load_candidate_specs(ROOT)["V69_PARENT"]
    base_policy = paper_execution.v101._policy(ROOT, spec.execution_policy)
    monkeypatch.setattr(
        paper_execution.v101,
        "_policy",
        lambda root, policy_id: replace(base_policy, dynamic_min_order_nav_fraction=0.005),
    )
    targets = [{
        "symbol": "069500", "target_weight": Decimal("0.9"),
        "target_quantity": Decimal("1000"), "reference_price": Decimal("100"),
        "adv20_d1_krw": Decimal("100000000"),
    }]
    plan, blocked = paper_execution._plan_v101_executable_intents(
        ROOT, URL, [], targets, spec.fingerprint,
        cash_krw=Decimal("1000000"), positions={"069500": Decimal("1000")},
        execution_references=None,
    )
    assert plan == []
    assert blocked == []


def test_custom_execution_reference_does_not_fall_back_to_symbol_daily_open() -> None:
    import quant_harness.paper_execution_runtime as paper_execution

    spec = load_candidate_specs(ROOT)["V69_PARENT"]
    intent = {
        "intent_id": "I-CUSTOM-OPEN", "symbol": "069500", "side": "BUY",
        "delta_quantity": Decimal("1000"), "reference_price": Decimal("100"),
        "adv20_d1_krw": Decimal("100000000"),
    }
    with pytest.raises(PaperExecutionError, match="missing executable open"):
        paper_execution._plan_v101_executable_intents(
            ROOT, URL, [intent],
            [{"symbol": "069500", "target_weight": Decimal("1"),
              "target_quantity": Decimal("1000"), "reference_price": Decimal("100"),
              "adv20_d1_krw": Decimal("100000000")}],
            spec.fingerprint, cash_krw=Decimal("1000000"), positions={},
            execution_references={"069500": Decimal("101")},
        )


def test_partition_retains_risk_status_for_registered_pending_conversion() -> None:
    from quant_harness.paper_execution_runtime import _partition_executable_intents

    executable, blocked = _partition_executable_intents([{
        "intent_id": "I-BLOCKED-MIN", "symbol": "069500",
        "authority_status": "HOLD_ONLY", "risk_status": "BELOW_MIN_ORDER_THRESHOLD",
    }])
    assert executable == []
    assert blocked[0]["risk_status"] == "BELOW_MIN_ORDER_THRESHOLD"
