"""Fixed Vibe factor outputs and QH rules under ONE frozen execution contract.

No production DB or Factory writes. Independent ledger checks run on every
result. Original Vibe engine results are reported separately, never ranked as
same-cost results.
"""
from pathlib import Path
import json,hashlib,sys
import pandas as pd
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'))
from quant_harness.investment.equities import stock_targets
from quant_harness.investment.research import replay_targets,metrics,digest
from quant_harness.v77_corrected_price_allocation.engine import ExecutionSpec
WORK=Path('/home/ansy/app/quant-diligence/vibe-work');inputs=WORK/'inputs';plan=json.loads((inputs/'preregistration.json').read_text());cfg=plan['contract'];out=ROOT/'runtime/task6_pre/comparison';out.mkdir(parents=True,exist_ok=True)
result={'preregistration_hash':digest(plan),'kind':'PAIRED_HISTORICAL_DIAGNOSTIC_NOT_NEW_FORWARD','model_calls':0,'tokens':0,'markets':{}}
for market,contract in plan['markets'].items():
 folder=out/market;folder.mkdir(exist_ok=True);names=contract['symbols'];frames={}
 for symbol,entry in contract['files'].items():
  path=inputs/market/(symbol+'.csv')
  if hashlib.sha256(path.read_bytes()).hexdigest()!=entry['sha256']:raise ValueError('snapshot changed')
  frames[symbol]=pd.read_csv(path,index_col='date',parse_dates=True)
 close=pd.DataFrame({s:frames[s].close for s in names}).dropna()
 dates=close.index[(close.index>=contract['start']) & (close.index<=contract['end'])]
 if len(dates)!=contract['sessions']:raise ValueError('session mismatch')
 panel={'close':pd.DataFrame({s:f.close for s,f in frames.items()}),'open':pd.DataFrame({s:f.open for s,f in frames.items()}),
        'adv20_d1':pd.DataFrame({s:f.value_approx.rolling(20,min_periods=20).mean().shift(1) for s,f in frames.items()})}
 factor=pd.read_csv(WORK/'poc'/(market+'_factor.csv'),index_col=0,parse_dates=True).reindex(columns=names)
 # Independently verify original factor values, then apply the registered map.
 formula=np.sign(pd.DataFrame({s:frames[s].volume for s in names}).diff())*-close.diff()
 error=float((factor-formula).abs().max().max())
 if error>1e-7:raise ValueError('factor formula mismatch')
 def map_factor(values):
  return pd.DataFrame([{'date':d,'target_weights_json':json.dumps({s:.2 for s in row[row>0].sort_values(ascending=False,kind='stable').index[:4]})} for d,row in values.shift(1).iterrows()])
 ledgers={k:stock_targets(close,cfg,k).set_index('date').reindex(dates).reset_index() for k in cfg['strategies']}
 ledgers['VIBE_ALPHA101_012']=map_factor(factor).set_index('date').reindex(dates).reset_index()
 # Future prices cannot alter previously generated factor/mapping outputs.
 cutoff=close.index[len(close)//2];mutated=factor.copy();mutated.loc[mutated.index>cutoff]=mutated.loc[mutated.index>cutoff]*-7
 a=map_factor(factor);b=map_factor(mutated)
 if not a[a.date<=cutoff].equals(b[b.date<=cutoff]):raise ValueError('future mapping leak')
 benchmark=contract['benchmark']
 for weight in (0.8,1.0):ledgers['BENCHMARK_HOLD_'+str(weight)] = pd.DataFrame({'date':dates,'target_weights_json':[json.dumps({benchmark:weight})]*len(dates)})
 assumptions=cfg['US_execution_assumptions'] if market=='US' else cfg['execution_assumptions']
 spec=ExecutionSpec(**{k:v for k,v in assumptions.items() if k!='minimum_order_nav_fraction'},minimum_order_notional_krw=cfg[market]['initial_capital']*assumptions['minimum_order_nav_fraction'])
 rows={}
 for name,ledger in ledgers.items():
  nav,fills,intents=replay_targets(panel,dates,ledger,cfg[market]['initial_capital'],spec,buy_hold=name.startswith('BENCHMARK_HOLD'))
  row=metrics(nav,fills,cfg[market]['initial_capital']);row['cost_in_currency']=row.pop('cost_krw');row['currency']=cfg[market]['currency']
  cash=float(cfg[market]['initial_capital']);held={};cash_error=nav_error=0.;byday={d:g for d,g in fills.groupby('date')} if len(fills) else {}
  for observation in nav.itertuples():
   for f in byday.get(observation.date,pd.DataFrame()).itertuples():
    cash+=(-f.quantity*f.fill_price_krw-f.fee_krw) if f.side=='BUY' else (f.quantity*f.fill_price_krw-f.fee_krw)
    held[f.ticker]=held.get(f.ticker,0)+(f.quantity if f.side=='BUY' else -f.quantity)
   recomputed=cash+sum(q*panel['close'].loc[observation.date,s] for s,q in held.items())
   cash_error=max(cash_error,abs(cash-observation.cash_krw));nav_error=max(nav_error,abs(recomputed-observation.nav_krw))
  if max(cash_error,nav_error)>1e-5:raise ValueError('ledger mismatch')
  row['independent_ledger_max_error']=max(cash_error,nav_error)
  nav.to_csv(folder/(name+'_nav.csv'),index=False);fills.to_csv(folder/(name+'_fills.csv'),index=False);ledger.to_csv(folder/(name+'_targets.csv'),index=False)
  rows[name]=row
 # Check old reference reproduction; don't rewrite the frozen old results.
 old=ROOT/('runtime/task3/us/final' if market=='US' else 'runtime/task3/kr/run3')/'comparison/comparison.json';prior=json.loads(old.read_text())
 reproduction={k:rows[k]['return_pct']-prior['results'][k]['return_pct'] for k in cfg['strategies']}
 if any(abs(v)>1e-6 for v in reproduction.values()):raise ValueError('frozen baseline mismatch')
 result['markets'][market]={'start':contract['start'],'end':contract['end'],'sessions':len(dates),'input_hash':digest(contract['files']),'results':rows,'factor_formula_error':error,'future_mapping_test':'PASSED','old_reference_return_error_pp':reproduction}
(out/'results.json').write_text(json.dumps(result,indent=2,allow_nan=False));print(json.dumps(result,indent=2))
