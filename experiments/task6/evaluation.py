"""Offline, frozen common-cost diagnostics. No research-worker final access."""
from pathlib import Path
import argparse,json,hashlib,subprocess,sys,shutil
import pandas as pd
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'))
from quant_harness.investment.research import replay_targets,metrics
from quant_harness.investment.equities import stock_targets
from quant_harness.v77_corrected_price_allocation.engine import ExecutionSpec
BASE=ROOT/'runtime/task6';EXT=Path('/home/ansy/app/quant-diligence')
def load_frames(market,split):
 folders=['worker_train','evaluator_validation']+(['private_final'] if split=='final' else [])
 frames={}
 for path in sorted((BASE/'worker_train').glob(market+'*.csv')):
  pieces=[pd.read_csv(BASE/f/path.name,parse_dates=['date']).set_index('date') for f in folders]
  frame=pd.concat(pieces).sort_index();assert not frame.index.has_duplicates
  frames[path.stem]=frame
 return frames

def make_hdf(frames,destination):
 rows=[]
 for s,f in frames.items():
  if 'BENCHMARK' in s:continue
  frame=f[['open','high','low','close','volume']].rename(columns=lambda c:'$'+c).copy();frame.index.name='datetime';frame['instrument']=s;frame=frame.set_index('instrument',append=True);frame['$return']=frame['$close'].pct_change(fill_method=None);rows.append(frame)
 pd.concat(rows).sort_index().to_csv(destination.with_suffix('.csv'))

def factor_values(engine,attempt,market,split,frames):
 candidate=BASE/'candidates'/engine/f'attempt{attempt}'
 directory=BASE/'evaluation'/split/market/f'{engine}{attempt}';directory.mkdir(parents=True,exist_ok=True)
 inputdir=directory/'input';inputdir.mkdir(exist_ok=True);make_hdf(frames,inputdir/'panel.h5')
 env=EXT/('vibe-env' if engine=='vibe' else f'task6-{engine}-env')
 cmd=['docker','run','--rm','--network=none','--cap-drop=ALL','--security-opt','no-new-privileges','--memory=4g','--cpus=2','--pids-limit=256','--user','1000:1000','-e','HOME=/work','-e','PYTHONDONTWRITEBYTECODE=1','-v',f'{env}:/venv:ro','-v',f'{candidate}:/candidate:ro','-v',f'{inputdir}:/input:ro','-v',f'{directory}:/work','-v',f'{ROOT}/experiments/task6:/code:ro','-w','/work','quant-research-task6:local','/venv/bin/python','/code/evaluate_worker.py',engine]
 result=subprocess.run(cmd,capture_output=True,text=True,timeout=230);(directory/'worker.log').write_text(result.stdout+result.stderr)
 if result.returncode:raise RuntimeError(f'{engine}: {result.stderr[-2000:]}')
 values=pd.read_csv(directory/'factor_values.csv',parse_dates=['datetime']).set_index(['datetime','instrument']).iloc[:,0].unstack('instrument')
 return values

def common(frames,signals,market,split,out):
 cfg=json.loads((ROOT/'config/task3_equity_contract.json').read_text());initial=cfg[market]['initial_capital'];bench=market+'_BENCHMARK';names=[s for s in frames if s!=bench]
 close=pd.DataFrame({s:f.close for s,f in frames.items()});opens=pd.DataFrame({s:f.open for s,f in frames.items()});adv=pd.DataFrame({s:(f.close*f.volume).rolling(20,min_periods=20).mean().shift(1) for s,f in frames.items()})
 panel={'close':close,'open':opens,'adv20_d1':adv};start,end=('2025-01-01','2025-12-31') if split=='validation' else ('2026-01-01','2026-12-31')
 eligible=close.dropna().index;dates=eligible[(eligible>=start)&(eligible<=end)];assert len(dates)>100
 ledgers={k:stock_targets(close[names],cfg,k).set_index('date').reindex(dates).reset_index() for k in cfg['strategies']}
 # Hold all named stocks at equal weight with 80% initial exposure, no daily rebalance.
 ledgers['EQUAL_STOCK_BUY_HOLD']=pd.DataFrame({'date':dates,'target_weights_json':[json.dumps({s:.8/len(names) for s in names})]*len(dates)})
 for name,values in signals.items():
  ledgers[name]=pd.DataFrame([{'date':d,'target_weights_json':json.dumps({s:.2 for s in row[row>0].sort_values(ascending=False,kind='stable').index[:4]})} for d,row in values.reindex(columns=names).shift(1).reindex(dates).iterrows()])
 for weight in (.8,1.):ledgers['BENCHMARK_HOLD_'+str(weight)]=pd.DataFrame({'date':dates,'target_weights_json':[json.dumps({bench:weight})]*len(dates)})
 assumptions=cfg['US_execution_assumptions'] if market=='US' else cfg['execution_assumptions'];spec=ExecutionSpec(**{k:v for k,v in assumptions.items() if k!='minimum_order_nav_fraction'},minimum_order_notional_krw=initial*assumptions['minimum_order_nav_fraction'])
 results={};paths={}
 for name,ledger in ledgers.items():
  nav,fills,intents=replay_targets(panel,dates,ledger,initial,spec,buy_hold='HOLD' in name)
  row=metrics(nav,fills,initial);row['cost_in_currency']=row.pop('cost_krw');row['currency']=cfg[market]['currency']
  # Independent reconstruction from fills, never from target weights.
  cash=float(initial);held={};error=0.;byday={d:g for d,g in fills.groupby('date')} if len(fills) else {}
  for obs in nav.itertuples():
   for f in byday.get(obs.date,pd.DataFrame()).itertuples():
    cash+=(-f.quantity*f.fill_price_krw-f.fee_krw) if f.side=='BUY' else f.quantity*f.fill_price_krw-f.fee_krw;held[f.ticker]=held.get(f.ticker,0)+(f.quantity if f.side=='BUY' else -f.quantity)
   error=max(error,abs(cash-obs.cash_krw),abs(cash+sum(q*close.loc[obs.date,s] for s,q in held.items() if q)-obs.nav_krw))
  assert error<1e-5;row['independent_ledger_error']=error
  exposure=[]
  for obs in nav.itertuples():exposure.append(sum(q*close.loc[obs.date,s] for s,q in json.loads(obs.holdings_json).items() if q)/obs.nav_krw)
  row['mean_exposure']=float(np.mean(exposure));row['maximum_close_exposure']=float(max(exposure))
  nav.to_csv(out/(name+'_nav.csv'),index=False);fills.to_csv(out/(name+'_fills.csv'),index=False);ledger.to_csv(out/(name+'_targets.csv'),index=False)
  paths[name]=nav.set_index('date').nav_krw;daily=paths[name].pct_change().fillna(paths[name].iloc[0]/initial-1)
  trend=close[bench].shift(1)>close[bench].rolling(120,min_periods=120).mean().shift(1)
  row['regime_daily_mean_bps']={str(k):float(daily[trend.reindex(dates).eq(k)].mean()*1e4) if trend.reindex(dates).eq(k).any() else None for k in [True,False]}
  # Realized next-session intraday label, all labels contained within evaluation split.
  if name in signals:
   signal=signals[name].reindex(columns=names);label=close[names].div(opens[names]).sub(1).shift(-1);valid=dates[:-1];ics=[]
   for d in valid:
    pair=pd.concat([signal.loc[d],label.loc[d]],axis=1).dropna()
    if len(pair)>=5 and pair.iloc[:,0].nunique()>1 and pair.iloc[:,1].nunique()>1:ics.append(pair.iloc[:,0].rank().corr(pair.iloc[:,1].rank()))
   row['IC']=float(np.mean(ics)) if ics else None;row['ICIR']=float(np.mean(ics)/np.std(ics)*np.sqrt(252)) if ics and np.std(ics)>0 else None;row['ic_sessions']=len(ics)
  results[name]=row
 for name,row in results.items():
  row['excess_benchmark_pp']=row['return_pct']-results['BENCHMARK_HOLD_0.8']['return_pct']
  if name in signals:
   ref=paths['MOM63_STOCKS'].pct_change().dropna();delta=paths[name].pct_change().dropna()-ref
   months=delta.groupby(delta.index.to_period('M')).sum().to_numpy();rng=np.random.default_rng(6013);samples=rng.choice(months,size=(1000,len(months)),replace=True).mean(axis=1)*12*100
   row['annualized_paired_excess_vs_mom_bootstrap95_pp']=np.quantile(samples,[.025,.975]).tolist()
 report={'kind':'RETROSPECTIVE_CURRENT_COHORT_DIAGNOSTIC_NOT_PIT_ALPHA_OR_FORWARD','market':market,'split':split,'sessions':len(dates),'start':str(dates[0]),'end':str(dates[-1]),'results':results,'input_hash':hashlib.sha256(''.join(hashlib.sha256(f.to_csv().encode()).hexdigest() for f in frames.values()).encode()).hexdigest()};(out/'results.json').write_text(json.dumps(report,indent=2,allow_nan=False));return report

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--split',choices=['validation','final'],default='validation');p.add_argument('--attempts',type=int,default=1);a=p.parse_args()
 if a.split=='final':
  freeze=json.loads((BASE/'candidate_freeze.json').read_text())
  for name,h in freeze['candidate_files'].items():
   if hashlib.sha256((BASE/name).read_bytes()).hexdigest()!=h:raise ValueError('candidate changed after freeze')
  if hashlib.sha256(Path(__file__).read_bytes()).hexdigest()!=freeze['evaluation_sha256']:raise ValueError('evaluator changed after freeze')
  if any((BASE/'evaluation/final'/m/'results.json').exists() for m in ['US','KR']):raise ValueError('final already evaluated; do not reuse for optimization')
 for market in ['US','KR']:
  frames=load_frames(market,a.split);signals={}
  for engine in ['vibe','quanta','rd']:
   for attempt in range(a.attempts):signals[f'{engine.upper()}{attempt}']=factor_values(engine,attempt,market,a.split,frames)
  if a.attempts==2:
   for specialist in ['QUANTA','RD']:
    left=signals['VIBE1'].where(signals['VIBE1']>0).rank(axis=1,pct=True).fillna(0)
    right=signals[specialist+'1'].where(signals[specialist+'1']>0).rank(axis=1,pct=True).fillna(0)
    signals['VIBE_PLUS_'+specialist]=.5*left+.5*right
  close=pd.DataFrame({s:f.close for s,f in frames.items() if 'BENCHMARK' not in s});volume=pd.DataFrame({s:f.volume for s,f in frames.items() if 'BENCHMARK' not in s});signals['VIBE_ALPHA101_012']=-np.sign(volume.diff())*close.diff()
  out=BASE/'evaluation'/a.split/market;out.mkdir(parents=True,exist_ok=True);common(frames,signals,market,a.split,out)
  print(market,a.split,'DONE',flush=True)
