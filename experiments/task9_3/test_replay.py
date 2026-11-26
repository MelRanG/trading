from pathlib import Path
import sys,json
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src'))
import pandas as pd
from quant_harness.investment.research import replay_targets
from quant_harness.v77_corrected_price_allocation.engine import ExecutionSpec

def sample():
 dates=['2026-05-15','2026-05-18','2026-05-19','2026-05-20'];p=pd.DataFrame({'A':[100.,100.,150.,200.]},index=dates)
 panel={'open':p,'close':p,'adv20_d1':p*100000};ledger=pd.DataFrame({'target_weights_json':[json.dumps({'A':.5})]*3})
 return panel,dates[1:],ledger,ExecutionSpec(0,0,0,0,0,.01,1)
def test_no_target_drift_rebalance_on_hold_days():
 p,d,l,s=sample();a,f,_=replay_targets(p,d,l,1000,s,rebalance_dates={d[0]});assert len(f)==1;assert a.iloc[-1].nav_krw==1500;assert json.loads(a.iloc[-1].holdings_json)=={'A':5}
def test_existing_default_behavior_unchanged():
 p,d,l,s=sample();a,f,_=replay_targets(p,d,l,1000,s);assert len(f)>1

def test_sale_only_on_next_registered_session():
 p,d,l,s=sample();l.iloc[2,0]='{}';a,f,_=replay_targets(p,d,l,1000,s,rebalance_dates={d[0],d[2]});assert f.iloc[-1]['date']==d[2];assert f.iloc[-1]['side']=='SELL';assert a.iloc[-1].cash_krw==1500

def test_missing_held_mark_remains_null_not_carried_forward():
 p,d,l,s=sample();p['close']=p['close'].copy();p['close'].loc[d[1],'A']=float('nan');a,f,_=replay_targets(p,d,l,1000,s,rebalance_dates={d[0]},allow_unpriced_hold=True);assert pd.isna(a.iloc[1].nav_krw);assert a.iloc[-1].nav_krw==1500;assert len(f)==1

def test_unpriced_previous_cannot_rebalance():
 p,d,l,s=sample();p['close']=p['close'].copy();p['close'].loc[d[1],'A']=float('nan');l.iloc[2,0]='{}';a,f,i=replay_targets(p,d,l,1000,s,rebalance_dates={d[0],d[2]},allow_unpriced_hold=True);assert len(f)==1;assert i.iloc[-1]['reason']=='HOLD_ONLY_MISSING_D1_MARK'

def test_close_stop_can_only_fill_following_open():
 import importlib.util
 pth=Path(__file__).with_name('evaluate.py');sys.path.insert(0,str(pth.parent));sp=importlib.util.spec_from_file_location('task93_eval_test',pth);ev=importlib.util.module_from_spec(sp);sp.loader.exec_module(ev)
 dates=['2026-05-18','2026-05-19','2026-05-20'];ix=['2026-05-15']+dates
 panel={'open':pd.DataFrame({'A':[100.,100.,100.,60.]},index=ix),'close':pd.DataFrame({'A':[100.,100.,70.,60.]},index=ix),'adv20_d1':pd.DataFrame({'A':[1e8]*4},index=ix)}
 decision={'asof':'2026-05-15','cases':[{'symbol':'A','weight':.25,'entry_price_ceiling':None}],'selection_top3':['A']}
 spec=ExecutionSpec(0,0,0,0,0,.01,1);ledger,rebalance,journal=ev.plan('US','POLICY',[decision],panel,dates,spec);a,f,_=replay_targets(panel,dates,ledger,100000,spec,rebalance_dates=rebalance,allow_unpriced_hold=True)
 assert f.iloc[-1]['date']=='2026-05-20' and f.iloc[-1]['side']=='SELL';assert not any((r['side']=='SELL' and r['date']=='2026-05-19') for r in f.to_dict('records'));assert a.iloc[-1].nav_krw==90000

def test_entry_ceiling_does_not_force_a_fill():
 import importlib.util
 pth=Path(__file__).with_name('evaluate.py');sys.path.insert(0,str(pth.parent));sp=importlib.util.spec_from_file_location('task93_eval_limit_test',pth);ev=importlib.util.module_from_spec(sp);sp.loader.exec_module(ev)
 p,d,l,s=sample();decision={'asof':'2026-05-15','cases':[{'symbol':'A','weight':.25,'entry_price_ceiling':90}],'selection_top3':['A']};ledger,dates,j=ev.plan('US','POLICY',[decision],p,d,s);a,f,_=replay_targets(p,d,ledger,1000,s,rebalance_dates=dates,allow_unpriced_hold=True);assert f.empty and a.iloc[-1].nav_krw==1000

def test_missing_adv_records_unfilled_order_without_inventing_liquidity():
 p,d,l,s=sample();p['adv20_d1']=p['adv20_d1'].copy();p['adv20_d1'].loc[d[0],'A']=float('nan');a,f,i=replay_targets(p,d,l,1000,s,rebalance_dates={d[0]},allow_unpriced_hold=True);assert f.empty;assert a.iloc[-1].cash_krw==1000;assert i.iloc[0]['reason']=='HOLD_ONLY_MISSING_OPEN_OR_ADV'
