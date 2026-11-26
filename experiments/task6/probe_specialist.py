"""Original component import/CLI readiness; no model or data calls."""
from pathlib import Path
import importlib.metadata,json,sys,traceback
engine=sys.argv[1];result={'engine':engine,'imports':{}}
for package in ('rdagent','quantaalpha','pyqlib','numpy','pandas','openai'):
 try:result[package]=importlib.metadata.version(package)
 except importlib.metadata.PackageNotFoundError:pass
names=['quantaalpha.factors.proposal','quantaalpha.factors.coder.factor','quantaalpha.pipeline.factor_mining'] if engine=='quanta' else ['rdagent.scenarios.qlib.proposal.factor_proposal','rdagent.scenarios.qlib.proposal.model_proposal','rdagent.components.coder.factor_coder.factor']
for name in names:
 try:__import__(name);result['imports'][name]='SUCCESS'
 except Exception as e:result['imports'][name]={'error_type':type(e).__name__,'reason':str(e)};traceback.print_exc()
Path('/work/probe.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
