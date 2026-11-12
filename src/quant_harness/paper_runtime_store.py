"""PostgreSQL persistence for one non-executable Paper decision account."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import json
from typing import Any

import psycopg
from psycopg.rows import dict_row


PAPER_ACCOUNT_ID = "PAPER-PRIMARY"
PAPER_SCHEMA_VERSION = 1
ACCOUNT_STATUSES = frozenset({"ACTIVE", "HOLD_ONLY", "BLOCKED"})
AUTHORITY_STATUSES = frozenset({"PREVIEW_ONLY", "HOLD_ONLY", "BLOCKED", "NOT_AUTHORIZED"})

DDL = """
CREATE TABLE IF NOT EXISTS paper_schema_version (
    version integer PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS paper_account (
    paper_account_id text PRIMARY KEY,
    singleton_slot integer NOT NULL DEFAULT 1 UNIQUE CHECK(singleton_slot = 1),
    status text NOT NULL CHECK(status IN ('ACTIVE','HOLD_ONLY','BLOCKED')),
    initial_capital_krw numeric NOT NULL CHECK(initial_capital_krw > 0),
    initial_capital_source text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS paper_cash (
    paper_account_id text NOT NULL REFERENCES paper_account(paper_account_id),
    currency text NOT NULL CHECK(currency = 'KRW'),
    amount numeric NOT NULL CHECK(amount >= 0),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(paper_account_id, currency)
);
CREATE TABLE IF NOT EXISTS paper_position (
    paper_account_id text NOT NULL REFERENCES paper_account(paper_account_id),
    symbol text NOT NULL,
    quantity numeric NOT NULL CHECK(quantity >= 0),
    average_price numeric NOT NULL DEFAULT 0 CHECK(average_price >= 0),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(paper_account_id, symbol)
);
CREATE TABLE IF NOT EXISTS paper_session (
    session_id text PRIMARY KEY,
    paper_account_id text NOT NULL REFERENCES paper_account(paper_account_id),
    as_of date NOT NULL,
    dataset_id text NOT NULL,
    input_hash text NOT NULL,
    config_hash text NOT NULL,
    strategy_build_hash text NOT NULL,
    candidate_fingerprint text NOT NULL,
    runtime_mode text NOT NULL CHECK(runtime_mode IN ('MOCK','REAL_READ_ONLY')),
    status text NOT NULL,
    authority_status text NOT NULL CHECK(authority_status IN ('PREVIEW_ONLY','HOLD_ONLY','BLOCKED','NOT_AUTHORIZED')),
    broker_observation_status text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz
);
CREATE TABLE IF NOT EXISTS strategy_decision (
    decision_id text PRIMARY KEY,
    session_id text NOT NULL UNIQUE REFERENCES paper_session(session_id),
    as_of date NOT NULL,
    input_hash text NOT NULL,
    strategy_build_hash text NOT NULL,
    regime text NOT NULL,
    selected_candidates jsonb NOT NULL,
    decision_status text NOT NULL,
    hold_reason text,
    decision_receipt jsonb NOT NULL,
    authority_status text NOT NULL CHECK(authority_status IN ('PREVIEW_ONLY','HOLD_ONLY','BLOCKED','NOT_AUTHORIZED')),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS target_allocation (
    decision_id text NOT NULL REFERENCES strategy_decision(decision_id),
    symbol text NOT NULL,
    target_weight numeric NOT NULL CHECK(target_weight >= 0 AND target_weight <= 1),
    target_notional numeric NOT NULL CHECK(target_notional >= 0),
    reference_price numeric NOT NULL CHECK(reference_price > 0),
    target_quantity numeric NOT NULL CHECK(target_quantity >= 0),
    adv20_d1_krw numeric,
    calculation_status text NOT NULL,
    reason text NOT NULL,
    PRIMARY KEY(decision_id, symbol)
);
CREATE TABLE IF NOT EXISTS order_intent_preview (
    intent_id text PRIMARY KEY,
    session_id text NOT NULL REFERENCES paper_session(session_id),
    paper_account_id text NOT NULL REFERENCES paper_account(paper_account_id),
    symbol text NOT NULL,
    side text NOT NULL CHECK(side IN ('BUY','SELL')),
    current_quantity numeric NOT NULL CHECK(current_quantity >= 0),
    target_quantity numeric NOT NULL CHECK(target_quantity >= 0),
    delta_quantity numeric NOT NULL,
    reference_price numeric NOT NULL CHECK(reference_price > 0),
    estimated_notional numeric NOT NULL CHECK(estimated_notional >= 0),
    adv20_d1_krw numeric,
    reason text NOT NULL,
    risk_status text NOT NULL,
    authority_status text NOT NULL CHECK(authority_status IN ('PREVIEW_ONLY','HOLD_ONLY','BLOCKED','NOT_AUTHORIZED')),
    created_at timestamptz NOT NULL DEFAULT now(),
    input_hash text NOT NULL
);
CREATE TABLE IF NOT EXISTS paper_audit_event (
    event_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    session_id text REFERENCES paper_session(session_id),
    paper_account_id text REFERENCES paper_account(paper_account_id),
    category text NOT NULL,
    status text NOT NULL,
    detail jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS paper_order (
    paper_order_id text PRIMARY KEY,
    client_order_id text NOT NULL UNIQUE,
    session_id text NOT NULL REFERENCES paper_session(session_id),
    intent_id text NOT NULL REFERENCES order_intent_preview(intent_id),
    paper_account_id text NOT NULL REFERENCES paper_account(paper_account_id),
    symbol text NOT NULL,
    side text NOT NULL CHECK(side IN ('BUY','SELL')),
    requested_quantity numeric NOT NULL CHECK(requested_quantity > 0),
    filled_quantity numeric NOT NULL CHECK(filled_quantity >= 0),
    remaining_quantity numeric NOT NULL CHECK(remaining_quantity >= 0),
    reference_price numeric NOT NULL CHECK(reference_price > 0),
    status text NOT NULL CHECK(status IN ('NEW','ACCEPTED','PARTIALLY_FILLED','FILLED','CANCELED','REJECTED')),
    execution_scope text NOT NULL CHECK(execution_scope='PAPER_ONLY'),
    live_authority boolean NOT NULL CHECK(live_authority=false),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS paper_fill (
    paper_fill_id text PRIMARY KEY,
    paper_order_id text NOT NULL REFERENCES paper_order(paper_order_id),
    symbol text NOT NULL,
    side text NOT NULL CHECK(side IN ('BUY','SELL')),
    quantity numeric NOT NULL CHECK(quantity > 0),
    fill_price numeric NOT NULL CHECK(fill_price > 0),
    fee numeric NOT NULL CHECK(fee >= 0),
    slippage numeric NOT NULL CHECK(slippage >= 0),
    filled_at timestamptz NOT NULL
);
CREATE TABLE IF NOT EXISTS paper_ledger_event (
    ledger_event_id text PRIMARY KEY,
    paper_fill_id text NOT NULL UNIQUE REFERENCES paper_fill(paper_fill_id),
    paper_order_id text NOT NULL REFERENCES paper_order(paper_order_id),
    paper_account_id text NOT NULL REFERENCES paper_account(paper_account_id),
    symbol text NOT NULL,
    side text NOT NULL CHECK(side IN ('BUY','SELL')),
    quantity_delta numeric NOT NULL,
    cash_delta numeric NOT NULL,
    fee numeric NOT NULL CHECK(fee >= 0),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS paper_reconciliation (
    reconciliation_id text PRIMARY KEY,
    paper_account_id text NOT NULL REFERENCES paper_account(paper_account_id),
    status text NOT NULL CHECK(status IN ('PASSED','FAILED')),
    detail jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS paper_daily_nav (
    paper_account_id text NOT NULL REFERENCES paper_account(paper_account_id),
    as_of date NOT NULL,
    session_id text,
    nav_krw numeric NOT NULL CHECK(nav_krw >= 0),
    cash_krw numeric NOT NULL CHECK(cash_krw >= 0),
    positions_value_krw numeric NOT NULL CHECK(positions_value_krw >= 0),
    freshness_status text NOT NULL CHECK(freshness_status IN ('FRESH','STALE','INCOMPLETE','FAILED')),
    authority_status text NOT NULL CHECK(authority_status IN ('PREVIEW_ONLY','HOLD_ONLY','BLOCKED','NOT_AUTHORIZED')),
    detail jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(paper_account_id, as_of)
);
CREATE OR REPLACE VIEW latest_paper_account_summary AS
SELECT a.paper_account_id, a.status, c.amount AS cash_krw,
       (SELECT count(*) FROM paper_position p WHERE p.paper_account_id=a.paper_account_id AND p.quantity<>0) AS position_count,
       a.initial_capital_krw, a.initial_capital_source, a.updated_at
FROM paper_account a JOIN paper_cash c USING(paper_account_id)
WHERE c.currency='KRW' ORDER BY a.created_at DESC LIMIT 1;
CREATE OR REPLACE VIEW latest_strategy_decision_summary AS
SELECT d.decision_id, d.session_id, d.as_of, d.regime, d.selected_candidates,
       d.decision_status, d.hold_reason, d.authority_status, d.created_at
FROM strategy_decision d JOIN paper_session s USING(session_id)
WHERE s.completed_at IS NOT NULL ORDER BY d.created_at DESC LIMIT 1;
CREATE OR REPLACE VIEW latest_target_summary AS
SELECT t.decision_id, t.symbol, t.target_weight, t.target_notional,
       t.reference_price, t.target_quantity, t.calculation_status, t.reason
FROM target_allocation t
JOIN latest_strategy_decision_summary d USING(decision_id)
ORDER BY t.symbol;
CREATE OR REPLACE VIEW latest_order_intent_preview AS
SELECT i.intent_id, i.session_id, i.symbol, i.side, i.current_quantity,
       i.target_quantity, i.delta_quantity, i.reference_price,
       i.estimated_notional, i.risk_status, i.authority_status
FROM order_intent_preview i
JOIN latest_strategy_decision_summary d USING(session_id)
ORDER BY i.symbol, i.side;
CREATE OR REPLACE VIEW latest_paper_runtime_health AS
SELECT session_id, as_of, status, authority_status, broker_observation_status,
       completed_at
FROM paper_session ORDER BY created_at DESC LIMIT 1;
"""


class PaperStoreError(RuntimeError):
    pass


def _safe_json(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    prohibited = ("access_token", "client_secret", "accountNo", "TOSS_CLIENT_SECRET", '"raw"')
    if any(token in encoded for token in prohibited):
        raise PaperStoreError("sensitive or raw provider data cannot be persisted")
    return encoded


def initialize_paper_schema(database_url: str) -> None:
    with psycopg.connect(database_url) as conn:
        conn.execute(DDL)
        conn.execute("ALTER TABLE paper_position ADD COLUMN IF NOT EXISTS average_price numeric NOT NULL DEFAULT 0")
        conn.execute("ALTER TABLE target_allocation ADD COLUMN IF NOT EXISTS adv20_d1_krw numeric")
        conn.execute("ALTER TABLE order_intent_preview ADD COLUMN IF NOT EXISTS adv20_d1_krw numeric")
        conn.execute(
            "INSERT INTO paper_schema_version(version) VALUES (%s) ON CONFLICT DO NOTHING",
            (PAPER_SCHEMA_VERSION,),
        )
        version = conn.execute("SELECT max(version) FROM paper_schema_version").fetchone()[0]
        if version != PAPER_SCHEMA_VERSION:
            raise PaperStoreError("incompatible Paper schema version")


def save_daily_nav(
    database_url: str,
    *,
    as_of: str,
    session_id: str | None,
    nav_krw: Decimal,
    cash_krw: Decimal,
    positions_value_krw: Decimal,
    freshness_status: str,
    authority_status: str,
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if freshness_status not in {"FRESH", "STALE", "INCOMPLETE", "FAILED"}:
        raise PaperStoreError("invalid daily NAV freshness status")
    if authority_status not in AUTHORITY_STATUSES:
        raise PaperStoreError("invalid daily NAV authority status")
    values = (Decimal(nav_krw), Decimal(cash_krw), Decimal(positions_value_krw))
    if any(value < 0 for value in values):
        raise PaperStoreError("daily NAV values cannot be negative")
    payload = detail or {}
    _safe_json(payload)
    with psycopg.connect(database_url) as conn:
        conn.execute(
            """
            INSERT INTO paper_daily_nav(
                paper_account_id,as_of,session_id,nav_krw,cash_krw,positions_value_krw,
                freshness_status,authority_status,detail
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
            ON CONFLICT (paper_account_id,as_of) DO UPDATE SET
                session_id=EXCLUDED.session_id,
                nav_krw=EXCLUDED.nav_krw,
                cash_krw=EXCLUDED.cash_krw,
                positions_value_krw=EXCLUDED.positions_value_krw,
                freshness_status=EXCLUDED.freshness_status,
                authority_status=EXCLUDED.authority_status,
                detail=EXCLUDED.detail
            """,
            (
                PAPER_ACCOUNT_ID,
                as_of,
                session_id,
                values[0],
                values[1],
                values[2],
                freshness_status,
                authority_status,
                json.dumps(payload, default=str),
            ),
        )
    return {
        "as_of": as_of,
        "session_id": session_id,
        "nav_krw": values[0],
        "cash_krw": values[1],
        "positions_value_krw": values[2],
        "freshness_status": freshness_status,
        "authority_status": authority_status,
    }


def _ensure_account(
    conn: psycopg.Connection[Any],
    initial_capital_krw: Decimal,
    source: str,
) -> str:
    row = conn.execute(
        "SELECT paper_account_id,initial_capital_krw,initial_capital_source "
        "FROM paper_account WHERE singleton_slot=1 FOR UPDATE"
    ).fetchone()
    if row:
        # A seeded recent replay deliberately starts from an opening
        # checkpoint rather than the normal configured capital/source.  The
        # seed is disposable and still uses the same singleton Paper account;
        # allow the existing account to be reused by the normal preview path.
        if row[0] == PAPER_ACCOUNT_ID and row[2] == "OPENING_CHECKPOINT":
            return "NO_OP"
        if (
            row[0] != PAPER_ACCOUNT_ID
            or Decimal(row[1]) != Decimal(initial_capital_krw)
            or row[2] != source
        ):
            raise PaperStoreError("Paper account initialization conflict")
        return "NO_OP"
    conn.execute(
        "INSERT INTO paper_account(paper_account_id,status,initial_capital_krw,initial_capital_source) "
        "VALUES (%s,'ACTIVE',%s,%s)",
        (PAPER_ACCOUNT_ID, initial_capital_krw, source),
    )
    conn.execute(
        "INSERT INTO paper_cash(paper_account_id,currency,amount) VALUES (%s,'KRW',%s)",
        (PAPER_ACCOUNT_ID, initial_capital_krw),
    )
    return "CREATED"


def ensure_paper_account(database_url: str, initial_capital_krw: Decimal, source: str) -> str:
    if initial_capital_krw <= 0 or not source:
        raise PaperStoreError("Paper account initialization requires a positive sourced capital")
    with psycopg.connect(database_url) as conn:
        return _ensure_account(conn, Decimal(initial_capital_krw), source)


def load_paper_account(database_url: str) -> dict[str, Any]:
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        account = conn.execute(
            "SELECT paper_account_id,status,initial_capital_krw,initial_capital_source "
            "FROM paper_account WHERE singleton_slot=1"
        ).fetchone()
        if not account:
            raise PaperStoreError("Paper account is not initialized")
        cash = conn.execute(
            "SELECT amount FROM paper_cash WHERE paper_account_id=%s AND currency='KRW'",
            (account["paper_account_id"],),
        ).fetchone()
        positions = conn.execute(
            "SELECT symbol,quantity,average_price FROM paper_position WHERE paper_account_id=%s AND quantity<>0",
            (account["paper_account_id"],),
        ).fetchall()
        previous = conn.execute(
            """
            SELECT s.session_id,d.decision_receipt
            FROM paper_session s JOIN strategy_decision d USING(session_id)
            WHERE s.paper_account_id=%s AND s.completed_at IS NOT NULL
            ORDER BY s.as_of DESC,s.created_at DESC LIMIT 1
            """,
            (account["paper_account_id"],),
        ).fetchone()
        pending = False
        if previous:
            pending = bool(conn.execute(
                """
                SELECT EXISTS(
                    SELECT 1 FROM order_intent_preview i
                    LEFT JOIN paper_order o USING(intent_id)
                    WHERE i.session_id=%s AND (
                    i.risk_status IN ('MISSING_OR_ZERO_D1_ADV','PAPER_CASH_POLICY_BLOCK','PARTICIPATION_LIMITED_PENDING','BELOW_MIN_ORDER_THRESHOLD_PENDING')
                        OR o.status IN ('NEW','ACCEPTED','PARTIALLY_FILLED','REJECTED')
                    )
                ) AS pending
                """,
                (previous["session_id"],),
            ).fetchone()["pending"])
        previous_receipt = previous["decision_receipt"] if previous else {}
        if isinstance(previous_receipt, str):
            previous_receipt = json.loads(previous_receipt)
        previous_target_hash = (
            previous_receipt.get("evidence", {}).get("target_hash")
            if isinstance(previous_receipt, dict) else None
        )
    return {
        "paper_account_id": account["paper_account_id"],
        "status": account["status"],
        "initial_capital_krw": Decimal(account["initial_capital_krw"]),
        "initial_capital_source": account["initial_capital_source"],
        "cash_krw": Decimal(cash["amount"]),
        "positions": {row["symbol"]: Decimal(row["quantity"]) for row in positions},
        "position_average_prices": {row["symbol"]: Decimal(row["average_price"]) for row in positions},
        "previous_target_hash": previous_target_hash,
        "execution_pending": pending,
    }


def save_paper_preview(
    database_url: str,
    preview: dict[str, Any],
    intents: list[dict[str, Any]],
) -> str:
    _safe_json({"preview": preview, "intents": intents})
    now = datetime.now(timezone.utc)
    with psycopg.connect(database_url) as conn:
        _ensure_account(
            conn,
            Decimal(str(preview["initial_capital_krw"])),
            str(preview["initial_capital_source"]),
        )
        old = conn.execute(
            "SELECT input_hash FROM paper_session WHERE session_id=%s FOR UPDATE",
            (preview["session_id"],),
        ).fetchone()
        if old:
            if old[0] == preview["input_hash"]:
                for target in preview["targets"]:
                    conn.execute(
                        "UPDATE target_allocation SET adv20_d1_krw=%s WHERE decision_id=%s AND symbol=%s",
                        (target.get("adv20_d1_krw"), preview["decision_id"], target["symbol"]),
                    )
                return "NO_OP"
            raise PaperStoreError("Paper session input hash conflict")
        conn.execute(
            """
            INSERT INTO paper_session(
                session_id,paper_account_id,as_of,dataset_id,input_hash,config_hash,
                strategy_build_hash,candidate_fingerprint,runtime_mode,status,
                authority_status,broker_observation_status,completed_at
            ) VALUES (
                %(session_id)s,%(paper_account_id)s,%(as_of)s,%(dataset_id)s,%(input_hash)s,
                %(config_hash)s,%(strategy_build_hash)s,%(candidate_fingerprint)s,
                %(runtime_mode)s,%(decision_status)s,%(authority_status)s,
                %(broker_observation_status)s,%(completed_at)s
            )
            """,
            {
                **preview,
                "paper_account_id": PAPER_ACCOUNT_ID,
                "completed_at": now,
            },
        )
        conn.execute(
            """
            INSERT INTO strategy_decision(
                decision_id,session_id,as_of,input_hash,strategy_build_hash,regime,
                selected_candidates,decision_status,hold_reason,decision_receipt,
                authority_status
            ) VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s::jsonb,%s)
            """,
            (
                preview["decision_id"],
                preview["session_id"],
                preview["as_of"],
                preview["input_hash"],
                preview["strategy_build_hash"],
                preview["regime"],
                json.dumps(preview["selected_candidates"], default=str),
                preview["decision_status"],
                preview.get("hold_reason"),
                json.dumps(preview["decision_receipt"], default=str),
                preview["authority_status"],
            ),
        )
        for target in preview["targets"]:
            conn.execute(
                """
                INSERT INTO target_allocation(
                    decision_id,symbol,target_weight,target_notional,reference_price,
                    target_quantity,adv20_d1_krw,calculation_status,reason
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    preview["decision_id"],
                    target["symbol"],
                    target["target_weight"],
                    target["target_notional"],
                    target["reference_price"],
                    target["target_quantity"],
                    target.get("adv20_d1_krw"),
                    target["calculation_status"],
                    target["reason"],
                ),
            )
        for intent in intents:
            conn.execute(
                """
                INSERT INTO order_intent_preview(
                    intent_id,session_id,paper_account_id,symbol,side,current_quantity,
                    target_quantity,delta_quantity,reference_price,estimated_notional,
                    adv20_d1_krw,reason,risk_status,authority_status,input_hash
                ) VALUES (
                    %(intent_id)s,%(session_id)s,%(paper_account_id)s,%(symbol)s,%(side)s,
                    %(current_quantity)s,%(target_quantity)s,%(delta_quantity)s,
                    %(reference_price)s,%(estimated_notional)s,%(adv20_d1_krw)s,
                    %(reason)s,%(risk_status)s,%(authority_status)s,%(input_hash)s
                )
                """,
                intent,
            )
        conn.execute(
            "INSERT INTO paper_audit_event(session_id,paper_account_id,category,status,detail) "
            "VALUES (%s,%s,'DECISION_PREVIEW',%s,%s::jsonb)",
            (
                preview["session_id"],
                PAPER_ACCOUNT_ID,
                preview["authority_status"],
                json.dumps(
                    {
                        "input_hash": preview["input_hash"],
                        "decision_id": preview["decision_id"],
                        "intent_count": len(intents),
                        "cash_and_positions_mutated": False,
                    }
                ),
            ),
        )
    return "SAVED"


def latest_paper_summaries(database_url: str) -> dict[str, Any]:
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        account = conn.execute("SELECT * FROM latest_paper_account_summary").fetchone()
        decision = conn.execute("SELECT * FROM latest_strategy_decision_summary").fetchone()
        targets = conn.execute("SELECT * FROM latest_target_summary").fetchall()
        intents = conn.execute("SELECT * FROM latest_order_intent_preview").fetchall()
        health = conn.execute("SELECT * FROM latest_paper_runtime_health").fetchone()
    return {
        "account": dict(account) if account else None,
        "decision": dict(decision) if decision else None,
        "targets": [dict(row) for row in targets],
        "intents": [dict(row) for row in intents],
        "health": dict(health) if health else None,
    }
