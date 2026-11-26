"""Evaluator-only descriptive diagnostics. No LLM, retraining or portfolio PnL."""
from pathlib import Path
import json,hashlib
import pandas as pd,numpy as np
from qlib.contrib.eva.alpha import calc_ic
B=Path('/evidence');out=Path('/work');contract=json.loads((B/'contract.json').read_text());rows=[];correlations={};parity=[]
def metrics(s,y,mask):
 s=s.where(mask);y=y.where(mask);valid=np.isfinite(s)&np.isfinite(y);s=s.where(valid);y=y.where(valid);ic,r=calc_ic(s.stack(future_stack=True),y.stack(future_stack=True));sp=[]
 for d in s.index:
  z=pd.concat([s.loc[d].rename('s'),y.loc[d].rename('y')],axis=1).dropna()
  if len(z)<8 or z.s.nunique()<2:continue
  z=z.sort_values('s',kind='stable');k=max(1,len(z)//5);sp.append(z.y.iloc[-k:].mean()-z.y.iloc[:k].mean())
 return {'IC':float(ic.mean()) if ic.notna().any() else None,'RankIC':float(r.mean()) if r.notna().any() else None,'mean_top_minus_bottom_return':float(np.mean(sp)) if sp else None,'rows':int(valid.sum().sum()),'dates':int((valid.sum(axis=1)>=8).sum()),'min_names':int(valid.sum(axis=1).loc[valid.sum(axis=1)>0].min()) if valid.any().any() else 0,'max_names':int(valid.sum(axis=1).max()),'label_overlap_nonindependent':True,'ICIR_not_annualized':float(ic.mean()/ic.std()) if ic.std()>0 else None,'positive_IC_date_fraction':float((ic.dropna()>0).mean()) if ic.notna().any() else None}
for m in ['US','KR']:
 f=pd.read_csv(B/'nominal_inputs'/m/'panel.csv',parse_dates=['datetime']).set_index(['datetime','instrument']);opens=f.open.unstack('instrument');close=f.close.unstack('instrument');vol=f.volume.unstack('instrument');days=opens.index;eligible=(np.isfinite(f[['open','high','low','close','volume']]).all(axis=1)&(f[['open','high','low','close','volume']]>0).all(axis=1)).unstack('instrument');Y=opens.shift(-21)/opens.shift(-1)-1
 for j in range(1,22):Y=Y.where((opens>0).shift(-j,fill_value=False))
 scores={}
 for cid in ['V_ROC20','V_LOWVAR20','Q0','Q1']:
  folder=B/'calculations'/cid/('nominal_'+m);raw=pd.read_csv(folder/'scores.csv',parse_dates=['datetime']).set_index(['datetime','instrument']).iloc[:,0].unstack('instrument');w=63 if cid.startswith('Q') else 21 if cid=='V_ROC20' else 20
  # Entire required causal input window, never use native min_periods=1 as imputation.
  usable=eligible.rolling(w,min_periods=w).sum().eq(w);s=raw.where(usable);s=s.where(pd.Series(np.arange(len(s))>=w,index=s.index),axis=0);scores[cid]=s
  diag=pd.DataFrame(np.tile((days>='2026-01-01')[:,None],(1,len(s.columns))),index=days,columns=s.columns);v=metrics(s,Y,diag);v.update(id=cid,market=m,H=20,track='NOMINAL_S_2026_EXPOSED_DIAGNOSTIC',warmup=w,mask_excluded_native_values=int((raw.notna()&~usable).sum().sum()),immature_label_cells=int((s.notna()&Y.isna()&diag).where(pd.Series(np.arange(len(s))>=len(s)-21,index=s.index),False,axis=0).sum().sum()),mature_window_missing_label_cells=int((s.notna()&Y.isna()&diag).where(pd.Series(np.arange(len(s))<len(s)-21,index=s.index),False,axis=0).sum().sum()),signal_std=float(s.stack().std()),distinct_values=int(s.stack().nunique()),scope='DESCRIPTIVE_NOT_TASK14_STATISTICAL_TEST_NOT_ALPHA_CONFIRMATION')
  pair=pd.concat({'score':s.stack(future_stack=True),'target':Y.stack(future_stack=True)},axis=1);pair.index.names=['datetime','instrument'];pair.loc[pair.index.get_level_values(0)>='2026-01-01'].to_csv(out/(cid+'_'+m+'_paired.csv'));rows.append(v)
  if cid in ['Q0','Q1']:
   c20=close/close.shift(20)-1
   reference=(-c20)*(close.pct_change(fill_method=None).abs()/(close*vol)).rolling(20,min_periods=20).mean() if cid=='Q0' else c20*vol.rolling(5,min_periods=5).mean()/vol.rolling(20,min_periods=20).mean()
   reference=reference.rank(axis=1,pct=True)
   # Check dates where all names have full declared input; avoid different rank denominators.
   keep=usable.all(axis=1);diff=(reference.loc[keep]-raw.loc[keep]).abs().stack();maxerr=float(diff.max()) if len(diff) else None
   assert maxerr is not None and maxerr<1e-10,(cid,m,maxerr)
   parity.append({'id':cid,'market':m,'complete_cross_section_dates':int(keep.sum()),'max_absolute_error':maxerr,'native_FILTER_false_returns_zero_not_missing':True,'native_TS_MEAN_min_periods':1,'guard':'common strict declared-window mask enforced; raw scores retained. No native functions modified.'})
 corr=pd.DataFrame(index=list(scores),columns=list(scores),dtype=float)
 for a,x in scores.items():
  for b,y in scores.items():
   rs=[]
   for d in days[days>='2026-01-01']:
    z=pd.concat([x.loc[d],y.loc[d]],axis=1).dropna()
    if len(z)>=8:rs.append(z.iloc[:,0].corr(z.iloc[:,1],method='spearman'))
   corr.loc[a,b]=np.nanmean(rs)
 corr.to_csv(out/(m+'_score_correlations.csv'));correlations[m]=corr.to_dict()
# Comparisons remain within each model market/track, no nominal/adjusted blending.
models={m:json.loads((B/'models'/m/'metrics.json').read_text()) for m in ['US','KR']}
(out/'initial_diagnostics.json').write_text(json.dumps({'scope':'EXPOSED_DEVELOPMENT_DIAGNOSTIC_ONLY','nominal_candidates':rows,'score_correlation':correlations,'native_formula_parity':parity,'model_adjusted_track':models,'no_economic_backtest':True,'no_formal_hypothesis_test':True},indent=2,allow_nan=False))
print(json.dumps(rows,indent=2))
