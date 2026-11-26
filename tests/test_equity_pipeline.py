from pathlib import Path
from datetime import datetime,timezone
import os
import json
import pandas as pd
import psycopg
import pytest
from quant_harness.investment import equities,stockpaper
from quant_harness.investment.store import Store
from quant_harness.investment.research import digest

ROOT=Path(__file__).resolve().parents[1]
URL=os.getenv('TASK3_STOCK_TEST_DATABASE_URL')


def test_chart_symbol_geometry_and_adjustment():
    payload={'chart':{'result':[{'meta':{'symbol':'AAPL'},'timestamp':[1700000000],
      'indicators':{'quote':[{'open':[100],'high':[110],'low':[90],'close':[105],'volume':[10]}],'adjclose':[{'adjclose':[52.5]}]}}]}}
    frame,_=equities.normalize_chart(payload,'AAPL')
    assert frame.raw_close.iloc[0]==105 and frame.close.iloc[0]==52.5 and frame.open.iloc[0]==50
    with pytest.raises(ValueError):equities.normalize_chart(payload,'MSFT')
    payload['chart']['result'][0]['indicators']['quote'][0]['high']=[80]
    with pytest.raises(ValueError):equities.normalize_chart(payload,'AAPL')


def test_stock_selection_causal_and_same_risk():
    cfg=equities.settings(ROOT)
    dates=pd.bdate_range('2024-01-01',periods=160)
    close=pd.DataFrame({'AAPL':range(100,260),'MSFT':range(200,360)},index=dates,dtype=float)
    original=equities.stock_targets(close,cfg,'MOM63_STOCKS')
    changed=close.copy();changed.iloc[150:]*=5
    after=equities.stock_targets(changed,cfg,'MOM63_STOCKS')
    pd.testing.assert_frame_equal(original.iloc[:150],after.iloc[:150])
    assert all(sum(json.loads(x).values())<=cfg['gross_cap'] for x in original.target_weights_json)


@pytest.fixture
def db():
    if not URL:pytest.skip('dedicated stock test database required')
    if not URL.endswith('/quant_task3_stocktest'):raise ValueError('destructive test DB identity')
    store=Store(URL,'US_STOCKS')
    stockpaper.initialize(store,equities.settings(ROOT),'US')
    with psycopg.connect(URL) as conn:
        conn.execute('TRUNCATE stock_nav,stock_fill,stock_position,stock_account,investment_run,investment_record CASCADE')
    stockpaper.initialize(store,equities.settings(ROOT),'US')
    return store


def seed(db):
    cfg=equities.settings(ROOT)
    decision={'algorithm_hash':stockpaper.algorithm_fingerprint(),'market':'US','currency':'USD','strategy_id':'MOM63_STOCKS','contract_hash':digest(cfg),'sealed_at':'2026-07-09T13:00:00+00:00',
        'input_hash':'fixture','opening_cash':'100000','opening_positions':{},'analysis':{'reason':'FIXTURE'},
        'intents':[{'symbol':'AAPL','target_quantity':'190','delta_quantity':'190','adv20_d1':1e9}], 'eligible':True}
    identity=db.put('stock_decision',decision);db.state(identity,'DECIDED')
    event={'symbol':'AAPL','asset_type':'EQUITY','currency':'USD','price':100,'event_at':'2026-07-09T13:30:01+00:00',
       'available_at':'2026-07-09T13:30:02+00:00','session_open':'2026-07-09T13:30:00+00:00','session_close':'2026-07-09T20:00:00+00:00',
       'source':'YAHOO_CHART_OBSERVED'}
    return identity,event


def test_us_fill_currency_and_idempotent_recovery(db):
    identity,event=seed(db)
    result=stockpaper.execute(db,ROOT,identity,[event],current='2026-07-09T13:30:03+00:00')
    assert result['status']=='COMPLETE' and result['currency']=='USD'
    duplicate=stockpaper.execute(db,ROOT,identity,[],current='2026-08-01T00:00:00+00:00')
    assert duplicate['idempotent']
    with psycopg.connect(URL) as conn:
        assert conn.execute('SELECT count(*) FROM stock_fill').fetchone()[0]==1
        assert conn.execute('SELECT count(*) FROM stock_nav').fetchone()[0]==1


@pytest.mark.parametrize('change',[{'asset_type':'ETF'},{'currency':'KRW'},{'event_at':'2026-07-09T12:00:00+00:00'},
    {'event_at':'2026-07-09T13:30:09+00:00'},{'price':200},{'price':float('nan')}])
def test_reject_etf_currency_future_and_gap(db,change):
    identity,event=seed(db)
    with pytest.raises((ValueError,ArithmeticError)):
        stockpaper.execute(db,ROOT,identity,[{**event,**change}],current='2026-07-09T13:30:03+00:00')
    with psycopg.connect(URL) as conn:assert conn.execute('SELECT count(*) FROM stock_fill').fetchone()[0]==0


def test_transaction_rollback_before_nav_and_restart(db,monkeypatch):
    identity,event=seed(db)
    original=stockpaper.reconcile
    calls=[]
    def fault(conn):
        calls.append(1)
        return original(conn) if len(calls)==1 else False
    monkeypatch.setattr(stockpaper,'reconcile',fault)
    with pytest.raises(ValueError,match='postfill'):stockpaper.execute(db,ROOT,identity,[event],current='2026-07-09T13:30:03+00:00')
    with psycopg.connect(URL) as conn:
        assert conn.execute('SELECT count(*) FROM stock_fill').fetchone()[0]==0
        assert conn.execute('SELECT cash FROM stock_account').fetchone()[0]==100000
    monkeypatch.setattr(stockpaper,'reconcile',original)
    assert stockpaper.execute(db,ROOT,identity,[event],current='2026-07-09T13:30:03+00:00')['status']=='COMPLETE'


def test_cash_tamper_blocks_even_completed_cache(db):
    identity,event=seed(db)
    stockpaper.execute(db,ROOT,identity,[event],current='2026-07-09T13:30:03+00:00')
    with psycopg.connect(URL) as conn:conn.execute('UPDATE stock_account SET cash=1')
    assert stockpaper.execute(db,ROOT,identity,[],current='2026-07-09T13:30:03+00:00')['status']=='HOLD_ONLY'


def test_us_kr_account_currency_cannot_mix(db):
    with pytest.raises(ValueError,match='isolation'):stockpaper.initialize(db,equities.settings(ROOT),'KR')


def test_v87_adapter_preserves_us_symbol_and_blocks_revision(tmp_path):
    frame=pd.DataFrame([{'timestamp':'2024-01-01T14:30:00+00:00','raw_open':100,'raw_high':110,'raw_low':90,'raw_close':100,'volume':100,'value_approx':10000}])
    receipt={'available_at':'2026-01-01T00:00:00+00:00','source_hash':'a'}
    assert equities.equity_revision_gate(frame,'AAPL',tmp_path,receipt)['passed']
    reference=next((tmp_path/'equity_revision').glob('*.reference.csv'))
    assert pd.read_csv(reference).ticker.iloc[0]=='AAPL'
    frame['raw_close']=105
    with pytest.raises(ValueError,match='revision'):equities.equity_revision_gate(frame,'AAPL',tmp_path,{**receipt,'source_hash':'b'})


def test_code_version_change_blocks_only_new_fills(db,monkeypatch):
    identity,event=seed(db)
    monkeypatch.setattr(stockpaper,'algorithm_fingerprint',lambda:'changed')
    result=stockpaper.execute(db,ROOT,identity,[event],current='2026-07-09T13:30:03+00:00')
    assert result['reason']=='ALGORITHM_VERSION_CHANGED_RESEAL_REQUIRED'
    with psycopg.connect(URL) as conn:assert conn.execute('SELECT count(*) FROM stock_fill').fetchone()[0]==0


def test_completed_accounting_survives_code_upgrade(db,monkeypatch):
    identity,event=seed(db)
    stockpaper.execute(db,ROOT,identity,[event],current='2026-07-09T13:30:03+00:00')
    monkeypatch.setattr(stockpaper,'algorithm_fingerprint',lambda:'changed')
    assert stockpaper.execute(db,ROOT,identity,[],current='2026-08-01T00:00:00+00:00')['idempotent']
