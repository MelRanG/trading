"""One frozen development query. Existing models/scaler only, no fitting."""
from pathlib import Path
import json,hashlib,pickle,sys,importlib.util
import numpy as np,pandas as pd,torch
sys.path.insert(0,'/shared');from loader import supervised
sys.path.insert(0,'/code');from feature_oracle import verify
from qlib.contrib.eva.alpha import calc_ic
root=Path('/work');torch.set_num_threads(2);mean,std=pd.read_pickle(root/'scaler.pkl');ridge=pickle.loads((root/'models.pkl').read_bytes());models={}
for name,path,nfeat in [('B','/baseline/model.py',5),('D','/candidate/model.py',6)]:
 s=importlib.util.spec_from_file_location('native'+name,path);mod=importlib.util.module_from_spec(s);s.loader.exec_module(mod);cls=getattr(mod,'model_cls',None) or getattr(mod,json.loads(Path('/candidate/model_generation.json').read_text())['task']['name']);m=cls(nfeat,1);weights=torch.load(root/(name+'.pth'),map_location='cpu',weights_only=True);m.load_state_dict({k.removeprefix('native.'):v for k,v in weights.items()});m.eval();models[name]=m
results={}
for market in ['US','KR']:
 d=pd.read_hdf('/eval/'+market+'_train.h5',key='data');folder=root/(market+'_development_factor');folder.mkdir(exist_ok=True)
 import os,runpy,contextlib
 d.to_hdf(folder/'daily_pv.h5',key='data');prev=os.getcwd()
 try:
  os.chdir(folder)
  with (folder/'execution.txt').open('w') as f,contextlib.redirect_stdout(f),contextlib.redirect_stderr(f):runpy.run_path('/candidate/factor.py',run_name='__main__')
 finally:os.chdir(prev)
 f=pd.read_hdf(folder/'result.h5',key='data');f=f if isinstance(f,pd.Series) else f.iloc[:,0];verify(f,d);frame,meta=supervised(d,20,cutoff='2024-12-31');X=frame['feature'].copy();X['new_liquidity_feature']=f.reindex(X.index);y=frame['label'].iloc[:,0];valid=np.isfinite(X).all(axis=1)&np.isfinite(y)&(X.index.get_level_values(0)>='2023-04-03');X=X.loc[valid];y=y.loc[valid];n=X.groupby(level=0).size();X=X.loc[X.index.get_level_values(0).isin(n[n>=50].index)];y=y.reindex(X.index);Z=(X-mean)/std;preds={}
 for name in ['A','B','C','D']:
  cols=list(mean.index[:-1]) if name in ['A','B'] else list(mean.index)
  if name in ['A','C']:p=pd.Series(Z[cols].to_numpy()@ridge[name].coef_+ridge[name].intercept_,index=X.index)
  else:
   with torch.no_grad():a=models[name](torch.tensor(Z[cols].to_numpy(dtype=np.float32)).reshape(-1,1,len(cols))).reshape(-1).numpy()
   p=pd.Series(a,index=X.index)
  assert np.isfinite(p).all();ic,ric=calc_ic(p,y);preds[name]={'IC':float(ic.mean()),'RankIC':float(ric.mean()),'MSE':float(((p-y)**2).mean()),'MAE':float((p-y).abs().mean()),'rows':len(p),'dates':p.index.get_level_values(0).nunique()};pd.concat([p.rename('prediction'),y.rename('target')],axis=1).to_csv(root/(market+'_'+name+'_development_predictions.csv'))
 results[market]=preds
 for p in folder.glob('*.h5'):p.unlink()
(root/'development_metrics.json').write_text(json.dumps({'markets':results,'training':False,'US_fitted_KR_transfer':True,'development_queries':1,'independent_holdout':False},indent=2));print(json.dumps(results))
