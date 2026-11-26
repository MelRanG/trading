"""Reuse Task9 notional evaluator; research portfolios, no new trading engine."""
from common import *
import pandas as pd,numpy as np,importlib.util
sys.path.insert(0,str(R/'experiments/task9_value'))
# Avoid this file importing itself if imported by name; explicit reuse below.
spec=importlib.util.spec_from_file_location('task9_notional',R/'experiments/task9_value/evaluate.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old);mix=old.mix;window=old.window;valid_prices=old.valid_prices
spec=importlib.util.spec_from_file_location('vibe_native_portfolio',Path('/home/ansy/app/quant-diligence/vibe-original/agent/src/quantlib/portfolio.py'));vibe=importlib.util.module_from_spec(spec);spec.loader.exec_module(vibe)
from quant_harness.investment.portfolio import aggregate

def baskets(date,market):
 screen=json.loads((B/'screens'/date/(market+'.json')).read_text());names=[x['symbol'] for x in screen['deep']];ports={}
 for arm in ['value','market']:
  d=json.loads((B/'decisions'/(date+'_'+arm+'.json')).read_text())['decision'];ports[arm]=next(x for x in d['portfolios'] if x['market']==market)
 quant=sorted(screen['deep'],key=lambda x:(-x['momentum63'],x['symbol']));qnames=[x['symbol'] for x in quant if x['momentum63']>0][:3]
 # No positive momentum: causal quant abstention, never force a buy.
 mixed=sorted(names,key=lambda s:(ports['market']['ranked_top3'].index(s)+1 if s in ports['market']['ranked_top3'] else len(names)+1)+([x['symbol'] for x in quant].index(s)+1))[:3]
 result={}
 for label,ns in [('SELECT_VALUE',ports['value']['ranked_top3']),('SELECT_MARKET',ports['market']['ranked_top3']),('SELECT_INTEGRATED_RANK_FUSION',mixed),('SELECT_QUANT_RANK100',[x['symbol'] for x in quant[:3]]),('QUANT_RULE_POSITIVE',qnames),('SELECT_EQUAL_DEEP',names)]:result[label]={s:1/len(ns) for s in ns} if ns else {}
 fixed=screen['allocation_basket'];n=len(fixed);result['ALLOC_EQUAL100']={s:1/n for s in fixed};result['ALLOC_FIXED60']={s:.6/n for s in fixed}
 series=[]
 for s in fixed:
  f=pd.read_csv(B/'inputs'/date/s/'bars.csv');series.append(f.set_index('date').close.pct_change().rename(s))
 returns=pd.concat(series,axis=1).dropna().tail(63);assert len(returns)>=60
 iv=vibe.inverse_variance_weights(returns.cov().to_numpy());result['ALLOC_VIBE_IVP60']={s:min(.2,float(w)*.6) for s,w in zip(fixed,iv)}
 for arm in ['value','market']:result['ALLOC_AI_'+arm.upper()]={s:float(w) for s,w in ports[arm]['fixed_basket_weights'].items() if w>0}
 sectors={x['symbol']:x['sector'] for x in screen['deep']};previews={k:aggregate([{'capital_fraction':1.,'weights':v}],gross_cap=.6,single_name_cap=.2,sector_caps={sec:.6 for sec in sectors.values()},sectors=sectors) for k,v in result.items() if k.startswith('ALLOC_') and k!='ALLOC_EQUAL100'}
 return result,previews

def path_for(date,s,entry,exit,dates):
 f=B/'evaluator_only'/date/s;r=json.loads((f/('receipt_v2.json' if (f/'receipt_v2.json').exists() else 'receipt.json')).read_text());assert r['status']=='SAVED';p,bad=valid_prices(pd.read_csv(f/'bars.csv'));y,ybad=valid_prices(pd.read_csv(f/'yahoo_bars.csv'));assert entry in p.index and exit in p.index,'MISSING_ENTRY_EXIT';assert set(dates)<=set(p.index),'MISSING_REQUIRED_PRICE_MARKS'
 split=pd.Series(1.,index=p.index)
 for e in r.get('events',{}).get('splits',{}).values():
  day=pd.Timestamp(e['date'],unit='s',tz='UTC').tz_convert('Asia/Seoul' if s.endswith(('.KS','.KQ')) else 'America/New_York').tz_localize(None).normalize()
  if entry<day<=exit:split.loc[split.index>=day]*=float(e['numerator'])/float(e['denominator'])
 out=p.loc[dates,'close']*split.loc[dates]/float(p.loc[entry,'open']);out.loc[entry-pd.Timedelta(seconds=1)]=1.;out.loc[exit]=float(p.loc[exit,'open']*split.loc[exit]/p.loc[entry,'open']);out=out.sort_index()
 # Price-return endpoint parity is invariant to later Yahoo split-unit rewrites.
 assert entry in y.index and exit in y.index,'MISSING_SECONDARY_ENDPOINT'
 secondary=float(y.loc[exit,'open']/y.loc[entry,'open']);assert abs(secondary/float(out.iloc[-1])-1)<=.005,'SOURCE_RETURN_CONFLICT'
 return out,{'symbol':s,'entry_open':float(p.loc[entry,'open']),'exit_open':float(p.loc[exit,'open']),'price_return':float(out.iloc[-1]-1),'secondary_price_return':secondary-1,'split_factor':float(split.loc[exit]),'rejected_bars':len(bad),'dividend_policy':'EXCLUDED_BOTH_SIDES','raw_entry_unit_ratio_toss_yahoo':float(p.loc[entry,'open']/y.loc[entry,'open'])}

def run(date):
 results=[];stock=[];policy={}
 for m,index in [('US','^GSPC'),('KR','^KS11')]:
  arms,previews=baskets(date,m);policy[m]={'arms':arms,'QH_preview':previews,'native_portfolio_hash':sha('/home/ansy/app/quant-diligence/vibe-original/agent/src/quantlib/portfolio.py')};f,bad=valid_prices(pd.read_csv(B/'evaluator_only'/date/index/'bars.csv'))
  for months in [3,6,12]:
   entry,exit=window(f.index,date,months);ds=f.loc[entry:exit].index;iv=f.loc[ds,'close']/float(f.loc[entry,'open']);iv.loc[entry-pd.Timedelta(seconds=1)]=1.;iv.loc[exit]=float(f.loc[exit,'open']/f.loc[entry,'open']);iv=iv.sort_index();paths={};errors={}
   for x in json.loads((B/'screens'/date/(m+'.json')).read_text())['deep']:
    s=x['symbol']
    try:p,note=path_for(date,s,entry,exit,ds);paths[s]=p;stock.append({'date':date,'market':m,'months':months,**note})
    except Exception as exc:errors[s]=str(exc)
   for label,w in arms.items():
    item={'date':date,'market':m,'months':months,'arm':label,'entry':str(entry.date()),'exit':str(exit.date()),'quality':'PARTIAL_HISTORICAL_RECONSTRUCTION_NOT_INDEPENDENT_ALPHA','positions':w,'errors':{s:errors[s] for s in w if s in errors}}
    try:
     if w:metric,nav=mix(paths,w,iv,6.5 if m=='KR' else 6,29.5 if m=='KR' else 6)
     else:metric,nav=mix({'CASH':pd.Series(1.,index=iv.index)},{'CASH':0},iv,0,0);metric['positions']={}
     item.update(status='CALCULATED_PARTIAL',**metric);nav.to_csv(B/'evaluation'/(date+'_'+m+'_'+str(months)+'_'+label+'.csv'),index=False)
    except Exception as exc:item.update(status='BLOCKED_SELECTED_DATA',reason=str(exc))
    results.append(item)
 dump(B/'evaluation'/(date+'.json'),results);dump(B/'evaluation'/(date+'_stock.json'),stock);freeze(B/'allocation_contracts'/(date+'.json'),policy);return results
if __name__=='__main__':
 date=sys.argv[1];assert date in ['2024-11-29','2025-06-30']
 if date=='2025-06-30':assert (B/'followup_preregistered.json').exists(),'followup must precede2025 outcomes'
 (B/'evaluation').mkdir(exist_ok=True);out=run(date);print(json.dumps([{k:x.get(k) for k in ['market','months','arm','status','net_price_return','benchmark_price_return','reason']} for x in out if x['months']==12],indent=2))
