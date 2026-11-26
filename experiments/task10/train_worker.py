"""Original RD model + Qlib GeneralPTNN. Prefix-only supervised training."""
from pathlib import Path
import sys,json,ast,hashlib,importlib.util
import numpy as np,pandas as pd,torch
from qlib.contrib.model.pytorch_general_nn import GeneralPTNN
from qlib.data.dataset import DatasetH
torch.set_num_threads(2);torch.manual_seed(42);np.random.seed(42)
source=Path('/candidate/model.py');tree=ast.parse(source.read_text())
for n in ast.walk(tree):
 if isinstance(n,(ast.Import,ast.ImportFrom)):
  names=[a.name for a in n.names] if isinstance(n,ast.Import) else [n.module]
  if any(s.split('.')[0] not in ['torch','numpy','pandas','math','typing'] for s in names):raise ValueError('deniedmodelimport')
 if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in ['open','exec','eval','compile','__import__']:raise ValueError('deniedmodelI/O')
spec=importlib.util.spec_from_file_location('native_generated',source);generated=importlib.util.module_from_spec(spec);spec.loader.exec_module(generated)
class NativeAdapter(torch.nn.Module):
 def __init__(self,num_features=5):super().__init__();self.native=generated.model_cls(num_features=num_features,num_timesteps=20)
 def forward(self,x):return self.native(x.reshape(-1,20,5)).reshape(-1,1)
class Data(DatasetH):
 def __init__(self,parts):self.parts=parts
 def prepare(self,segment,**kwargs):return self.parts[segment]
xs=[];ys=[];keys=[];maturity=[];all_dates=None
for p in sorted(Path('/input').glob('*[0-9][0-9][0-9].csv')):
 f=pd.read_csv(p,parse_dates=['date']).set_index('date').sort_index();all_dates=f.index if all_dates is None else all_dates.union(f.index)
 feat=pd.DataFrame({'ret':f.close.pct_change(fill_method=None),'gap':f.open/f.close.shift(1)-1,'high':f.high/f.close-1,'low':f.low/f.close-1,'volume':np.log(f.volume/f.volume.rolling(20,min_periods=20).mean())});label=f.open.shift(-6)/f.open.shift(-1)-1
 for i in range(19,len(f)):
  x=feat.iloc[i-19:i+1].to_numpy(dtype=np.float32)
  if np.isfinite(x).all():xs.append(x);ys.append(float(label.iloc[i]) if pd.notna(label.iloc[i]) else np.nan);keys.append((f.index[i],p.stem));maturity.append(f.index[i+6] if i+6<len(f) else pd.NaT)
x=np.array(xs);y=np.array(ys,dtype=np.float32);index=pd.MultiIndex.from_tuples(keys,names=['datetime','instrument']);days=index.get_level_values(0);maturity=pd.DatetimeIndex(maturity);mode=sys.argv[1];root=Path('/work')
model=GeneralPTNN(n_epochs=5,batch_size=256,early_stop=5,n_jobs=0,GPU=-1,seed=42,pt_model_uri='__main__.NativeAdapter',pt_model_kwargs={})
if mode=='train':
 val_start=all_dates[-80];fit_end=all_dates[99] if len(all_dates)==200 else all_dates[-87];inner_dates=all_dates[all_dates<=fit_end];early_start=inner_dates[int(len(inner_dates)*.8)]
 fit=(days<early_start)&(maturity<early_start)&np.isfinite(y);early=(days>=early_start)&(days<=fit_end)&(maturity<=fit_end)&np.isfinite(y);outer=(days>=val_start)&np.isfinite(y)
 assert fit.sum()>100 and early.sum()>50 and outer.sum()>100,('insufficientcompletewindows',fit.sum(),early.sum(),outer.sum())
 effective_batch=min(256,2**int(np.floor(np.log2(int(fit.sum())))));model.batch_size=effective_batch;mean=x[fit].mean(axis=(0,1));std=x[fit].std(axis=(0,1));std=np.where(std>0,std,1);z=(x-mean)/std;frame=pd.DataFrame(np.column_stack([z.reshape(len(z),-1),y]),index=index);history={};model.fit(Data({'train':frame.loc[fit],'valid':frame.loc[early],'test':frame.loc[outer]}),evals_result=history,save_path='/work/model.pth');pred=model.predict(Data({'test':frame.loc[outer]}));pred.to_csv('/work/validation_predictions.csv');meta={'model_code_hash':hashlib.sha256(source.read_bytes()).hexdigest(),'checkpoint_hash':hashlib.sha256((root/'model.pth').read_bytes()).hexdigest(),'train_rows':int(fit.sum()),'effective_batch_size':effective_batch,'internal_early_rows':int(early.sum()),'outer_rows':int(outer.sum()),'train_target_max':str(maturity[fit].max()),'early_target_max':str(maturity[early].max()),'outer_start':str(val_start),'asof':str(all_dates.max()),'mean':mean.tolist(),'std':std.tolist(),'loss_history':history,'outer_mse':float(np.mean((pred.to_numpy()-y[outer])**2)),'outer_mae':float(np.mean(abs(pred.to_numpy()-y[outer]))),'original_trainer':'qlib.GeneralPTNN','full_fin_quant':False};(root/'training.json').write_text(json.dumps(meta,indent=2));print('TRAINED',meta['train_rows'],meta['outer_mse'],flush=True)
else:
 meta=json.loads(Path('/trained/training.json').read_text());assert meta['model_code_hash']==hashlib.sha256(source.read_bytes()).hexdigest();model.dnn_model.load_state_dict(torch.load('/trained/model.pth',map_location='cpu',weights_only=True));model.fitted=True;z=(x-np.array(meta['mean']))/np.array(meta['std']);frame=pd.DataFrame(np.column_stack([z.reshape(len(z),-1),np.zeros(len(z))]),index=index);pred=model.predict(Data({'test':frame}));pred.to_csv('/work/predictions.csv');print('PREDICTED_FROZEN',len(pred),flush=True)
