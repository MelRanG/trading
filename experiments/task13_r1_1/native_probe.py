from pathlib import Path
import json,shutil,os,sys,traceback
from quantaalpha.pipeline.evolution import EvolutionController
from quantaalpha.factors.proposal import AlphaAgentHypothesis2FactorExpression
from quantaalpha.factors.regulator.consistency_checker import FactorQualityGate
from quantaalpha.factors.coder.config import FACTOR_COSTEER_SETTINGS
out={'conda_executable':shutil.which('conda'),'python':sys.executable,'CONDA_DEFAULT_ENV_present':bool(os.environ.get('CONDA_DEFAULT_ENV')),'quality_checks':[]}
for p in sorted(Path('/prior/native/quanta').glob('Q*/generation.json')):
 g=json.loads(p.read_text());t=g['tasks'][0];gate=FactorQualityGate(consistency_enabled=False);passed,feedback,result=gate.evaluate(str(g['hypothesis']),t['factor_name'],t['factor_description'],t['factor_formulation'],t['factor_expression'],t['variables']);out['quality_checks'].append({'candidate':p.parent.name,'passed':passed,'feedback':feedback,'result':result,'semantic_LLM_calls':0})
# get_factor_env() unconditionally constructs CondaConf when python_bin exists.
# Passing an actual executable is accepted by LocalConf, but upstream does not expose that path here.
from rdagent.components.coder.factor_coder.config import get_factor_env
try:get_factor_env();out['original_environment']='OK'
except Exception as e:out['original_environment']={'error':str(e),'type':type(e).__name__}
Path('/work/native_probe.json').write_text(json.dumps(out,indent=2,default=str));print(json.dumps(out,default=str))
