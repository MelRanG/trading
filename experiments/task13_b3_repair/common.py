from pathlib import Path
import json,hashlib,importlib.util,sys,re
R=Path(__file__).resolve().parents[2];B=R/'runtime/task13_b3_repair';C=json.loads((B/'plan.json').read_text());assert hashlib.sha256((B/'plan.json').read_bytes()).hexdigest()==(B/'plan.sha256').read_text()
spec=importlib.util.spec_from_file_location('old_sources',R/'experiments/task13_b1/common.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m.B=B;m.P=C
sha=m.sha;dump=m.dump;body=m.body;now=m.now;Sources=m.Sources
