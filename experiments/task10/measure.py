from shared import *
def measure(scores,fs,m,start,end):
 metric,nav,fills,intents,ledger,journal=portfolio(scores,fs,m,start,end);ics=rank_ic(scores,fs,end,start);vals=[r['IC'] for r in ics];metric['IC']=float(np.mean(vals)) if vals else None;metric['ICIR']=float(np.mean(vals)/np.std(vals)) if vals and np.std(vals)>0 else 0.;metric['IC_sessions']=len(vals);metric['nonoverlap_blocks']=len(vals[::5]);metric['orders_unfilled']=len(intents)
 n=nav.set_index('date');etf=fs[m+'_BENCHMARK'];idx=etf.close.reindex(n.index).pct_change(fill_method=None);idx.iloc[0]=etf.close.loc[n.index[0]]/etf.open.loc[n.index[0]]-1;exp=n.exposure.shift(1).fillna(0.);rets=n.nav_krw.pct_change(fill_method=None);rets.iloc[0]=n.nav_krw.iloc[0]/C['strategy']['capital'][m]-1;matched=exp*idx;metric['exposure_matched_etf_return']=float((1+matched).prod()-1);metric['net_active_return']=metric['return_pct']/100-metric['exposure_matched_etf_return'];metric['market_reference']='SPY_PRICE' if m=='US' else 'KODEX200_PRICE';cumcost=pd.Series(0.,index=n.index)
 if len(fills):
  costs=fills[['fee_krw','half_spread_cost_krw','impact_cost_krw']].sum(axis=1).groupby(fills.date).sum();cumcost=costs.reindex(n.index,fill_value=0.).cumsum()
 gross=n.nav_krw+cumcost;gr=gross.pct_change(fill_method=None);gr.iloc[0]=gross.iloc[0]/C['strategy']['capital'][m]-1;delta=gr-matched;netdelta=rets-matched
 def relmdd(path):
  x=(1+path).cumprod()/(1+matched).cumprod();return float((x/x.cummax().clip(lower=1)-1).min())
 metric['gross_same_fills_return']=float(gross.iloc[-1]/C['strategy']['capital'][m]-1);metric['native_aliases']={'IC':metric['IC'] or 0.,'RankIC':metric['IC'] or 0.,'ICIR':metric['ICIR'],'1day.excess_return_without_cost.annualized_return':float(delta.mean()*252),'1day.excess_return_without_cost.max_drawdown':relmdd(gr),'1day.excess_return_without_cost.information_ratio':float(delta.mean()/delta.std(ddof=0)*np.sqrt(252)) if delta.std(ddof=0)>0 else 0.,'1day.excess_return_with_cost.annualized_return':float(netdelta.mean()*252),'1day.excess_return_with_cost.max_drawdown':relmdd(rets)}
 metric['alias_note']='1daylegacykey=dailyNAVexcess; factorICtarget5sessionopen-to-open, notintradaylabel. Gross=cashaddbackactualfills, no hypotheticalextrashares.'
 return metric,nav,fills,intents,ledger,journal,ics
