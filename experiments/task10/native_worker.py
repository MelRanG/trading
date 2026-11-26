"""Native specialist components; researcher sees only current training prefix."""
from pathlib import Path
import sys,json,pickle,hashlib,traceback
sys.path.insert(0,'/oldcode')
from native_factor_stage import ResearchScenario
class Scenario(ResearchScenario):
 @property
 def experiment_setting(self):return Path('/work/context.json').read_text()
 def get_runtime_environment(self):return 'Python3.12 pandas numpy torchCPU Qlib, CPU2. No tools or host network. One causal factor or GRU16 only. No future labels/data. Data are anonymous price-volume training prefix only.'
 @property
 def interface(self):return 'Factor: ./daily_pv.h5 key=data, MultiIndex(datetime,instrument), $open/$high/$low/$close/$volume/$return. Export result.h5 key=data identical index one float column; no forward shift, bfill, centerrolling, global time normalization, use only causal rolling <=63sessions. Higher predicts nextopen t+1 toopen t+6 return, five-session holding. Model: model_cls(num_features,num_timesteps),forward [B,20,F]->[B] tensor. No model I/O or traininginside model; host originalQlib trains5epochs.'

def generate_q(stage):
 from quantaalpha.pipeline.evolution import EvolutionController,EvolutionConfig
 from quantaalpha.pipeline.planning import generate_parallel_directions
 from quantaalpha.core.proposal import Trace
 from quantaalpha.factors.proposal import AlphaAgentHypothesisGen,AlphaAgentHypothesis2FactorExpression
 from quantaalpha.factors.coder.evolving_strategy import FactorParsingStrategy
 from quantaalpha.factors.coder.config import FACTOR_COSTEER_SETTINGS
 root=Path('/work');node=root/stage;node.mkdir(exist_ok=True);scen=Scenario()
 cfg=EvolutionConfig(num_directions=1,max_rounds=2,crossover_enabled=False,pool_save_path='/work/pool.json',fresh_start=stage=='initial')
 controller=EvolutionController(cfg)
 if stage!='initial':controller.load_state(root/'controller.json')
 if (node/'factor.py').exists():return
 if stage=='initial':
  directions=generate_parallel_directions('One economically motivated low-turnover past-only price-volume factor for 5session nextopen-to-nextopen stock selection. No arbitrary search grids, <=63lookback. All profits unknown.',1,Path('/venv/lib/python3.12/site-packages/quantaalpha/pipeline/prompts/planning_prompts.yaml'),max_attempts=1,allow_fallback=False);(root/'directions.json').write_text(json.dumps(directions));assert len(directions)==1
 else:directions=['']
 task=controller.get_next_task();assert task is not None;phase=task['phase'].value;assert phase==('original' if stage=='initial' else 'mutation')
 direction=(directions[0] if stage=='initial' else '')+'\n'+task['strategy_suffix']+'\n'+scen.experiment_setting
 trace=Trace(scen);h=AlphaAgentHypothesisGen(scen,potential_direction=direction).gen(trace);exp=AlphaAgentHypothesis2FactorExpression(consistency_enabled=False).convert(h,trace);assert len(exp.sub_tasks)==1,'Onlyonefactor allowed';code=FactorParsingStrategy(scen=scen,settings=FACTOR_COSTEER_SETTINGS).implement_one_task(exp.sub_tasks[0],None)
 (node/'factor.py').write_text(code);info={'stage':stage,'phase':phase,'asof':json.loads(scen.experiment_setting)['asof'],'parents':[p.trajectory_id for p in task['parent_trajectories']],'guidance':task['strategy_suffix'],'hypothesis':vars(h),'tasks':[vars(t) for t in exp.sub_tasks],'code_hash':hashlib.sha256(code.encode()).hexdigest(),'native_controller':True,'fullAlphaAgentLoop':False};(node/'generation.json').write_text(json.dumps(info,default=str,indent=2))
 with (node/'state.pkl').open('wb') as f:pickle.dump({'hypothesis':h,'exp':exp,'trace':trace,'task':task},f)
 controller.save_state(root/'pending_controller.json');print('NATIVE_FACTOR_GENERATED',stage,flush=True)

def feedback_q(stage):
 from quantaalpha.pipeline.evolution import EvolutionController,EvolutionConfig
 from quantaalpha.factors.feedback import AlphaAgentQlibFactorHypothesisExperiment2Feedback
 from types import SimpleNamespace
 import pandas as pd
 root=Path('/work');node=root/stage
 if (node/'feedback.json').exists():return
 with (node/'state.pkl').open('rb') as f:z=pickle.load(f)
 scen=z['trace'].scen;met=json.loads((node/'metrics.json').read_text());scen.validation_note='Actual same-cutoff historical development evaluation, NOTfuture/independentForward. '+json.dumps(met);exp=z['exp'];exp.sub_tasks[0].factor_implementation=True;exp.sub_workspace_list=[SimpleNamespace(code_dict={'factor.py':(node/'factor.py').read_text()})];exp.result=pd.DataFrame({'0':met['native_aliases']});fb=AlphaAgentQlibFactorHypothesisExperiment2Feedback(scen).generate_feedback(exp,z['hypothesis'],z['trace']);(node/'feedback.json').write_text(json.dumps(vars(fb),indent=2,default=str));controller=EvolutionController(EvolutionConfig(num_directions=1,max_rounds=2,crossover_enabled=False,pool_save_path='/work/pool.json',fresh_start=False));controller.load_state(root/'pending_controller.json');trajectory=controller.create_trajectory_from_loop_result(z['task'],z['hypothesis'],exp,fb);controller.report_task_complete(z['task'],trajectory);controller.save_state(root/'controller.json');print('NATIVE_FEEDBACK_POOL_SAVED',stage,flush=True)

def generate_rd():
 from rdagent.core.proposal import Trace
 from rdagent.scenarios.qlib.proposal.model_proposal import QlibModelHypothesisGen,QlibModelHypothesis2Experiment
 from rdagent.components.coder.model_coder.model import ModelTask,ModelFBWorkspace
 from rdagent.components.coder.model_coder.evolving_strategy import ModelMultiProcessEvolvingStrategy
 from rdagent.components.coder.model_coder.conf import MODEL_COSTEER_SETTINGS
 root=Path('/work');scen=Scenario();trace=Trace(scen)
 if (root/'model.py').exists():return
 h=QlibModelHypothesisGen(scen).gen(trace);exp=QlibModelHypothesis2Experiment().convert(h,trace);task=exp.sub_tasks[0];task.description+=' CPU causal GRU hidden16, one layer, flexible num_features. model_cls(num_features,num_timesteps), forward [B,20,F] ->[B]. NO I/O/training. HostQlibhandles5epochs.';ws=ModelFBWorkspace(target_task=task);code=ModelMultiProcessEvolvingStrategy(scen=scen,settings=MODEL_COSTEER_SETTINGS).implement_one_task(task,None,workspace=ws);(root/'model.py').write_text(code);(root/'generation.json').write_text(json.dumps({'hypothesis':vars(h),'task':vars(task),'extra_unexecuted_tasks':len(exp.sub_tasks)-1,'asof':json.loads(scen.experiment_setting)['asof'],'origin':'ORIGINAL_RD_MODEL_HYPOTHESIS_EXPERIMENT_COSTEER','full_fin_quant':False},default=str,indent=2))
 print('NATIVE_RD_MODEL_GENERATED',flush=True)
def feedback_rd():
 from rdagent.core.proposal import Hypothesis,Trace
 from rdagent.components.coder.model_coder.model import ModelTask,ModelFBWorkspace
 from rdagent.scenarios.qlib.experiment.model_experiment import QlibModelExperiment
 from rdagent.scenarios.qlib.developer.feedback import QlibModelExperiment2Feedback
 import pandas as pd
 root=Path('/work')
 if (root/'model_feedback.json').exists():return
 z=json.loads((root/'generation.json').read_text());m=json.loads((root/'feedback_metrics.json').read_text());scen=Scenario();scen.validation_note='Real same-cutoff prefixtraining/validation/retraining results, notfutureorindependentalpha: '+json.dumps(m);task=ModelTask.from_dict(z['task']);ws=ModelFBWorkspace(target_task=task);ws.file_dict={'model.py':(root/'model.py').read_text()};exp=QlibModelExperiment([task],hypothesis=Hypothesis(**z['hypothesis']));exp.sub_workspace_list=[ws];exp.result=pd.DataFrame({'0':m['candidate']['native_aliases']});fb=QlibModelExperiment2Feedback(scen).generate_feedback(exp,Trace(scen));(root/'model_feedback.json').write_text(json.dumps(vars(fb),indent=2,default=str));print('NATIVE_RD_FEEDBACK',flush=True)

if __name__=='__main__':
 try:
  mode=sys.argv[1];stage=sys.argv[2] if len(sys.argv)>2 else 'initial'
  if mode=='q':generate_q(stage)
  elif mode=='qfeedback':feedback_q(stage)
  elif mode=='rd':generate_rd()
  elif mode=='rdfeedback':feedback_rd()
 except Exception as e:Path('/work/last_failure.json').write_text(json.dumps({'mode':sys.argv[1:],'type':type(e).__name__,'error':str(e)}));traceback.print_exc();raise
