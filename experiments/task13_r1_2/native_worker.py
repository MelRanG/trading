from pathlib import Path
from types import SimpleNamespace
import sys,json,time,hashlib,pickle,traceback
import pandas as pd
sys.path.insert(0,'/oldcode');from native_factor_stage import ResearchScenario
class Scenario(ResearchScenario):
 def __init__(self):self.data=pd.read_hdf('/train/US_train.h5',key='data');self.validation_note=''
 @property
 def interface(self):return 'Factor only. Original DSL code reads daily_pv.h5 key=data, MultiIndex(datetime,instrument), $open/$high/$low/$close/$volume/$return. Export identical index Series to result.h5. $return is adjusted close-to-close simple return, never a label. No model architecture, training, other targets, portfolio, or order instructions.'
 @property
 def experiment_setting(self):return 'US176 anonymous SURVIVOR_RESEARCH train2017..2022 only. H20: signal close t, entry open t+1, exit open t+21. Common63valid warmup and >=50 eligible names. No future/validation raw data. Only the frozen mechanism below is permitted. Do not add residualization/controls/filters/extra windows or claim fictitious results.'
 def get_scenario_all_desc(self,*a,**kw):return self.get_source_data_desc()+'\n'+self.interface+'\n'+self.experiment_setting+'\n'+self.validation_note

def strict_gate_result(result,expression):
 passed,feedback,details=result;c=details.get('consistency')
 if not passed or not c or c.get('is_consistent') is not True:raise ValueError('SEMANTIC_GATE_FAILED')
 text=json.dumps(c).lower()
 if any(x in text for x in ['error during check','skipping check','failed with error']):raise ValueError('SEMANTIC_GATE_ERROR_FAIL_CLOSED')
 if details.get('corrected_expression')!=expression:raise ValueError('NO_AUTOCORRECTION_ALLOWED')
 return result

def main():
 from quantaalpha.pipeline.evolution import EvolutionController
 from quantaalpha.core.proposal import Trace
 from quantaalpha.factors.proposal import AlphaAgentHypothesisGen,AlphaAgentHypothesis2FactorExpression
 from quantaalpha.factors.coder.evolving_strategy import FactorParsingStrategy
 from quantaalpha.factors.coder.config import FACTOR_COSTEER_SETTINGS
 from quantaalpha.factors.regulator.consistency_checker import FactorQualityGate,FactorConsistencyChecker
 from quantaalpha.factors.feedback import AlphaAgentQlibFactorHypothesisExperiment2Feedback
 root=Path('/work');node=root/'S0';node.mkdir(exist_ok=True);scen=Scenario();contract=json.loads(Path('/spec/contract.json').read_text());trace=Trace(scen)
 direction=json.dumps({'economic_hypothesis':contract['hypothesis'],'essential_semantics':contract['requirements'],'native_H':20,'rule':'Do not add any controls, filters, conditioning, alternative windows, or forecasts. This is a NEW asymmetric squared-return risk-composition hypothesis, not a simplified old shock-recovery hypothesis.'})
 h=AlphaAgentHypothesisGen(scen,potential_direction=direction).gen(trace);(node/'hypothesis.json').write_text(json.dumps(vars(h),indent=2,default=str))
 # No embedded correction/retry gate; native full QualityGate called explicitly with strict once-only semantics below.
 constructor=AlphaAgentHypothesis2FactorExpression(consistency_enabled=False)
 from syntax_adapter import attach
 attach(constructor.factor_regulator)
 exp=constructor.convert(h,trace);(node/'all_proposals.json').write_text(json.dumps([vars(t) for t in exp.sub_tasks],indent=2,default=str));task=exp.sub_tasks[0]
 checker=FactorConsistencyChecker(max_correction_attempts=1,enabled=True,strict_mode=True);gate=FactorQualityGate(consistency_checker=checker,consistency_enabled=True)
 attach(gate.redundancy_checker.factor_regulator)
 result=gate.evaluate(str(h),task.factor_name,task.factor_description,task.factor_formulation,task.factor_expression,task.variables);(node/'semantic_gate.json').write_text(json.dumps({'passed':result[0],'feedback':result[1],'details':result[2]},indent=2,default=str));strict_gate_result(result,task.factor_expression)
 # Independent operator review verifies hypothesis has not expanded the frozen requirements.
 (node/'awaiting_review.json').write_text(json.dumps({'scope':'Native gate passed; manual and numeric reviews still mandatory'}))
 until=time.monotonic()+900
 while not (node/'manual_review.json').exists():
  if time.monotonic()>until:raise TimeoutError('manual review missing')
  time.sleep(1)
 if not json.loads((node/'manual_review.json').read_text())['passed']:raise ValueError('FROZEN_HYPOTHESIS_MISMATCH')
 exp.sub_tasks=exp.sub_tasks[:1];code=FactorParsingStrategy(scen=scen,settings=FACTOR_COSTEER_SETTINGS).implement_one_task(task,None);(node/'factor.py').write_text(code);(node/'generation.json').write_text(json.dumps({'id':'S0','hypothesis':vars(h),'tasks':[vars(task)],'fingerprint':hashlib.sha256(code.encode()).hexdigest(),'H':20,'selection':'first returned task, prior to metrics','native':'Original hypothesis/converter/strict semantic gate/DSL coder; explicit evaluator adapter','fullAlphaAgentLoop':False},indent=2,default=str))
 until=time.monotonic()+1200
 while not (node/'metrics.json').exists():
  if time.monotonic()>until:raise TimeoutError('Numeric review/evaluation missing')
  time.sleep(1)
 m=json.loads((node/'metrics.json').read_text());assert m['code_hash']==hashlib.sha256(code.encode()).hexdigest() and m['candidate']=='S0'
 if m.get('failed'):raise ValueError('SEMANTIC_OR_NUMERIC_OR_POOL_GATE_BLOCKED')
 task.factor_implementation=True;task.factor_description=task.factor_description.replace('This factor has not been evaluated.','')+' CURRENT STATUS EVALUATED candidate=S0 code_hash='+m['code_hash']+' H20. Use only the bound metrics.';exp.sub_workspace_list=[SimpleNamespace(code_dict={'factor.py':code})];exp.result=pd.DataFrame({'0':{'IC':m['IC'],'RankIC':m['RankIC']}});scen.validation_note='CURRENT_EVALUATED_BOUND_RECORD '+json.dumps(m)
 fb=AlphaAgentQlibFactorHypothesisExperiment2Feedback(scen).generate_feedback(exp,h,trace);(node/'feedback.json').write_text(json.dumps(vars(fb),indent=2,default=str))
 with (node/'state.pkl').open('wb') as f:pickle.dump({'h':h,'exp':exp,'feedback':fb},f)
 (root/'complete.json').write_text(json.dumps({'generated_candidates':1,'native_semantic_gate':True,'fullAlphaAgentLoop':False}))
if __name__=='__main__':
 try:main()
 except Exception as e:Path('/work/failure.json').write_text(json.dumps({'type':type(e).__name__,'error':str(e)}));traceback.print_exc();raise
