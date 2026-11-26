"""Trusted dispatcher; generated code executes only in a credential-free evaluator."""
from pathlib import Path
import importlib.util,sys,json,shutil,time,traceback
ROOT=Path(__file__).resolve().parents[2];spec=importlib.util.spec_from_file_location('old_eval',ROOT/'experiments/task6/evaluation.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
sys.path.insert(0,str(Path(__file__).parent));from aligned import evaluate
from native_metrics import native_metrics
frames=old.load_frames('US','validation');old.BASE=ROOT/'runtime/task6_completion';work=Path('/home/ansy/app/quant-diligence/completion-quanta-work');deadline=time.monotonic()+1700
while time.monotonic()<deadline:
 for path in sorted(work.glob('node*/request.json')):
  node=path.parent;i=int(node.name.removeprefix('node'))
  if (node/'metrics.json').exists():continue
  target=old.BASE/'candidates/quanta'/f'attempt{i}';target.mkdir(parents=True,exist_ok=True);shutil.copy2(node/'factor.py',target/'factor.py');shutil.copy2(path,target/'request.json')
  try:
   values=old.factor_values('quanta',i,'US','validation',frames);metrics,nav,fills=evaluate(values,frames);metrics['native_aliases']=native_metrics(metrics,nav);out=old.BASE/'aligned'/node.name;out.mkdir(parents=True,exist_ok=True);nav.to_csv(out/'nav.csv',index=False);fills.to_csv(out/'fills.csv',index=False);(out/'metrics.json').write_text(json.dumps(metrics,indent=2,allow_nan=False));(node/'metrics.json').write_text(json.dumps(metrics,indent=2,allow_nan=False));print(node.name,metrics,flush=True)
  except Exception as e:(node/'metrics.json').write_text(json.dumps({'status':'FAILED','error':str(e)}));traceback.print_exc()
 if (work/'result.json').exists() or (work/'failure.json').exists():break
 time.sleep(1)
