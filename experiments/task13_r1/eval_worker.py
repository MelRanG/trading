from pathlib import Path
import json,sys,subprocess,hashlib,os,runpy,contextlib
import pandas as pd,numpy as np
from qlib.contrib.eva.alpha import calc_ic
out=Path('/work');H=20;results={}
for market in ['US','KR']:
 d=pd.read_hdf('/inputs/'+market+'_train.h5',key='data');days=d.index.get_level_values(0).unique().sort_values()
 def run(frame,tag):
  folder=out/(market+'_'+tag);folder.mkdir(exist_ok=True);frame.to_hdf(folder/'daily_pv.h5',key='data');previous=os.getcwd()
  try:
   os.chdir(folder)
   with (folder/'stderr.txt').open('w') as log,contextlib.redirect_stderr(log):runpy.run_path('/candidate/factor.py',run_name='__main__')
  finally:os.chdir(previous)
  v=pd.read_hdf(folder/'result.h5',key='data');v=v if isinstance(v,pd.Series) else v.iloc[:,0];assert v.sort_index().index.equals(frame.index);return v.sort_index()
 raw=run(d,'full');cut=days[len(days)//2];prefix=d.loc[d.index.get_level_values(0)<=cut];v=run(prefix,'prefix');pd.testing.assert_series_equal(raw.reindex(prefix.index),v,check_exact=False,rtol=1e-8,atol=1e-10)
 # future perturbation of values; causal prefix must remain unchanged.
 changed=d.copy();future=changed.index.get_level_values(0)>cut
 for c in ['$open','$high','$low','$close']:changed.loc[future,c]*=1.7
 changed.loc[future,'$volume']*=2.3;changed['$return']=changed['$close'].groupby(level=1).pct_change(fill_method=None);v=run(changed,'perturb');pd.testing.assert_series_equal(raw.reindex(prefix.index),v.reindex(prefix.index),check_exact=False,rtol=1e-8,atol=1e-10)
 good=np.isfinite(d.iloc[:,:5]).all(axis=1).unstack();past=good.rolling(63,min_periods=63).sum().eq(63);past.iloc[:63]=False;op=d['$open'].unstack();target=op.shift(-21)/op.shift(-1)-1
 for j in range(1,22):target=target.where(good.shift(-j,fill_value=False))
 score=raw.unstack().where(past);pair=pd.concat([score.stack(future_stack=True).rename('score'),target.stack(future_stack=True).rename('label')],axis=1).dropna();n=pair.groupby(level=0).size();pair=pair.loc[pair.index.get_level_values(0).isin(n[n>=50].index)];ic,ric=calc_ic(pair.score,pair.label);spread=[]
 for day,g in pair.groupby(level=0):
  g=g.sort_values('score');k=len(g)//5;spread.append(g.label.iloc[-k:].mean()-g.label.iloc[:k].mean())
 close=d['$close'].unstack();baselines={'MOM20':close/close.shift(20)-1,'REV5':-(close/close.shift(5)-1),'LOWVOL20':-close.pct_change(fill_method=None).rolling(20).std()};comparisons={}
 for name,b in baselines.items():
  z=pair.join(b.stack(future_stack=True).rename('base')).dropna();corr=[];resics=[]
  for _,g in z.groupby(level=0):
   if len(g)<50:continue
   ranks=g[['score','base','label']].rank(pct=True);corr.append(ranks.score.corr(ranks.base));X=np.c_[np.ones(len(g)),ranks.base];res=ranks.score-X@np.linalg.lstsq(X,ranks.score,rcond=None)[0];resics.append(np.corrcoef(np.asarray(res),ranks.label.to_numpy())[0,1])
  bi,br=calc_ic(z.base,z.label);comparisons[name]={'RankIC':float(br.mean()),'rank_correlation':float(np.mean(corr)),'residual_rank_correlation_with_target':float(np.mean(resics))}
 raw.to_csv(out/(market+'_raw_scores.csv'));pair.to_csv(out/(market+'_paired.csv'));results[market]={'IC':float(ic.mean()),'RankIC':float(ric.mean()),'spread':float(np.mean(spread)),'dates':len(ric),'paired_rows':len(pair),'baseline':comparisons,'prefix_and_future_perturbation':True,'scope':'FIT_ONLY_NO_OUTER_RESULTS','H':20}
 # Full HDF intermediates are reproducible temporary inputs, not retained copies.
 for folder in out.glob(market+'_*'):
  if folder.is_dir():
   for p in folder.glob('*.h5'):p.unlink()
(out/'metrics.json').write_text(json.dumps(results,indent=2));print(json.dumps(results))
