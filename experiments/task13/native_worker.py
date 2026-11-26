"""New native research; no old candidates, no outer-evaluation results mounted."""
from pathlib import Path
from types import SimpleNamespace
import sys,json,pickle,time,hashlib,traceback
import pandas as pd
sys.path.insert(0,'/oldcode');from native_factor_stage import ResearchScenario
class Scenario(ResearchScenario):
 def __init__(self):
  self.validation_note='';self.data=pd.read_csv('/train/panel.csv',parse_dates=['datetime']).set_index(['datetime','instrument']).sort_index()
 @property
 def experiment_setting(self):return 'TASK13: anonymous38US adjusted-provider-claim cohort. Research train2022..2024 only; repeated/exposed historical diagnostic, not PIT-proof or independent Holdout. No trade backtest, no portfolio/risk/annualized excess metrics. Hypothesis close t predicts open t+1 to open t+H+1. QuantaH20, RDH5. All mutations selected only on train descriptive evidence; no2025/2026 data. No future shifts or training normalization across validation.'
 @property
 def interface(self):return 'Factor: read ./daily_pv.h5 key=data MultiIndex(datetime,instrument), columns $open/$high/$low/$close/$volume/$return; export result.h5 key=data identical index one float score. Group rolling by instrument; cross-section rank per date. Max effective warmup63. Higher score predicts higher20session nextopen-to-open return. Model: torch model_cls(num_features,num_timesteps), forward [B,1,5]->[B]. CPU <=100parameters, linear or ONE hidden layer<=8units, no GRU/attention/sequence. Features ret1,mom20,mom60,vol20,relativevolume20; fit standardization supplied by host. Target raw5session return. No model I/O/training; host originalQlib trains20fixedepochs, no validation fitting.'
 def get_runtime_environment(self):return 'Python3.12 pandas numpy torchCPU Qlib; CPU2 memory4GB, no network or tools. Fit data only. Return one code, no hyperparameter grid.'
 def get_scenario_all_desc(self,*a,**k):return self.get_source_data_desc()+'\n'+self.interface+'\n'+self.experiment_setting+'\n'+self.validation_note

def run_q():
 from quantaalpha.pipeline.evolution import EvolutionController,EvolutionConfig
 from quantaalpha.pipeline.planning import generate_parallel_directions
 from quantaalpha.core.proposal import Trace
 from quantaalpha.factors.proposal import AlphaAgentHypothesisGen,AlphaAgentHypothesis2FactorExpression
 from quantaalpha.factors.coder.evolving_strategy import FactorParsingStrategy
 from quantaalpha.factors.coder.config import FACTOR_COSTEER_SETTINGS
 from quantaalpha.factors.feedback import AlphaAgentQlibFactorHypothesisExperiment2Feedback
 root=Path('/work');scen=Scenario();controller=EvolutionController(EvolutionConfig(num_directions=2,max_rounds=3,crossover_size=2,crossover_n=1,pool_save_path='/work/pool.json',fresh_start=True))
 directions=generate_parallel_directions('Two genuinely different hypotheses: liquidity-driven medium-term reversal versus volume-confirmed continuation. Each uses only OHLCV, primary20sessions, effective warmup<=63. No previous research results or false metrics. One formula per branch.',2,Path('/venv/lib/python3.12/site-packages/quantaalpha/pipeline/prompts/planning_prompts.yaml'),max_attempts=1,allow_fallback=False);assert len(directions)==2
 (root/'directions.json').write_text(json.dumps(directions));events=[];proposed_count=0
 while len(events)<5 and proposed_count<5:
  if len(events)==2:
   until=time.monotonic()+900
   while not (root/'phase2_authorization.json').exists():
    if time.monotonic()>until:raise TimeoutError('Phase2 gate missing')
    time.sleep(1)
   if not json.loads((root/'phase2_authorization.json').read_text())['allow']:break
  task=controller.get_next_task()
  if task is None:break
  phase=task['phase'].value;node=root/('Q'+str(len(events)));node.mkdir(exist_ok=True);trace=Trace(scen)
  before={'attempt_id':node.name,'phase':phase,'direction_id':task['direction_id'],'primary_H':20,'target':'OPEN_t1_TO_OPEN_t21_RETURN','max_effective_warmup':63,'parents':[p.trajectory_id for p in task['parent_trajectories']],'guidance':task['strategy_suffix'],'registered_before_generation':True};(node/'attempt.json').write_text(json.dumps(before,indent=2))
  direction=(str(directions[task['direction_id']]) if phase=='original' else '')+'\n'+task['strategy_suffix']+'\n'+scen.interface
  h=AlphaAgentHypothesisGen(scen,potential_direction=direction).gen(trace);exp=AlphaAgentHypothesis2FactorExpression(consistency_enabled=False).convert(h,trace);
  proposed_count+=len(exp.sub_tasks)
  (node/'all_proposed_tasks.json').write_text(json.dumps({'tasks':[vars(t) for t in exp.sub_tasks],'selection':'First original task in returned order before any score; extras preserved UNEXECUTED_NOT_REGISTERED; count in5proposal cap','proposed_total':proposed_count},indent=2,default=str))
  if proposed_count>5:raise ValueError('Quanta proposal cap exceeded; do not execute additional tasks')
  exp.sub_tasks=exp.sub_tasks[:1]
  code=FactorParsingStrategy(scen=scen,settings=FACTOR_COSTEER_SETTINGS).implement_one_task(exp.sub_tasks[0],None);assert isinstance(code,str)
  (node/'factor.py').write_text(code);(node/'generation.json').write_text(json.dumps({**before,'hypothesis':vars(h),'tasks':[vars(t) for t in exp.sub_tasks],'fingerprint':hashlib.sha256(code.encode()).hexdigest(),'native':'Original planning/controller/operators/proposal/DSL coder; external evaluator adapter','fullAlphaAgentLoop':False},indent=2,default=str))
  until=time.monotonic()+900
  while not (node/'metrics.json').exists():
   if time.monotonic()>until:raise TimeoutError('Fit evaluator did not reply')
   time.sleep(1)
  met=json.loads((node/'metrics.json').read_text());assert met['scope']=='FIT_ONLY_NO_OUTER_RESULTS'
  if met.get('failed'):raise RuntimeError('Native factor execution failed: '+str(met))
  scen.validation_note='Actual20session training-only IC/RankIC/spread; no strategy or annualized excess aliases. Exploratory in-sample, not validation: '+json.dumps(met)
  exp.sub_tasks[0].factor_implementation=True;exp.sub_workspace_list=[SimpleNamespace(code_dict={'factor.py':code})];exp.result=pd.DataFrame({'0':{'IC':met['IC'],'RankIC':met['RankIC']}})
  fb=AlphaAgentQlibFactorHypothesisExperiment2Feedback(scen).generate_feedback(exp,h,trace);(node/'feedback.json').write_text(json.dumps(vars(fb),indent=2,default=str))
  tr=controller.create_trajectory_from_loop_result(task,h,exp,fb);controller.report_task_complete(task,tr);controller.save_state(root/'controller.json');events.append({**before,'trajectory_id':tr.trajectory_id});(root/'events.json').write_text(json.dumps(events,indent=2))
  with (node/'native_state.pkl').open('wb') as f:pickle.dump({'task':task,'hypothesis':h,'exp':exp,'feedback':fb},f)
 print('NEW_NATIVE_QUANTA_NODES',len(events),flush=True)
def run_rd():
 from rdagent.core.proposal import Trace
 from rdagent.scenarios.qlib.proposal.model_proposal import QlibModelHypothesisGen,QlibModelHypothesis2Experiment
 from rdagent.components.coder.model_coder.model import ModelFBWorkspace
 from rdagent.components.coder.model_coder.evolving_strategy import ModelMultiProcessEvolvingStrategy
 from rdagent.components.coder.model_coder.conf import MODEL_COSTEER_SETTINGS
 scen=Scenario();h=QlibModelHypothesisGen(scen).gen(Trace(scen));exp=QlibModelHypothesis2Experiment().convert(h,Trace(scen));assert len(exp.sub_tasks)==1
 task=exp.sub_tasks[0];task.description+=' '+scen.interface;ws=ModelFBWorkspace(target_task=task);code=ModelMultiProcessEvolvingStrategy(scen=scen,settings=MODEL_COSTEER_SETTINGS).implement_one_task(task,None,workspace=ws)
 root=Path('/work');(root/'model.py').write_text(code);(root/'generation.json').write_text(json.dumps({'hypothesis':vars(h),'tasks':[vars(t) for t in exp.sub_tasks],'fingerprint':hashlib.sha256(code.encode()).hexdigest(),'native':'Original RD hypothesis/experiment/CoSTEER, independent originalQlib training','full_fin_quant':False,'primary_H':5},indent=2,default=str));print('NEW_NATIVE_RD_CODE',flush=True)
if __name__=='__main__':
 try:run_q() if sys.argv[1]=='quanta' else run_rd()
 except Exception as exc:Path('/work/failure.json').write_text(json.dumps({'type':type(exc).__name__,'error':str(exc)},indent=2));traceback.print_exc();raise
