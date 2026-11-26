"""Small missing descriptive tables, no research or new statistical selection."""
from pathlib import Path
import json
import pandas as pd,numpy as np
from stats_eval import corr,block_mean
R=Path(__file__).resolve().parents[2];B=R/'runtime/task14';S=R/'runtime/task13'
model={};episodes=[]
for m in ['US','KR']:
 data={n:pd.read_csv(S/'models'/m/(n+'_paired.csv'),parse_dates=['datetime']).set_index(['datetime','instrument']) for n in ['RD_SMALL','ZERO','QLIB_RIDGE','QLIB_TREE']};rows={}
 for name,f in data.items():
  stats=[]
  for d,g in f.groupby(level=0):stats.append({'date':d,'IC':corr(g.prediction,g.target),'RankIC':corr(g.prediction,g.target,True),'mae_zero_minus_candidate':g.target.abs().mean()-(g.prediction-g.target).abs().mean()})
  z=pd.DataFrame(stats).set_index('date');old=json.loads((S/'models'/m/'metrics.json').read_text())[name]
  ic=z.IC.mean() if z.IC.notna().any() else None;ric=z.RankIC.mean() if z.RankIC.notna().any() else None
  if ric is not None:assert abs(ric-old['RankIC'])<1e-12
  rows[name]={'IC':ic,'RankIC':ric,'native_record_IC':old['IC'],'Pearson_delta_vs_native':ic-old['IC'] if ic is not None else None,'constant_or_near_constant_dates':int(z.IC.isna().sum()),'IC_parity_note':'Task14 float64 CSV and explicit constant guard; rawinmemory float32 tiny drift or constant-series pseudocorrelation excluded, original Task13 remains immutable','mae_zero_minus_candidate':block_mean(z.mae_zero_minus_candidate,5)}
 model[m]=rows
 p=data['RD_SMALL'];ds=pd.read_csv(S/'adjusted_inputs'/(m+'.csv'),parse_dates=['datetime']).datetime.drop_duplicates().sort_values();ds=pd.DatetimeIndex(ds)
 reg=pd.read_csv(R/'runtime/task12'/('US_SPY_PROXY_2022_2026_regimes.csv' if m=='US' else 'LEGACY_KS11_regimes.csv'),index_col='date',parse_dates=True);dates=p.index.get_level_values(0).unique().sort_values()
 for axis in ['AS_OF_REGIME','EX_POST_REGIME','AS_OF_HIGH_VOL']:
  series=reg[axis].astype(str);runs=series.ne(series.shift()).cumsum();tags=reg[axis].reindex(dates).fillna('NO_REGIME_DATA')
  for tag in tags.unique():
   ix=dates[tags==tag];raw=runs.reindex(ix).dropna().unique();spans=[]
   for run in raw:
    rr=ix[runs.reindex(ix)==run];a=int(ds.searchsorted(rr.min()));b=int(ds.searchsorted(rr.max()))+5
    if spans and a<=spans[-1][1]:spans[-1]=(spans[-1][0],max(b,spans[-1][1]))
    else:spans.append((a,b))
   episodes.append({'id':'RD_SMALL','market':m,'axis':axis,'group':str(tag),'dates':len(ix),'names':int(p.loc[(slice(ix.min(),ix.max()),slice(None)),:].index.get_level_values(1).nunique()),'raw_runs':len(raw),'label_extended_episode_count':len(spans)})
# Concentration diagnostics explain positive means without monotonic ranking.
f=pd.read_csv(B/'factor_daily.csv',parse_dates=['date']);q=f[(f.id=='V_ROC20')&(f.market=='KR')];con=pd.read_csv(B/'factor_tail_contributions.csv',parse_dates=['date']);c=con[(con.id=='V_ROC20')&(con.market=='KR')];n=len(q);symbols={a['alias']:a['symbol'] for a in json.loads((R/'runtime/task10/universe.json').read_text())};names=c.groupby('instrument').weighted_contribution.sum()/n
panel=pd.read_csv(S/'nominal_inputs/KR/panel.csv',parse_dates=['datetime']).set_index(['datetime','instrument']);opens=panel.open.unstack();days=opens.index;tail=[]
for _,r in c.reindex(c.weighted_contribution.abs().sort_values(ascending=False).index).head(10).iterrows():
 i=days.get_loc(r.date);a,b=days[i+1],days[i+21];base=opens.at[a,r.instrument];last=opens.at[b,r.instrument];assert np.isclose(last/base-1,r.target)
 tail.append({'signal':str(r.date.date()),'alias':r.instrument,'symbol':symbols[r.instrument],'entry_open_date':str(a.date()),'exit_open_date':str(b.date()),'entry_open':base,'exit_open':last,'H20_return':r.target,'source':'Task13 nominal input; hashes preserved; no fresh exchange/corporate-action verification','identity_caveat':'Task12 firstTradeDate missing for KR015/009150; raw price identity/actions remain partial'})
x={'KR_V_ROC20':{'dates':n,'average_top_mean':q.top_mean.mean(),'average_bottom_mean':q.bottom_mean.mean(),'average_within_top_median':q.top_median.mean(),'average_within_bottom_median':q.bottom_median.mean(),'median_daily_top_mean':q.top_mean.median(),'median_daily_bottom_mean':q.bottom_mean.median(),'median_daily_spread':q.spread.median(),'mean_daily_spread':q.spread.mean(),'positive_spread_fraction':(q.spread>0).mean(),'top5_abs_dates_share_of_total_signed_spread':q.loc[q.spread.abs().nlargest(5).index].spread.sum()/q.spread.sum(),'contributions':[{'alias':s,'symbol':symbols[s],'mean_contribution':v,'share_of_net':v/q.spread.mean()} for s,v in names.reindex(names.abs().sort_values(ascending=False).index).head(5).items()],'extreme_return_endpoint_audit':tail,'bin_definition':'Original spread uses equal floor(N/5) top/bottom; full fivebins elsewhere assign remainder tobins, so Q5 mean can differ from fixed-k top mean.'},'RD_native_metric_parity':model,'RD_regime_episodes':episodes,'zero_new_models_or_data':True}
(B/'supplement.json').write_text(json.dumps(x,indent=2,default=str,allow_nan=False)+'\n');print('SUPPLEMENT_PASS')
