"""Bounded original full-loop/model execution readiness; no credentials/network."""
import argparse,json,importlib.util,traceback,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('engine');a=p.parse_args();result={'engine':a.engine,'full_controller_status':'NOT_EXECUTED_WITH_US_DATA','reason':'Native Qlib provider/calendar/instrument/features and conda/nested Docker environment are not supplied. Current bounded original components use explicit OHLCV scenario adapter.'}
if a.engine=='rd':
 from rdagent.components.coder.model_coder.model import ModelTask,ModelFBWorkspace
 task=ModelTask(name='readiness_only_not_generated_model',description='Environment readiness probe, not a research result',architecture='none',hyperparameters={},training_hyperparameters={})
 ws=ModelFBWorkspace(target_task=task)
 try:
  log,output=ws.execute();result['original_model_workspace']={'log':str(log),'output_exists':output is not None}
 except Exception as e:result['original_model_workspace']={'exception':type(e).__name__,'message':str(e)}
 result['torch_installed']=importlib.util.find_spec('torch') is not None
 try:
  cp=subprocess.run(['/venv/bin/rdagent','fin_factor','--help'],capture_output=True,text=True,timeout=40);result['official_cli_help_exit']=cp.returncode;Path('/work/official_cli_help.log').write_text(cp.stdout+cp.stderr)
 except Exception as e:result['official_cli_help_error']=str(e)
else:
 import quantaalpha
 from quantaalpha.factors.proposal import AlphaAgentHypothesisGen
 result['original_gen_import']=True
result['scope']='READINESS_PROBE_NOT_COMPLETED_MODEL_RESEARCH';Path('/work/readiness.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
