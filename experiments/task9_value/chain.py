"""Descriptive chaining of all three sealed12m allocations, no new optimization."""
from pathlib import Path
import json,pandas as pd,numpy as np
R=Path(__file__).resolve().parents[2];B=R/'runtime/task9_value';results=json.loads((B/'evaluation/portfolios.json').read_text());rows=[]
for market in ['US','KR']:
 for mode in ['value_only_top2','value_market_top2','relative_final_top2','policy']:
  chosen=[next(r for r in results if r['year']==y and r['market']==market and r['mode']==mode and r['months']==12) for y in [2021,2022,2023]];assert all(r['status']=='CALCULATED_PARTIAL' for r in chosen);assert all(chosen[i]['exit']==chosen[i+1]['entry'] for i in [0,1]);nav=1.;bench=1.;path=[1.];records=[]
  for segment in chosen:
   df=pd.read_csv(B/'evaluation'/(str(segment['year'])+'_'+market+'_12_'+mode+'.csv'))
   for i,r in df.iloc[1:].iterrows():records.append({'segment':segment['year'],'mark':r['date'],'nav':nav*float(r.net_nav),'kind':'OBSERVED_MARK_OR_EXIT_OPEN'});path.append(records[-1]['nav'])
   nav*=1+segment['net_price_return'];bench*=1+segment['benchmark_price_return']
  duration=(pd.Timestamp(chosen[-1]['exit'])-pd.Timestamp(chosen[0]['entry'])).days/365.25;p=pd.Series(path);x={'market':market,'mode':mode,'entry':chosen[0]['entry'],'exit':chosen[-1]['exit'],'annual_research_segments':3,'net_price_return':nav-1,'benchmark_price_return':bench-1,'excess':nav-bench,'cagr':nav**(1/duration)-1,'mdd_observed_marks':float((p/p.cummax()-1).min()),'scope':'Post-hoc descriptive chaining of every prespecified12m evaluation; not newly selected strategy or independent validation; no monthly/event research replay','input_decision_hashes':[r['decision_hash'] for r in chosen]};rows.append(x);pd.DataFrame(records).to_csv(B/'evaluation'/('chain_'+market+'_'+mode+'.csv'),index=False)
(B/'evaluation/chained.json').write_text(json.dumps(rows,indent=2));print(json.dumps(rows,indent=2))
