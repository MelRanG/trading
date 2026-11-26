from pathlib import Path
import json,traceback
from quantaalpha.pipeline.evolution import EvolutionController
from quantaalpha.factors.proposal import AlphaAgentHypothesis2FactorExpression
from rdagent.utils.env import LocalEnv,LocalConf
from rdagent.scenarios.shared.get_runtime_info import get_runtime_environment_by_env
from quantaalpha.factors.coder.config import FACTOR_COSTEER_SETTINGS
out={}
try:
 env=LocalEnv(conf=LocalConf(bin_path='/venv/bin',default_entry='python main.py'));env.prepare();info=get_runtime_environment_by_env(env=env);out['existing_venv_runtime_probe']='PASS';out['runtime_info']=info
except Exception as e:out['existing_venv_runtime_probe']={'type':type(e).__name__,'error':str(e)}
folder=Path(FACTOR_COSTEER_SETTINGS.data_folder);out['original_data_folder']=str(folder);out['data_folder_present']=folder.exists();out['meaning']='No installed source patched; LocalConf adapter probe concerns runtime compatibility only. No planner, learner or backtest executed.'
Path('/work/environment_probe.json').write_text(json.dumps(out,indent=2,default=str));print(json.dumps(out,default=str))
