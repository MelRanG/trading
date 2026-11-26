"""Run unchanged mandatory tests on current-code snapshot excluding runtime/.venv.
Avoid original test fixture recursively copying research evidence and environments.
"""
from pathlib import Path
import tempfile,shutil,subprocess,os,json,hashlib
R=Path(__file__).resolve().parents[2];B=R/'runtime/task13_b3_repair';temp=Path(tempfile.mkdtemp(prefix='quant-b3-repair-regression-'));snapshot=temp/'project';snapshot.mkdir();files=[]
try:
 for name in ['src','scripts','tests','config','data','reports']:
  shutil.copytree(R/name,snapshot/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc','runtime'))
 for p in R.iterdir():
  if p.is_file() and p.suffix in ['.md','.json','.yaml','.toml'] and not p.name.startswith('.'):
   shutil.copy2(p,snapshot/p.name)
 for name in ['src','scripts','tests','config','data','reports']:
  for p in (snapshot/name).rglob('*'):
   if not p.is_file():continue
   original=R/p.relative_to(snapshot);h=hashlib.sha256(p.read_bytes()).hexdigest();assert h==hashlib.sha256(original.read_bytes()).hexdigest();files.append({'path':str(p.relative_to(snapshot)),'sha256':h})
 env=dict(os.environ,PYTHONPATH=str(snapshot/'src'),PYTEST_DISABLE_PLUGIN_AUTOLOAD='1');cmd=[str(R/'.venv/bin/python'),'-m','pytest','-q','tests/test_v104_end_to_end_causal_challenger_audit.py','tests/test_v104_2_jul30_crash_bridge.py','tests/test_v84_dual_paper_parity.py','tests/test_v89_forward_governance.py']
 p=subprocess.run(cmd,cwd=snapshot,env=env,capture_output=True,text=True,timeout=240);(B/'safety.log').write_text(p.stdout+p.stderr);(B/'safety_snapshot.json').write_text(json.dumps({'method':'Unchanged tests against exact current code/config/data/reports snapshot, no runtime/.venv/.env. All copied file content SHA compared to original. Temporary files removed after invocation.','exit_code':p.returncode,'copied_files':files},indent=2));print('SAFETY_EXIT',p.returncode);raise SystemExit(p.returncode)
finally:shutil.rmtree(temp)
