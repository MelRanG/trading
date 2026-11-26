"""Run AGENTS mandatory checks on SHA-matched code/data snapshot, not runtime."""
from pathlib import Path
import hashlib,json,os,resource,shutil,subprocess,tempfile,time
R=Path(__file__).resolve().parents[2];B=R/'runtime/task13_c1'
start=time.monotonic();prior=resource.getrusage(resource.RUSAGE_CHILDREN)
with tempfile.TemporaryDirectory(prefix='quant-c1-safety-') as td:
 s=Path(td)/'project';s.mkdir();records=[]
 for name in ['src','scripts','tests','config','data','reports']:
  shutil.copytree(R/name,s/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
  for p in (s/name).rglob('*'):
   if p.is_file():
    h=hashlib.sha256(p.read_bytes()).hexdigest();assert h==hashlib.sha256((R/p.relative_to(s)).read_bytes()).hexdigest();records.append((str(p.relative_to(s)),h))
 for p in R.iterdir():
  if p.is_file() and p.suffix in ['.md','.json','.yaml','.toml'] and not p.name.startswith('.'):shutil.copy2(p,s/p.name)
 env=dict(os.environ,PYTHONPATH=str(s/'src'),PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',PYTHONDONTWRITEBYTECODE='1')
 c=subprocess.run([str(R/'.venv/bin/python'),'-m','compileall','-q','src','scripts','tests'],cwd=s,capture_output=True,text=True)
 cmd=[str(R/'.venv/bin/python'),'-m','pytest','-q','-p','no:cacheprovider','tests/test_v104_end_to_end_causal_challenger_audit.py','tests/test_v104_2_jul30_crash_bridge.py','tests/test_v84_dual_paper_parity.py','tests/test_v89_forward_governance.py']
 p=subprocess.run(cmd,cwd=s,env=env,capture_output=True,text=True,timeout=240)
 out={'method':'Unchanged AGENTS mandatory tests in current SHA-matched src/scripts/tests/config/data/reports snapshot. Temp removed; excludes runtime/.venv to avoid V89 recursive copying. No operational or research replay executed.','snapshot_files':len(records),'snapshot_content_hash':hashlib.sha256(json.dumps(sorted(records)).encode()).hexdigest(),'compileall_exit':c.returncode,'pytest_exit':p.returncode,'pytest_stdout':p.stdout,'pytest_stderr':p.stderr,'CPU_seconds':None,'wall_seconds':time.monotonic()-start}
 after=resource.getrusage(resource.RUSAGE_CHILDREN);out['CPU_seconds']=after.ru_utime+after.ru_stime-prior.ru_utime-prior.ru_stime
 (B/'safety_validation.json').write_text(json.dumps(out,indent=2)+'\n');print(p.stdout,p.stderr);assert c.returncode==0 and p.returncode==0
