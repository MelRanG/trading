"""Offline original code calculation and causal/meaning checks; no research LLM."""
from pathlib import Path
import sys,json,hashlib,subprocess
import pandas as pd,numpy as np
from qlib.contrib.eva.alpha import calc_ic
root=Path('/work');cfg=json.loads(Path('/spec/spec.json').read_text());kind=cfg['kind'];h=cfg['H']
frame=pd.read_csv('/input/panel.csv',parse_dates=['datetime']).set_index(['datetime','instrument']).sort_index();frame.columns=frame.columns.str.removeprefix('$');days=frame.index.get_level_values(0).unique().sort_values()
if 'return' not in frame:frame['return']=frame.close.groupby(level='instrument').pct_change(fill_method=None)
def compute(f,tag):
 if kind=='vibe':
  sys.path.insert(0,'/native');from src.factors.registry import get_default_registry
  panel={c:f[c].unstack('instrument') for c in ['open','high','low','close','volume']};values=get_default_registry().compute(cfg['native_id'],panel)
  if tag=='full':
   manual=panel['close'].shift(20)/panel['close'] if cfg['native_id']=='qlib158_roc20' else panel['close'].rolling(20,min_periods=20).std(ddof=1)/panel['close']
   np.testing.assert_allclose(values.to_numpy(),manual.to_numpy(),rtol=1e-9,atol=1e-10,equal_nan=True)
  series=values.stack(future_stack=True)*cfg['sign'];series.index.names=['datetime','instrument']
 else:
  d=root/tag;d.mkdir(exist_ok=True);f.rename(columns=lambda c:'$'+c).to_hdf(d/'daily_pv.h5',key='data');p=subprocess.run([sys.executable,'/candidate/factor.py'],cwd=d,capture_output=True,text=True,timeout=90);(d/'stdout.txt').write_text(p.stdout);(d/'stderr.txt').write_text(p.stderr)
  if p.returncode:raise ValueError('nativecodefailed '+p.stderr[-700:])
  s=pd.read_hdf(d/'result.h5',key='data');assert isinstance(s,pd.Series) or s.shape[1]==1;series=s if isinstance(s,pd.Series) else s.iloc[:,0];series=series.sort_index()
 assert series.index.equals(f.index),'index changed';assert not np.isinf(series).any();return series.rename('score')
x=compute(frame,'full');cut=days[len(days)//2];p=frame.loc[frame.index.get_level_values(0)<=cut];a=compute(p,'prefix');pd.testing.assert_series_equal(x.reindex(p.index),a,check_exact=False,rtol=1e-9,atol=1e-10)
changed=frame.copy();mask=changed.index.get_level_values(0)>cut;changed.loc[mask,['open','high','low','close']]*=1.7;changed.loc[mask,'volume']*=2.3;changed['return']=changed.close.groupby(level='instrument').pct_change(fill_method=None);b=compute(changed,'future_perturbed');pd.testing.assert_series_equal(x.reindex(p.index),b.reindex(p.index),check_exact=False,rtol=1e-9,atol=1e-10)
opens=frame.open.unstack('instrument');y=opens.shift(-h-1)/opens.shift(-1)-1
for j in range(1,h+2):y=y.where((opens>0).shift(-j,fill_value=False))
end=pd.Series(days,index=days).shift(-h-1)
scores=x.unstack('instrument');scores=scores.where(pd.Series(np.arange(len(scores))>=cfg['warmup'],index=scores.index),axis=0);target=y.stack(future_stack=True);target.index.names=['datetime','instrument'];ic,ric=calc_ic(scores.stack(future_stack=True),target)
# Fit-only feedback; outer diagnostics are computed later in a separate read-only role.
if cfg.get('fit_only'):scores=scores.where(end.lt(pd.Timestamp('2025-01-01')),axis=0);ic,ric=calc_ic(scores.stack(future_stack=True),target)
pair=pd.concat([scores.stack(future_stack=True).rename('score'),target.rename('label')],axis=1);pair=pair.dropna();spread=[]
for d,g in pair.groupby(level=0):
 if len(g)<8:continue
 g=g.sort_values('score');k=max(1,len(g)//5);spread.append(g.label.iloc[-k:].mean()-g.label.iloc[:k].mean())
x.to_csv(root/'scores.csv');meta={'scope':'FIT_ONLY_NO_OUTER_RESULTS' if cfg.get('fit_only') else 'CALCULATION_ONLY_OUTER_DIAGNOSTIC_LATER','IC':float(ic.mean()),'RankIC':float(ric.mean()),'spread_mean':float(np.mean(spread)),'finite_rows':int(x.notna().sum()),'paired_rows':len(pair),'paired_dates':pair.index.get_level_values(0).nunique(),'missing_scores':int(x.isna().sum()),'H':h,'primary_target':'open_t1_to_open_tH1_return','warmup':cfg['warmup'],'prefix_match':True,'future_perturbation_match':True,'parity':'Vibe original arrays vs literal original formula' if kind=='vibe' else 'Raw result.h5 vs exported score exact; factor DSL correspondence separately audited','input_hash':hashlib.sha256(Path('/input/panel.csv').read_bytes()).hexdigest(),'output_hash':hashlib.sha256((root/'scores.csv').read_bytes()).hexdigest()};(root/'calculation.json').write_text(json.dumps(meta,indent=2,allow_nan=False));print(json.dumps(meta))
