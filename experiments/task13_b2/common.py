"""Reuse B1 archived-source transport without modifying B1 state or settings."""
from pathlib import Path
import importlib.util,json,hashlib,sys,datetime,os
R=Path(__file__).resolve().parents[2];B=R/'runtime/task13_b2';C=json.loads((B/'contract.json').read_text());assert hashlib.sha256((B/'contract.json').read_bytes()).hexdigest()==(B/'contract.sha256').read_text()
spec=importlib.util.spec_from_file_location('b1_transport_reused',R/'experiments/task13_b1/common.py');native=importlib.util.module_from_spec(spec);spec.loader.exec_module(native);native.B=B;native.P=C
sha=native.sha;dump=native.dump;body=native.body;now=native.now
class Sources(native.Sources):
 def __init__(self):
  super().__init__()
  for p in (R/'runtime/task13_b1/sources').glob('*/receipt.json'):
   d=json.loads(p.read_text())
   if d.get('url') and d.get('status')=='SAVED':self.old[d['url']]=d
