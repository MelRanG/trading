from common import *
import importlib.util,pandas as pd,numpy as np
spec=importlib.util.spec_from_file_location('endpoint_parent',R/'experiments/task9_1/evaluate.py');ev=importlib.util.module_from_spec(spec);spec.loader.exec_module(ev)
def endpoints(date,s,entry,exit):
 f=B/'evaluator_only'/date/s;n,b=ev.valid_prices(pd.read_csv(B/'third_source'/s/'bars.csv'));y,b=ev.valid_prices(pd.read_csv(f/'yahoo_bars.csv'));r=json.loads((f/'receipt_v2.json').read_text());assert not r.get('events',{}).get('splits',{}),'ACTION_AUDIT_REQUIRED'
 for d in [entry,exit]:
  assert d in n.index and d in y.index,'MISSING_ENDPOINT';assert abs(float(n.loc[d,'open']/y.loc[d,'open'])-1)<=.005,'CONFLICTING_ENDPOINT'
 return float(n.loc[exit,'open']/n.loc[entry,'open']),{'symbol':s,'entry_open':float(n.loc[entry,'open']),'exit_open':float(n.loc[exit,'open']),'entry':str(entry.date()),'exit':str(exit.date()),'source':'NAVER_OPEN_MATCHES_YAHOO','reference_sha256':sha(B/'third_source'/s/'body.txt'),'no_split_declared':True}
if __name__=='__main__':
 rows=[];events=[]
 for date in ['2024-11-29','2025-06-30']:
  arms,_=ev.baskets(date,'KR');idx,bad=ev.valid_prices(pd.read_csv(B/'evaluator_only'/date/'^KS11/bars.csv'))
  for months in [3,6,12]:
   a,z=ev.window(idx.index,date,months);ds=pd.DatetimeIndex([a,z]);iv=pd.Series([1.,float(idx.loc[z,'open']/idx.loc[a,'open'])],index=ds);paths={};errors={}
   for x in json.loads((B/'screens'/date/'KR.json').read_text())['deep']:
    try:
     r,note=endpoints(date,x['symbol'],a,z);paths[x['symbol']]=pd.Series([1.,r],index=ds);events.append({'date':date,'months':months,**note})
    except Exception as exc:errors[x['symbol']]=str(exc)
   for arm,w in arms.items():
    item={'date':date,'market':'KR','months':months,'arm':arm,'entry':str(a.date()),'exit':str(z.date()),'positions':w,'quality':'PARTIAL_ENDPOINT_RETURN_ONLY_NO_DAILY_RISK','full_daily_replay':'BLOCKED_WHERE_UNCORROBORATED','errors':{s:errors[s] for s in w if s in errors}}
    try:
     if w:metric,_=ev.mix(paths,w,iv,6.5,29.5)
     else:metric,_=ev.mix({'CASH':pd.Series(1.,index=ds)},{'CASH':0},iv,0,0);metric['positions']={}
     metric.update(mdd_observed_marks=None,sharpe_rf0_diagnostic=None,missing_index_marks=None);item.update(status='CALCULATED_ENDPOINT_PARTIAL',**metric)
    except Exception as exc:item.update(status='BLOCKED_SELECTED_ENDPOINT',reason=str(exc))
    rows.append(item)
 dump(B/'evaluation_endpoint/portfolios.json',rows);dump(B/'evaluation_endpoint/price_events.json',events);print('ENDPOINT_CALCULATED',sum(x['status']=='CALCULATED_ENDPOINT_PARTIAL' for x in rows),'BLOCKED',sum(x['status']!='CALCULATED_ENDPOINT_PARTIAL' for x in rows))
