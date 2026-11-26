"""Thin fixed-share holding adapter around the EXISTING QH fee/fill/NAV engine."""
from pathlib import Path
import json,sys,hashlib
import numpy as np,pandas as pd
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'))
from quant_harness.investment.research import replay_targets,digest
from quant_harness.v77_corrected_price_allocation.engine import ExecutionSpec

def price_market(frame,symbol):
 f=frame.copy();f.index=pd.to_datetime(f.index);f=f.sort_index()
 for name in ('open','high','low','close','volume'):
  if not np.isfinite(f[name]).all() or (f[name]<=0).any():raise ValueError('missing/nonpositive execution inputs')
 return {'close':f[['close']].rename(columns={'close':symbol}),'open':f[['open']].rename(columns={'open':symbol}),'adv20_d1':(f.close*f.volume).rolling(20,min_periods=20).mean().shift(1).to_frame(symbol)}

def fixed_hold(frame,symbol,dates,weight,initial,spec,actions=()):
 if actions:raise ValueError('corporate-action interval not supported by this fixed-share adapter')
 if not 0<=weight<=.2:raise ValueError('initial weight cap')
 dates=pd.DatetimeIndex(dates);market=price_market(frame,symbol)
 if len(dates)!=64 or any(d not in market['close'].index for d in dates):raise ValueError('63 holding sessions and next open exit required')
 if weight==0:
  ledger=pd.DataFrame({'target_weights_json':['{}']*len(dates)});return (*replay_targets(market,dates,ledger,initial,spec),{'quantity':0,'initial_exposure':0,'policy':'FROZEN_CASH_DECISION'})
 # Preview only: same original QH entry calculation, no SQL or real orders.
 first=pd.DataFrame({'target_weights_json':[json.dumps({symbol:weight})]});preview,entry,intents=replay_targets(market,dates[:1],first,initial,spec)
 if entry.empty:raise ValueError('no eligible minimum/participation fill')
 q=int(entry.quantity.sum());cash=float(preview.cash_krw.iloc[0]);previous=market['close'].shift(1)[symbol];targets=[{symbol:weight}]
 for day in dates[1:-1]:
  nav=cash+q*float(previous.loc[day])
  # Half-open integer sizing bin: this maps to EXACTLY q shares, so the
  # legacy target replayer holds shares rather than rebalancing daily.
  targets.append({symbol:(q+.25)*float(previous.loc[day])/nav})
 targets.append({});ledger=pd.DataFrame({'target_weights_json':[json.dumps(t) for t in targets]})
 account,fills,intents=replay_targets(market,dates,ledger,initial,spec)
 if len(fills)!=2 or fills.side.tolist()!=['BUY','SELL'] or list(fills.quantity.astype(int))!=[q,q]:raise ValueError('unexpected turnover in fixed holding interval')
 if json.loads(account.holdings_json.iloc[-1]).get(symbol,0)!=0:raise ValueError('exit not flat')
 expected=initial-q*float(fills.fill_price_krw.iloc[0])-float(fills.fee_krw.iloc[0])+q*float(fills.fill_price_krw.iloc[1])-float(fills.fee_krw.iloc[1])
 if not np.isclose(account.nav_krw.iloc[-1],expected,atol=1e-7):raise ValueError('cash/fill/NAV mismatch')
 detail={'quantity':q,'initial_exposure':q*float(fills.reference_open_krw.iloc[0])/initial,'policy':'D1_SIZING_NEXT_OPEN_FIXED_SHARES_63_SESSIONS_EXIT_OPEN','target_weight':weight}
 return account,fills,intents,detail

def performance(account,fills,detail,frame,benchmark,dates,initial):
 dates=pd.DatetimeIndex(dates);f=frame.copy();f.index=pd.to_datetime(f.index);b=benchmark.copy();b.index=pd.to_datetime(b.index)
 if any(d not in b.index for d in dates):raise ValueError('missing benchmark session')
 nav=pd.Series([initial]+account.nav_krw.tolist());daily=nav.pct_change().dropna();base=float(b.loc[dates[0],'open']);end=float(b.loc[dates[-1],'open']);bench=end/base-1;exp=detail['initial_exposure'];net=float(nav.iloc[-1]/initial-1)
 benchmark_path=pd.Series([base]+[float(b.loc[d,'close']) if i<len(dates)-1 else end for i,d in enumerate(dates)])
 if not np.isfinite(benchmark_path).all() or (benchmark_path<=0).any():raise ValueError('missing observed benchmark mark')
 if fills.empty:cost=gross_pnl=0
 else:
  cost=float(fills[['fee_krw','half_spread_cost_krw','impact_cost_krw']].to_numpy().sum());gross_pnl=detail['quantity']*(float(fills.reference_open_krw.iloc[-1])-float(fills.reference_open_krw.iloc[0]))
 positions=[json.loads(x) for x in account.holdings_json];symbol=next(iter(positions[0]),None);exposures=[sum(q*float(f.loc[pd.Timestamp(row.date),'close']) for s,q in positions[i].items())/float(row.nav_krw) for i,row in account.iterrows()]
 return {'evidence':'HISTORICAL_BOUNDED_RECONSTRUCTION_NOT_FORWARD','net_return':net,'gross_price_return':gross_pnl/initial,'recorded_assumed_cost':cost,'net_pnl':float(nav.iloc[-1]-initial),'mdd':float((nav/nav.cummax()-1).min()),'benchmark_mdd_daily_observed_marks':float((benchmark_path/benchmark_path.cummax()-1).min()),'sample_sharpe_rf0_252':float(daily.mean()/daily.std(ddof=1)*np.sqrt(252)) if daily.std(ddof=1)>0 else None,'benchmark_price_return_same_open_interval':bench,'excess_vs_full_index_gross':net-bench,'initial_capital_matched_index_cash_gross':exp*bench,'selection_gross_difference':gross_pnl/initial-exp*bench,'net_difference_vs_gross_matched_control':net-exp*bench,'initial_exposure':exp,'max_observed_close_exposure':max(exposures),'mean_observed_close_exposure':float(np.mean(exposures)),'cash_at_exit':float(account.cash_krw.iloc[-1]),'turnover_over_initial':float((fills.quantity*fills.reference_open_krw).sum()/initial) if not fills.empty else 0,'fills':len(fills),'dividend_cash':0,'dividend_basis':'Original issuer no-dividend evidence for this holding interval, not missing-to-zero fill','contribution':{detail.get('symbol',symbol) or 'CASH':net},'cash_interest':0,'benchmark_costs':'Gross noninvestable price-index reference, no fabricated ETF costs'}
