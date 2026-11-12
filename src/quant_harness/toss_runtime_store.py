"""PostgreSQL-only persistence for Toss read-only operational snapshots."""
from __future__ import annotations

from contextlib import contextmanager
from hashlib import sha256
import json
from typing import Any, Iterator

import psycopg

SCHEMA_VERSION = 1

DDL = """
CREATE TABLE IF NOT EXISTS schema_version (version integer PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS runtime_session (session_id text PRIMARY KEY, mode text NOT NULL, provider text NOT NULL, contract_version text NOT NULL, started_at timestamptz NOT NULL, completed_at timestamptz, overall_status text NOT NULL, account_fingerprint text, snapshot_hash text, failure_stage text, failure_category text, UNIQUE(session_id, snapshot_hash));
CREATE TABLE IF NOT EXISTS account_snapshot (session_id text PRIMARY KEY REFERENCES runtime_session(session_id), account_fingerprint text NOT NULL, snapshot_hash text NOT NULL);
CREATE TABLE IF NOT EXISTS cash_snapshot (session_id text REFERENCES runtime_session(session_id), currency text NOT NULL, buying_power numeric NOT NULL, observed_at timestamptz NOT NULL, source_status text NOT NULL, PRIMARY KEY(session_id,currency));
CREATE TABLE IF NOT EXISTS holding_snapshot (session_id text REFERENCES runtime_session(session_id), symbol text NOT NULL, quantity numeric, available_quantity numeric, average_price numeric, market_value numeric, currency text, observed_at timestamptz, source_status text NOT NULL, PRIMARY KEY(session_id,symbol));
CREATE TABLE IF NOT EXISTS order_snapshot (session_id text REFERENCES runtime_session(session_id), provider_order_id text NOT NULL, symbol text, side text, order_type text, requested_quantity numeric, executed_quantity numeric, remaining_quantity numeric, limit_price numeric, status text NOT NULL, submitted_at timestamptz, updated_at timestamptz, source_status text NOT NULL, PRIMARY KEY(session_id,provider_order_id));
CREATE TABLE IF NOT EXISTS endpoint_receipt (session_id text REFERENCES runtime_session(session_id), endpoint text NOT NULL, method text NOT NULL CHECK(method='GET' OR endpoint='/oauth2/token'), request_fingerprint text NOT NULL, started_at timestamptz NOT NULL, completed_at timestamptz NOT NULL, status_category text NOT NULL, pagination_count integer NOT NULL, result_status text NOT NULL, response_digest text, error_category text, PRIMARY KEY(session_id,endpoint,request_fingerprint));
CREATE TABLE IF NOT EXISTS audit_event (id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, session_id text REFERENCES runtime_session(session_id), created_at timestamptz NOT NULL DEFAULT now(), category text NOT NULL, detail text NOT NULL);
CREATE OR REPLACE VIEW latest_account_summary AS SELECT a.account_fingerprint,s.completed_at,s.overall_status FROM account_snapshot a JOIN runtime_session s USING(session_id) WHERE s.overall_status='COMPLETED' ORDER BY s.completed_at DESC LIMIT 1;
CREATE OR REPLACE VIEW latest_cash_summary AS SELECT c.currency,c.buying_power,c.observed_at,c.source_status FROM cash_snapshot c JOIN runtime_session s USING(session_id) WHERE s.overall_status='COMPLETED' ORDER BY s.completed_at DESC;
CREATE OR REPLACE VIEW latest_holdings_summary AS SELECT h.symbol,h.quantity,h.market_value,h.currency,h.source_status FROM holding_snapshot h JOIN runtime_session s USING(session_id) WHERE s.overall_status='COMPLETED' ORDER BY s.completed_at DESC;
CREATE OR REPLACE VIEW latest_orders_summary AS SELECT o.provider_order_id,o.symbol,o.status,o.executed_quantity,o.remaining_quantity,o.source_status FROM order_snapshot o JOIN runtime_session s USING(session_id) WHERE s.overall_status='COMPLETED' ORDER BY s.completed_at DESC;
CREATE OR REPLACE VIEW latest_runtime_health AS SELECT session_id,mode,provider,completed_at,overall_status,failure_stage,failure_category FROM runtime_session ORDER BY started_at DESC LIMIT 1;
"""

def fingerprint(value: str) -> str: return sha256(value.encode()).hexdigest()
def digest(value: Any) -> str: return sha256(json.dumps(value,sort_keys=True,separators=(',',':'),default=str).encode()).hexdigest()

def initialize(database_url: str) -> None:
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(DDL); cur.execute("INSERT INTO schema_version(version) VALUES (%s) ON CONFLICT DO NOTHING", (SCHEMA_VERSION,))
            cur.execute("SELECT max(version) FROM schema_version")
            if cur.fetchone()[0] != SCHEMA_VERSION: raise RuntimeError("incompatible runtime schema version")

def save_snapshot(database_url: str, snapshot: dict[str, Any]) -> str:
    """All snapshot rows commit atomically; raw responses and account numbers are rejected."""
    prohibited = ('access_token','client_secret','accountNo','raw')
    encoded = json.dumps(snapshot, default=str)
    if any(key in encoded for key in prohibited): raise ValueError('sensitive or raw data cannot be persisted')
    session_id, snap_hash = snapshot['session_id'], snapshot['snapshot_hash']
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT snapshot_hash FROM runtime_session WHERE session_id=%s FOR UPDATE", (session_id,)); old=cur.fetchone()
            if old:
                if old[0] == snap_hash: return 'NO_OP'
                raise RuntimeError('snapshot hash conflict')
            cur.execute("INSERT INTO runtime_session(session_id,mode,provider,contract_version,started_at,completed_at,overall_status,account_fingerprint,snapshot_hash,failure_stage,failure_category) VALUES (%(session_id)s,%(mode)s,%(provider)s,%(contract_version)s,%(started_at)s,%(completed_at)s,'COMPLETED',%(account_fingerprint)s,%(snapshot_hash)s,NULL,NULL)", snapshot)
            cur.execute("INSERT INTO account_snapshot VALUES (%s,%s,%s)",(session_id,snapshot['account_fingerprint'],snap_hash))
            for c in snapshot['cash']: cur.execute("INSERT INTO cash_snapshot VALUES (%s,%s,%s,%s,%s)",(session_id,c['currency'],c['buying_power'],c['observed_at'],c['source_status']))
            for h in snapshot['holdings']: cur.execute("INSERT INTO holding_snapshot VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",(session_id,h['symbol'],h.get('quantity'),h.get('available_quantity'),h.get('average_price'),h.get('market_value'),h.get('currency'),h.get('observed_at'),h['source_status']))
            for o in snapshot['orders']: cur.execute("INSERT INTO order_snapshot VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",(session_id,o['provider_order_id'],o.get('symbol'),o.get('side'),o.get('order_type'),o.get('requested_quantity'),o.get('executed_quantity'),o.get('remaining_quantity'),o.get('limit_price'),o['status'],o.get('submitted_at'),o.get('updated_at'),o['source_status']))
            for r in snapshot['receipts']: cur.execute("INSERT INTO endpoint_receipt VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",(session_id,r['endpoint'],r['method'],r['request_fingerprint'],r['started_at'],r['completed_at'],r['status_category'],r['pagination_count'],r['result_status'],r.get('response_digest'),r.get('error_category')))
    return 'SAVED'

def latest_summary(database_url: str) -> dict[str, Any] | None:
    with psycopg.connect(database_url) as conn:
        row=conn.execute('SELECT account_fingerprint,completed_at,overall_status FROM latest_account_summary').fetchone()
    return None if row is None else {'account_fingerprint':row[0], 'completed_at':row[1], 'overall_status':row[2]}
