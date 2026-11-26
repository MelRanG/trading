"""Offline native input/ABI probes only. No fitting or strategy evaluation."""
from pathlib import Path
import sys,json,hashlib,importlib.util,inspect
import pandas as pd,numpy as np
ROOT=Path('/data');out={}
if sys.argv[1]=='vibe':
 sys.path.insert(0,'/native')
 from src.factors.registry import get_default_registry
 from src.research_lab import service
 reg=get_default_registry();names=reg.list();frames={p.stem:pd.read_csv(p,index_col='date',parse_dates=True).iloc[:120] for p in sorted((ROOT/'US').glob('US0*.csv'))[:4]};panel={k:pd.DataFrame({s:f[k] for s,f in frames.items()}) for k in ['open','high','low','close','volume']}
 for name in ['alpha101_012','alpha101_009']:
  values=reg.compute(name,panel);changed={k:v.copy() for k,v in panel.items()};cut=values.index[79]
  for v in changed.values():v.loc[v.index>cut]*=2
  after=reg.compute(name,changed);pd.testing.assert_frame_equal(values.loc[:cut],after.loc[:cut]);out[name]={'shape':list(values.shape),'finite_cells':int(np.isfinite(values.to_numpy()).sum()),'prefix_invariance':True,'economic_test':False,'output_hash':hashlib.sha256(values.to_json().encode()).hexdigest()}
 out.update(native_catalog=len(names),registry_health=reg.health(),research_lab_run_callable=callable(service.run),research_lab_execution='PRE existing run reused, no new backtest')
elif sys.argv[1]=='qa':
 from quantaalpha.pipeline.evolution import EvolutionController,EvolutionConfig
 from quantaalpha.factors.proposal import AlphaAgentHypothesisGen,AlphaAgentHypothesis2FactorExpression
 from quantaalpha.factors.coder.evolving_strategy import FactorParsingStrategy
 from quantaalpha.factors.feedback import AlphaAgentQlibFactorHypothesisExperiment2Feedback
 controller=EvolutionController(EvolutionConfig(num_directions=2,max_rounds=3,pool_save_path='/qa_saved/pool.json',fresh_start=False));controller.load_state(Path('/qa_saved/controller.json'))
 out={'restored_trajectories':len(controller.pool.get_all()),'planner_callable':True,'DSL_coder':FactorParsingStrategy.__name__,'proposal':AlphaAgentHypothesisGen.__name__,'feedback':AlphaAgentQlibFactorHypothesisExperiment2Feedback.__name__,'new_hypotheses':0,'LLM_calls':0,'fullAlphaAgentLoop':False,'scenario_horizon':'Original API accepts custom Scenario; old Task10 worker is fixed5/GRU16 and is not the Task13 policy'}
else:
 import torch,importlib.metadata
 torch.set_num_threads(2)
 from qlib.contrib.model.linear import LinearModel
 from qlib.contrib.model.pytorch_general_nn import GeneralPTNN
 from qlib.contrib.eva.alpha import calc_ic
 from rdagent.scenarios.qlib.proposal.model_proposal import QlibModelHypothesisGen
 from rdagent.components.coder.model_coder.evolving_strategy import ModelMultiProcessEvolvingStrategy
 out['linear']={'class':LinearModel.__name__,'ridge_constructor':isinstance(LinearModel(estimator='ridge',alpha=1.),LinearModel),'trained':False}
 try:
  from qlib.contrib.model.gbdt import LGBModel
  out['tree']={'class':LGBModel.__name__,'import':'PASS','trained':False}
 except Exception as e:out['tree']={'import':'BLOCKED','error_type':type(e).__name__}
 from qlib.contrib.model.pytorch_gru import GRU
 out['sequence']={'class':GRU.__name__,'trainer':GeneralPTNN.__name__,'trained':False}
 idx=pd.MultiIndex.from_product([pd.date_range('2025-01-01',periods=2),list('abcdefghij')],names=['datetime','instrument']);x=pd.Series(list(range(1,11))*2,index=idx);ic,rank=calc_ic(x,x);assert np.isclose(ic.mean(),1) and np.isclose(rank.mean(),1)
 sys.path[:0]=['/repo/experiments/task12','/repo/src']
 from evaluation import signal_statistics
 result=signal_statistics(x.unstack('instrument'),x.unstack('instrument'),native_ic=calc_ic);assert np.isclose(result['IC'].mean(),1) and result['spread']
 out['common_layer1_route']={'original_qlib_IC_used':True,'scope':'SYNTHETIC_ADAPTER_TEST_NOT_INVESTMENT_PERFORMANCE'}
 out['native_metrics']={'PearsonIC':float(ic.mean()),'RankIC':float(rank.mean()),'scope':'SYNTHETIC_ABI_CHECK_NOT_ALPHA'}
 code=Path('/model/model.py');spec=importlib.util.spec_from_file_location('generated',code);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);model=mod.model_cls(num_features=5,num_timesteps=20);state=torch.load('/checkpoint/model.pth',map_location='cpu',weights_only=True);model.load_state_dict({k.removeprefix('native.'):v for k,v in state.items()});model.eval()
 with torch.no_grad():pred=model(torch.zeros((2,20,5)))
 assert torch.isfinite(pred).all();out['frozen_checkpoint']={'forward_shape':list(pred.shape),'finite':True,'code_hash':hashlib.sha256(code.read_bytes()).hexdigest(),'checkpoint_hash':hashlib.sha256(Path('/checkpoint/model.pth').read_bytes()).hexdigest(),'trained_or_updated':False}
 out['native_research_apis']={'hypothesis_class':QlibModelHypothesisGen.__name__,'coder_class':ModelMultiProcessEvolvingStrategy.__name__,'new_LLM_calls':0,'full_fin_quant_executed':False}
 out['versions']={k:importlib.metadata.version(k) for k in ['rdagent','pyqlib','torch','scikit-learn']}
Path('/out/'+sys.argv[1]+'_probe.json').write_text(json.dumps(out,indent=2,default=str));print(json.dumps(out,default=str))
