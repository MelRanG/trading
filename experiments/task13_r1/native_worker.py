"""New native research; no old candidates, no outer-evaluation results mounted."""
from pathlib import Path
from types import SimpleNamespace
import sys,json,pickle,time,hashlib,traceback
import pandas as pd
sys.path.insert(0,'/oldcode');from native_factor_stage import ResearchScenario
class Scenario(ResearchScenario):
 def __init__(self):
  self.validation_note='';self.data=pd.read_hdf('/train/US_train.h5',key='data')
 @property
 def experiment_setting(self):return 'TASK13_R1: anonymous176US survivor research, train2017..2022 only. No future data/validation prices. OHLCV adjusted research; higher score forecasts nextopen to20session later open. Common63valid past sessions; >=50names. Only measured train and trusted dev IC/RankIC/spread, never annualized excess aliases. Mechanisms: overnight/intraday asymmetry and liquidity shocks with price resilience; do not merely rename momentum/reversal.'
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
 root=Path('/work');scen=Scenario();controller=EvolutionController(EvolutionConfig(num_directions=2,max_rounds=3,crossover_size=2,crossover_n=1,pool_save_path='/work/pool.json',fresh_start=not (root/'events.json').exists()))
 directions=generate_parallel_directions('Two genuinely different economic mechanisms: overnight-versus-intraday return asymmetry and liquidity shocks with price resilience. OHLCV only, positive orientation20session future return, maximum past lookback63. Distinguish from simple momentum/reversal; no future or imagined metrics.',2,Path('/venv/lib/python3.12/site-packages/quantaalpha/pipeline/prompts/planning_prompts.yaml'),max_attempts=1,allow_fallback=False);assert len(directions)==2
 (root/'directions.json').write_text(json.dumps(directions));events=json.loads((root/'events.json').read_text()) if (root/'events.json').exists() else [];proposed_count=0
 if events:controller.load_state(root/'controller.json')
 while len(events)<4:
  if len(events)==2:
   until=time.monotonic()+900
   while not (root/'phase2_authorization.json').exists():
    if time.monotonic()>until:raise TimeoutError('Phase2 gate missing')
    time.sleep(1)
   if not json.loads((root/'phase2_authorization.json').read_text())['allow']:break
  task=controller.get_next_task()
  if task is None:break
  phase=task['phase'].value;node=root/('Q'+str(len(events)));node.mkdir(exist_ok=True);scen.validation_note=''
  parent_ids=[p.trajectory_id for p in task['parent_trajectories']]
  bindings=[{'parent':e['trajectory_id'],'evaluation':json.loads((root/e['attempt_id']/'metrics.json').read_text())} for e in events if e['trajectory_id'] in parent_ids]
  if bindings:scen.validation_note='EXACT_PARENT_EVALUATIONS, not other branches: '+json.dumps(bindings)
  trace=Trace(scen)
  before={'attempt_id':node.name,'phase':phase,'direction_id':task['direction_id'],'primary_H':20,'target':'OPEN_t1_TO_OPEN_t21_RETURN','max_effective_warmup':63,'parents':[p.trajectory_id for p in task['parent_trajectories']],'guidance':task['strategy_suffix'],'registered_before_generation':True};(node/'attempt.json').write_text(json.dumps(before,indent=2))
  direction=(str(directions[task['direction_id']]) if phase=='original' else '')+'\n'+task['strategy_suffix']+'\n'+scen.interface
  h=AlphaAgentHypothesisGen(scen,potential_direction=direction).gen(trace);exp=AlphaAgentHypothesis2FactorExpression(consistency_enabled=False).convert(h,trace);
  proposed_count+=len(exp.sub_tasks)
  (node/'all_proposed_tasks.json').write_text(json.dumps({'tasks':[vars(t) for t in exp.sub_tasks],'selection':'First original task in returned order before any score; extras preserved UNEXECUTED_NOT_REGISTERED; count in5proposal cap','proposed_total':proposed_count},indent=2,default=str))
  # All proposals recorded; execute first task by frozen return order, never performance selection.
  exp.sub_tasks=exp.sub_tasks[:1]
  code=FactorParsingStrategy(scen=scen,settings=FACTOR_COSTEER_SETTINGS).implement_one_task(exp.sub_tasks[0],None);assert isinstance(code,str)
  (node/'factor.py').write_text(code);(node/'generation.json').write_text(json.dumps({**before,'hypothesis':vars(h),'tasks':[vars(t) for t in exp.sub_tasks],'fingerprint':hashlib.sha256(code.encode()).hexdigest(),'native':'Original planning/controller/operators/proposal/DSL coder; external evaluator adapter','fullAlphaAgentLoop':False},indent=2,default=str))
  until=time.monotonic()+900
  while not (node/'metrics.json').exists():
   if time.monotonic()>until:raise TimeoutError('Fit evaluator did not reply')
   time.sleep(1)
  met=json.loads((node/'metrics.json').read_text());assert met['scope']=='FIT_ONLY_NO_OUTER_RESULTS'
  if met.get('failed'):raise RuntimeError('Native factor execution failed: '+str(met))
  scen.validation_note='ACTUALLY EVALUATED candidate ID/code hash/H20 binding below. Train metrics and permitted dev summaries only, not an annualized excess return or backtest. Use measured evidence, never say unevaluated: '+json.dumps(met)
  exp.sub_tasks[0].factor_implementation=True;exp.sub_workspace_list=[SimpleNamespace(code_dict={'factor.py':code})];exp.result=pd.DataFrame({'0':{'IC':met['IC'],'RankIC':met['RankIC']}})
  fb=AlphaAgentQlibFactorHypothesisExperiment2Feedback(scen).generate_feedback(exp,h,trace);(node/'feedback.json').write_text(json.dumps(vars(fb),indent=2,default=str))
  tr=controller.create_trajectory_from_loop_result(task,h,exp,fb);controller.report_task_complete(task,tr);controller.save_state(root/'controller.json');events.append({**before,'trajectory_id':tr.trajectory_id});(root/'events.json').write_text(json.dumps(events,indent=2))
  with (node/'native_state.pkl').open('wb') as f:pickle.dump({'task':task,'hypothesis':h,'exp':exp,'feedback':fb},f)
 print('NEW_NATIVE_QUANTA_NODES',len(events),flush=True)

if __name__=='__main__':
 try:run_q()
 except Exception as exc:Path('/work/failure.json').write_text(json.dumps({'type':type(exc).__name__,'error':str(exc)}));traceback.print_exc();raise
