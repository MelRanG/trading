from pathlib import Path
import sys,json,hashlib,copy,importlib.util
import pytest
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'));sys.path.insert(0,str(Path(__file__).parent))
from common import B,sha
from quant_harness.investment.financial_packet import verify_fact,research_state,model_numeric_view,score_financial_forecast
from quant_harness.investment import research_dispatcher as d

def example():
 p=B/'historical_numeric_packet.json';x=json.loads(p.read_text());f=x['cases'][0]['verified_facts'][0];return copy.deepcopy(f),(R/f['source_path']).read_bytes()

def test_exact_amount_unit_period_and_source():
 f,raw=example();assert verify_fact(f,raw,'2025-06-30')['value']=='2236436000'
 f['value']='2236436'
 with pytest.raises(ValueError,match='normalization'):verify_fact(f,raw,'2025-06-30')

def test_future_publication_rejected():
 f,raw=example()
 with pytest.raises(ValueError,match='future'):verify_fact(f,raw,'2025-04-01')

def test_wrong_hash_and_quote_rejected():
 f,raw=example()
 with pytest.raises(ValueError,match='hash'):verify_fact(f,raw+b'changed','2025-06-30')
 f['locator']['start']+=1
 with pytest.raises(ValueError,match='quote'):verify_fact(f,raw,'2025-06-30')

def test_eps_currency_unit_is_not_revenue():
 f,raw=example();f['metric']='ifrs-full_BasicEarningsLossPerShare'
 with pytest.raises(ValueError,match='EPS requires'):verify_fact(f,raw,'2025-06-30')

def test_rank_never_implies_eligible_and_wait_reasons_differ():
 assert research_state(numeric_complete=False,valuation_complete=True,price_verified=True,entry_met=True,attractive=True,rank=1)=='RESEARCH_INCOMPLETE'
 assert research_state(numeric_complete=True,valuation_complete=True,price_verified=True,entry_met=True,attractive=False)=='UNATTRACTIVE'
 assert research_state(numeric_complete=True,valuation_complete=True,price_verified=True,entry_met=False,attractive=True)=='WATCH'

def test_numeric_view_never_drops_capital_facts():
 x=json.loads((B/'historical_numeric_packet_v3.json').read_text());facts=x['cases'][1]['annual_verified_facts'];view=model_numeric_view(facts);assert len(view)==len(facts)
 assert [(f['value'],f['source_hash'],f['period_end']) for f in facts]==[(f['value'],f['source_hash'],f['period_end']) for f in view]

def test_inclusive_cf_periods_and_missing_actual_pending():
 f,raw=example();forecast={k:f[k] for k in ['metric','unit','currency','basis','period_end']};forecast.update(value=2e9,sealed_at='2025-01-01T00:00:00Z')
 assert score_financial_forecast(forecast,None,None,'2025-06-30')['status']=='PENDING'
 assert score_financial_forecast(forecast,f,raw,'2025-06-30')['status']=='MATURE'
 forecast['basis']='SFS'
 with pytest.raises(ValueError,match='accounting'):score_financial_forecast(forecast,f,raw,'2025-06-30')

def test_price_loss_does_not_prove_forecast_failure():
 dec={'sealed_at':'2026-11-15T00:00:00+09:00'};e={'A':{'event_at':'2026-11-16T09:00:01+09:00','price':80}}
 assert d.classify_observation(dec,e)['cause']=='UNDETERMINED'
 e['A']['event_at']='2026-11-13T15:00:00+09:00'
 with pytest.raises(ValueError,match='preseal'):d.classify_observation(dec,e)

def test_factory_block_does_not_execute_or_bypass(monkeypatch):
 def block(*a,**k):raise ValueError('Factory daily proposal budget exhausted')
 monkeypatch.setattr(d,'register_review_proposal',block);monkeypatch.setattr(d,'evaluate_numeric_bundle',lambda *a:pytest.fail('must not execute'))
 bundle={'asof':'2025-06-30','cases':[]};proposal={'worker_hash':d.worker_hash(),'input_hash':d.digest(bundle)};r=d.factory_work(R,proposal,bundle);assert r['status']=='BLOCKED' and not r['experiment_executed']

def test_numeric_source_path_escape_fails_closed():
 bundle={'asof':'2025-06-30','cases':[{'symbol':'X','facts':[{'source_path':'../../etc/passwd'}]}]}
 with pytest.raises(ValueError,match='outside'):d.evaluate_numeric_bundle(R,bundle)

def test_actual_historical_and_current_numeric_sources_verify():
 for name in ['historical_numeric_packet_v3.json','current_numeric_packet_v2.json']:
  x=json.loads((B/name).read_text())
  for c in x['cases']:
   for f in c.get('verified_facts',[])+c.get('annual_verified_facts',[]):verify_fact(f,(R/f['source_path']).read_bytes(),x['asof'])

def test_typed_native_bridge_uses_future_stub_and_no_double_debt():
 from value_check import timed_value
 x=json.loads((B/'model_outputs/current_timing.json').read_text())
 for c in x['cases']:
  for s in c['scenarios']:
   r=timed_value(x['asof'],s);assert r['first_stub_years']>0
   expected=r['EV_conditional']-s['debt']+s['cash']-s['other_claims'];assert abs(r['equity_conditional']-expected)<max(1,abs(expected)*1e-10)
   assert r['dilution_plus5pct_value']<r['value_per_share_conditional'] if r['value_per_share_conditional']>0 else r['dilution_plus5pct_value']>=r['value_per_share_conditional']

def test_future_cf_before_asof_rejected():
 from value_check import timed_value
 x=json.loads((B/'model_outputs/current_timing.json').read_text());s=x['cases'][0]['scenarios'][0];s['cashflows'][0]['end_date']='2026-01-01'
 with pytest.raises(AssertionError):timed_value(x['asof'],s)

def test_isolated_factory_native_worker_executes_once_and_keeps_minimum(tmp_path):
 from quant_harness.investment.exploration import research_store
 # Reuse real frozen bundle/proposal read-only; only the temporary registry mutates.
 store,_=research_store(R);manifest=json.loads((B/'dispatch_registry.json').read_text());proposal=store.get(manifest['proposal_id']);bundle=store.get(manifest['bundle_id'])
 first=d.factory_work(R,proposal,bundle,directory=tmp_path/'factory');assert first['experiment_executed']
 assert first['status']=='INSUFFICIENT_EVIDENCE';assert first['record']['result']['verified_numeric_facts']==88;assert not first['record']['result']['failures']
 second=d.factory_work(R,proposal,bundle,directory=tmp_path/'factory');assert not second['experiment_executed'] and second['cached_result']

def test_dated_filing_poll_excludes_preseal_and_future_notices(tmp_path,monkeypatch):
 monkeypatch.setattr(d,'reserve',lambda *a:None)
 class Dart:
  def _request(self,*a,**kw):return {'list':[{'rcept_dt':'20261115','rcept_no':'same_day'},{'rcept_dt':'20261116','rcept_no':'new'},{'rcept_dt':'20261117','rcept_no':'future'}]}
 decision={'market':'KR','sealed_at':'2026-11-15T00:15:00+09:00','issuer_codes':{'003230.KS':'00126955'}}
 result=d.poll_filings(tmp_path,None,{'daily_provider_calls':12},decision,'2026-11-16T09:01:00+09:00',Dart());assert [r['rcept_no'] for r in result['issuers'][0]['new_filings']]==['new']

def test_active_monitor_never_routes_nontradable_index_to_stock_quote(tmp_path,monkeypatch):
 import contextlib,psycopg
 manifest={'decision_ids':['D'],'proposal_id':'P','bundle_id':'B'};manifest['registry_hash']=d.digest(manifest);folder=tmp_path/'runtime/task9_2';folder.mkdir(parents=True);(folder/'dispatch_registry.json').write_text(json.dumps(manifest))
 class Store:
  url='fake_research_connection'
  def lock(self):return contextlib.nullcontext()
  def get(self,key):return {'sealed_at':'2026-11-15T00:00:00+09:00','market':'US','symbols':['PH','DECK'],'benchmark_symbol':'^GSPC'} if key=='D' else {}
  def put(self,kind,payload):return kind
 class Queue:
  def __init__(self,s):self.jobs={}
  def enqueue(self,kind,payload):self.jobs[kind]=payload;return kind
  def claim(self,owner,lease,job):return None if job=='TASK92_FACTORY_NUMERIC_AUDIT' else {'payload':self.jobs[job]}
  def finish(self,*args):pass
  def fail(self,*args):pytest.fail('unexpected monitor failure')
 class Conn:
  def __enter__(self):return self
  def __exit__(self,*a):pass
  def execute(self,*a):return self
  def fetchall(self):return []
 monkeypatch.setattr(d,'research_store',lambda root:(Store(),{}));monkeypatch.setattr(d,'Queue',Queue);monkeypatch.setattr(psycopg,'connect',lambda *a,**k:Conn())
 session={'day':'2026-11-16','opening':'2026-11-16T09:00:00+09:00','closing':'2026-11-16T16:00:00+09:00'};monkeypatch.setattr(d,'official_sessions',lambda *a:[session]);seen=[]
 def provider(root,store,cfg,client,stage,path,query,limit):seen.append(query['symbols']);return {},{}
 monkeypatch.setattr(d,'provider_call',provider);monkeypatch.setattr(d,'quote_events',lambda raw,r,m,names,*a:{s:{'event_at':'2026-11-16T09:01:00+09:00','price':100} for s in names});monkeypatch.setattr(d,'poll_filings',lambda *a:{'status':'UNSUPPORTED_US_FINANCIAL_FEED'})
 from types import SimpleNamespace
 out=d.run_tick(tmp_path,current='2026-11-16T09:01:01+09:00',client=SimpleNamespace(endpoint_map=SimpleNamespace(quote_path='/stock-quotes')))
 assert seen==['DECK,PH'];assert out['broker_mutations']==0
 assert out['results'][0]['benchmark_status']=='PENDING_SEPARATE_NONTRADABLE_INDEX_ADAPTER'
