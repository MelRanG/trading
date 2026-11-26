from pathlib import Path
import importlib.util,json,hashlib,gzip,datetime,sys,re
R=Path(__file__).resolve().parents[2];B=R/'runtime/task13_b3';P=json.loads((B/'plan.json').read_text());assert hashlib.sha256((B/'plan.json').read_bytes()).hexdigest()==(B/'plan.sha256').read_text()
spec=importlib.util.spec_from_file_location('b1_sources_reused',R/'experiments/task13_b1/common.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m.B=B;m.P=P
sha=m.sha;dump=m.dump;body=m.body;now=m.now
class Sources(m.Sources):
 def __init__(self):
  super().__init__()
  for root in ['task13_b1','task13_b2']:
   for p in(R/'runtime'/root/'sources').glob('*/receipt.json'):
    d=json.loads(p.read_text())
    if d.get('url')and d.get('status')=='SAVED':self.old[d['url']]=d
