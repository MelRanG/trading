"""Original RD-generated GRU through original Qlib GeneralPTNN, CPU.
Only dataset/shape adapters; factor augmentation is fixed before evaluation.
"""
from pathlib import Path
import sys,json,hashlib,ast,importlib.util
import numpy as np,pandas as pd,torch
from qlib.contrib.model.pytorch_general_nn import GeneralPTNN
from qlib.data.dataset import DatasetH
sys.path.insert(0,'/code');from aligned import evaluate
from native_metrics import native_metrics
torch.set_num_threads(2);np.random.seed(42)
source=Path('/candidate/model.py');tree=ast.parse(source.read_text())
for n in ast.walk(tree):
 if isinstance(n,(ast.Import,ast.ImportFrom)):
  names=[a.name for a in n.names] if isinstance(n,ast.Import) else [n.module]
  if any(s.split('.')[0] not in ['torch','numpy','math','typing'] for s in names):raise ValueError('model import denied')
 if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in ['open','exec','eval','compile','__import__']:raise ValueError('model I/O or eval denied')
spec=importlib.util.spec_from_file_location('generated_model',source);generated=importlib.util.module_from_spec(spec);spec.loader.exec_module(generated)
class NativeAdapter(torch.nn.Module):
 def __init__(self,num_features):super().__init__();self.f=num_features;self.native=generated.model_cls(num_features=num_features,num_timesteps=20)
 def forward(self,x):return self.native(x.reshape(-1,20,self.f)).reshape(-1,1)
class FrozenDataset(DatasetH):
 def __init__(self,parts):self.parts=parts
 def prepare(self,segment,**kwargs):return self.parts[segment]
frames={};xs=[];ys=[];keys=[];realized=[]
for path in sorted(Path('/train').glob('US[0-9]*.csv')):
 f=pd.concat([pd.read_csv(path,parse_dates=['date']).set_index('date'),pd.read_csv(Path('/validation')/path.name,parse_dates=['date']).set_index('date')]).sort_index();frames[path.stem]=f
 feat=pd.DataFrame({'ret':f.close.pct_change(fill_method=None),'gap':f.open/f.close.shift(1)-1,'high':f.high/f.close-1,'low':f.low/f.close-1,'volume':np.log(f.volume/f.volume.rolling(20,min_periods=20).mean()),'factor':((2*f.close-f.high-f.low)/(f.high-f.low)).rolling(20,min_periods=20).mean()})
 label=(f.close/f.open-1).shift(-1)
 for i in range(19,len(f)-1):
  win=feat.iloc[i-19:i+1].to_numpy(dtype=np.float32)
  if np.isfinite(win).all() and np.isfinite(label.iloc[i]):xs.append(win);ys.append(label.iloc[i]);keys.append((f.index[i],path.stem));realized.append(f.index[i+1])
x=np.array(xs);y=np.array(ys,dtype=np.float32);index=pd.MultiIndex.from_tuples(keys,names=['datetime','instrument']);days=index.get_level_values('datetime');realized=np.array(realized,dtype='datetime64[ns]');train_dates=sorted(set(days[days<='2024-12-31']));boundary=train_dates[int(len(train_dates)*.8)]
fit=(days<boundary)&(realized<np.datetime64(boundary));early=(days>=boundary)&(realized<=np.datetime64('2024-12-31'));test=(days>='2025-01-01')&(realized<=np.datetime64('2025-12-31'))
assert fit.sum()>1000 and early.sum()>100 and test.sum()>100
result={'model_code_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'train_rows':int(fit.sum()),'internal_earlystop_rows':int(early.sum()),'prediction_rows':int(test.sum()),'internal_split':str(boundary),'fit_max_target_date':str(realized[fit].max()),'early_max_target_date':str(realized[early].max()),'outer_validation_used_for_fitting':False,'native_trainer':'qlib.contrib.model.pytorch_general_nn.GeneralPTNN','full_fin_quant_controller':False}
for name,features in [('baseline',5),('factor_augmented',6)]:
 torch.manual_seed(42);mean=x[fit,:,:features].mean(axis=(0,1));std=x[fit,:,:features].std(axis=(0,1));std=np.where(std>0,std,1);z=(x[:,:,:features]-mean)/std
 data=pd.DataFrame(np.column_stack([z.reshape(len(z),-1),y]),index=index)
 dataset=FrozenDataset({'train':data.loc[fit],'valid':data.loc[early],'test':data.loc[test]});model=GeneralPTNN(n_epochs=5,batch_size=256,early_stop=5,n_jobs=0,GPU=-1,seed=42,pt_model_uri='__main__.NativeAdapter',pt_model_kwargs={'num_features':features})
 # Independently ensure Qlib prediction/loss shape cannot broadcast across samples.
 pred=model.dnn_model(torch.tensor(z[fit][:8].reshape(8,-1)));target=torch.tensor(y[fit][:8]);assert pred.shape==(8,1)
 native_loss=model.loss_fn(pred,target);manual=torch.mean((pred[:,0]-target)**2);assert torch.allclose(native_loss,manual)
 history={};model.fit(dataset,evals_result=history,save_path='/work/'+name+'.pth');prediction=model.predict(dataset);prediction.to_csv('/work/'+name+'_predictions.csv')
 score=prediction.unstack('instrument').reindex(index=pd.DataFrame({s:f.close for s,f in frames.items()}).index);metrics,nav,fills=evaluate(score,frames);metrics['native_aliases']=native_metrics(metrics,nav);metrics['annualized_net_mean']=float(nav.net_return.mean()*252)
 mse=float(np.mean((prediction.to_numpy()-y[test])**2));mae=float(np.mean(np.abs(prediction.to_numpy()-y[test])));nav.to_csv('/work/'+name+'_nav.csv',index=False);fills.to_csv('/work/'+name+'_fills.csv',index=False)
 result[name]={'features':features,'loss_history':history,'validation_mse':mse,'validation_mae':mae,'aligned':metrics,'checkpoint_sha256':hashlib.sha256(Path('/work/'+name+'.pth').read_bytes()).hexdigest(),'normalization_mean':mean.tolist(),'normalization_std':std.tolist()}
Path('/work/training_metrics.json').write_text(json.dumps(result,indent=2,allow_nan=False));print(json.dumps(result,indent=2))
