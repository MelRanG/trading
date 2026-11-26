"""Original RD-generated code + original Qlib trainers, no trade simulation."""
from pathlib import Path
import sys,json,hashlib,ast,importlib.util,pickle
import pandas as pd,numpy as np,torch
from qlib.contrib.model.pytorch_general_nn import GeneralPTNN
from qlib.contrib.model.linear import LinearModel
from qlib.contrib.model.gbdt import LGBModel
from qlib.data.dataset import DatasetH
from qlib.contrib.eva.alpha import calc_ic
import os
os.environ['MLFLOW_ALLOW_FILE_STORE']='true'
import qlib
qlib.init(provider_uri='/work/provider_unused',exp_manager={'class':'MLflowExpManager','module_path':'qlib.workflow.expm','kwargs':{'uri':'file:/work/mlruns','default_exp_name':'TASK13_LOCAL_CONTROL_DIAGNOSTIC'}})
root=Path('/work');torch.set_num_threads(2);torch.manual_seed(42);np.random.seed(42)
raw=pd.read_csv('/input/panel.csv',parse_dates=['datetime']).set_index(['datetime','instrument']).sort_index();days=raw.index.get_level_values(0).unique().sort_values();h=5
source=Path('/candidate/model.py');code=source.read_text()
for n in ast.walk(ast.parse(code)):
 if isinstance(n,(ast.Import,ast.ImportFrom)):
  names=[a.name for a in n.names] if isinstance(n,ast.Import) else [n.module]
  if any(a.split('.')[0] not in ['torch','math','numpy','typing'] for a in names):raise ValueError('unregistered model import')
 if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in ['open','exec','eval','compile','__import__']:raise ValueError('model I/O denied')
spec=importlib.util.spec_from_file_location('native_generated',source);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
def features(frame):
 parts=[]
 for symbol,g in frame.groupby(level=1):
  f=g.droplevel(1).reindex(days);r=f.close.pct_change(fill_method=None)
  z=pd.DataFrame({'ret1':r,'mom20':f.close/f.close.shift(20)-1,'mom60':f.close/f.close.shift(60)-1,'vol20':r.rolling(20,min_periods=20).std(),'relative_volume20':f.volume/f.volume.rolling(20,min_periods=20).mean()-1});z['instrument']=symbol;z.index.name='datetime';parts.append(z.set_index('instrument',append=True))
 return pd.concat(parts).sort_index()
X=features(raw);opens=raw.open.unstack('instrument');y=opens.shift(-h-1)/opens.shift(-1)-1
for j in range(1,h+2):y=y.where((opens>0).shift(-j,fill_value=False))
y=y.stack(future_stack=True).reindex(X.index).rename('target');ends=pd.Series(days,index=days).shift(-h-1);dates=X.index.get_level_values(0);end=pd.DatetimeIndex(dates.map(ends));valid=np.isfinite(X).all(axis=1)&np.isfinite(y);fit=valid&(dates<'2024-07-01')&(end<'2024-07-01');inner=valid&(dates>='2024-08-01')&(end<'2025-01-01');test=valid&(dates>='2025-02-01')&(end<='2025-12-31');assert fit.sum()>1000 and len(set(dates[fit]))>=500
mean=X.loc[fit].mean();std=X.loc[fit].std().replace(0,1);Z=(X-mean)/std
# Native functions require one frame; column groups allow both Qlib Linear/LGB and PTNN.
class Data(DatasetH):
 def __init__(self):self.segments={'train':None,'valid':None,'test':None}
 def prepare(self,segment,**kwargs):
  m=fit if segment=='train' else inner if segment=='valid' else test;xx=Z.loc[m];yy=y.loc[m];cs=kwargs.get('col_set')
  return xx if cs=='feature' else pd.concat({'feature':xx,'label':yy.to_frame()},axis=1)
class NativeAdapter(torch.nn.Module):
 def __init__(self):super().__init__();self.native=mod.model_cls(num_features=5,num_timesteps=1)
 def forward(self,x):return self.native(x.reshape(-1,1,5)).reshape(-1,1)
dataset=Data();model=GeneralPTNN(n_epochs=20,batch_size=256,early_stop=100,n_jobs=0,GPU=-1,seed=42,lr=.001,pt_model_uri='__main__.NativeAdapter',pt_model_kwargs={});params=sum(p.numel() for p in model.dnn_model.parameters());assert params<=100
prediction=model.dnn_model(torch.tensor(Z.loc[fit].iloc[:8].to_numpy(dtype=np.float32)));target=torch.tensor(y.loc[fit].iloc[:8].to_numpy(dtype=np.float32));assert prediction.shape==(8,1);assert torch.allclose(model.loss_fn(prediction,target),torch.mean((prediction[:,0]-target)**2))
# Fixed-epoch fit contains train only, no outer validation passed to trainer.
class TrainOnly(Data):
 def prepare(self,segment,**kwargs):
  if segment=='valid':return super().prepare(segment,**kwargs)
  return super().prepare(segment,**kwargs)
history={}
checkpoint=root/'model.pth'
if checkpoint.exists():
 model.dnn_model.load_state_dict(torch.load(checkpoint,map_location='cpu',weights_only=True));model.fitted=True;history={'recovered_intermediate_checkpoint':True,'initial_fit_history_unavailable_after_later_control_failure':True}
else:model.fit(TrainOnly(),evals_result=history,save_path=str(checkpoint))
pred=model.predict(dataset)
with torch.no_grad():
 history['selected_checkpoint_fit_MSE']=float(torch.mean((model.dnn_model(torch.tensor(Z.loc[fit].to_numpy(dtype=np.float32)))[:,0]-torch.tensor(y.loc[fit].to_numpy(dtype=np.float32)))**2))
 history['selected_checkpoint_inner_validation_MSE']=float(torch.mean((model.dnn_model(torch.tensor(Z.loc[inner].to_numpy(dtype=np.float32)))[:,0]-torch.tensor(y.loc[inner].to_numpy(dtype=np.float32)))**2))
controls={'RD_SMALL':pred,'ZERO':pd.Series(0.,index=pred.index)}
for name,base in [('QLIB_RIDGE',LinearModel(estimator='ridge',alpha=1.,fit_intercept=True,include_valid=False)),('QLIB_TREE',LGBModel(num_leaves=7,max_depth=3,learning_rate=.05,num_threads=2))]:
 if name=='QLIB_TREE':
  try:base.fit(TrainOnly(),num_boost_round=50,early_stopping_rounds=None,verbose_eval=False)
  except AttributeError as exc:
   if 'qlib.init()' not in str(exc) or base.model is None or base.model.current_iteration()!=50:raise
   (root/'qlib_tree_tracking_failure.json').write_text(json.dumps({'status':'TRAINED_PREDICTABLE_BUT_NATIVE_TRACKING_FAILED','reason':str(exc),'iterations':base.model.current_iteration(),'no_exception_hidden':True}))
 else:base.fit(TrainOnly())
 controls[name]=base.predict(dataset)
 with (root/(name+'.pkl')).open('wb') as f:pickle.dump(base,f)
cut=days[days>='2025-02-01'][80];changed=raw.copy();mask=changed.index.get_level_values(0)>cut;changed.loc[mask,['open','high','low','close']]*=1.9;changed.loc[mask,'volume']*=2.1;alter=features(changed);pd.testing.assert_frame_equal(X.loc[dates<=cut],alter.loc[dates<=cut]);pd.testing.assert_frame_equal(X.loc[fit],alter.loc[fit]);zz=(alter-mean)/std
with torch.no_grad():
 pp=model.dnn_model(torch.tensor(Z.loc[test & (dates<=cut)].to_numpy(dtype=np.float32)));qq=model.dnn_model(torch.tensor(zz.loc[test & (dates<=cut)].to_numpy(dtype=np.float32)));assert torch.allclose(pp,qq)
result={}
for name,p in controls.items():
 truth=y.reindex(p.index);p.rename('prediction').to_csv(root/(name+'_predictions.csv'));ic,rank=calc_ic(p,truth);pair=pd.concat([p.rename('prediction'),truth.rename('target')],axis=1);pair.to_csv(root/(name+'_paired.csv'))
 result[name]={'mse':float(((p-truth)**2).mean()),'mae':float((p-truth).abs().mean()),'IC':float(ic.mean()) if ic.notna().any() else None,'RankIC':float(rank.mean()) if rank.notna().any() else None,'rows':len(p),'dates':p.index.get_level_values(0).nunique(),'target':'open_t1_to_open_t6_adjusted_provider_claim_return','parameters':params if name=='RD_SMALL' else None}
result.update({'training':{'fit_rows':int(fit.sum()),'fit_dates':len(set(dates[fit])),'max_fit_target':str(end[fit].max()),'min_validation_signal':str(dates[test].min()),'validation_dates':len(set(dates[test])),'internal_validation_rows':int(inner.sum()),'internal_validation_dates':len(set(dates[inner])),'internal_checkpoint_selection':'nativeQLib best internal validation checkpoint within fixed20epochs; no outer results','H':5,'effective_warmup':61,'primary_H_nonoverlap_fit_blocks_upper_bound':len(set(dates[fit]))//5,'feature_names':list(X.columns),'normalization_fit_only':True,'mean':mean.to_dict(),'std':std.to_dict(),'loss_history':history,'native_trainer':'originalQlibGeneralPTNN','parameter_count':params,'code_hash':hashlib.sha256(source.read_bytes()).hexdigest(),'checkpoint_hash':hashlib.sha256((root/'model.pth').read_bytes()).hexdigest(),'outer_validation_fitting':False,'price_track':'SEPARATE_TASK6_ADJUSTED_CLAIM','full_fin_quant':False},'causality':{'feature_prefix_and_future_perturbation':True,'frozen_model_future_prediction_invariance':True,'loss_shape_and_manual_MSE_parity':True}})
(root/'metrics.json').write_text(json.dumps(result,indent=2,default=str,allow_nan=False));print(json.dumps(result,default=str))
