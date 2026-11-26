"""Independent arithmetic inspection of original engine fills, cash and NAV."""
from pathlib import Path
import json
import pandas as pd
ROOT=Path(__file__).resolve().parents[2];WORK=Path('/home/ansy/app/quant-diligence/vibe-work');out={}
for market in ('US','KR'):
 directory=WORK/'poc'/(market+'_native')/'artifacts';fills=[json.loads(x) for x in (directory/'fills.jsonl').read_text().splitlines() if x]
 equity=pd.read_csv(directory/'equity.csv',parse_dates=['timestamp']);positions={};cash=100000. if market=='US' else 10000000.;error=0.
 frames={p.stem.removeprefix('ohlcv_'):pd.read_csv(p,index_col=0,parse_dates=True) for p in directory.glob('ohlcv_*.csv')}
 byday={}
 for row in fills:byday.setdefault(pd.Timestamp(row['timestamp']),[]).append(row)
 for row in equity.itertuples():
  for fill in byday.get(row.timestamp,[]):
   q=float(fill['signed_quantity']);cash-=q*float(fill['execution_price'])+float(fill['fee']);positions[fill['symbol']]=positions.get(fill['symbol'],0)+q
  value=cash+sum(q*float(frames[s].loc[row.timestamp,'close']) for s,q in positions.items() if abs(q)>1e-10)
  error=max(error,abs(value-row.equity))
 native=pd.read_csv(directory/'target_positions.csv',index_col=0,parse_dates=True);native.columns=[s.removesuffix('.US') for s in native.columns]
 ledger=pd.read_csv(ROOT/'runtime/task6_pre/comparison'/market/'VIBE_ALPHA101_012_targets.csv',parse_dates=['date'])
 expected=pd.DataFrame([json.loads(x) for x in ledger.target_weights_json],index=ledger.date).reindex(columns=native.columns).fillna(0)
 difference=(native.reindex(expected.index)-expected).abs()
 out[market]={'native_return_pct':float((equity.equity.iloc[-1]/(100000 if market=='US' else 10000000)-1)*100),
  'fills':len(fills),'fees_in_currency':sum(float(f['fee']) for f in fills),'independent_nav_max_error':error,
  'signal_target_max_abs_difference':float(difference.max().max()),'target_mismatch_cells':int((difference>1e-10).sum().sum()),
  'native_execution_not_same_cost':True,'differences':['US native zero commission and fractional .01 shares','QH D1 NAV/close sizing vs native opening event sizing/rebalance lifecycle','Native fixed slip/tick vs shared D1 ADV impact/minimum order/participation', 'Native KR tick/limit-price rules present; common research replay does not model these']}
 if error>1e-4:raise ValueError('native NAV arithmetic discrepancy')
path=ROOT/'runtime/task6_pre/evidence/native_inspection.json';path.write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
