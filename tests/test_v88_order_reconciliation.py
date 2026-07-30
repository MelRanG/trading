from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from quant_harness.v72_integration_ready.contracts import BrokerAccount, BrokerHolding
from quant_harness.v88_order_reconciliation.engine import (
    OrderCoordinator,
    OrderIntent,
    OrderJournal,
    SimulatedBrokerGateway,
    reconcile_positions,
    run,
)


def test_timeout_after_accept_is_reconciled_without_duplicate(tmp_path: Path) -> None:
    gateway = SimulatedBrokerGateway()
    gateway.set_behavior("X", "TIMEOUT_AFTER_ACCEPT")
    coordinator = OrderCoordinator(OrderJournal(tmp_path / "journal.db"), gateway)
    intent = OrderIntent("s", "X", "069500", "BUY", Decimal("3"), "test")
    first = coordinator.submit(intent)
    second = coordinator.submit(intent)
    assert first.broker_order_id == second.broker_order_id
    assert gateway.submit_counts["X"] == 1
    assert len(gateway.orders) == 1


def test_same_client_id_with_changed_intent_is_blocked(tmp_path: Path) -> None:
    gateway = SimulatedBrokerGateway()
    coordinator = OrderCoordinator(OrderJournal(tmp_path / "journal.db"), gateway)
    coordinator.submit(OrderIntent("s", "X", "069500", "BUY", Decimal("3"), "test"))
    with pytest.raises(ValueError, match="different intent"):
        coordinator.submit(OrderIntent("s", "X", "069500", "BUY", Decimal("4"), "test"))


def test_partial_fill_and_live_block(tmp_path: Path) -> None:
    gateway = SimulatedBrokerGateway()
    gateway.set_behavior("P", "PARTIAL")
    coordinator = OrderCoordinator(OrderJournal(tmp_path / "journal.db"), gateway)
    order = coordinator.submit(OrderIntent("s", "P", "069500", "BUY", Decimal("9"), "test"))
    assert order.status == "PARTIALLY_FILLED"
    assert order.filled_quantity == Decimal("4")
    with pytest.raises(PermissionError):
        coordinator.submit(OrderIntent("s", "L", "069500", "BUY", Decimal("1"), "live", dry_run=False))


def test_material_mismatch_forces_hold_only() -> None:
    account = BrokerAccount(
        account_id="A",
        cash=Decimal("100"),
        total_equity=Decimal("10100"),
        holdings=(BrokerHolding("069500", Decimal("1"), Decimal("10000")),),
    )
    result = reconcile_positions(
        strategy_id="s",
        expected_cash=Decimal("100"),
        expected_holdings={"069500": Decimal("2")},
        broker_account=account,
    )
    assert result.exact is False
    assert result.mode == "HOLD_ONLY"
    assert result.auto_reorder_allowed is False


def test_v88_harness(tmp_path: Path) -> None:
    source_root = Path(__file__).resolve().parents[1]
    root = tmp_path / "project"
    (root / "config").mkdir(parents=True)
    (root / "data/runtime").mkdir(parents=True)
    (root / "reports").mkdir(parents=True)
    (root / "config/v88_order_reconciliation.yaml").write_text(
        (source_root / "config/v88_order_reconciliation.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    result = run(root)
    assert all(result["gates"].values())
