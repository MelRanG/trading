"""Reuse the existing credential-isolated transport, Task13 budget scope only."""
from pathlib import Path
import importlib.util,json,socketserver,hashlib,copy
from json_shape import repair_formulation
R=Path(__file__).resolve().parents[2];B=R/'runtime/task13_r2'
spec=importlib.util.spec_from_file_location('prior_transport',R/'experiments/task13_r2/transport.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.BUDGET=json.loads((R/'experiments/task13_r2/contract.json').read_text())['budgets']
class ShapeRelay(m.Relay):
 def call(self,engine,body):
  result=super().call(engine,body)
  content=result['choices'][0]['message'].get('content')
  if content and body.get('response_format',{}).get('type')=='json_object':
   fixed,changed=repair_formulation(content)
   if changed:
    receipt={'engine':engine,'original_sha256':hashlib.sha256(content.encode()).hexdigest(),'repaired_sha256':hashlib.sha256(fixed.encode()).hexdigest(),'rule':'Escape single LaTex backslashes ONLY in formulation JSON string; raw model response remains unchanged','new_LLM_calls':0,'original_content':content,'repaired_content':fixed}
    (B/('json_shape_'+receipt['original_sha256']+'.json')).write_text(json.dumps(receipt,indent=2));result=copy.deepcopy(result);result['choices'][0]['message']['content']=fixed
  return result
p=Path('/tmp/quant-task13-r2.sock')
if p.exists():raise ValueError('socket already exists; inspect before cleanup')
s=socketserver.ThreadingUnixStreamServer(str(p),m.Handler);s.relay=ShapeRelay(B/'model_calls');p.chmod(0o600)
try:s.serve_forever()
finally:s.server_close();p.unlink(missing_ok=True)
