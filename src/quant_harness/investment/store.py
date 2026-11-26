"""Immutable research records alongside existing, isolated Paper tables."""
from contextlib import contextmanager
from pathlib import Path
import json
from urllib.parse import urlsplit
import psycopg
from psycopg.rows import dict_row
from .research import digest

DDL = '''
CREATE TABLE IF NOT EXISTS investment_identity (slot integer PRIMARY KEY CHECK(slot=1), strategy text NOT NULL);
CREATE TABLE IF NOT EXISTS investment_record (
 record_id text PRIMARY KEY, kind text NOT NULL, payload jsonb NOT NULL, payload_hash text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS investment_run (
 run_id text PRIMARY KEY REFERENCES investment_record(record_id), status text NOT NULL,
 outcome jsonb, updated_at timestamptz NOT NULL DEFAULT now());
'''


def require_database(url):
    """Never accepts an operational DB or another project's database."""
    parsed = urlsplit(url)
    if parsed.scheme not in ('postgresql', 'postgres') or parsed.hostname not in ('localhost', '127.0.0.1'):
        raise ValueError('isolated local PostgreSQL required')
    if parsed.port != 55432 or not parsed.path.startswith('/quant_task3_') or parsed.query:
        raise ValueError('dedicated Task3 database identity required')
    return url


class Store:
    def __init__(self, url, strategy):
        self.url = require_database(url)
        with psycopg.connect(self.url) as conn:
            conn.execute(DDL)
            conn.execute('INSERT INTO investment_identity VALUES (1,%s) ON CONFLICT DO NOTHING', (strategy,))
            actual = conn.execute('SELECT strategy FROM investment_identity WHERE slot=1').fetchone()[0]
            if actual != strategy:
                raise ValueError('one strategy per isolated Paper database')

    @contextmanager
    def lock(self):
        with psycopg.connect(self.url) as conn:
            if not conn.execute('SELECT pg_try_advisory_lock(330013)').fetchone()[0]:
                raise ValueError('investment cycle already running')
            try:
                yield
            finally:
                conn.execute('SELECT pg_advisory_unlock(330013)')

    def put(self, kind, payload, identity=None):
        encoded = json.dumps(payload, sort_keys=True, default=str, allow_nan=False)
        payload = json.loads(encoded)
        fingerprint = digest(payload)
        identity = identity or fingerprint
        with psycopg.connect(self.url) as conn:
            conn.execute('INSERT INTO investment_record VALUES (%s,%s,%s::jsonb,%s,now()) ON CONFLICT DO NOTHING', (identity, kind, encoded, fingerprint))
            prior = conn.execute('SELECT kind,payload_hash FROM investment_record WHERE record_id=%s', (identity,)).fetchone()
            if prior != (kind, fingerprint):
                raise ValueError('immutable record conflict')
        return identity

    def get(self, identity):
        with psycopg.connect(self.url, row_factory=dict_row) as conn:
            row = conn.execute('SELECT * FROM investment_record WHERE record_id=%s', (identity,)).fetchone()
        if not row or row['payload_hash'] != digest(row['payload']):
            raise ValueError('missing or corrupted record')
        return row['payload']

    def state(self, identity, status, outcome=None):
        with psycopg.connect(self.url) as conn:
            conn.execute('INSERT INTO investment_run VALUES (%s,%s,%s::jsonb,now()) ON CONFLICT (run_id) DO UPDATE SET status=EXCLUDED.status,outcome=EXCLUDED.outcome,updated_at=now()', (identity, status, json.dumps(outcome, default=str)))

    def export(self, path):
        with psycopg.connect(self.url, row_factory=dict_row) as conn:
            rows = conn.execute('SELECT * FROM investment_record ORDER BY created_at,record_id').fetchall()
        for row in rows:
            if digest(row['payload']) != row['payload_hash']:
                raise ValueError('record hash mismatch')
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(''.join(json.dumps(row, default=str, ensure_ascii=False) + '\n' for row in rows))
        return len(rows)
