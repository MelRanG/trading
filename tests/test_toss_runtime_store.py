from __future__ import annotations
import os, uuid
from datetime import datetime, timezone
from decimal import Decimal
import pytest
from quant_harness.toss_runtime_store import digest, initialize, latest_summary, save_snapshot

URL = os.getenv('TEST_DATABASE_URL')
pytestmark = pytest.mark.skipif(not URL, reason='TEST_DATABASE_URL is required for PostgreSQL acceptance')

def _snapshot(session_id: str, amount: str = '1'):
    now=datetime.now(timezone.utc)
    value={'session_id':session_id,'mode':'MOCK','provider':'TOSS_OPENAPI','contract_version':'1.2.5','started_at':now,'completed_at':now,'account_fingerprint':'f'*64,'cash':[{'currency':'KRW','buying_power':Decimal(amount),'observed_at':now,'source_status':'MOCK'}],'holdings':[],'orders':[],'receipts':[]}
    value['snapshot_hash']=digest({'amount':amount})
    return value

def test_postgres_idempotency_and_hash_conflict():
    initialize(URL); sid='pytest-'+str(uuid.uuid4()); first=_snapshot(sid)
    assert save_snapshot(URL,first)=='SAVED'
    assert latest_summary(URL)['overall_status']=='COMPLETED'
    assert save_snapshot(URL,first)=='NO_OP'
    with pytest.raises(RuntimeError, match='conflict'): save_snapshot(URL,_snapshot(sid,'2'))

def test_transaction_rolls_back_on_invalid_child_row():
    initialize(URL); sid='pytest-'+str(uuid.uuid4()); bad=_snapshot(sid); bad['cash']=[{'currency':'KRW','buying_power':None,'observed_at':datetime.now(timezone.utc),'source_status':'MOCK'}]
    with pytest.raises(Exception): save_snapshot(URL,bad)
    import psycopg
    with psycopg.connect(URL) as conn:
        assert conn.execute('SELECT count(*) FROM runtime_session WHERE session_id=%s',(sid,)).fetchone()[0]==0
