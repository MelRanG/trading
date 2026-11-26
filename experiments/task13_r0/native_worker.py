"""Shared train-only data ABI. No hypotheses, model fitting or economic tests."""
from pathlib import Path
import sys,json,hashlib
import pandas as pd,numpy as np
R=Path('/repo');B=Path('/work');source=R/'runtime/task13_r0'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
if sys.argv[1]=='build':
 assets=json.loads((source/'native_manifest/assets.json').read_text());records={}
 for m in ['US','KR']:
  parts=[];mapping=[]
  for a in [a for a in assets if a['market']==m]:
   p=R/a['adjusted_path'];assert sha(p)==a['adjusted_hash'];ep=R/a['eligibility_path'];assert sha(ep)==a['eligibility_hash'];days=pd.read_csv(R/a['calendar_path'],index_col='date',parse_dates=True).index
   f=pd.read_csv(p,index_col='date',parse_dates=True).reindex(days);eligible=pd.read_csv(ep,index_col='date',parse_dates=True).eligible.reindex(days).eq(True);f=f.where(eligible,axis=0).loc[:'2022-12-31'];alias=m+hashlib.sha256(('R0_ANON_'+a['symbol']).encode()).hexdigest()[:10]
   f['return']=f.close.pct_change(fill_method=None);f.columns=['$'+c for c in f.columns];f['instrument']=alias;f.index.name='datetime';parts.append(f.set_index('instrument',append=True));mapping.append({'native_alias':alias,'symbol':a['symbol'],'cohort':a['cohort'],'source_path':a['adjusted_path'],'source_hash':a['adjusted_hash'],'eligibility_hash':a['eligibility_hash']})
  data=pd.concat(parts).sort_index();p=B/(m+'_train.h5');data.to_hdf(p,key='data');(B/(m+'_private_mapping.json')).write_text(json.dumps(mapping,indent=2));records[m]={'path':'runtime/task13_r0/native/'+p.name,'sha256':sha(p),'instruments':data.index.get_level_values(1).nunique(),'rows':len(data),'finite_OHLCV_rows':int(np.isfinite(data.iloc[:,:5]).all(axis=1).sum()),'first':str(data.index.get_level_values(0).min().date()),'last':str(data.index.get_level_values(0).max().date()),'label_columns':[],'future_or_current_cap_sector_features':False,'cohort_note':'CombinedKR core+eligible small cohort, private mapping kept outside researcher mount. Group analyses must retain strata; small7 not standalone>=8crosssection.'}
 (B/'inputs.json').write_text(json.dumps(records,indent=2));print('SHARED_INPUTS',records)
elif sys.argv[1]=='probe':
 from qlib.data.dataset import DatasetH
 from qlib.contrib.model.linear import LinearModel
 from rdagent.scenarios.qlib.proposal.model_proposal import QlibModelHypothesisGen
 from rdagent.components.coder.model_coder.evolving_strategy import ModelMultiProcessEvolvingStrategy
 sys.path.insert(0,'/repo/experiments/task13_r0');from loader import supervised
 sys.path.insert(0,'/vibe');from src.factors.registry import get_default_registry
 outputs={}
 class SharedDataset(DatasetH):
  def __init__(self,frame):self.frame=frame;self.segments={'train':None}
  def prepare(self,segment,**kwargs):return self.frame
 for m in ['US','KR']:
  data=pd.read_hdf('/inputs/'+m+'_train.h5',key='data');panel={k:data['$'+k].unstack('instrument') for k in ['open','high','low','close','volume']};values={}
  for fid in ['qlib158_roc20','qlib158_std20']:
   v=get_default_registry().compute(fid,panel);values[fid]={'shape':list(v.shape),'finite':int(np.isfinite(v.to_numpy()).sum()),'scope':'EXISTING_FUNCTION_INPUT_ABI_NOT_NEW_ALPHA_OR_PERFORMANCE'}
  model=LinearModel(estimator='ridge',alpha=1.,include_valid=False);sample=data.dropna().iloc[:100];adapter=SharedDataset(sample);assert adapter.prepare('train').shape==sample.shape
  label_abi={}
  for H in [5,20,60]:
   frame,info=supervised(data,H);typed=SharedDataset(frame);assert typed.prepare('train').feature.shape[1]==5;label_abi[str(H)]=info
  outputs[m]={'supervised_H5_H20_H60':label_abi,'rows':len(data),'dates':data.index.get_level_values(0).nunique(),'stocks':data.index.get_level_values(1).nunique(),'native_Vibe':values,'QlibDatasetH_prepare':True,'Ridge_constructor_not_fit':isinstance(model,LinearModel),'RD_original_model_proposal_coder_imported':bool(QlibModelHypothesisGen and ModelMultiProcessEvolvingStrategy),'training_jobs':0,'LLM_calls':0}
 (B/'probe.json').write_text(json.dumps(outputs,indent=2));print('NATIVE_INPUT_PROBE',outputs)
elif sys.argv[1]=='quanta':
 from quantaalpha.factors.coder.function_lib import DELAY,RANK
 from quantaalpha.pipeline.evolution import EvolutionController,EvolutionConfig
 results={}
 for m in ['US','KR']:
  d=pd.read_hdf('/inputs/'+m+'_train.h5',key='data');x=RANK(d['$close']/DELAY(d['$close'],20)-1);assert x.index.equals(d.index);results[m]={'native_DSL_operations':'DELAY/RANK original input ABI fixture, not a generatedcandidate','rows':len(x),'finite':int(x.notna().sum()),'index_preserved':True,'planner_evolution_controller_available':bool(EvolutionController),'evolution_executed':False,'LLM_calls':0}
 (B/'quanta_probe.json').write_text(json.dumps(results,indent=2));print(results)
