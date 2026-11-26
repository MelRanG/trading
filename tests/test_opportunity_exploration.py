"""Real SQL + synthetic market fixtures. No fixture is Forward investment evidence."""
from pathlib import Path
from copy import deepcopy
from types import SimpleNamespace
import json,hashlib
import pytest
from quant_harness.investment.opportunity import value_scenario,probe_plan
from quant_harness.investment.exploration import checkpoint_result,quote_events,account_store
R=Path(__file__).resolve().parents[1]
CFG=json.loads((R/'config/task8b_exploration.json').read_text())

def test_eps_equity_and_projected_ev_bridge():
 s={'years':3,'scenario':'base','method':'EPS_PE','future_diluted_eps':5,'exit_multiple':20,'discount_rate':.1,'assumptions':'Synthetic sensitivity, not forecast'}
 v=value_scenario(s,80);assert v['future_price']==100 and v['probability'] is None
 s.update(method='FCFF_MULTIPLE',revenue_million=1000,fcff_margin=.1,exit_multiple=20,debt_million=1000,cash_million=100,other_claims_million=100,shares_million=100,dilution_per_year=.1)
 v=value_scenario(s,10);assert v['enterprise_value_million']==2000 and v['equity_value_million']==1000 and v['future_price']==pytest.approx(1000/133.1)
 s['debt_million']=3000;v=value_scenario(s,10);assert v['future_price']==0 and v['equity_impaired']
 s['fcff_margin']=0;assert value_scenario(s,10)['status']=='NOT_VALUABLE_WITH_POSITIVE_FCFF_MULTIPLE'
 s['fcff_margin']=.1;s['cash_million']=None
 with pytest.raises(ValueError):value_scenario(s,10)

def test_source_and_research_permission_not_paper_authority():
 c={'ticker':'TEST','market':'US','sector':'fixture','status':'RESEARCH_SHADOW','listing_verified':True,'source_hashes':['a'*64],'falsification':['Source-verified test condition'],'bull_thesis':'Synthetic bull','bear_thesis':'Synthetic bear','entry_rule':{'trigger':'NEXT_REGULAR_QUOTE'},'current_price':100}
 assert probe_plan(c,CFG)['weight']==.025
 c['entry_rule']['trigger']='AFTER_EVENT_REVIEW';assert not probe_plan(c,CFG)['eligible_for_probe']
 c['status']='PAPER_ELIGIBLE'
 with pytest.raises(ValueError,match='official'):probe_plan(c,CFG)
 cfg=deepcopy(CFG);cfg['market_accounts']['US']='quant_task3_us'
 with pytest.raises(ValueError,match='separate'):account_store(cfg,'US')

def test_exact_session_horizon_and_corporate_action_pending():
 entry={'initial_capital':100000,'benchmark_entry':{'price':100}}
 assert checkpoint_result(entry,[],21,[21,63,126])['status']=='PENDING'
 marks=[{'nav':105000,'benchmark_price':102,'completed_sessions':21,'corporate_actions_verified':False}]
 assert checkpoint_result(entry,marks,21,[21,63,126])['reason']=='CORPORATE_ACTIONS_NOT_INDEPENDENTLY_VERIFIED'
 marks[0]['corporate_actions_verified']=True;r=checkpoint_result(entry,marks,21,[21,63,126]);assert r['labels']['21']['net_return']==pytest.approx(.05) and r['labels']['63']['status']=='PENDING'
 marks[0]['completed_sessions']=22;assert checkpoint_result(entry,marks,22,[21])['labels']['21']['status']=='PENDING'

def test_quote_clock_currency_and_regular_boundaries():
 raw={'result':[{'symbol':'TEST','currency':'USD','lastPrice':'100','timestamp':'2026-11-16T14:31:08Z'}]};receipt={'available_at':'2026-11-16T14:31:10Z','source_hash':'a'*64};session={'opening':'2026-11-16T14:30:00Z','closing':'2026-11-16T21:00:00Z'}
 assert quote_events(raw,receipt,'US',['TEST'],session,'2026-11-16T14:31:00Z','2026-11-16T14:31:10Z')['TEST']['price']==100
 for field,value in [('timestamp','2026-11-16T14:30:00Z'),('currency','KRW'),('lastPrice','nan')]:
  bad=deepcopy(raw);bad['result'][0][field]=value
  with pytest.raises(ValueError):quote_events(bad,receipt,'US',['TEST'],session,'2026-11-16T14:31:00Z','2026-11-16T14:31:10Z')

def test_real_sql_entry_postcommit_recovery_marks_and_horizon_exit(tmp_path,monkeypatch):
 import psycopg,pandas as pd,shutil
 from quant_harness.investment import exploration as e,stockpaper
 from quant_harness.investment.store import Store
 from quant_harness.investment.review_jobs import Queue
 from quant_harness.investment.equities import settings
 from quant_harness.investment.research import digest
 research=Store('postgresql://quant_task8b_test@127.0.0.1:55432/quant_task3_task8b_test','TASK8B_RESEARCH_ONLY');Queue(research)
 with psycopg.connect(research.url) as conn:
  conn.execute(e.DDL);conn.execute('TRUNCATE review_job,investment_run,investment_record,exploration_budget CASCADE')
 paper=Store('postgresql://quant_task3@127.0.0.1:55432/quant_task3_stocktest','US_STOCKS');stockpaper.initialize(paper,settings(R),'US')
 with psycopg.connect(paper.url) as conn:conn.execute('TRUNCATE stock_nav,stock_fill,stock_position,stock_account,investment_run,investment_record CASCADE')
 (tmp_path/'config').mkdir();shutil.copy2(R/'config/task3_equity_contract.json',tmp_path/'config/task3_equity_contract.json')
 cfg=deepcopy(CFG);monkeypatch.setattr(e,'research_store',lambda root:(research,cfg));monkeypatch.setattr(e,'account_store',lambda c,m:paper);clock=['2026-11-16T14:31:10Z'];monkeypatch.setattr(e,'now',lambda:clock[0]);monkeypatch.setattr(stockpaper,'now',lambda:'2026-11-16T14:30:00Z')
 sessions=[{'day':'2026-11-16','opening':'2026-11-16T14:30:00Z','closing':'2026-11-16T21:00:00Z'},{'day':'2026-11-17','opening':'2026-11-17T14:30:00Z','closing':'2026-11-17T21:00:00Z'}];monkeypatch.setattr(e,'official_sessions',lambda m,c:sessions)
 analysis={'status':'CANDIDATES','weights':{'TEST':.025},'execution_eligible':True,'prior_marks':{'TEST':100},'adv20_d1':{'TEST':1e9},'strategy_id':'SYNTHETIC_EXPLORATION_FIXTURE','input_hash':'fixture','reason':'SYNTHETIC_NOT_FORWARD'}
 identity,sealed=stockpaper.seal(paper,tmp_path,'US',analysis,{'TEST':{'meta':{'instrumentType':'EQUITY'}}},'fixture')
 plan={'market':'US','weights':{'TEST':.025},'paper_decision_id':identity,'benchmark':'SPY','exploration_policy_hash':digest(cfg),'worker_hash':hashlib.sha256(Path(e.__file__).read_bytes()).hexdigest(),'catalog_id':'fixture','sectors':{'TEST':'FIXTURE'}};plan_id=research.put('exploration_plan',plan)
 calls=[]
 class Client:
  endpoint_map=SimpleNamespace(quote_path='/quotes',candles_path='/candles')
  def _request(self,method,path,query):
   calls.append((path,query))
   if path=='/quotes':
    day=clock[0][:10];return {'result':[{'symbol':s,'currency':'USD','lastPrice':str(100 if day.endswith('16') and s=='TEST' else 110 if s=='TEST' else 200 if day.endswith('16') else 205),'timestamp':day+'T14:31:08Z'} for s in query['symbols'].split(',')]}
   symbol=query['symbol'];days=pd.bdate_range(end='2026-11-16',periods=int(query['count']));value=110 if symbol=='TEST' else 205
   return {'result':[{'timestamp':d.strftime('%Y-%m-%d')+'T21:00:00Z','currency':'USD','openPrice':value,'highPrice':value+1,'lowPrice':value-1,'closePrice':value,'volume':1000000} for d in days]}
 client=Client();r=e.run_tick(tmp_path,client=client,current=clock[0]);assert r['markets'][0]['status']=='ENTERED_EXPLORATORY_ONLY'
 with psycopg.connect(paper.url) as conn:assert conn.execute('SELECT count(*) FROM stock_fill').fetchone()[0]==1
 # Simulate process death AFTER account commit but BEFORE research entry receipt.
 with psycopg.connect(research.url) as conn:conn.execute('DELETE FROM investment_record WHERE record_id=%s',(plan_id+':entry',))
 count=len(calls);r=e.run_tick(tmp_path,client=client,current=clock[0]);assert any(x['status']=='POSTCOMMIT_ENTRY_RECOVERED_NO_NEW_FILL' for x in r['markets']);assert len(calls)==count
 clock[0]='2026-11-16T21:06:00Z';monkeypatch.setattr(e,'_count_sessions',lambda *args:1);r=e.run_tick(tmp_path,client=client,current=clock[0]);assert r['markets'][0]['status']=='MARKED'
 with psycopg.connect(research.url) as conn:
  mark=conn.execute("SELECT payload FROM investment_record WHERE kind='exploration_mark'").fetchone()[0]
 assert mark['nav']>100000 and not mark['corporate_actions_verified']
 # Registered horizon due is a synthetic control marker, NOT126 elapsed real sessions.
 mark['completed_sessions']=126;research.put('exploration_mark',mark,plan_id+':synthetic_due')
 clock[0]='2026-11-17T14:31:10Z';monkeypatch.setattr(stockpaper,'now',lambda:'2026-11-17T14:30:00Z');r=e.run_tick(tmp_path,client=client,current=clock[0]);assert r['markets'][0]['status']=='CLOSED'
 with psycopg.connect(paper.url) as conn:
  assert stockpaper.reconcile(conn);assert conn.execute('SELECT count(*) FROM stock_fill').fetchone()[0]==2;assert conn.execute('SELECT sum(quantity) FROM stock_position').fetchone()[0]==0
 assert e.run_tick(tmp_path,client=client,current=clock[0])['markets'][0]['status']=='CLOSED'


def test_exploration_caps_are_stricter_than_unchanged_paper_caps():
 from quant_harness.investment.exploration import exposure_guard
 from quant_harness.investment.equities import settings
 decision={'market':'US','opening_positions':{},'opening_cash':'100000','intents':[{'symbol':'TEST','delta_quantity':'25'}]}
 assert exposure_guard(decision,{'TEST':{'price':100}},CFG,settings(R),{'TEST':'fixture'})['TEST']<.026
 with pytest.raises(ValueError,match='name cap'):exposure_guard(decision,{'TEST':{'price':300}},CFG,settings(R),{'TEST':'fixture'})

def test_nvda_official_newsroom_source_repair_is_issuer_specific():
 from quant_harness.investment.company_outcomes import parse_release,ISSUER_HOSTS,INDEX
 assert INDEX['NVDA']=='https://nvidianews.nvidia.com/news'
 assert 'nvidianews.nvidia.com' in ISSUER_HOSTS['NVDA']
 raw=b'<meta property="article:published_time" content="2026-11-17T21:20:00Z"><h1>Third Quarter Fiscal 2027</h1><p>USD in millions</p><table><tr><th>Three Months Ended</th></tr><tr><th></th><th>October 25, 2026</th></tr><tr><td>Revenue</td><td>108,500</td></tr></table>'
 label=parse_release(raw,'NVDA','https://nvidianews.nvidia.com/news/test','2026-11-17T21:21:00Z');assert label['actual']==108500
 with pytest.raises(ValueError,match='identity'):parse_release(raw,'NVDA','https://investors.coreweave.com/test','2026-11-17T21:21:00Z')


def test_cash_control_is_exposure_matched_and_costs_remain_separate():
 from quant_harness.investment.exploration_evaluation import matched_metrics
 r=matched_metrics(100000,.10,104000,1000,100,120)
 assert r['benchmark_full_price_return']==pytest.approx(.20)
 assert r['benchmark_capital_matched_gross_return']==pytest.approx(.02)
 assert r['portfolio_gross_before_recorded_cost']==pytest.approx(.05)
 assert r['gross_selection_difference']==pytest.approx(.03)
 assert r['recorded_cost_drag']==.01 and r['investment_alpha_proven'] is False
