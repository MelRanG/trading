"""Trusted native factor execution + original Qlib trainers. No research LLM here."""
from pathlib import Path
import sys,json,time,hashlib,ast,importlib.util,pickle,os,runpy,contextlib
import numpy as np,pandas as pd,torch
sys.path.insert(0,'/shared');sys.path.insert(0,'/code');from loader import supervised
from feature_oracle import reference,verify
from qlib.data.dataset import DatasetH
from qlib.contrib.model.linear import LinearModel
from qlib.contrib.model.pytorch_general_nn import GeneralPTNN
from qlib.contrib.eva.alpha import calc_ic
root=Path('/work');mode=sys.argv[1];torch.set_num_threads(2);torch.manual_seed(42);np.random.seed(42);os.environ['MLFLOW_ALLOW_FILE_STORE']='true'
import qlib
qlib.init(provider_uri='/work/unused_provider',exp_manager={'class':'MLflowExpManager','module_path':'qlib.workflow.expm','kwargs':{'uri':'file:/work/mlruns','default_exp_name':'R2_NATIVE_QLIB'}})
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load_module(path,name):
 code=Path(path).read_text()
 for n in ast.walk(ast.parse(code)):
  if isinstance(n,(ast.Import,ast.ImportFrom)):
   mods=[a.name for a in n.names] if isinstance(n,ast.Import) else [n.module]
   assert all(m.split('.')[0] in ['torch','numpy','math','typing'] for m in mods),'MODEL_IO_IMPORT_DENIED'
  if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute):assert n.func.attr not in ['load','save','open','read_csv','read_hdf','load_state_dict'],'MODEL_IO_DENIED'
  if isinstance(n,ast.Call) and isinstance(n.func,ast.Name):assert n.func.id not in ['open','exec','eval','compile','__import__'],'MODEL_IO_DENIED'
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

if mode=='factor':
 code=Path('/candidate/factor.py').read_text()
 for n in ast.walk(ast.parse(code)):
  if isinstance(n,(ast.Import,ast.ImportFrom)):
   names=[a.name for a in n.names] if isinstance(n,ast.Import) else [n.module]
   assert all(m.split('.')[0] in ['pandas','numpy','os','pathlib','math'] for m in names),'FACTOR_IMPORT_DENIED'
  if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute):assert n.func.attr not in ['system','popen','remove','unlink','rmdir','mkdir','rmtree','read_csv','read_json','load','save'],'FACTOR_FILE_ACTION_DENIED'
 data={};proofs={}
 for market in ['US','KR']:
  d=pd.read_hdf('/inputs/'+market+'_train.h5',key='data');days=d.index.get_level_values(0).unique().sort_values()
  def calc(frame,tag):
   folder=root/(market+'_'+tag);folder.mkdir(exist_ok=True);frame.to_hdf(folder/'daily_pv.h5',key='data');prev=os.getcwd()
   try:
    os.chdir(folder)
    with (folder/'execution.txt').open('w') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):runpy.run_path('/candidate/factor.py',run_name='__main__')
   finally:os.chdir(prev)
   v=pd.read_hdf(folder/'result.h5',key='data');return (v if isinstance(v,pd.Series) else v.iloc[:,0]).sort_index()
  actual=calc(d,'full');proofs[market]=verify(actual,d);cut=days[len(days)//2];pre=d.loc[d.index.get_level_values(0)<=cut];p=calc(pre,'prefix');np.testing.assert_allclose(actual.reindex(pre.index),p,rtol=1e-9,atol=1e-12,equal_nan=True)
  changed=d.copy();mask=d.index.get_level_values(0)>cut;changed.loc[mask,['$open','$high','$low','$close']]*=1.7;changed.loc[mask,'$volume']*=2.2;changed['$return']=changed['$close'].groupby(level=1).pct_change(fill_method=None);q=calc(changed,'perturb');np.testing.assert_allclose(actual.reindex(pre.index),q.reindex(pre.index),rtol=1e-9,atol=1e-12,equal_nan=True);proofs[market]['prefix_future_perturbation']=True
  frame,info=supervised(d,20);X=frame['feature'].copy();X['new_liquidity_feature']=actual.reindex(X.index);y=frame['label'].iloc[:,0];valid=np.isfinite(X).all(axis=1)&np.isfinite(y);X=X.loc[valid];y=y.loc[valid];n=X.groupby(level=0).size();allowed=n[n>=50].index;X=X.loc[X.index.get_level_values(0).isin(allowed)];y=y.reindex(X.index);dates=X.index.get_level_values(0);ends=pd.Series(days,index=days).shift(-21);maturity=pd.DatetimeIndex(dates.map(ends));fit=(dates<='2020-12-31')&(maturity<='2020-12-31');inner=(dates>='2021-04-01')&(maturity<='2022-12-31');assert fit.sum()>1000 and inner.sum()>1000
  assert maturity[fit].max()<dates[inner].min();data[market]={'X':X,'y':y,'fit':fit,'inner':inner,'dates':dates,'maturity':maturity};actual.rename('feature').to_csv(root/(market+'_feature.csv'));proofs[market].update({'fit_rows':int(fit.sum()),'inner_rows':int(inner.sum()),'fit_dates':dates[fit].nunique(),'inner_dates':dates[inner].nunique(),'max_fit_target':str(maturity[fit].max()),'min_inner_signal':str(dates[inner].min())})
 (root/'factor_proofs.json').write_text(json.dumps(proofs,indent=2));pd.to_pickle(data,root/'prepared.pkl')
 mean=data['US']['X'].loc[data['US']['fit']].mean();std=data['US']['X'].loc[data['US']['fit']].std().replace(0,1);pd.to_pickle((mean,std),root/'scaler.pkl');models={};history={}
else:
 data=pd.read_pickle(root/'prepared.pkl');mean,std=pd.read_pickle(root/'scaler.pkl');models=pickle.loads((root/'models.pkl').read_bytes());history=json.loads((root/'histories.json').read_text())
class Data(DatasetH):
 def __init__(self,cols,market='US',test_mask=None):self.cols=cols;self.market=market;self.test_mask=test_mask;self.segments={'train':None,'valid':None,'test':None}
 def prepare(self,segment,**kwargs):
  a=data['US'] if segment in ['train','valid'] else data[self.market];mask=a['fit'] if segment=='train' else a['inner'] if segment=='valid' else a['inner'] if self.test_mask is None else self.test_mask;X=((a['X']-mean)/std).loc[mask,self.cols];y=a['y'].loc[mask]
  return X if kwargs.get('col_set')=='feature' else pd.concat({'feature':X,'label':y.to_frame('H20')},axis=1)
basecols=list(mean.index[:-1]);allcols=list(mean.index)
oldmod=load_module('/baseline/model.py','old_native_model');improved=None
class NativeB(torch.nn.Module):
 def __init__(self):super().__init__();self.native=oldmod.model_cls(5,1)
 def forward(self,x):return self.native(x.reshape(-1,1,5)).reshape(-1,1)
class NativeD(torch.nn.Module):
 def __init__(self):super().__init__();self.native=improved.model_cls(6,1)
 def forward(self,x):return self.native(x.reshape(-1,1,6)).reshape(-1,1)
def fit_pt(cls,name,cols):
 torch.manual_seed(42);np.random.seed(42);model=GeneralPTNN(n_epochs=20,batch_size=256,early_stop=100,n_jobs=0,GPU=-1,seed=42,lr=.001,pt_model_uri='__main__.'+cls,pt_model_kwargs={});size=sum(p.numel() for p in model.dnn_model.parameters());assert size<=80;h={};start=time.monotonic();model.fit(Data(cols),evals_result=h,save_path=str(root/(name+'.pth')));history[name]={'native_score_history':h,'history_semantics':'Original Qlib metric_fn returns positive MSE, lower is better','parameters':size,'seconds':time.monotonic()-start,'checkpoint_hash':sha(root/(name+'.pth'))};return model
if mode=='factor':
 for name,cols in [('A',basecols),('C',allcols)]:
  start=time.monotonic();m=LinearModel(estimator='ridge',alpha=1.,include_valid=False);m.fit(Data(cols));models[name]=m;history[name]={'seconds':time.monotonic()-start,'parameters':len(m.coef_)+1,'coef':m.coef_.tolist(),'intercept':float(m.intercept_)}
 models['B']=fit_pt('NativeB','B',basecols)
else:
 restored=GeneralPTNN(n_epochs=20,batch_size=256,n_jobs=0,GPU=-1,seed=42,pt_model_uri='__main__.NativeB',pt_model_kwargs={});restored.dnn_model.load_state_dict(torch.load(root/'B.pth',map_location='cpu',weights_only=True));restored.fitted=True;models['B']=restored
 improved=load_module('/candidate/model.py','improved_native')
 if not hasattr(improved,'model_cls'):
  declared=json.loads(Path('/candidate/model_generation.json').read_text())['task']['name'];actual=getattr(improved,declared);assert issubclass(actual,torch.nn.Module);improved.model_cls=actual;(root/'model_entrypoint.json').write_text(json.dumps({'requested_alias':'model_cls','native_declared_class':declared,'code_unchanged':True,'meaning':'Use original Qlib dynamic model entrypoint semantics, no architecture change'}))
 probe=improved.model_cls(6,1);x=torch.randn(128,1,6);assert probe(x).numel()==128 and torch.isfinite(probe(x)).all();assert sum(p.numel() for p in probe.parameters())==9
 weights=[v for v in probe.parameters() if tuple(v.shape)==(1,8)];biases=[v for v in probe.parameters() if tuple(v.shape)==(1,)];assert len(weights)==1 and len(biases)==1
 plain=x[:,0,:];expanded=torch.cat([plain,(plain[:,5]*plain[:,3]).unsqueeze(1),(plain[:,5]*plain[:,4]).unsqueeze(1)],dim=1);expected=(expanded@weights[0].T+biases[0]).reshape(-1);torch.testing.assert_close(probe(x).reshape(-1),expected)
 (root/'model_semantic_proof.json').write_text(json.dumps({'parameters':9,'independent_affine_interaction_oracle':True,'formula':'linear([x0..x5,x5*x3,x5*x4])','H':20,'no_input_feature_added_beyond_one_declared_factor':True}))
 # Hypothesis must claim an actual nonlinear factor interaction; model code reviewed before entry.
 a=x.clone();b=x.clone();c=x.clone();a[:,:,3]+=.7;b[:,:,5]+=.7;c[:,:,3]+=.7;c[:,:,5]+=.7
 interaction=probe(c)-probe(a)-probe(b)+probe(x);assert interaction.abs().max().item()>1e-7,'NO_VOLATILITY_NEW_FEATURE_INTERACTION';models['D']=fit_pt('NativeD','D',allcols)
result={}
for market,a in data.items():
 result[market]={}
 for name,model in models.items():
  cols=basecols if name in ['A','B'] else allcols;pred=model.predict(Data(cols,market));target=a['y'].reindex(pred.index);assert pred.index.equals(target.index) and np.isfinite(pred).all();ic,ric=calc_ic(pred,target);metrics={'IC':float(ic.mean()),'RankIC':float(ric.mean()),'MSE':float(((pred-target)**2).mean()),'MAE':float((pred-target).abs().mean()),'rows':len(pred),'dates':pred.index.get_level_values(0).nunique()};result[market][name]=metrics;pd.concat([pred.rename('prediction'),target.rename('target')],axis=1).to_csv(root/(market+'_'+name+'_predictions.csv'))
 # Feature as a standalone signal is distinct from models' predictive performance.
 feature=a['X'].loc[a['inner'],'new_liquidity_feature'];ic,ric=calc_ic(feature,a['y'].reindex(feature.index));result[market]['feature_standalone']={'IC':float(ic.mean()),'RankIC':float(ric.mean())}
# Only US internal results are returned to researcher. KR remains trusted evaluator evidence.
(root/('factor_metrics.json' if mode=='factor' else 'model_metrics.json')).write_text(json.dumps({'markets':result,'training':history,'US_only_fit':True,'KR_transfer_only':True,'H':20,'development_queried':False},indent=2))
# PTNN object class is defined in __main__, save state in native torch checkpoint, not full live class pickle.
ridges={k:v for k,v in models.items() if k in ['A','C']};(root/'models.pkl').write_bytes(pickle.dumps(ridges))
(root/'histories.json').write_text(json.dumps(history,indent=2));print(json.dumps(result))
