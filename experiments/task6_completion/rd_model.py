from pathlib import Path
import sys,json,time,traceback
sys.path.insert(0,'/oldcode')
from native_factor_stage import ResearchScenario
from rdagent.components.coder.model_coder.model import ModelTask,ModelFBWorkspace
from rdagent.components.coder.model_coder.evolving_strategy import ModelMultiProcessEvolvingStrategy
from rdagent.components.coder.model_coder.conf import MODEL_COSTEER_SETTINGS
class Scenario(ResearchScenario):
 @property
 def experiment_setting(self):return 'Train through2024 only; internal chronological train/earlystop split within2024. 2025 repeated diagnostic, not Holdout; no2026. Input [batch,20,num_features], output [batch]. CPU torch2.8 installed. No I/O in model code; provide model_cls class(num_features,num_timesteps). Qlib trainer supplies data and loss.'
 def get_runtime_environment(self):return 'Python3.12, torch2.8 CPU,pandas/numpy/Qlib, two threads.'
try:
 root=Path('/work')
 if (root/'result.json').exists():
  print((root/'result.json').read_text());raise SystemExit(0)
 scen=Scenario();spec=json.loads(Path('/work/model_proposal.json').read_text());task=ModelTask.from_dict(spec['tasks'][0]);task.description+=' Use causal GRU16 only, flexible num_features input, return 1d tensor; export model_cls class. No training or file I/O inside model code.'
 ws=ModelFBWorkspace(target_task=task);code=(root/'model.py').read_text() if (root/'model.py').exists() else ModelMultiProcessEvolvingStrategy(scen=scen,settings=MODEL_COSTEER_SETTINGS).implement_one_task(task,None,workspace=ws);(root/'model.py').write_text(code);(root/'model_request.json').write_text(json.dumps({'hypothesis':spec['hypothesis'],'task':vars(task),'origin':'ORIGINAL_RD_MODEL_COSTEER'},indent=2,default=str))
 until=time.monotonic()+600
 while not (root/'training_metrics.json').exists():
  if time.monotonic()>until:raise TimeoutError('training evaluator response missing')
  time.sleep(1)
 metrics=json.loads((root/'training_metrics.json').read_text());scen.validation_note='Actual original-code/Qlib CPU training results, repeated2025 only; no final. '+json.dumps(metrics)
 from rdagent.core.proposal import Hypothesis,Trace
 from rdagent.scenarios.qlib.experiment.model_experiment import QlibModelExperiment
 from rdagent.scenarios.qlib.developer.feedback import QlibModelExperiment2Feedback
 from rdagent.scenarios.qlib.proposal.model_proposal import QlibModelHypothesisGen
 import pandas as pd
 h=Hypothesis(**spec['hypothesis']);exp=QlibModelExperiment([task],hypothesis=h);exp.sub_workspace_list=[ws];ws.file_dict={'model.py':code};trace=Trace(scen)
 m=metrics['factor_augmented']['aligned'];exp.result=pd.DataFrame({'0':m['native_aliases']})
 from rdagent.core.proposal import HypothesisFeedback
 fb=HypothesisFeedback(**json.loads((root/'model_feedback.json').read_text())) if (root/'model_feedback.json').exists() else QlibModelExperiment2Feedback(scen).generate_feedback(exp,trace)
 trace.hist.append((exp,fb));(root/'model_feedback.json').write_text(json.dumps(vars(fb),indent=2,default=str));new=QlibModelHypothesisGen(scen).gen(trace);(root/'followup_model_hypothesis.json').write_text(json.dumps(vars(new),indent=2,default=str));(root/'result.json').write_text(json.dumps({'status':'ORIGINAL_MODEL_CODER_QLIB_TRAINING_FEEDBACK_FOLLOWUP_EXECUTED','full_fin_quant_controller':False},indent=2))
except Exception as e:Path('/work/failure.json').write_text(json.dumps({'type':type(e).__name__,'error':str(e)},indent=2));traceback.print_exc();raise
