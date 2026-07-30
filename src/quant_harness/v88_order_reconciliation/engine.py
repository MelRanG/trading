from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import yaml

from quant_harness.v72_integration_ready.contracts import BrokerAccount, BrokerHolding, BrokerOrder, BrokerQuote, Side

REPORT = "v88_order_reconciliation"


class TransportAfterAcceptError(ConnectionError):
    pass


@dataclass(frozen=True)
class OrderIntent:
    strategy_id: str
    client_order_id: str
    symbol: str
    side: Side
    quantity: Decimal
    reason: str
    dry_run: bool = True


@dataclass(frozen=True)
class ReconciliationResult:
    status: str
    mode: str
    quantity_differences: dict[str, str]
    cash_difference_krw: str
    exact: bool
    auto_reorder_allowed: bool


class SimulatedBrokerGateway:
    """Deterministic broker contract simulator for lifecycle failure tests."""

    def __init__(self, *, cash: Decimal = Decimal("10000000"), holdings: dict[str, Decimal] | None = None):
        self.cash = cash
        self.holdings = {str(k).zfill(6): Decimal(str(v)) for k, v in (holdings or {}).items()}
        self.orders: dict[str, BrokerOrder] = {}
        self.submit_counts: dict[str, int] = {}
        self.behavior: dict[str, str] = {}
        self.allow_live_orders = False

    def set_behavior(self, client_order_id: str, behavior: str) -> None:
        self.behavior[client_order_id] = behavior

    def health_check(self) -> dict[str, Any]:
        return {"ok_for_read": True, "ok_for_live": False, "live_orders_enabled": False}

    def get_quote(self, symbol: str) -> BrokerQuote:
        return BrokerQuote(symbol=str(symbol).zfill(6), price=Decimal("10000"), as_of=datetime.now(timezone.utc), source="SIMULATOR")

    def get_account(self) -> BrokerAccount:
        holding_rows = tuple(
            BrokerHolding(symbol=s, quantity=q, average_price=Decimal("10000"), current_price=Decimal("10000"), market_value=q * Decimal("10000"))
            for s, q in sorted(self.holdings.items()) if q != 0
        )
        equity = self.cash + sum(x.market_value or Decimal("0") for x in holding_rows)
        return BrokerAccount(account_id="SIM", cash=self.cash, total_equity=equity, holdings=holding_rows, as_of=datetime.now(timezone.utc))

    def list_orders(self, *, start_date: str | None = None, end_date: str | None = None) -> list[BrokerOrder]:
        return list(self.orders.values())

    def create_order(
        self,
        *,
        client_order_id: str,
        symbol: str,
        side: Side,
        quantity: Decimal,
        order_type: str = "MARKET",
        limit_price: Decimal | None = None,
        reason: str = "",
        dry_run: bool = True,
    ) -> BrokerOrder:
        if not dry_run or self.allow_live_orders:
            raise PermissionError("simulator and V88 contract require dry-run")
        self.submit_counts[client_order_id] = self.submit_counts.get(client_order_id, 0) + 1
        if client_order_id in self.orders:
            return self.orders[client_order_id]
        behavior = self.behavior.get(client_order_id, "FILLED")
        filled = quantity
        status = "FILLED"
        if behavior == "PARTIAL":
            filled = max(Decimal("1"), (quantity / Decimal("2")).quantize(Decimal("1")))
            status = "PARTIALLY_FILLED"
        elif behavior == "REJECT":
            filled = Decimal("0"); status = "REJECTED"
        price = Decimal("10000") if filled else None
        order = BrokerOrder(
            client_order_id=client_order_id,
            symbol=str(symbol).zfill(6),
            side=side,
            quantity=quantity,
            order_type=order_type,
            status=status,
            broker_order_id=f"SIM-{len(self.orders)+1:06d}",
            average_fill_price=price,
            filled_quantity=filled,
            reason=reason,
            created_at=datetime.now(timezone.utc),
            raw={"behavior": behavior},
        )
        self.orders[client_order_id] = order
        if filled:
            notional = filled * Decimal("10000")
            if side == "BUY":
                if self.cash < notional:
                    order = replace(order, status="REJECTED", filled_quantity=Decimal("0"), average_fill_price=None)
                    self.orders[client_order_id] = order
                else:
                    self.cash -= notional
                    self.holdings[order.symbol] = self.holdings.get(order.symbol, Decimal("0")) + filled
            else:
                available = self.holdings.get(order.symbol, Decimal("0"))
                if available < filled:
                    order = replace(order, status="REJECTED", filled_quantity=Decimal("0"), average_fill_price=None)
                    self.orders[client_order_id] = order
                else:
                    self.cash += notional
                    self.holdings[order.symbol] = available - filled
        if behavior == "TIMEOUT_AFTER_ACCEPT":
            raise TransportAfterAcceptError("transport failed after broker accepted order")
        return order

    def cancel_order(self, broker_order_id: str) -> BrokerOrder:
        match = next((x for x in self.orders.values() if x.broker_order_id == broker_order_id), None)
        if match is None:
            raise KeyError(broker_order_id)
        canceled = replace(match, status="CANCELED")
        self.orders[match.client_order_id] = canceled
        return canceled


class OrderJournal:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as conn:
            conn.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS intents(
                    client_order_id TEXT PRIMARY KEY,
                    strategy_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    quantity TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    dry_run INTEGER NOT NULL,
                    intent_hash TEXT NOT NULL,
                    status TEXT NOT NULL,
                    broker_order_id TEXT,
                    filled_quantity TEXT NOT NULL DEFAULT '0',
                    average_fill_price TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events(
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_order_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS reconciliations(
                    reconciliation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    strategy_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    @staticmethod
    def intent_hash(intent: OrderIntent) -> str:
        return sha256(json.dumps({**asdict(intent), "quantity": str(intent.quantity)}, sort_keys=True).encode()).hexdigest()

    def persist_intent(self, intent: OrderIntent) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        digest = self.intent_hash(intent)
        with sqlite3.connect(self.path) as conn:
            row = conn.execute("SELECT intent_hash,status,broker_order_id,filled_quantity,average_fill_price FROM intents WHERE client_order_id=?", (intent.client_order_id,)).fetchone()
            if row:
                if row[0] != digest:
                    raise ValueError("client_order_id reused with different intent")
                return {"existing": True, "status": row[1], "broker_order_id": row[2], "filled_quantity": row[3], "average_fill_price": row[4]}
            conn.execute(
                "INSERT INTO intents(client_order_id,strategy_id,symbol,side,quantity,reason,dry_run,intent_hash,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (intent.client_order_id, intent.strategy_id, intent.symbol, intent.side, str(intent.quantity), intent.reason, int(intent.dry_run), digest, "PERSISTED", now, now),
            )
        return {"existing": False, "status": "PERSISTED"}

    def record_event(self, client_order_id: str, event_type: str, payload: Any) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.path) as conn:
            conn.execute("INSERT INTO events(client_order_id,event_type,payload_json,created_at) VALUES(?,?,?,?)", (client_order_id, event_type, json.dumps(payload, default=str, sort_keys=True), now))

    def update_order(self, order: BrokerOrder) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                "UPDATE intents SET status=?,broker_order_id=?,filled_quantity=?,average_fill_price=?,updated_at=? WHERE client_order_id=?",
                (order.status, order.broker_order_id, str(order.filled_quantity), str(order.average_fill_price) if order.average_fill_price is not None else None, now, order.client_order_id),
            )
        self.record_event(order.client_order_id, "BROKER_ORDER", asdict(order))

    def get(self, client_order_id: str) -> dict[str, Any] | None:
        with sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM intents WHERE client_order_id=?", (client_order_id,)).fetchone()
        return dict(row) if row else None

    def record_reconciliation(self, strategy_id: str, result: ReconciliationResult) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                "INSERT INTO reconciliations(strategy_id,status,mode,payload_json,created_at) VALUES(?,?,?,?,?)",
                (strategy_id, result.status, result.mode, json.dumps(asdict(result), sort_keys=True), datetime.now(timezone.utc).isoformat()),
            )


class OrderCoordinator:
    def __init__(self, journal: OrderJournal, gateway: Any):
        self.journal = journal
        self.gateway = gateway

    def submit(self, intent: OrderIntent) -> BrokerOrder:
        if not intent.dry_run:
            raise PermissionError("V88 live submission is blocked")
        existing = self.journal.persist_intent(intent)
        if existing["existing"] and existing["status"] not in {"PERSISTED", "SUBMITTING", "TRANSPORT_UNKNOWN"}:
            orders = {x.client_order_id: x for x in self.gateway.list_orders()}
            if intent.client_order_id in orders:
                return orders[intent.client_order_id]
        self.journal.record_event(intent.client_order_id, "SUBMIT_ATTEMPT", {"dry_run": True})
        try:
            order = self.gateway.create_order(
                client_order_id=intent.client_order_id,
                symbol=intent.symbol,
                side=intent.side,
                quantity=intent.quantity,
                reason=intent.reason,
                dry_run=True,
            )
        except (ConnectionError, TimeoutError) as exc:
            self.journal.record_event(intent.client_order_id, "TRANSPORT_ERROR", {"error": type(exc).__name__})
            matches = [x for x in self.gateway.list_orders() if x.client_order_id == intent.client_order_id]
            if len(matches) != 1:
                raise RuntimeError(f"transport recovery found {len(matches)} matching orders") from exc
            order = matches[0]
        self.journal.update_order(order)
        return order


def reconcile_positions(
    *,
    strategy_id: str,
    expected_cash: Decimal,
    expected_holdings: dict[str, Decimal],
    broker_account: BrokerAccount,
    quantity_tolerance: Decimal = Decimal("0"),
    cash_tolerance_krw: Decimal = Decimal("1"),
) -> ReconciliationResult:
    actual = {x.symbol: x.quantity for x in broker_account.holdings}
    symbols = sorted(set(expected_holdings) | set(actual))
    differences = {s: str(actual.get(s, Decimal("0")) - expected_holdings.get(s, Decimal("0"))) for s in symbols if abs(actual.get(s, Decimal("0")) - expected_holdings.get(s, Decimal("0"))) > quantity_tolerance}
    cash_diff = broker_account.cash - expected_cash
    exact = not differences and abs(cash_diff) <= cash_tolerance_krw
    return ReconciliationResult(
        status="MATCHED" if exact else "MATERIAL_MISMATCH",
        mode="NORMAL" if exact else "HOLD_ONLY",
        quantity_differences=differences,
        cash_difference_krw=str(cash_diff),
        exact=exact,
        auto_reorder_allowed=False,
    )


def _load_cfg(root: Path) -> dict[str, Any]:
    return yaml.safe_load((root / "config/v88_order_reconciliation.yaml").read_text(encoding="utf-8"))


def run(root: Path | str) -> dict[str, Any]:
    root = Path(root)
    cfg = _load_cfg(root)
    db = root / cfg["paths"]["journal_db"]
    if db.exists():
        db.unlink()
    journal = OrderJournal(db)
    gateway = SimulatedBrokerGateway(cash=Decimal("10000000"))
    coordinator = OrderCoordinator(journal, gateway)
    timeout_id = "V88-TIMEOUT-AFTER-ACCEPT"
    gateway.set_behavior(timeout_id, "TIMEOUT_AFTER_ACCEPT")
    recovered = coordinator.submit(OrderIntent("v69_fixed80_daily_control", timeout_id, "069500", "BUY", Decimal("10"), "transport recovery"))
    duplicate = coordinator.submit(OrderIntent("v69_fixed80_daily_control", timeout_id, "069500", "BUY", Decimal("10"), "transport recovery"))
    partial_id = "V88-PARTIAL"
    gateway.set_behavior(partial_id, "PARTIAL")
    partial = coordinator.submit(OrderIntent("v79_core70_generic_trend30", partial_id, "395160", "BUY", Decimal("9"), "partial fill"))
    account = gateway.get_account()
    expected = {x.symbol: x.quantity for x in account.holdings}
    matched = reconcile_positions(strategy_id="paper", expected_cash=account.cash, expected_holdings=expected, broker_account=account)
    mismatch = reconcile_positions(strategy_id="paper", expected_cash=account.cash, expected_holdings={**expected, "069500": expected.get("069500", Decimal("0")) + Decimal("1")}, broker_account=account)
    journal.record_reconciliation("paper", matched)
    journal.record_reconciliation("paper", mismatch)
    gates = {
        "timeout_after_accept_recovered": recovered.status == "FILLED",
        "no_duplicate_broker_order": gateway.submit_counts[timeout_id] == 1 and duplicate.broker_order_id == recovered.broker_order_id,
        "partial_fill_recorded": partial.status == "PARTIALLY_FILLED" and partial.filled_quantity < partial.quantity,
        "exact_reconciliation_normal": matched.exact and matched.mode == "NORMAL",
        "mismatch_forces_hold_only": (not mismatch.exact) and mismatch.mode == "HOLD_ONLY" and not mismatch.auto_reorder_allowed,
        "live_blocked": not cfg["live_execution_allowed"],
    }
    out = root / cfg["paths"]["report_dir"]
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{"gate": k, "passed": v} for k, v in gates.items()]).to_csv(out / "quality_gates.csv", index=False)
    result = {
        "status": "v88_order_lifecycle_reconciliation_ready_live_blocked",
        "gates": gates,
        "recovered_order": asdict(recovered),
        "partial_order": asdict(partial),
        "matched_reconciliation": asdict(matched),
        "mismatch_reconciliation": asdict(mismatch),
        "live_execution_allowed": False,
    }
    (out / "summary.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    return result
