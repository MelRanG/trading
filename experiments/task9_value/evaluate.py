"""Research-only notional portfolios. No broker/Paper order path, no signal tuning."""
from pathlib import Path
import sys,json,hashlib
import pandas as pd,numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'))
from quant_harness.investment.research import metrics
B=R/'runtime/task9_value'

def valid_prices(f):
 f=f.copy();f['date']=pd.to_datetime(f.date).dt.normalize();f=f.set_index('date').sort_index()
 good=f[['open','high','low','close','volume']].notna().all(axis=1)&(f[['open','high','low','close']]>0).all(axis=1)&(f.volume>0)&(f.high>=f[['open','close','low']].max(axis=1))&(f.low<=f[['open','close','high']].min(axis=1))
 return f[good],f[~good]

def window(index,cutoff,months):
 ds=pd.DatetimeIndex(index).sort_values();after=ds[ds>pd.Timestamp(cutoff)];assert len(after),'no entry event';entry=after[0];target=entry+pd.DateOffset(months=months);tail=ds[ds>=target];assert len(tail),'PENDING_HORIZON';return entry,tail[0]

def mix(paths,weights,index_path,buy_bps,sell_bps):
 assert weights and all(0<=v<=1 for v in weights.values()) and sum(weights.values())<=1+1e-9
 for s in weights:
  if s not in paths:raise ValueError('MISSING_SELECTED_OUTCOME:'+s)
 common=index_path.index
 for s in weights:common=common.intersection(paths[s].index)
 if len(common)<2 or common[0]!=index_path.index[0] or common[-1]!=index_path.index[-1]:raise ValueError('MISSING_ENTRY_OR_EXIT')
 s=sum(weights.values());gross=pd.Series(1-s,index=common,dtype=float)
 for symbol,w in weights.items():gross+=w*paths[symbol].reindex(common)
 buy=buy_bps/10000;sell=sell_bps/10000;fund=1+buy*s;net=gross/fund;terminal_risky=sum(w*paths[symbol].loc[common[-1]] for symbol,w in weights.items());net.iloc[-1]-=sell*terminal_risky/fund
 account=pd.DataFrame({'date':common,'nav_krw':net.to_numpy()});m=metrics(account,pd.DataFrame(),1)
 benchmark=float(index_path.iloc[-1]-1);matched=s*benchmark;gross_return=float(gross.iloc[-1]-1);net_return=float(net.iloc[-1]-1)
 result={'gross_price_return':gross_return,'net_price_return':net_return,'cost_effect':gross_return-net_return,'mdd_observed_marks':m['mdd_pct']/100,'sharpe_rf0_diagnostic':m['sharpe'],'benchmark_price_return':benchmark,'excess_vs_full_index':net_return-benchmark,'gross_index_cash_initial_exposure_matched':matched,'selection_gross_residual':gross_return-matched,'net_vs_matched_gross':net_return-matched,'target_equity_exposure':s,'cash_target':1-s,'entry_cost_funding_scale':1/fund,'end_equity_exposure_before_liquidation':float(terminal_risky/gross.iloc[-1]),'turnover_notional_over_initial':s/fund+terminal_risky/fund,'positions':weights,'observed_marks':len(common),'missing_index_marks':len(index_path)-len(common),'contribution_gross':{symbol:float(w*(paths[symbol].iloc[-1]-1)) for symbol,w in weights.items()},'no_actual_orders_or_fills':True}
 return result,pd.DataFrame({'date':common,'gross_nav':gross.to_numpy(),'net_nav':net.to_numpy(),'index_nav':index_path.reindex(common).to_numpy()})

def load_index(market):
 f=pd.read_csv(B/'prices'/('^KS11' if market=='KR' else '^GSPC')/'bars.csv');f['date']=pd.to_datetime(f.date);f=f.set_index('date').sort_index()
 if market=='KR':
  patch=json.loads((R/'runtime/task9_completion/benchmark_patch/close_patch.json').read_text());d=pd.Timestamp(patch['date'])
  if d not in f.index:f.loc[d,'close']=patch['value'];f=f.sort_index()
 return f

def ratio_for(s,market,entry,exit,dates):
 folder=B/'evaluator_only'/s;f,bad=valid_prices(pd.read_csv(folder/'bars.csv'));assert entry in f.index and exit in f.index,'missing actual selected price event'
 raw_y=pd.read_csv(B/'prices'/s/'bars.csv');y,ybad=valid_prices(raw_y);r=json.loads((B/'prices'/s/'receipt_v3.json').read_text());events=r.get('events',{});split=pd.Series(1.,index=f.index)
 for e in events.get('splits',{}).values():
  d=pd.Timestamp(e['date'],unit='s',tz='UTC').tz_convert('Asia/Seoul' if market=='KR' else 'America/New_York').normalize().tz_localize(None)
  if entry<d<=exit:split.loc[split.index>=d]*=float(e['numerator'])/float(e['denominator'])
 ds=dates.intersection(f.index);path=f.loc[ds,'close']*split.loc[ds]/float(f.loc[entry,'open']);path.loc[entry-pd.Timedelta(seconds=1)]=1.;path.loc[exit]=float(f.loc[exit,'open'])*float(split.loc[exit])/float(f.loc[entry,'open']);path=path.sort_index()
 common=ds.intersection(y.index);delta=(f.loc[common,'close']/y.loc[common,'close']-1).abs();outliers=delta[delta>.005]
 # Raw unit/price errors at endpoints block a result; intermediate conflicts
 # remain a visible PARTIAL-source limitation with primary Toss marks.
 for day in [entry,exit]:
  if day not in y.index:raise ValueError('secondary endpoint missing')
  if abs(float(f.loc[day,'open'])/float(y.loc[day,'open'])-1)>.005:raise ValueError('endpoint source/unit mismatch')
 divs=[e for e in events.get('dividends',{}).values() if pd.Timestamp(e['date'],unit='s',tz='UTC').date()>=entry.date() and pd.Timestamp(e['date'],unit='s',tz='UTC').date()<exit.date()]
 tr=None
 if entry in y.index and exit in y.index:
  a=float(y.loc[entry,'open'])*float(y.loc[entry,'adjusted_close'])/float(y.loc[entry,'close']);z=float(y.loc[exit,'open'])*float(y.loc[exit,'adjusted_close'])/float(y.loc[exit,'close']);tr=z/a-1
 note={'symbol':s,'entry_open':float(f.loc[entry,'open']),'exit_open':float(f.loc[exit,'open']),'price_return':float(path.iloc[-1]-1),'provider_adjusted_return_diagnostic':tr,'observed_dividend_events':len(divs),'split_events':len(events.get('splits',{})),'intermediate_cross_source_outliers':{str(d.date()):float(v) for d,v in outliers.items()},'missing_primary_marks':len(dates)-len(ds),'quality':'PARTIAL_TWO_PROVIDER_RECONSTRUCTION_NOT_FULL_ACTION_AUDIT','dividend_policy':'Price-only primary comparison excludes dividends on both stock/index sides; adjusted diagnostic not a verified total-return ledger'}
 return path,note

def main():
 assert len(json.loads((B/'decision_seals.json').read_text()))==3
 O=B/'evaluation';O.mkdir(exist_ok=True);all_results=[];stock=[]
 for year in [2021,2022,2023]:
  seal=json.loads((B/'decisions'/(str(year)+'.json')).read_text());decision=seal['decision']
  for market in ['US','KR']:
   index=load_index(market);portfolio=next(p for p in decision['portfolios'] if p['market']==market);companies=[x for x in decision['companies'] if x['market']==market]
   for months in [3,6,12]:
    entry,exit=window(index.index,str(year)+'-11-30',months);dates=index.loc[entry:exit].index;iv=index.loc[entry:exit,'close']/float(index.loc[entry,'open']);iv.loc[entry-pd.Timedelta(seconds=1)]=1;iv.loc[exit]=float(index.loc[exit,'open'])/float(index.loc[entry,'open']);iv=iv.sort_index()
    if not np.isfinite(iv).all():raise ValueError('unobserved benchmark close')
    paths={};errors={}
    for c in companies:
     try:
      path,note=ratio_for(c['symbol'],market,entry,exit,dates);paths[c['symbol']]=path;stock.append({'year':year,'market':market,'months':months,**note})
     except Exception as e:errors[c['symbol']]=str(e)
    baskets={k:{s:.5 for s in portfolio[k]} for k in ['value_only_top2','value_market_top2','relative_final_top2']};baskets['policy']={c['symbol']:float(c['policy_weight']) for c in companies if c['policy_weight']>0}
    for mode,weights in baskets.items():
     base={'year':year,'market':market,'months':months,'mode':mode,'entry':str(entry.date()),'exit':str(exit.date()),'currency':'KRW' if market=='KR' else 'USD','decision_hash':seal['output_sha256'],'transport_status':seal['transport_status'],'research_diagnostic_only':True,'selected_errors':{s:errors[s] for s in weights if s in errors}}
     try:
      if not weights:
       empty=pd.Series(1.,index=iv.index);metric,nav=mix({'CASH':empty},{'CASH':0},iv,0,0);metric['positions']={}
      else:metric,nav=mix(paths,weights,iv,6.5 if market=='KR' else 6,29.5 if market=='KR' else 6)
      base.update(status='CALCULATED_PARTIAL',**metric);nav.to_csv(O/(str(year)+'_'+market+'_'+str(months)+'_'+mode+'.csv'),index=False)
     except Exception as e:base.update(status='BLOCKED_SELECTED_DATA',error=str(e),net_price_return=None)
     all_results.append(base)
 (O/'portfolios.json').write_text(json.dumps(all_results,ensure_ascii=False,indent=2));(O/'stock_outcomes.json').write_text(json.dumps(stock,ensure_ascii=False,indent=2));print(json.dumps([{k:x.get(k) for k in ['year','market','months','mode','status','net_price_return','benchmark_price_return']} for x in all_results if x['mode'] in ['relative_final_top2','policy']],indent=2))
if __name__=='__main__':main()
