"""Original specialist proposal/coding APIs with a declared dataset adapter.

Run only inside its own offline credential-free worker. Full native Qlib loop
and these bounded component calls are distinguished in receipts.
"""
from pathlib import Path
import argparse,json,time,pickle,traceback,hashlib,subprocess,sys
import pandas as pd


class ResearchScenario:
 def __init__(self):
  self.validation_note='';self.data=pd.read_hdf('/work/data/daily_pv.h5',key='data')
 @property
 def background(self):return self.get_scenario_all_desc()
 @property
 def rich_style_description(self):return 'Frozen US-primary OHLCV research; cross-market transfer diagnostic'
 @property
 def interface(self):return 'Read ./daily_pv.h5 key=data; MultiIndex datetime,instrument; produce result.h5 key=data, one float factor column/Series on the identical index. Strictly causal, higher value predicts higher next-session close/open return.'
 @property
 def output_format(self):return self.interface
 @property
 def simulator(self):return 'Independent validation/common execution worker. No production orders or final outcomes available.'
 @property
 def experiment_setting(self):return 'Train <=2024-12-31, selection validation2025, hidden final2026. Fixed 20% top4 positive scores, max80% gross, transaction costs. No native Qlib benchmark substitution.'
 def get_runtime_environment(self):return f'Python3.12, CPU, pandas{pd.__version__}. numpy/pandas/scikit-learn/lightgbm available. No conda/Docker socket/network/torch/GPU.'
 def get_source_data_desc(self,*args,**kwargs):return f'Training-only adjusted OHLCV, {self.data.index.get_level_values("instrument").nunique()} anonymous US stocks; first/last date {self.data.index.get_level_values("datetime").min()} / {self.data.index.get_level_values("datetime").max()}. Columns {list(self.data.columns)}.\n{self.data.head(3).to_string()}'
 def get_scenario_all_desc(self,*args,**kwargs):return ('Generate exactly ONE factor per hypothesis, no candidate grids. Prefer a distinct economic market mechanism, not arbitrary indicator mixing. Use only past/current OHLCV and past returns; no forward shifts, future labels, data access outside the training file, or invented performance. Missing $factor/$vwap/fundamentals must not be fabricated. All grouping is within one market at a time. Keep turnover/cost/risk in mind.\n'+self.get_source_data_desc()+'\n'+self.interface+'\n'+self.experiment_setting+'\n'+self.validation_note)


def hydrate_previous(previous,engine):
 from types import SimpleNamespace
 exp=previous['experiment'];code=Path('/work/attempt0/factor.py').read_text()
 exp.sub_workspace_list=[SimpleNamespace(code_dict={'factor.py':code},file_dict={'factor.py':code})]
 # Native proposal templates insist on no-cost metric keys. They are missing,
 # explicitly NaN, not relabelled net returns. Actual net feedback is in scenario.
 for metric in ['1day.excess_return_without_cost.annualized_return','1day.excess_return_without_cost.max_drawdown']:
  exp.result.loc[metric]=float('nan')
 exp.result=exp.result.copy()

def generate(engine,attempt):
 directory=Path('/work')/f'attempt{attempt}';directory.mkdir(exist_ok=True)
 if (directory/'generation.json').exists():return json.loads((directory/'generation.json').read_text())
 scen=ResearchScenario()
 if engine=='quanta':
  from quantaalpha.core.proposal import Trace
  from quantaalpha.factors.proposal import AlphaAgentHypothesisGen,AlphaAgentHypothesis2FactorExpression
  from quantaalpha.factors.coder.evolving_strategy import FactorParsingStrategy
  from quantaalpha.factors.coder.config import FACTOR_COSTEER_SETTINGS
  trace=Trace(scen)
  if attempt:
   with Path('/work/attempt0/state.pkl').open('rb') as f:previous=pickle.load(f)
   trace=previous['trace'];scen=trace.scen;hydrate_previous(previous,engine)
  generator=AlphaAgentHypothesisGen(scen,potential_direction='Investigate one novel causal price-volume or regime mechanism with explicit falsification and low-turnover rationale.')
  h=generator.gen(trace);exp=AlphaAgentHypothesis2FactorExpression(consistency_enabled=False).convert(h,trace)
  if not exp.sub_tasks:raise ValueError('original expression constructor produced no eligible tasks')
  task=exp.sub_tasks[0];code=FactorParsingStrategy(scen=scen,settings=FACTOR_COSTEER_SETTINGS).implement_one_task(task,None)
 else:
  from rdagent.core.proposal import Trace
  from rdagent.scenarios.qlib.proposal.factor_proposal import QlibFactorHypothesisGen,QlibFactorHypothesis2Experiment
  from rdagent.components.coder.factor_coder.evolving_strategy import FactorMultiProcessEvolvingStrategy
  from rdagent.components.coder.factor_coder.config import FACTOR_COSTEER_SETTINGS
  from rdagent.components.coder.CoSTEER.knowledge_management import CoSTEERQueriedKnowledgeV1
  trace=Trace(scen)
  if attempt:
   with Path('/work/attempt0/state.pkl').open('rb') as f:previous=pickle.load(f)
   trace=previous['trace'];scen=trace.scen;hydrate_previous(previous,engine)
  h=QlibFactorHypothesisGen(scen).gen(trace,plan={'user_instruction':'Propose one CPU/past-only economical factor; honor the actual training interface and fixed execution policy.'})
  exp=QlibFactorHypothesis2Experiment().convert(h,trace)
  if not exp.sub_tasks:raise ValueError('original experiment constructor produced no tasks')
  task=exp.sub_tasks[0];info=task.get_task_information()
  knowledge=CoSTEERQueriedKnowledgeV1(task_to_former_failed_traces={info:([],None)},task_to_similar_task_successful_knowledge={info:[]})
  code=FactorMultiProcessEvolvingStrategy(scen=scen,settings=FACTOR_COSTEER_SETTINGS).implement_one_task(task,knowledge)
 if not code:raise ValueError('original coder returned empty code')
 if isinstance(code,dict):code=code['factor.py']
 (directory/'factor.py').write_text(code);(directory/'daily_pv.h5').symlink_to('/work/data/daily_pv.h5')
 # Persist before execution: failure never erases hypothesis/code.
 record={'engine':engine,'attempt':attempt,'hypothesis':vars(h),'tasks':[vars(t) for t in exp.sub_tasks],'selected_task':0,'extra_tasks_not_evaluated':len(exp.sub_tasks)-1,'code_sha256':hashlib.sha256(code.encode()).hexdigest(),'scope':'ORIGINAL_PROPOSAL_AND_CODER_APIS_WITH_DECLARED_SCENARIO_ADAPTER','full_native_qlib_loop':False}
 (directory/'generation.json').write_text(json.dumps(record,indent=2,default=str))
 with (directory/'state.pkl').open('wb') as f:pickle.dump({'trace':trace,'hypothesis':h,'experiment':exp},f)
 started=time.monotonic()
 try:
  result=subprocess.run([sys.executable,str(directory/'factor.py')],cwd=directory,capture_output=True,text=True,timeout=90)
  (directory/'execution.stdout').write_text(result.stdout);(directory/'execution.stderr').write_text(result.stderr)
  record.update(exit_code=result.returncode,execution_seconds=time.monotonic()-started,output_exists=(directory/'result.h5').exists())
  if result.returncode==0 and (directory/'result.h5').exists():
   values=pd.read_hdf(directory/'result.h5');values.to_csv(directory/'factor_values.csv');record['rows']=len(values)
 except subprocess.TimeoutExpired:record.update(status='EXECUTION_TIMEOUT',execution_seconds=time.monotonic()-started)
 (directory/'generation.json').write_text(json.dumps(record,indent=2,default=str));return record


def feedback(engine):
 path=Path('/work/attempt0');destination=path/'feedback.json'
 if destination.exists():return json.loads(destination.read_text())
 with (path/'state.pkl').open('rb') as f:state=pickle.load(f)
 trace=state['trace'];trace.hist=[];scen=trace.scen;exp=state['experiment'];h=state['hypothesis']
 report=json.loads(Path('/work/validation_feedback.json').read_text());row=report['candidate'];baseline=report['baseline'];sessions=report['sessions']
 # Native metric names are retained, but all values are computed from the
 # common net NAV. The scenario explicitly explains the external evaluator.
 def result_df(r):
  return pd.DataFrame({'0':{'IC':r.get('IC',float('nan')),'1day.excess_return_with_cost.annualized_return':r['annualized_mean_daily_excess_vs_benchmark'],'1day.excess_return_with_cost.max_drawdown':r['relative_nav_mdd']}})
 scen.validation_note='Actual independent 2025 US validation ONLY; no final outcomes. Common net-cost execution, not native Qlib backtest. IC target is next-session intraday, while portfolio NAV includes overnight risk after next-open entry. Full metrics and neutral baseline: '+json.dumps(report)
 for task in exp.sub_tasks:task.factor_implementation=True
 exp.result=result_df(row);exp.hypothesis=h
 import copy
 neutral=copy.deepcopy(exp);neutral.result=result_df(baseline);exp.based_experiments=[neutral]
 if engine=='quanta':
  from quantaalpha.factors.feedback import AlphaAgentQlibFactorHypothesisExperiment2Feedback
  fb=AlphaAgentQlibFactorHypothesisExperiment2Feedback(scen).generate_feedback(exp,h,trace)
  trace.hist.append((h,exp,fb))
 else:
  from rdagent.scenarios.qlib.developer.feedback import QlibFactorExperiment2Feedback
  fb=QlibFactorExperiment2Feedback(scen).generate_feedback(exp,trace)
  trace.hist.append((exp,fb))
 record={'scope':'ORIGINAL_FEEDBACK_WITH_COMMON_VALIDATION_ADAPTER','final_access':False,'feedback':vars(fb),'metrics':report}
 destination.write_text(json.dumps(record,indent=2,default=str))
 with (path/'state.pkl').open('wb') as f:pickle.dump(state,f)
 return record


def model_proposal():
 from rdagent.core.proposal import Trace
 from rdagent.scenarios.qlib.proposal.model_proposal import QlibModelHypothesisGen,QlibModelHypothesis2Experiment
 scen=ResearchScenario();trace=Trace(scen)
 scen.validation_note='Auxiliary prediction-model proposal only, inside the same RD token budget. Exactly one modest CPU model, only train<=2024; no final data. Native model workspace readiness failed; do not invent fitted model or performance. Model features use past OHLCV, target next-session intraday return. This is not a third evaluated factor strategy.'
 h=QlibModelHypothesisGen(scen).gen(trace);exp=QlibModelHypothesis2Experiment().convert(h,trace)
 record={'scope':'ORIGINAL_MODEL_HYPOTHESIS_AND_EXPERIMENT_SPEC_ONLY','hypothesis':vars(h),'tasks':[vars(t) for t in exp.sub_tasks],'trained':False,'evaluation':'NOT_RUN_NATIVE_MODEL_ENVIRONMENT_UNAVAILABLE','final_access':False}
 Path('/work/model_proposal.json').write_text(json.dumps(record,indent=2,default=str));return record


if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('engine',choices=['quanta','rd']);p.add_argument('--attempt',type=int,default=0);p.add_argument('--feedback',action='store_true');p.add_argument('--model-proposal',action='store_true');a=p.parse_args()
 try:print(json.dumps(model_proposal() if a.model_proposal else feedback(a.engine) if a.feedback else generate(a.engine,a.attempt),indent=2,default=str))
 except Exception as e:
  error={'status':'FAILED','error_type':type(e).__name__,'reason':str(e)};path=Path('/work')/f'attempt{a.attempt}';path.mkdir(exist_ok=True);(path/'failure.json').write_text(json.dumps(error,indent=2));traceback.print_exc();raise
