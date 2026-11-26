from common import *
import importlib.util,pandas as pd,numpy as np
spec=importlib.util.spec_from_file_location('selected_evaluator',R/'experiments/task9_1/evaluate.py');ev=importlib.util.module_from_spec(spec);spec.loader.exec_module(ev)
spec=importlib.util.spec_from_file_location('endpoint_reuse',R/'experiments/task9_1/evaluate_endpoint.py');ep=importlib.util.module_from_spec(spec);spec.loader.exec_module(ep)
from quant_harness.investment.portfolio import aggregate
W=Path('/home/ansy/app/quant-diligence/task9-1-work');W=W if (W/'allocation_selected.json').exists() else B/'model_outputs';raw=W/'allocation_selected.json';answer=json.loads(raw.read_text());date='2025-06-30';foundation=json.loads((B/'model_inputs'/date/'foundation.json').read_text());assert answer['foundation_hash']==digest(foundation);assert answer['asof']==foundation['asof'];assert answer['promotion']=='NONE'
rows=[];policies=[]
for market,index in [('US','^GSPC'),('KR','^KS11')]:
 seal=json.loads((B/'decisions'/(date+'_market.json')).read_text());basket=next(p['ranked_top3'] for p in seal['decision']['portfolios'] if p['market']==market);port=next(p for p in answer['portfolios'] if p['market']==market);assert port['selected_basket']==basket;assert set(port['weights'])<=set(basket);assert all(0<=v<=.2 for v in port['weights'].values());assert sum(port['weights'].values())<=.6+1e-9
 returns=pd.concat([pd.read_csv(B/'inputs'/date/s/'bars.csv').set_index('date').close.pct_change().rename(s) for s in basket],axis=1).dropna().tail(63);assert len(returns)>=60;iv=ev.vibe.inverse_variance_weights(returns.cov().to_numpy())
 arms={'SELECTED_EQUAL100':{s:1/3 for s in basket},'SELECTED_FIXED60':{s:.2 for s in basket},'SELECTED_VIBE_IVP60':{s:min(.2,.6*float(w)) for s,w in zip(basket,iv)},'SELECTED_AI':{s:v for s,v in port['weights'].items() if v>0}}
 for label,weights in arms.items():
  preview=aggregate([{'capital_fraction':1,'weights':weights}],gross_cap=.6,single_name_cap=.2,sector_caps={'UNVERIFIED':.6},sectors={s:'UNVERIFIED' for s in basket});policies.append({'market':market,'arm':label,'basket':basket,'weights':weights,'QH_preview':preview,'cash_reason':port['cash_reason'] if label=='SELECTED_AI' else 'PREREGISTERED_RESEARCH_CONTROL','not_actual_paper':True})
 indexbars,bad=ev.valid_prices(pd.read_csv(B/'evaluator_only'/date/index/'bars.csv'))
 for months in [3,6,12]:
  a,z=ev.window(indexbars.index,date,months);ds=indexbars.loc[a:z].index if market=='US' else pd.DatetimeIndex([a,z]);bench=indexbars.loc[ds,'close']/float(indexbars.loc[a,'open']);bench.loc[z]=float(indexbars.loc[z,'open']/indexbars.loc[a,'open'])
  if market=='US':bench.loc[a-pd.Timedelta(seconds=1)]=1;bench=bench.sort_index()
  else:bench.loc[a]=1.
  paths={};errors={}
  for s in basket:
   try:
    if market=='US':paths[s],note=ev.path_for(date,s,a,z,ds)
    else:r,note=ep.endpoints(date,s,a,z);paths[s]=pd.Series([1.,r],index=ds)
   except Exception as exc:errors[s]=str(exc)
  for label,w in arms.items():
   base={'date':date,'market':market,'months':months,'arm':label,'fixed_selected_basket':basket,'post_readout_allocation_call':'Outcome-blinded model; operator knew historical readout, diagnostic only','errors':{s:errors[s] for s in w if s in errors}}
   try:
    if w:metric,nav=ev.mix(paths,w,bench,6.5 if market=='KR' else 6,29.5 if market=='KR' else 6)
    else:metric,nav=ev.mix({'CASH':pd.Series(1.,index=bench.index)},{'CASH':0},bench,0,0);metric['positions']={}
    if market=='KR':metric.update(mdd_observed_marks=None,sharpe_rf0_diagnostic=None,missing_index_marks=None)
    base.update(status='CALCULATED_PARTIAL' if market=='US' else 'CALCULATED_ENDPOINT_PARTIAL',**metric)
   except Exception as exc:base.update(status='BLOCKED',reason=str(exc))
   rows.append(base)
reservations=[json.loads(p.read_text()) for p in (B/'model_calls/allocation').glob('*.reserved.json')];assert len(reservations)==1 and reservations[0]['status']=='SUCCEEDED'
freeze(B/'selected_allocation_seal.json',{'output_sha256':sha(raw),'request_sha256':sha(W/'allocation_selected.request.json'),'answer':answer,'transport':reservations[0],'no_paper_mutation':True});dump(B/'selected_allocation/portfolios.json',rows);freeze(B/'selected_allocation/policies.json',policies);print('SELECTED_ALLOCATION_RESULTS',len(rows))
