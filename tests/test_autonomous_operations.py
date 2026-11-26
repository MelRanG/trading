"""Operations contract tests. DB fixture uses a dedicated disposable test DB."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import json,os
import psycopg
import pytest
from quant_harness.investment.operations_data import Warehouse,parse_calendar,phase,strict_rows,encode_prices,decode_prices
from quant_harness.investment.operations import latest_completed,decision_for_session,quote_events
from quant_harness.investment.operations_experiment import validate_contract
from quant_harness.investment.research import digest
ROOT=Path(__file__).resolve().parents[1]


def calendar(day='2026-11-13',opening='2026-11-13T23:30:00+09:00',closing='2026-11-14T06:00:00+09:00'):
    return {'result':{'today':{'date':day,'regularMarket':{'startTime':opening,'endTime':closing}}}}


def test_us_cross_midnight_and_official_dst():
    rows=parse_calendar(calendar(),'US')
    assert rows[0]['day']=='2026-11-13'
    assert phase(rows,'2026-11-13T15:00:00Z')[0]=='REGULAR'
    assert phase(rows,'2026-11-13T21:00:00Z')[0]=='CLOSED'
    summer=parse_calendar(calendar('2026-07-01','2026-07-01T22:30:00+09:00','2026-07-02T05:00:00+09:00'),'US')
    assert summer[0]['day']=='2026-07-01'
    assert phase(summer,'2026-07-01T13:45:00Z')[0]=='REGULAR'


def test_closed_holiday_never_guessed_as_weekday():
    payload={'result':{'today':{'date':'2026-11-26'},'nextBusinessDay':calendar('2026-11-27','2026-11-27T23:30:00+09:00','2026-11-28T03:00:00+09:00')['result']['today']}}
    rows=parse_calendar(payload,'US')
    assert [r['day'] for r in rows]==['2026-11-27']
    assert phase(rows,'2026-11-26T17:00:00Z')[0]=='CLOSED'
    assert phase(rows,'2026-11-27T19:00:00Z')[0]=='CLOSED'  # official early close
    with pytest.raises(ValueError):latest_completed({'sessions':rows},'2026-11-27T18:04:00Z')
    assert latest_completed({'sessions':rows},'2026-11-27T18:05:00Z')['day']=='2026-11-27'


def test_korean_venue_and_no_calendar_fail_closed():
    p={'result':{'today':{'integrated':{'regularMarket':{'startTime':'2026-11-13T09:00:00+09:00','endTime':'2026-11-13T15:30:00+09:00'}}}}}
    assert parse_calendar(p,'KR')[0]['day']=='2026-11-13'
    with pytest.raises(ValueError):parse_calendar({'result':{}},'KR')


def test_candle_identity_currency_geometry_and_us_date():
    row={'timestamp':'2026-11-12T14:00:00+09:00','openPrice':'100','highPrice':'110','lowPrice':'90','closePrice':'105','volume':'100','currency':'USD'}
    f=strict_rows({'result':{'candles':[row]}},'AAPL','USD','America/New_York','2026-11-12')
    assert f.date.iloc[0]=='2026-11-12'
    for change in ({'highPrice':'99'},{'closePrice':'nan'},{'currency':'KRW'},{'volume':'-1'}):
        with pytest.raises(ValueError):strict_rows({'result':{'candles':[{**row,**change}]}},'AAPL','USD','America/New_York','2026-11-12')
    with pytest.raises(ValueError):strict_rows({'result':{'candles':[row,row]}},'AAPL','USD','America/New_York','2026-11-12')


@pytest.fixture
def warehouse(tmp_path):
    url=os.environ.get('TASK5_TEST_DATABASE_URL')
    if not url:pytest.fail('TASK5_TEST_DATABASE_URL required; no silent DB skip')
    if not url.endswith('/quant_task3_ops_test'):pytest.fail('dedicated Task5 test DB required')
    with psycopg.connect(url) as c:
        c.execute('DROP SCHEMA public CASCADE');c.execute('CREATE SCHEMA public')
    return Warehouse(url,tmp_path)


def test_budget_reservation_failure_circuit_and_restart(warehouse):
    w=warehouse;w.reserve('TOSS_US',2);w.reserve('TOSS_US',2)
    restarted=Warehouse(w.url,w.root)
    with pytest.raises(ValueError):restarted.reserve('TOSS_US',2)
    w.reserve('TOSS_KR',20);w.failure('TOSS_KR',True)
    with pytest.raises(ValueError):restarted.reserve('TOSS_KR',20)


def test_immutable_raw_and_snapshot_replay(warehouse):
    w=warehouse;receipt=w.raw({'price':1},'test');path=w.root/receipt['path']
    assert w.raw({'price':1},'test')['source_hash']==receipt['source_hash']
    path.write_text('corruption')
    with pytest.raises(ValueError):w.raw({'price':1},'test')
    identity=w.point('p','fixture',{'frozen':1})
    with pytest.raises(ValueError):w.store.put('fixture',{'frozen':2},identity)
    assert Warehouse(w.url,w.root).lookup('p')=={'frozen':1}


def test_duplicate_process_and_crashed_connection_release(warehouse):
    with warehouse.store.lock():
        with pytest.raises(ValueError):
            with Warehouse(warehouse.url,warehouse.root).store.lock():pass
    connection=psycopg.connect(warehouse.url)
    assert connection.execute('SELECT pg_try_advisory_lock(330013)').fetchone()[0]
    connection.close()  # same release boundary as killed worker
    with warehouse.store.lock():pass


def test_metadata_discovery_cannot_enroll_strategy_and_is_bounded(warehouse):
    w=warehouse;w.watch('US',['AAPL'],'SPY',4)
    catalog={'rows':[{'symbol':s,'common_stock_verified':True} for s in ['X','Y','Z']]}
    assert w.discover('US',catalog,2,4)==2
    w.discover('US',catalog,2,4)
    with psycopg.connect(w.url) as c:
        rows=c.execute('SELECT symbol,role FROM ops_watch ORDER BY symbol').fetchall()
    assert len(rows)==4 and ('X','RESEARCH_UNQUALIFIED') in rows and ('AAPL','STRATEGY') in rows


def test_no_broker_writes_and_legacy_scheduler_is_opt_in():
    text=(ROOT/'src/quant_harness/investment/operations.py').read_text()
    assert 'place_order(' not in text and 'submit_order(' not in text
    import yaml
    services=yaml.safe_load((ROOT/'compose.yaml').read_text())['services']
    assert all('legacy-reference' in s['profiles'] for s in services.values())


def test_common_contract_rejects_automatic_promotion():
    c={'team':'quant','adapter':'STOCK_DAILY_FROZEN_V1','snapshot_hash':'frozen','baseline':'A','challenger':'B','model_version':'NONE','prompt_version':'NONE','strategy_version':'V1',
       'period':'FROZEN','metrics':['return'],'budget':{'experiments':1,'parameter_search':0},'stop_conditions':['changed input'],'promotion_conditions':['independent Forward','human approval']}
    assert validate_contract(c)
    c['promotion_conditions']=['automatic']
    with pytest.raises(ValueError):validate_contract(c)


def test_session_recovery_after_committed_decision_and_expiry(warehouse):
    from quant_harness.investment.operations import decision_for_session
    w=warehouse
    identity=w.store.put('stock_decision',{'market':'US','sealed_at':'2026-11-13T12:00:00Z'})
    w.store.state(identity,'DECIDED')
    assert decision_for_session(w.url,'US','2026-11-13')==identity
    w.store.state(identity,'COMPLETE')
    assert decision_for_session(w.url,'US','2026-11-13')==identity  # crash after fill commit
    w.store.state(identity,'EXPIRED')
    assert decision_for_session(w.url,'US','2026-11-13') is None


def test_automatic_labels_use_observed_marks_not_future_date(warehouse):
    from quant_harness.investment.operations import labels_for
    from quant_harness.investment.review import policy,score_mature_outcome
    w=warehouse;identity=w.store.put('stock_decision',{'market':'US'})
    with psycopg.connect(w.url) as c:
        c.execute('CREATE TABLE stock_nav(decision_id text,nav numeric,created_at timestamptz)')
        c.execute('INSERT INTO stock_nav VALUES (%s,100,%s)',(identity,'2020-01-02T15:00:00Z'))
        for day in ('2020-01-02','2020-01-03','2020-01-06'):
            c.execute('INSERT INTO ops_session VALUES (%s,%s,%s,%s,%s,%s)',('US',day,day+'T14:30:00Z',day+'T21:00:00Z','SYNTHETIC_CALENDAR',day+'T22:00:00Z'))
        for a,b in [('2020-01-02','2020-01-03'),('2020-01-03','2020-01-06')]:c.execute('INSERT INTO ops_session_edge VALUES (%s,%s,%s,%s)',('US',a,b,'FIXTURE'))
    w.point('mark:US:2020-01-03','ops_account_mark',{'nav':90,'observed_at':'2020-01-03T22:00:00Z','source_hash':'FIXTURE','benchmark':92})
    labels=labels_for(w,w.url,identity)
    assert labels['nav']=={'2020-01-02':100,'2020-01-03':90}
    packet={'source_decision_id':identity,'market':'US','strategy_id':'MOM63_STOCKS','cutoff':'2020-01-02T14:00:00Z'}
    cfg=policy(ROOT);process={'packet_hash':digest(packet),'decision_id':identity,'policy_hash':digest(cfg),'findings':[]}
    scored=score_mature_outcome(process,packet,cfg,labels)
    assert scored['horizons']['1']['status']=='MATURED'
    assert scored['horizons']['1']['return']==pytest.approx(-.1)
    # Jan 6 exists in calendar, but its missing mark is never invented.
    cfg['strategy_horizons']['MOM63_STOCKS']=[2];process['policy_hash']=digest(cfg)
    assert score_mature_outcome(process,packet,cfg,labels)['horizons']['2']['status']=='INSUFFICIENT_EVIDENCE'


def test_calendar_outage_never_compresses_horizon(warehouse):
    from quant_harness.investment.operations import labels_for
    w=warehouse;identity=w.store.put('stock_decision',{'market':'US'})
    with psycopg.connect(w.url) as c:
        c.execute('CREATE TABLE stock_nav(decision_id text,nav numeric,created_at timestamptz)')
        c.execute('INSERT INTO stock_nav VALUES (%s,100,%s)',(identity,'2020-01-02T15:00:00Z'))
        for day in ('2020-01-02','2020-01-10'):
            c.execute('INSERT INTO ops_session VALUES (%s,%s,%s,%s,%s,%s)',('US',day,day+'T14:30:00Z',day+'T21:00:00Z','SYNTHETIC',day+'T22:00:00Z'))
    w.point('mark:US:2020-01-10','ops_account_mark',{'nav':120,'observed_at':'2020-01-10T22:00:00Z','benchmark':100})
    labels=labels_for(w,w.url,identity)
    assert labels['sessions']==['2020-01-02'] and '2020-01-10' not in labels['nav']


def test_incremental_overlap_revision_and_snapshot_merge(warehouse,monkeypatch):
    import pandas as pd
    import quant_harness.investment.operations_data as data
    from quant_harness.investment.discovery import now
    w=warehouse;w.root=ROOT;monkeypatch.setattr(data.time,'sleep',lambda _:None)
    dates=pd.bdate_range('2025-01-02',periods=210)
    rows=[{'timestamp':str(d.date())+'T14:00:00+09:00','openPrice':str(100+i),'highPrice':str(102+i),'lowPrice':str(99+i),'closePrice':str(101+i),'volume':'1000','currency':'USD'} for i,d in enumerate(dates)]
    serving=rows[:200];counts=[]
    def fake(client,market,path,query=None,limit=100):
        counts.append(query['count']);payload={'result':{'candles':serving}}
        return payload,{'source_hash':digest(payload),'available_at':now()}
    monkeypatch.setattr(w,'call',fake)
    class Client:
        class endpoint_map:candles_path='/api/v1/candles'
    def session(index):
        day=str(dates[index].date())
        return {'day':day,'opening':day+'T14:30:00Z','closing':day+'T21:00:00Z'}
    first=data.collect_toss(w,Client(),'US',['AAPL'],session(199),100)
    assert len(first['AAPL']['frame'])==200 and counts==[200,200]
    serving=rows[193:201];counts.clear()
    second=data.collect_toss(w,Client(),'US',['AAPL'],session(200),100)
    assert len(second['AAPL']['frame'])==201 and counts==[8,8]
    serving=[{**r,'closePrice':str(float(r['closePrice'])+.5)} for r in rows[194:202]]
    with pytest.raises(ValueError,match='revision'):data.collect_toss(w,Client(),'US',['AAPL'],session(201),100)
    # Rejected revision never replaces the last accepted snapshot.
    assert len(w.lookup('price:US:AAPL')['frame'])==201


def test_presealed_next_session_not_repeated_after_fill_commit(warehouse):
    from quant_harness.investment.operations import recover_session
    w=warehouse;analysis={'as_of':'2026-11-13T07:00:00Z','input_hash':'fixed'}
    quant=w.store.put('stock_quant_analysis',analysis)
    identity=w.store.put('stock_decision',{'market':'KR','sealed_at':'2026-11-13T07:00:00Z','analysis':analysis})
    w.store.state(identity,'COMPLETE')
    w.point('manifest:KR:2026-11-16','ops_preseal_manifest',{'quant_id':quant})
    # Monday's assignment survives a crash before its pointer was committed,
    # despite the decision having been sealed on the previous Friday.
    assert recover_session(w,w.store,'KR','2026-11-16')==identity
    w.point('decision:KR:2026-11-16','ops_decision_link',{'decision_id':identity})
    assert recover_session(w,w.store,'KR','2026-11-16')==identity
    w.store.state(identity,'EXPIRED')
    assert recover_session(w,w.store,'KR','2026-11-16') is None
