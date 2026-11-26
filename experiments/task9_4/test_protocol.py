from pathlib import Path
import sys,json,importlib.util
import pandas as pd
import pytest
sys.path.insert(0,str(Path(__file__).parent))
from protocol import choose_observation
s=importlib.util.spec_from_file_location('static_mix_test',Path(__file__).parents[1]/'task9_value/evaluate.py');ev=importlib.util.module_from_spec(s);s.loader.exec_module(ev)

def test_price_conflict_is_not_averaged_or_filled():
 v,proof=choose_observation({'YAHOO':100.,'NAVER':1000.,'TOSS':1000.});assert v==1000 and proof['pair']==['TOSS','NAVER']
 assert choose_observation({'YAHOO':100.,'TOSS':200.})[0] is None
 assert choose_observation({'YAHOO':100.})[0] is None

def test_unknown_or_zero_prices_fail_closed():
 assert choose_observation({'YAHOO':0.,'NAVER':0.})[0] is None
 assert choose_observation({'YAHOO':float('nan'),'NAVER':100.})[0] is None

def test_missing_slot_cash_without_reweighting_and_cost_funding():
 ds=pd.to_datetime(['2026-05-18','2026-06-18']);path=pd.Series([1.,1.3],index=ds);index=pd.Series([1.,1.1],index=ds)
 result,_=ev.mix({'A':path},{'A':1/3},index,6,6);assert abs(result['gross_price_return']-.1)<1e-10;assert abs(result['cash_target']-2/3)<1e-10;assert result['net_price_return']<.1

def test_lost_terminal_mark_does_not_get_interpolated():
 ds=pd.to_datetime(['2026-05-18','2026-06-18']);index=pd.Series([1.,1.1],index=ds)
 with pytest.raises(ValueError):ev.mix({'A':pd.Series([1.],index=ds[:1])},{'A':1/3},index,6,6)

def test_all_model_inputs_exclude_post_cutoff_sources_and_no_trading_directive():
 b=Path(__file__).resolve().parents[2]/'runtime/task9_4'
 for m in ['US','KR']:
  request=json.loads((b/'requests'/('final_'+m+'.request.json')).read_text());view=json.loads(request['messages'][1]['content'])
  assert 'No buy/sell/weight/entry/exit' in request['messages'][0]['content']
  for d in view['sources']:assert d['published']<'2026-05-15'
  for d in view['deeper_packets']:
   for g in d['numeric_groups'].values():assert g[3]<'2026-05-15'
   if 'asof_price' in d:assert d['asof_price']['date']=='2026-05-15' and not d['asof_price']['futurepricesqueried']

def test_both_sealed_research_and_comparator_assets_remain_immutable():
 from protocol import research_seal,asset_list
 z=research_seal();assets=asset_list();assert len(z['markets'])==2;assert {a['symbol'] for a in assets if a['role']=='selected'}=={'AIR','ETN','GEV','010120.KS','003230.KS','281820.KS'}

def test_ita_verified_split_changes_quantity_not_economic_value():
 b=Path(__file__).resolve().parents[2]/'runtime/task9_4';f=b/'evaluator_only/ITA';z=json.loads((f/'resolution_v2.json').read_text());assert z['action']=={'date':'2026-11-05','quantity_multiplier':3}
 df=pd.read_csv(f/'bars_v2.csv').set_index('date');r=3*df.loc['2026-11-13','close']/df.loc['2026-05-18','open']-1
 result=next(x for x in json.loads((b/'evaluation_v2/asset_returns.json').read_text()) if x['symbol']=='ITA' and x['horizon']=='6m');assert abs(result['price_return']-r)<1e-12
 # Initially blocked result remains, rather than overwritten as a prior success.
 assert next(x for x in json.loads((b/'evaluation/asset_returns.json').read_text()) if x['symbol']=='ITA' and x['horizon']=='6m')['status']=='BLOCKED_PRICE'

def test_final_primary_metric_and_expected_period_are_not_replaced_by_guidance():
 b=Path(__file__).resolve().parents[2]/'runtime/task9_4';rows=json.loads((b/'evaluation_v2/hypothesis_scores.json').read_text());assert len(rows)==6
 for x in rows:assert x['actual']['published']<='2026-11-13';assert x['sealed_prediction']['period_end']<x['actual']['published']
 assert next(x for x in rows if x['symbol']=='GEV')['actual']['value']==122
 assert next(x for x in rows if x['symbol']=='AIR')['actual']['value']==13
 assert next(x for x in rows if x['symbol']=='281820.KS')['actual']['value']==pytest.approx(1141.86690295)

def test_no_model_call_after_the_both_market_seal():
 import datetime
 b=Path(__file__).resolve().parents[2]/'runtime/task9_4';seal=json.loads((b/'research_seal.json').read_text());time=datetime.datetime.fromisoformat(seal['created_UTC']).timestamp();records=[json.loads(p.read_text()) for p in (b/'model_calls/research').glob('*.reserved.json')];assert len(records)==8
 assert all(r['at']+r.get('elapsed_seconds',0)<time for r in records);assert sum(r.get('measured_tokens',0) for r in records)<=550000
