"""Original EvolutionController/planner/operators; explicit common evaluator bridge."""
from pathlib import Path
from types import SimpleNamespace
import json,pickle,time,hashlib,sys,traceback
sys.path.insert(0,'/oldcode')
from native_factor_stage import ResearchScenario
from quantaalpha.pipeline.evolution import EvolutionController,EvolutionConfig
from quantaalpha.pipeline.planning import generate_parallel_directions
from quantaalpha.core.proposal import Trace
from quantaalpha.factors.proposal import AlphaAgentHypothesisGen,AlphaAgentHypothesis2FactorExpression
from quantaalpha.factors.coder.evolving_strategy import FactorParsingStrategy
from quantaalpha.factors.coder.config import FACTOR_COSTEER_SETTINGS
from quantaalpha.factors.feedback import AlphaAgentQlibFactorHypothesisExperiment2Feedback
class Scenario(ResearchScenario):
 @property
 def experiment_setting(self):return 'Train<=2024; repeated2025 diagnostic. No2026 data. Signal close t, entry open t+1, exit close t+1, top4 positive at20%, cost both sides; no overnight.'

def main():
 root=Path('/work')
 if (root/'result.json').exists():
  print((root/'result.json').read_text());return
 scen=Scenario();controller=EvolutionController(EvolutionConfig(num_directions=2,max_rounds=3,crossover_size=2,crossover_n=1,pool_save_path='/work/pool.json',fresh_start=True));directions=generate_parallel_directions('Discover diverse economically motivated past-only OHLCV mechanisms for anonymous US stocks. No final data or fictitious evaluation.',2,Path('/venv/lib/python3.12/site-packages/quantaalpha/pipeline/prompts/planning_prompts.yaml'),max_attempts=1,allow_fallback=False)
 if len(directions)!=2:raise ValueError('planning failed')
 (root/'directions.json').write_text(json.dumps(directions));events=[]
 # Bound the adapter by the preregistered 2 original +2 mutation +1 crossover.
 # Native phase transition can otherwise dispatch one task beyond max_rounds.
 while len(events)<5:
  task=controller.get_next_task()
  if task is None:break
  phase=task['phase'].value;node=root/f'node{len(events)}';node.mkdir();trace=Trace(scen)
  direction=(directions[task['direction_id']] if phase=='original' else '')+'\n'+task['strategy_suffix']
  h=AlphaAgentHypothesisGen(scen,potential_direction=direction).gen(trace);exp=AlphaAgentHypothesis2FactorExpression(consistency_enabled=False).convert(h,trace)
  if len(exp.sub_tasks)!=1:raise ValueError('exactly one factor required')
  code=FactorParsingStrategy(scen=scen,settings=FACTOR_COSTEER_SETTINGS).implement_one_task(exp.sub_tasks[0],None);(node/'factor.py').write_text(code)
  info={'phase':phase,'round':task['round_idx'],'direction':task['direction_id'],'parents':[p.trajectory_id for p in task['parent_trajectories']],'guidance':task['strategy_suffix'],'hypothesis':vars(h),'tasks':[vars(t) for t in exp.sub_tasks],'code_sha256':hashlib.sha256(code.encode()).hexdigest()};(node/'request.json').write_text(json.dumps(info,indent=2,default=str))
  until=time.monotonic()+300
  while not (node/'metrics.json').exists():
   if time.monotonic()>until:raise TimeoutError('independent evaluator did not reply')
   time.sleep(1)
  metrics=json.loads((node/'metrics.json').read_text())
  if metrics.get('status')=='FAILED':raise RuntimeError(metrics)
  exp.sub_tasks[0].factor_implementation=True;exp.sub_workspace_list=[SimpleNamespace(code_dict={'factor.py':code})]
  import pandas as pd
  exp.result=pd.DataFrame({'0':metrics['native_aliases']})
  scen.validation_note='ACTUAL repeated2025 aligned-intraday evaluation, not independent holdout; all net/gross/IC: '+json.dumps(metrics)
  fb=AlphaAgentQlibFactorHypothesisExperiment2Feedback(scen).generate_feedback(exp,h,trace);(node/'feedback.json').write_text(json.dumps(vars(fb),indent=2,default=str))
  trajectory=controller.create_trajectory_from_loop_result(task,h,exp,fb);controller.report_task_complete(task,trajectory);controller.save_state(root/'controller.json');events.append({**info,'trajectory_id':trajectory.trajectory_id,'metrics':metrics,'feedback':vars(fb)});(root/'events.json').write_text(json.dumps(events,indent=2,default=str))
  with (node/'state.pkl').open('wb') as f:pickle.dump({'h':h,'exp':exp,'feedback':fb},f)
 assert set(e['phase'] for e in events)=={'original','mutation','crossover'}
 restored=EvolutionController(EvolutionConfig(num_directions=2,max_rounds=3,pool_save_path='/work/pool.json',fresh_start=False));restored.load_state(root/'controller.json')
 (root/'result.json').write_text(json.dumps({'status':'PASS_ORIGINAL_EVOLUTION_CONTROLLER_WITH_EXTERNAL_EVALUATOR','nodes':len(events),'phase_counts':{p:sum(e['phase']==p for e in events) for p in ['original','mutation','crossover']},'restored_pool_count':len(restored.pool.get_all()),'native_alpha_agent_loop':False,'adapter':'Original controller, planner, mutation/crossover operators and proposal/coder/feedback. Qlib backtest replaced with explicit aligned evaluation bridge.'},indent=2))
if __name__=='__main__':
 try:main()
 except Exception as e:Path('/work/failure.json').write_text(json.dumps({'type':type(e).__name__,'error':str(e)},indent=2));traceback.print_exc();raise
