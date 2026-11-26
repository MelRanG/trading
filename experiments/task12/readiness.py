"""Bounded existing-file readiness audit, labels and regimes. No strategy test."""
from pathlib import Path
import json,hashlib,datetime,collections,ast
import pandas as pd,numpy as np
R=Path(__file__).resolve().parents[2];B=R/'runtime/task12';C=json.loads((Path(__file__).parent/'contract.json').read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(name,x):
 p=B/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False,default=str)+'\n')
def load(m):
 return {p.stem:pd.read_csv(p,index_col='date',parse_dates=True) for p in sorted((R/'runtime/task10/tape'/m).glob('*.csv'))}
def labels(frames,market,H,cutoff):
 days=frames[market+'_BENCHMARK'].loc[:cutoff].index
 opens=pd.DataFrame({s:f.open.reindex(days) for s,f in frames.items() if 'BENCHMARK' not in s})
 y=opens.shift(-H-1)/opens.shift(-1)-1
 # All intermediate market marks must be present, even when an endpoint exists.
 good=pd.DataFrame(np.isfinite(opens)&(opens>0),index=days,columns=opens.columns)
 for step in range(1,H+2):y=y.where(good.shift(-step,fill_value=False))
 target_end=pd.Series(days,index=days).shift(-H-1);return y,target_end

def regimes(close):
 a=C['regime']['AS_OF'];e=C['regime']['EX_POST'];ret=close.pct_change(fill_method=None);r63=close/close.shift(63)-1;dd=close/close.rolling(63,min_periods=63).max()-1;ma=close.rolling(a['MA'],min_periods=a['MA']).mean();vol=ret.rolling(20,min_periods=20).std(ddof=0)*np.sqrt(252)
 crash=(close/close.shift(5)-1)<=a['crash_return5'];rebound=(close/close.shift(10)-1>=a['rebound_return10'])&(dd.rolling(20,min_periods=20).min()<=a['prior20_min_drawdown63']);up=(r63>=a['return63_up'])&(close>=ma);down=(r63<=a['return63_down'])&(close<ma);side=r63.abs()<=a['sideways_abs_return63']
 asof=pd.Series(np.select([crash,rebound,up,down,side],['CRASH','REBOUND','UP','DOWN','SIDEWAYS'],default='TRANSITION'),index=close.index).where(ma.notna(),'WARMUP')
 f20=close.shift(-20)/close-1;f5=close.shift(-5)/close-1
 post=pd.Series(np.select([f5<=e['crash_next5'],(dd<=-.15)&(f20>=e['up']),f20>=e['up'],f20<=e['down'],f20.abs()<=e['sideways_abs_future20']],['CRASH','REBOUND','UP','DOWN','SIDEWAYS'],default='TRANSITION'),index=close.index).where(f20.notna(),'PENDING')
 return pd.DataFrame({'close':close,'AS_OF_REGIME':asof,'EX_POST_REGIME':post,'AS_OF_HIGH_VOL':vol>=a['volatility20_annual_high'],'EX_POST_HIGH_VOL':vol.shift(-20)>=a['volatility20_annual_high']})
def runs(s):
 g=s.ne(s.shift()).cumsum();out=[]
 for _,v in s.groupby(g):out.append({'label':v.iloc[0],'start':str(v.index[0].date()),'end':str(v.index[-1].date()),'sessions':len(v)})
 return sorted(out,key=lambda x:(-x['sessions'],x['start']))

def main():
 B.mkdir(exist_ok=True);assets=json.loads((R/'runtime/task10/universe.json').read_text());by={};refs=[]
 for m in ['US','KR']:
  fs=load(m);days=fs[m+'_BENCHMARK'].index;rows=[]
  for a in [x for x in assets if x['market']==m]:
   p=R/'runtime/task10/tape'/m/(a['alias']+'.csv');f=fs[a['alias']].reindex(days);q=R/'runtime/task10/data'/a['symbol']/'quality.json';z=json.loads(q.read_text());resolution=json.loads((q.parent/'resolution.json').read_text());splits=z.get('declared_actions',{}).get('splits',{});active_splits=[]
   for event in splits.values():
    day=datetime.datetime.fromtimestamp(event['date'],datetime.timezone.utc).date().isoformat()
    if str(days.min().date())<=day<=str(days.max().date()):active_splits.append(event)
   row={'alias':a['alias'],'symbol':a['symbol'],'role':a['role'],'path':str(p.relative_to(R)),'sha256':sha(p),'start':str(days.min().date()),'end':str(days.max().date()),'rows':len(f),'missing_OHLCV':int(f[['open','high','low','close','volume']].isna().any(axis=1).sum()),'V87':resolution['V87'],'first_trade_epoch':z.get('meta',{}).get('firstTradeDate'),'split_events_in_window':active_splits,'dividend_events':len(z.get('declared_actions',{}).get('dividends',{})),'historical_membership':'UNVERIFIED_CURRENT_SURVIVOR_COHORT','historical_receipt':'BACKFILL_OBSERVED_2026_11_NOT_ORIGINAL_PIT_RECEIPT','actions':'PARTIAL_PROVIDER_EVENTS_PRICE_ONLY'};rows.append(row);refs.append({'path':str(p.relative_to(R)),'sha256':sha(p)})
  horizons={}
  for H in C['labels']['horizons']:
   y,end=labels(fs,m,H,str(days.max().date()));valid=y.iloc[63:];finite=int(valid.notna().sum().sum());boundary=pd.Timestamp(C['split']['fit_end']);fit=(y.index<=boundary)&end.lt(boundary).to_numpy()&(np.arange(len(y))>=63);validation=y.index>=pd.Timestamp(C['split']['diagnostic_validation_start']);horizons[str(H)]={'valid_symbol_sessions_after63warmup':finite,'eligible_dates_min8_names':int((valid.notna().sum(axis=1)>=8).sum()),'fit_labels_after63warmup_end_before_boundary':int(y.loc[fit].notna().sum().sum()),'diagnostic_validation_labels':int(y.loc[validation].notna().sum().sum()),'last_mature_signal':str(y.dropna(how='all').index.max().date()),'trailing_unmatured_sessions':H+1,'label_hash':hashlib.sha256(y.to_json(date_format='iso').encode()).hexdigest()}
  by[m]={'stocks':sum(x['role']=='stock' for x in rows),'sessions':len(days),'start':str(days.min().date()),'end':str(days.max().date()),'assets':rows,'horizons':horizons,'S_status':'READY_PRICE_ONLY_LIMITED_RESEARCH' if not any(x['split_events_in_window'] for x in rows) else 'PARTIAL_ACTION_RECONCILIATION_REQUIRED','B_status':'BLOCKED_N_LT50_AND_PIT_MEMBERSHIP_ACTIONS_INCOMPLETE'}
 # Inspect immutable library metadata without importing or economically evaluating 478 factors.
 zoo=Path('/home/ansy/app/quant-diligence/vibe-original/agent/src/factors/zoo');meta=[];bad=[]
 for p in sorted(zoo.rglob('*.py')):
  if p.name.startswith('_'):continue
  try:
   tree=ast.parse(p.read_text());node=next((n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='__alpha_meta__' for t in n.targets)),None)
   if node is None:continue
   d=ast.literal_eval(node);cols=set(d['columns_required']);available={'open','high','low','close','volume'};missing=sorted(cols-available);extra=d.get('extras_required',[]);sectors=d.get('requires_sector',False);d.update(source=str(p),source_hash=sha(p),missing_input=missing,admissible_price_only=not missing and not extra and not sectors);meta.append(d)
  except Exception as exc:bad.append({'path':str(p),'error_type':type(exc).__name__})
 dump('factor_catalog.json',{'metadata':meta,'parse_failures':bad,'catalog_is_not_independent_strategies':True,'actual_computation':'Only representative offline probes, no economic backtests'})
 # Index regime context: old broad index first; overlap conflicts remain separate series.
 series={}
 proxy=R/'runtime/task6/data/accepted/SPY.csv';pf=pd.read_csv(proxy,index_col='date',parse_dates=True);series['US_SPY_PROXY_2022_2026']=(pf.close,{'path':str(proxy.relative_to(R)),'sha256':sha(proxy),'authority':'ADJUSTED_ETF_PROXY_NOT_SP500_INDEX_OR_PIT_MARKET_MEMBERSHIP'})
 historical=R/'data/all_prices_long_v62_9_expanded.csv';df=pd.read_csv(historical,dtype={'ticker':str},low_memory=False)
 index=df[df.ticker.isin(['KS11','^KS11','^GSPC','GSPC'])]
 for name,g in index.groupby('ticker'):
  ser=g.assign(date=pd.to_datetime(g.date)).drop_duplicates('date',keep=False).set_index('date').close.sort_index();series['LEGACY_'+name]=(ser,{'path':str(historical.relative_to(R)),'sha256':sha(historical),'authority':'LEGACY_PRICE_INDEX_CONTEXT_NOT_CANONICAL_REPLACEMENT'})
 for m,sym in [('US','^GSPC'),('KR','^KS11')]:
  p=R/'runtime/task9_1/evaluator_only/2025-06-30'/sym/'bars.csv';f=pd.read_csv(p,index_col='date',parse_dates=True);series[m+'_2025_2026']=(f.close,{'path':str(p.relative_to(R)),'sha256':sha(p),'authority':'PREVIOUSLY_EXPOSED_INDEX_BACKFILL_PARTIAL'})
  p2=R/'runtime/task10/evaluation'/(m+'_index.csv');f2=pd.read_csv(p2,index_col='date',parse_dates=True);series[m+'_2026_TAIL']=(f2.close,{'path':str(p2.relative_to(R)),'sha256':sha(p2),'authority':'SEPARATE_SNAPSHOT_NO_SILENT_STITCH'})
 regimes_out={}
 for key,(close,source) in series.items():
  t=regimes(close);counts={k:{str(x):int(v) for x,v in t[k].value_counts().items()} for k in ['AS_OF_REGIME','EX_POST_REGIME','AS_OF_HIGH_VOL']};rs=runs(t['EX_POST_REGIME']);regimes_out[key]={'source':source,'start':str(close.index.min().date()),'end':str(close.index.max().date()),'rows':len(close),'counts':counts,'longest_ex_post_ranges':rs[:20],'states':{state:[r for r in rs if r['label']==state][:2] for state in ['UP','DOWN','CRASH','REBOUND','SIDEWAYS']},'years':sorted(set(close.index.year.astype(int))),'ex_post_not_research_input':True}
  t.to_csv(B/(key+'_regimes.csv'),index_label='date')
 dump('regime_coverage.json',regimes_out)
 dump('readiness.json',{'scope':'S_PRICE_VOLUME_DIAGNOSTIC_NOT_B_ECONOMIC_CONFIRMATION','contract_hash':sha(Path(__file__).parent/'contract.json'),'markets':by,'feature_only_extended_data':'Task6 adjusted bars reference only; do not mix with raw trade prices','new_requests':0,'LLM_calls':0,'training_jobs':0,'source_references':refs,'catalog_summary':{'factors':len(meta),'price_only_declared':sum(d['admissible_price_only'] for d in meta),'themes':dict(collections.Counter(k for d in meta for k in d['theme'])),'missing_columns':dict(collections.Counter(k for d in meta for k in d['missing_input'])),'sector_required':sum(d.get('requires_sector',False) for d in meta),'parse_failures':bad}})
 print(json.dumps({'markets':{m:{k:v for k,v in d.items() if k!='assets'} for m,d in by.items()},'library':len(meta),'price_only_declared':sum(d['admissible_price_only'] for d in meta),'index_series':list(series)},ensure_ascii=False))
if __name__=='__main__':main()
