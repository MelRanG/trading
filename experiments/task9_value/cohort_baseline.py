"""Single-provider broad-cohort diagnostic; known unsupported spin-off blocks it."""
from pathlib import Path
import json,sys,pandas as pd
sys.path.insert(0,str(Path(__file__).parent))
from evaluate import load_index,window,valid_prices,mix
R=Path(__file__).resolve().parents[2];B=R/'runtime/task9_value';rows=[]
for year in [2021,2022,2023]:
 packet=json.loads((B/'screen_inputs'/('screen_'+str(year)+'.json')).read_text())
 for market in ['US','KR']:
  cohort=[x['symbol'] for x in packet['candidates'] if x['market']==market and x['status']=='AVAILABLE_BOUNDED'];idx=load_index(market)
  for h in [3,6,12]:
   entry,exit=window(idx.index,str(year)+'-11-30',h);iv=idx.loc[entry:exit,'close']/idx.loc[entry,'open'];iv.loc[entry-pd.Timedelta(seconds=1)]=1.;iv.loc[exit]=idx.loc[exit,'open']/idx.loc[entry,'open'];iv=iv.sort_index();paths={};errors={}
   for s in cohort:
    try:
     if s=='MMM' and entry<pd.Timestamp('2024-04-01')<=exit:raise ValueError('IDENTIFIED_SOLVENTUM_SPINOFF_DISTRIBUTION_NOT_ACCOUNTED')
     f,bad=valid_prices(pd.read_csv(B/'prices'/s/'bars.csv'));assert entry in f.index and exit in f.index,'unusable endpoint'
     ds=idx.loc[entry:exit].index.intersection(f.index);p=f.loc[ds,'close']/f.loc[entry,'open'];p.loc[entry-pd.Timedelta(seconds=1)]=1.;p.loc[exit]=f.loc[exit,'open']/f.loc[entry,'open'];paths[s]=p.sort_index()
    except Exception as e:errors[s]=str(e)
   r={'year':year,'market':market,'months':h,'cohort_size_fixed_before_selection':len(cohort),'status':'UNVERIFIED_SINGLE_PROVIDER_DIAGNOSTIC','omitted_from_initial_price_gate':[x['symbol'] for x in packet['candidates'] if x['market']==market and x['status']!='AVAILABLE_BOUNDED'],'selected_errors':errors,'no_survivor_renormalization':True}
   try:
    metric,nav=mix(paths,{s:1/len(cohort) for s in cohort},iv,6.5 if market=='KR' else 6,29.5 if market=='KR' else 6);r.update(metric)
   except Exception as e:r.update(status='BLOCKED_COHORT_DATA_OR_ACTION',net_price_return=None,error=str(e))
   rows.append(r)
(B/'evaluation/cohort_baseline.json').write_text(json.dumps(rows,indent=2))
for r in rows:
 if r['months']==12:print(r['year'],r['market'],r['status'],r.get('net_price_return'),r['selected_errors'])
