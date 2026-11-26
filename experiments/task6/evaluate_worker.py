"""Run frozen original factor code offline, with a prefix causality probe."""
from pathlib import Path
import argparse,subprocess,sys,json,importlib.util
import pandas as pd
import numpy as np
p=argparse.ArgumentParser();p.add_argument('engine');a=p.parse_args();work=Path('/work')
full=pd.read_csv('/input/panel.csv',parse_dates=['datetime']).set_index(['datetime','instrument']).sort_index()
def calculate(frame,subdir):
 subdir.mkdir(exist_ok=True)
 if a.engine!='vibe':frame.to_hdf(subdir/'daily_pv.h5',key='data')
 if a.engine=='vibe':
  spec=importlib.util.spec_from_file_location('candidate','/candidate/factor.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  dm={s:f.droplevel('instrument').rename(columns=lambda c:c.removeprefix('$')) for s,f in frame.groupby(level='instrument')}
  values=module.SignalEngine().generate(dm)
  series=pd.concat(values,names=['instrument','datetime']).swaplevel().sort_index().rename('factor')
 else:
  result=subprocess.run([sys.executable,'/candidate/factor.py'],cwd=subdir,capture_output=True,text=True,timeout=90)
  (subdir/'stdout.txt').write_text(result.stdout);(subdir/'stderr.txt').write_text(result.stderr)
  if result.returncode:raise RuntimeError(result.stderr[-2500:])
  series=pd.read_hdf(subdir/'result.h5')
  if isinstance(series,pd.DataFrame):
   if series.shape[1]!=1:raise ValueError('not one factor')
   series=series.iloc[:,0]
  series=series.rename('factor').sort_index()
 if series.index.has_duplicates or not series.index.equals(frame.index):raise ValueError('factor index mismatch')
 if np.isinf(series).any():raise ValueError('infinite factor values')
 return series
values=calculate(full,work/'full');cut=sorted(full.index.get_level_values('datetime').unique())[len(full.index.get_level_values('datetime').unique())//2]
part=full[full.index.get_level_values('datetime')<=cut];prefix=calculate(part,work/'prefix')
pd.testing.assert_series_equal(values.reindex(part.index),prefix,check_names=False,check_exact=False,rtol=1e-10,atol=1e-10)
values.to_csv(work/'factor_values.csv');(work/'causality.json').write_text(json.dumps({'status':'PREFIX_MATCH','cutoff':str(cut),'rows':len(values),'missing':int(values.isna().sum())},indent=2))
