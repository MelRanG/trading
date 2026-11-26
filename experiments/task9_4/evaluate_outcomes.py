"""Original static mix evaluator with sealed open-to-close paths, no trading."""
from protocol import *
import pandas as pd,numpy as np,importlib.util
spec=importlib.util.spec_from_file_location('static_value',R/'experiments/task9_value/evaluate.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
ENDPOINTS={'1m':'2026-06-18','3m':'2026-08-18','6m':'2026-11-13'}

def path_for(asset,end,benchmark_dates):
 s=asset['symbol'];f=B/'evaluator_only'/s;q=json.loads((f/'quality.json').read_text());resolution=f/'resolution_v2.json';action=json.loads(resolution.read_text()) if resolution.exists() else None;p=f/('bars_v2.csv' if action else 'bars.csv');assert p.exists(),'NO_BARS';df=pd.read_csv(p);df['date']=pd.to_datetime(df.date);df=df.set_index('date').sort_index();assert not df.index.duplicated().any();entry=pd.Timestamp('2026-05-18');exit=pd.Timestamp(end)
 assert entry in df.index and exit in df.index,'MISSING_ACTUAL_ENTRY_OR_END';a=float(df.loc[entry,'open']);z=float(df.loc[exit,'close']);assert np.isfinite(a) and np.isfinite(z) and min(a,z)>0,'UNRESOLVED_ENDPOINT_PRICE'
 assert s.startswith('^') or q.get('V87',{}).get('passed',False),'V87_NOT_PASSED'
 for e in q.get('events',{}).get('splits',{}).values():
  d=pd.Timestamp(e['date'],unit='s',tz='UTC').date().isoformat();assert not '2026-05-18'<=d<=end or (action and action['action']['date']==d),'SPLIT_REQUIRES_INDEPENDENT_ACTION_RECONCILIATION'
 # Raw Yahoo is nominal split-adjusted convention in some cases; no assumed reversal.
 ds=benchmark_dates[(benchmark_dates>=entry)&(benchmark_dates<=exit)];values=df.close.reindex(ds)/a
 if action:
  assert sha(R/action['source_path'])==action['source_hash'];values.loc[values.index>=pd.Timestamp(action['action']['date'])]*=action['action']['quantity_multiplier']
 missing=values.isna();values=values.dropna();values.loc[entry-pd.Timedelta(seconds=1)]=1.;values=values.sort_index()
 assert values.index[-1]==exit,'MISSING_EXIT';return values,{'entry':'2026-05-18','entry_open':a,'exit':end,'exit_close':z,'price_return':float(values.iloc[-1]-1),'missing_daily_closes':int(missing.sum()),'quality':'PARTIAL_PROVIDER_CONSENSUS' if asset['market'] in ['US','KR'] and s!='^GSPC' else 'PARTIAL_SINGLE_SOURCE','declared_cash_distribution_events':len(q.get('events',{}).get('dividends',{})),'dividends_excluded_symmetric':True,'source_quality_hash':sha(f/'quality.json')}

def evaluate():
 assets=asset_list();lookup={a['symbol']:a for a in assets};O=B/'evaluation_v2';O.mkdir(exist_ok=True);out=[];portfolios=[];relative=[]
 for m,index in [('US','^GSPC'),('KR','^KS11')]:
  research=json.loads((B/'research'/(m+'.json')).read_text());idxfile=B/'evaluator_only'/index/'bars.csv';ix=pd.DatetimeIndex(pd.to_datetime(pd.read_csv(idxfile).date)).sort_values();symbols=sorted(set([index]+[x['symbol'] for x in research['selected']]+[a['symbol'] for x in research['selected'] for a in x['comparators'] if a.get('symbol')]))
  for h,end in ENDPOINTS.items():
   ds=ix[(ix>=pd.Timestamp('2026-05-18'))&(ix<=pd.Timestamp(end))];paths={};notes={}
   for s in symbols:
    row={'market_context':m,'symbol':s,'horizon':h}
    try:
     path,note=path_for(lookup[s],end,ds);paths[s]=path;notes[s]=note;row.update(status='CALCULATED_PARTIAL',**note)
     if not note['missing_daily_closes']:
      mdd=float((path/path.cummax()-1).min());r=path.pct_change().dropna();row.update(mdd=mdd,annualized_volatility=float(r.std(ddof=1)*np.sqrt(252)),sharpe_rf0=float(r.mean()/r.std(ddof=1)*np.sqrt(252)) if r.std(ddof=1)>0 else None)
     else:row.update(mdd=None,annualized_volatility=None,sharpe_rf0=None)
     path.rename('relative_price').to_csv(O/(m+'_'+s+'_'+h+'.csv'),index_label='date')
    except (AssertionError,ValueError,KeyError,FileNotFoundError) as e:row.update(status='BLOCKED_PRICE',reason=str(e),price_return=None)
    out.append(row)
   assert index in paths,'BENCHMARK_UNAVAILABLE';benchmark=paths[index]
   top=sorted(research['selected'],key=lambda x:x['rank'])[:3];w={x['symbol']:1/3 for x in top if x['symbol'] in paths};cash=[{'slot':i+1,'symbol':x['symbol'],'reason':'UNPRICEABLE_REMAINS_CASH_NO_REPLACEMENT'} for i,x in enumerate(top) if x['symbol'] not in paths]
   for i in range(len(top),3):cash.append({'slot':i+1,'symbol':None,'reason':'NO_SELECTED_CANDIDATE'})
   if w:result,nav=old.mix(paths,w,benchmark,6 if m=='US' else 6.5,6 if m=='US' else 26.5)
   else:result={'gross_price_return':0.,'net_price_return':0.,'cash_target':1.,'target_equity_exposure':0.,'benchmark_price_return':float(benchmark.iloc[-1]-1),'excess_vs_full_index':float(1-benchmark.iloc[-1]),'positions':{},'missing_index_marks':0};nav=pd.DataFrame({'date':benchmark.index,'gross_nav':1.,'net_nav':1.,'index_nav':benchmark.to_numpy()})
   if result['missing_index_marks'] or notes[index]['missing_daily_closes']:result.update(mdd_observed_marks=None,sharpe_rf0_diagnostic=None,metric_limit='MISSING_HELD_OR_INDEX_DAILY_MARKS')
   portfolios.append({'market':m,'horizon':h,'entry':'2026-05-18_OPEN','exit':end+'_CLOSE','label':'FIXED_TOP3_DISCOVERY_RESEARCH_NOT_AI_ALLOCATION','cash_slots':cash,**result});nav.to_csv(O/(m+'_top3_'+h+'_nav.csv'),index=False)
   for x in research['selected']:
    s=x['symbol'];row={'market':m,'symbol':s,'horizon':h,'benchmark':index,'stock_return':notes.get(s,{}).get('price_return'),'comparators':[]}
    if s in paths:row['excess_market']=float(paths[s].iloc[-1]-benchmark.iloc[-1])
    for a in x['comparators']:
     c=a.get('symbol');v={'symbol':c,'relation':a['relation'],'verification':a.get('verification'),'currency':a.get('currency'),'holdings_overlap':a.get('holdings_overlap'),'price_return':notes.get(c,{}).get('price_return')}
     if s in paths and c in paths and a.get('currency')==lookup[s]['currency']:v['gap_percentage_points']=100*float(paths[s].iloc[-1]-paths[c].iloc[-1]);v['pair_price_status']='COMPARABLE_PRICE_ONLY_RELATION_QUALIFICATION_RETAINED'
     else:v['pair_price_status']='CROSS_CURRENCY_OR_MISSING_DATA_NO_POOLED_RANK'
     row['comparators'].append(v)
    valid=[a for a in row['comparators'] if a.get('gap_percentage_points') is not None and ('peer' in a['relation'].lower() or '동종' in a['relation'])];row['peer_price_rank_if_relationship_valid']=1+sum(a['gap_percentage_points']<0 for a in valid) if s in paths and valid else None;relative.append(row)
 freeze(O/'asset_returns.json',out);freeze(O/'portfolios.json',portfolios);freeze(O/'relative.json',relative)
 print(json.dumps(portfolios,ensure_ascii=False,indent=2))
if __name__=='__main__':evaluate()
