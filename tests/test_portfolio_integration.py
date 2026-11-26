"""Decision and release-boundary tests; fixtures are not Forward alpha evidence."""
from pathlib import Path
from copy import deepcopy
import json
import pytest
from quant_harness.investment.decision import decide,enterprise_to_equity
from quant_harness.investment.company_analysis import parse_response
from quant_harness.investment.company_outcomes import parse_release
R=Path(__file__).resolve().parents[1];POLICY=json.loads((R/'config/task8_portfolio.json').read_text());AT='2026-11-14T00:00:00Z'
def signal(team='quant',symbol='TEST',horizon=5,direction='LONG',source='a'):
 return {'ticker':symbol,'team':team,'engine':'SYNTHETIC_TEST','market':'US','currency':'USD','source_hashes':[source*64],'available_at':'2026-11-13T15:00:00Z','valid_until':'2026-11-15T00:00:00Z','horizon_sessions':horizon,'direction':direction,'status':'SHADOW_ELIGIBLE','expected_return':.05,'downside':.1,'round_trip_cost':.005,'liquidity_verified':True,'sector':'FIXTURE_SECTOR','hypothesis':'Synthetic test only','falsification':'Synthetic invalidation','version':'FIXTURE','edge_evidence':'PREREGISTERED_FORWARD_SHADOW'}
def test_nonzero_independent_and_no_double_count():
 q=signal();c=signal('company');a=decide([q,c],POLICY,'US',AT)
 assert a['weights']=={'TEST':.1} and a['cash_weight']==.9
 assert decide([q,c],POLICY,'US',AT,mode='company')['weights']=={'TEST':.1}
def test_same_horizon_conflict_and_cross_horizon_independence():
 q=signal();c=signal('company',direction='AVOID')
 assert decide([q,c],POLICY,'US',AT)['status']=='ABSTAIN_CASH'
 c['horizon_sessions']=63
 assert decide([q,c],POLICY,'US',AT)['weights']=={'TEST':.1}
def test_bad_quant_does_not_veto_qualified_company():
 q=signal(direction='AVOID');q['edge_evidence']='UNPROVEN'
 assert decide([q,signal('company')],POLICY,'US',AT)['weights']=={'TEST':.1}
@pytest.mark.parametrize('mutation',[{'expected_return':None},{'round_trip_cost':.1},{'status':'RESEARCH_ONLY'},{'liquidity_verified':False},{'sector':None},{'valid_until':'2026-11-13T16:00:00Z'}])
def test_missing_evidence_and_costs_abstain(mutation):
 s=signal();s.update(mutation);assert decide([s],POLICY,'US',AT)['status']=='ABSTAIN_CASH'
@pytest.mark.parametrize('mutation',[{'available_at':'2027-01-01T00:00:00Z'},{'currency':'KRW'},{'source_hashes':['fake']}])
def test_future_fx_and_hash_fail_closed(mutation):
 s=signal();s.update(mutation)
 with pytest.raises(ValueError):decide([s],POLICY,'US',AT)
def test_correlation_cluster_and_missing_data():
 policy=deepcopy(POLICY);policy.update(research_name_weight=.2,max_turnover=.8)
 rows=[signal(symbol='ONE'),signal(symbol='TWO')]
 assert decide(rows,policy,'US',AT)['status']=='HOLD_ONLY'
 d=decide(rows,policy,'US',AT,correlations={'ONE|TWO':.9});assert sum(d['weights'].values())==pytest.approx(.3)
def test_turnover_and_no_silent_flatten():
 policy=deepcopy(POLICY);policy['max_turnover']=.05
 assert decide([signal()],policy,'US',AT)['status']=='HOLD_ONLY'
 result=decide([],POLICY,'US',AT,current={'TEST':.1});assert result['status']=='HOLD_ONLY' and result['weights']=={'TEST':.1}
def test_ev_and_equity_not_interchangeable():
 r=enterprise_to_equity(100,80,10,5,10);assert r['equity_value']==25 and r['equity_value_per_share']==2.5
 assert enterprise_to_equity(50,80,10,5,10)['equity_impaired']
 with pytest.raises(ValueError):enterprise_to_equity(100,80,None,0,10)
def test_original_cli_fallback_rejected_and_component_validated():
 packet=json.loads((R/'runtime/task7/company/packet.json').read_text());valid=(R/'runtime/task8/company_response.json').read_text();assert len(parse_response(valid,packet))==2
 data=json.loads(valid);data['cases'][0]['facts']=[]
 with pytest.raises(ValueError,match='fallback'):parse_response(json.dumps(data),packet)
 data=json.loads(valid);data['cases'][0]['facts'][0]['source_id']='UNKNOWN'
 with pytest.raises(ValueError,match='uncited'):parse_response(json.dumps(data),packet)
def release_html(time='2027-02-01T21:00:00Z',quarter='Fourth Quarter 2026',first='December 31, 2026'):
 return (f'<meta property="article:published_time" content="{time}"><h1>CoreWeave {quarter}</h1><p>USD in millions</p><table><tr><th>Three Months Ended</th></tr><tr><th></th><th>{first}</th><th>December 31, 2025</th></tr><tr><td>Revenue</td><td>$</td><td>4,900</td><td>2,000</td></tr></table>').encode()
def test_actual_label_table_identity_and_unit():
 label=parse_release(release_html(),'CRWV','https://investors.coreweave.com/test','2027-02-02T00:00:00Z');assert label['actual']==4900 and label['unit']=='USD_million'
 for raw in [release_html(quarter='Third Quarter 2026'),release_html(first='December 31, 2025'),release_html(time='2028-02-01T00:00:00Z'),release_html().replace(b'in millions',b'in thousands'),release_html().replace(b'Three Months Ended',b'Year Ended')]:
  with pytest.raises(ValueError):parse_release(raw,'CRWV','https://investors.coreweave.com/test','2027-02-02T00:00:00Z')

def test_real_database_observer_reservation_scoring_and_revision(tmp_path):
 """Synthetic future official release in an explicitly isolated test database."""
 import psycopg
 from quant_harness.investment.store import Store
 from quant_harness.investment.review_jobs import Queue
 from quant_harness.investment.company_outcomes import run_tick
 url='postgresql://quant_task8_test@127.0.0.1:55432/quant_task3_task8_test'
 store=Store(url,'TASK8_RESEARCH_ONLY');Queue(store)
 with psycopg.connect(url) as conn:conn.execute('TRUNCATE review_job,investment_run,investment_record CASCADE')
 cfg=deepcopy(POLICY);cfg['research_database']='quant_task3_task8_test'
 # Test role is selected through the explicit test URL adapter, never real DB.
 import quant_harness.investment.company_outcomes as module
 original=module.Store
 class TestStore(Store):
  def __init__(self,provided,strategy):
   assert provided.endswith('/quant_task3_task8_test')
   super().__init__(url,strategy)
 config=tmp_path/'config';config.mkdir();(config/'task8_portfolio.json').write_text(json.dumps(cfg))
 f={'ticker':'CRWV','metric':'quarterly_revenue','unit':'USD_million','period_end':'2026-12-31','sealed_at':'2026-11-13T15:00:00Z','base_value':4800,'bear_value':4100,'bull_value':5100}
 store.put('imported_task7_forecast',f);calls=[]
 def fakefetch(root,url,allowed):
  calls.append(url)
  raw=b'<a href="/news/news-details/2026/Fourth-Quarter-2026/default.aspx">Q4</a>' if len(calls)==1 else release_html()
  import hashlib
  return raw,{'url':url,'sha256':hashlib.sha256(raw).hexdigest(),'observed_at':'2027-02-02T00:00:00Z'}
 from unittest.mock import patch
 with patch.object(module,'Store',TestStore):
  result=run_tick(tmp_path,fetcher=fakefetch,current='2027-02-02T00:00:00Z')
  assert result['requests']==2 and result['companies'][0]['scores'][0]['status']=='MATURE'
  again=run_tick(tmp_path,fetcher=fakefetch,current='2027-02-02T01:00:00Z');assert again['status']=='NOT_DUE' and len(calls)==2
 with psycopg.connect(url) as conn:
  outcome=conn.execute("SELECT payload FROM investment_record WHERE kind='company_forecast_score'").fetchone()[0]
 assert outcome['score']['absolute_error']==100
 # Different body version after normal budget renewal is append-only.
 def revised(root,url,allowed):
  raw,receipt=fakefetch(root,url,allowed)
  if '/news/news-details/' in url:raw=release_html().replace(b'4,900',b'4,800')
  else:raw=b'<a href="/news/news-details/2026/Fourth-Quarter-2026/default.aspx">Q4</a>'
  import hashlib
  receipt.update(sha256=hashlib.sha256(raw).hexdigest(),observed_at='2027-02-03T00:00:00Z');return raw,receipt
 with patch.object(module,'Store',TestStore):run_tick(tmp_path,fetcher=revised,current='2027-02-03T00:00:00Z')
 with psycopg.connect(url) as conn:
  assert conn.execute("SELECT count(*) FROM investment_record WHERE kind='official_company_label'").fetchone()[0]==2
  assert conn.execute("SELECT count(*) FROM review_job WHERE kind='FOLLOWUP'").fetchone()[0]==2

def test_target_to_existing_paper_fill_and_restart(tmp_path):
 """Nonzero synthetic policy target flows through the unchanged real SQL ledger."""
 import os,shutil
 from datetime import datetime,timezone,timedelta
 import pandas as pd,psycopg
 from quant_harness.investment.store import Store
 from quant_harness.investment.shadow_portfolio import seal_shadow,execute_shadow
 from quant_harness.investment.stockpaper import execute,reconcile
 # Dedicated destructive stock-test DB is already used by the existing regression suite.
 url='postgresql://quant_task3@127.0.0.1:55432/quant_task3_stocktest';store=Store(url,'US_STOCKS')
 from quant_harness.investment.stockpaper import initialize
 from quant_harness.investment.equities import settings
 initialize(store,settings(R),'US')
 with psycopg.connect(url) as conn:conn.execute('TRUNCATE stock_nav,stock_fill,stock_position,stock_account,investment_run,investment_record CASCADE')
 (tmp_path/'config').mkdir();shutil.copy2(R/'config/task3_equity_contract.json',tmp_path/'config/task3_equity_contract.json')
 policy=deepcopy(POLICY);policy['market_accounts']['US']='quant_task3_stocktest';(tmp_path/'config/task8_portfolio.json').write_text(json.dumps(policy))
 clock=datetime.now(timezone.utc);at=clock.isoformat();s=signal();s.update(available_at=(clock-timedelta(minutes=1)).isoformat(),valid_until=(clock+timedelta(days=1)).isoformat())
 decision=decide([s],policy,'US',at);prices={'TEST':{'frame':pd.DataFrame({'raw_close':[100.]*20,'volume':[1e7]*20}),'available_at':(clock-timedelta(minutes=1)).isoformat(),'session_close':(clock-timedelta(hours=1)).isoformat(),'source_hash':'a'*64,'meta':{'instrumentType':'EQUITY'}}}
 identity,sealed=seal_shadow(store,tmp_path,decision,prices,'SYNTHETIC_TEST_CATALOG')
 changed=deepcopy(policy);changed['max_turnover']=.3
 (tmp_path/'config/task8_portfolio.json').write_text(json.dumps(changed))
 assert execute_shadow(store,tmp_path,identity,[])['status']=='HOLD_ONLY'
 (tmp_path/'config/task8_portfolio.json').write_text(json.dumps(policy))
 # Reset the synthetic fixture only, to test a newly sealed eligible request.
 with psycopg.connect(url) as conn:conn.execute('TRUNCATE stock_nav,stock_fill,stock_position,stock_account,investment_run,investment_record CASCADE')
 identity,sealed=seal_shadow(store,tmp_path,decision,prices,'SYNTHETIC_TEST_RESEAL')
 moment=datetime.fromisoformat(sealed['sealed_at']);event={'symbol':'TEST','asset_type':'EQUITY','currency':'USD','price':100,'event_at':(moment+timedelta(seconds=1)).isoformat(),'available_at':(moment+timedelta(seconds=2)).isoformat(),'session_open':moment.isoformat(),'session_close':(moment+timedelta(hours=1)).isoformat(),'source':'YAHOO_CHART_OBSERVED'}
 result=execute_shadow(store,tmp_path,identity,[event],current=(moment+timedelta(seconds=3)).isoformat());assert result['status']=='COMPLETE'
 assert execute_shadow(Store(url,'US_STOCKS'),tmp_path,identity,[],current=(moment+timedelta(seconds=4)).isoformat())['idempotent']
 with psycopg.connect(url) as conn:
  assert reconcile(conn)
  assert conn.execute('SELECT quantity FROM stock_position WHERE symbol=\'TEST\'').fetchone()[0]==100
  assert conn.execute('SELECT count(*) FROM stock_fill').fetchone()[0]==1
 bad=deepcopy(decision);bad['weights']={'TEST':.2}
 with pytest.raises(ValueError,match='immutable'):seal_shadow(store,tmp_path,bad,prices,'fixture')
