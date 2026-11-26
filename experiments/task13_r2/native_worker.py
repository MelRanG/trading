from pathlib import Path
from types import SimpleNamespace
import os,sys,json,time,hashlib,pickle,traceback
import pandas as pd
sys.path.insert(0,'/oldcode');from native_factor_stage import ResearchScenario
from rdagent.scenarios.qlib.experiment.quant_experiment import QlibQuantScenario
from rdagent.scenarios.qlib.proposal.quant_proposal import QlibQuantHypothesisGen,QuantTrace,QlibQuantHypothesis
from rdagent.app.qlib_rd_loop.conf import QUANT_PROP_SETTING
from rdagent.oai.llm_conf import LLM_SETTINGS
class Scenario(ResearchScenario,QlibQuantScenario):
 def __init__(self):self.data=pd.read_hdf('/train/US_train.h5',key='data');self.validation_note=''
 @property
 def interface(self):return 'FACTOR: daily_pv.h5 key=data MultiIndex(datetime,instrument), $open/$high/$low/$close/$volume/$return; output result.h5 key=data same full index, one factor score. No dropping index rows. MODEL: torch class model_cls(num_features,num_timesteps), input [B,1,F], output [B] or [B,1], no I/O or training. F=6 (ret1,mom20,mom60,vol20,relative_volume20,new feature), supplied US train-only standardization. At most80parameters, CPU. No GRU/LSTM/attention and no assumed sample counts.'
 @property
 def experiment_setting(self):return 'R2 H20 raw adjusted-provider-claim return: signal close t, entry open t+1, exit open t+21. US-only fit2017..2020 with target maturity<=2020-12-31, internal2021-04..2022 with target maturity<=2022-12-31; actual supervised rows141110fit/68673inner BEFORE joint feature mask. Dates/effective sample count far below independent rows. No2023+ prices or labels. >=50names, 63valid past and entire label path valid. Constant seed42, fixed20epochs/AdamLR.001/batch256, originalQlib best internal checkpoint. Factor+model coding only, no portfolio or annualized returns.'
 def get_scenario_all_desc(self,*args,**kwargs):return self.get_source_data_desc()+'\n'+self.interface+'\n'+self.experiment_setting+'\n'+self.validation_note
root=Path('/work')
from trace_view import install;install()
def role(scope,purpose):
 key='task6-'+scope;os.environ['OPENAI_API_KEY']=key;LLM_SETTINGS.openai_api_key=key;LLM_SETTINGS.chat_openai_api_key=key
 with (root/'purposes.jsonl').open('a') as f:f.write(json.dumps({'scope':scope,'purpose':purpose,'at':time.time()})+'\n')
def wait(path,seconds=1200):
 end=time.monotonic()+seconds
 while not path.exists():
  if time.monotonic()>end:raise TimeoutError(str(path))
  time.sleep(1)
 return json.loads(path.read_text())
class ActualQuantHypothesisGen(QlibQuantHypothesisGen):
 def prepare_context(self,trace):
  context,flag=super().prepare_context(trace)
  if self.targets=='model':context['RAG']='ACTUAL141110fit/68673inner BEFOREcommonfeaturemask, H20 overlapping labels, only176USnames/2017..2022. CPU2/4GiB. No assumed478000/128000samples and noGRU/LSTM preference. At most80parameters; research nonlinear interaction of current newfeature with baseline volatility/relativevolume if economically warranted; not merely another linear projection. Only1model-improvement experiment remains. Do not claim a new factor was accepted if actual Feedback rejected it.'
  if self.targets=='model':context['hypothesis_specification']='Propose exactly one bounded tabular model improvement for six supplied features and H20. Describe a verifiable nonlinear interaction mechanism if justified by the bound actual feedback. CPU model<=80parameters; fixed trainer20epochs/lr.001/seed42. No RNN requirement, no new input features, no hyperparameter grid, no conference-level novelty requirement. Do not treat the rejected feature as accepted SOTA; the experiment may test a conditional rescue hypothesis only.'
  return context,flag

def main():
 from rdagent.scenarios.qlib.proposal.factor_proposal import QlibFactorHypothesis2Experiment
 from rdagent.components.coder.factor_coder.evolving_strategy import FactorMultiProcessEvolvingStrategy
 from rdagent.components.coder.factor_coder.config import FACTOR_COSTEER_SETTINGS
 from rdagent.components.coder.CoSTEER.knowledge_management import CoSTEERQueriedKnowledgeV1
 from rdagent.scenarios.qlib.developer import feedback as feedback_module
 from rdagent.scenarios.qlib.developer.feedback import QlibFactorExperiment2Feedback,QlibModelExperiment2Feedback
 from rdagent.scenarios.qlib.proposal.model_proposal import QlibModelHypothesis2Experiment
 from rdagent.components.coder.model_coder.evolving_strategy import ModelMultiProcessEvolvingStrategy
 from rdagent.components.coder.model_coder.conf import MODEL_COSTEER_SETTINGS
 from rdagent.components.coder.model_coder.model import ModelFBWorkspace
 from rdagent.oai.llm_utils import APIBackend
 scen=Scenario();trace=QuantTrace(scen);QUANT_PROP_SETTING.action_selection='bandit'
 scen.validation_note='Only1new feature allowed. Investigate intraday range-based price impact per relative trading volume, economically a liquidity state potentially interacting with volatility. Use negative5session mean of ((high-low)/close)/(volume/mean20(volume)) as a testable liquidity-impact proxy: higher means less impact and expected higher H20. Preserve all components, positive-volume/range validity, full20 and5 windows; no crosssectional residuals/extra features/alternative horizon. This is not MOM/reversal. Declare exact mechanism and conditions; no evaluated results exist.'
 role('economic','initial_economic_factor_hypothesis_original_bandit_first_factor');h=QlibQuantHypothesis(**json.loads((root/'hypothesis.json').read_text())) if (root/'hypothesis.json').exists() else ActualQuantHypothesisGen(scen).gen(trace);assert h.action=='factor';(root/'hypothesis.json').write_text(json.dumps(vars(h),indent=2,default=str))
 review=wait(root/'hypothesis_review.json');assert review['passed'],'HYPOTHESIS_SCOPE_FAILED'
 role('rd','factor_task_conversion');exp=QlibFactorHypothesis2Experiment().convert(h,trace);(root/'factor_proposals.json').write_text(json.dumps([vars(t) for t in exp.sub_tasks],indent=2,default=str));assert len(exp.sub_tasks)>=1;exp.sub_tasks=exp.sub_tasks[:1];task=exp.sub_tasks[0]
 taskreview=wait(root/'task_review.json');assert taskreview['passed'],'TASK_SEMANTIC_SCOPE_FAILED'
 role('rd','native_factor_CoSTEER_code');info=task.get_task_information();knowledge=CoSTEERQueriedKnowledgeV1(task_to_former_failed_traces={info:([],None)},task_to_similar_task_successful_knowledge={info:[]});code=(root/'factor.py').read_text() if (root/'factor.py').exists() else FactorMultiProcessEvolvingStrategy(scen=scen,settings=FACTOR_COSTEER_SETTINGS).implement_one_task(task,knowledge);(root/'factor.py').write_text(code);(root/'factor_generation.json').write_text(json.dumps({'hypothesis':vars(h),'task':vars(task),'code_hash':hashlib.sha256(code.encode()).hexdigest(),'H':20,'full_QuantRDLoop':False},indent=2,default=str))
 met=wait(root/'factor_training.json');assert met['code_hash']==hashlib.sha256(code.encode()).hexdigest() and not met.get('failed')
 task.factor_implementation=True;task.description+=' CURRENT STATUS EVALUATED R2_FACTOR code_hash='+met['code_hash']+' H20; originalQlib Ridge+feature comparison C vs A; not standalone-factor portfolio.';exp.sub_workspace_list=[SimpleNamespace(file_dict={'factor.py':code})];exp.result=pd.DataFrame({'0':met['C']});exp.based_experiments[-1].result=pd.DataFrame({'0':met['A']});scen.validation_note='ACTUAL_BOUND_INTERNAL_US_RESULTS_C_VS_A '+json.dumps(met)+' Only one feature has been executed; one model improvement allowed, no additional factor is allowed. No dev orKR outcomes supplied.'
 feedback_module.IMPORTANT_METRICS=['IC','RankIC','MSE','MAE']
 role('rd','native_factor_feedback_actual_Qlib_internal_results');from rdagent.core.proposal import HypothesisFeedback
 fb=HypothesisFeedback(**json.loads((root/'factor_feedback.json').read_text())) if (root/'factor_feedback.json').exists() else QlibFactorExperiment2Feedback(scen).generate_feedback(exp,trace);(root/'factor_feedback.json').write_text(json.dumps(vars(fb),indent=2,default=str));trace.hist.append((exp,fb));
 with (root/'factor_state.pkl').open('wb') as f:pickle.dump({'exp':exp,'feedback':fb,'hypothesis':h,'trace':trace},f)
 QUANT_PROP_SETTING.action_selection='llm';role('economic','native_followup_action_and_economic_model_hypothesis');next_h=ActualQuantHypothesisGen(scen).gen(trace);(root/'followup_choice.json').write_text(json.dumps(vars(next_h),indent=2,default=str))
 if next_h.action!='model':
  (root/'complete.json').write_text(json.dumps({'status':'STOP_NATIVE_CHOSE_FACTOR_BUT_FEATURE_BUDGET_USED','model_improvement':'NOT_RUN','native_choice_not_overridden':True}));return
 role('rd','native_model_task_conversion');mx=QlibModelHypothesis2Experiment().convert(next_h,trace);(root/'model_proposals.json').write_text(json.dumps([vars(t) for t in mx.sub_tasks],indent=2,default=str));assert len(mx.sub_tasks)==1
 modelreview=wait(root/'model_review.json');assert modelreview['passed'],'MODEL_SEMANTIC_SCOPE_FAILED'
 role('rd','native_model_CoSTEER_code');ws=ModelFBWorkspace(target_task=mx.sub_tasks[0]);modelcode=ModelMultiProcessEvolvingStrategy(scen=scen,settings=MODEL_COSTEER_SETTINGS).implement_one_task(mx.sub_tasks[0],None,workspace=ws);(root/'model.py').write_text(modelcode);(root/'model_generation.json').write_text(json.dumps({'hypothesis':vars(next_h),'task':vars(mx.sub_tasks[0]),'code_hash':hashlib.sha256(modelcode.encode()).hexdigest(),'H':20},indent=2,default=str))
 mm=wait(root/'model_training.json');assert mm['code_hash']==hashlib.sha256(modelcode.encode()).hexdigest() and not mm.get('failed');mx.result=pd.DataFrame({'0':mm['D']});ws.file_dict={'model.py':modelcode};mx.sub_workspace_list=[ws];scen.validation_note='ACTUAL_BOUND_INTERNAL_US_RESULTS_D_VS_A_B_C '+json.dumps(mm)+' No development orKR outcomes disclosed. No further experiment budget; propose only a research recommendation.'
 # Same original feedback implementation, exact memo prevents its duplicate request.
 backend=type(APIBackend());original=backend.build_messages_and_create_chat_completion;memo={};calls=[]
 def dedup(self,*args,**kwargs):
  key=json.dumps({'args':args,'kwargs':kwargs},sort_keys=True,default=str);calls.append({'cache_hit':key in memo,'request_sha256':hashlib.sha256(key.encode()).hexdigest()})
  if key not in memo:memo[key]=original(self,*args,**kwargs)
  return memo[key]
 backend.build_messages_and_create_chat_completion=dedup
 try:
  role('rd','native_model_feedback_deduplicated_actual_Qlib_results');mf=QlibModelExperiment2Feedback(scen).generate_feedback(mx,trace)
 finally:backend.build_messages_and_create_chat_completion=original
 (root/'model_feedback.json').write_text(json.dumps(vars(mf),indent=2,default=str));(root/'model_feedback_invocations.json').write_text(json.dumps(calls,indent=2));trace.hist.append((mx,mf))
 with (root/'model_state.pkl').open('wb') as f:pickle.dump({'exp':mx,'feedback':mf,'trace':trace},f)
 (root/'complete.json').write_text(json.dumps({'status':'NATIVE_COMPONENTS_FACTOR_MODEL_FEEDBACK_SHARED_TRACE_COMPLETE','trace_experiments':len(trace.hist),'full_QuantRDLoop':False,'additional_research_not_run':True}))
if __name__=='__main__':
 try:main()
 except Exception as e:(root/'failure.json').write_text(json.dumps({'type':type(e).__name__,'error':str(e)}));traceback.print_exc();raise
