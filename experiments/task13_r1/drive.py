from pathlib import Path
import time,json,subprocess,hashlib
R=Path(__file__).resolve().parents[2];B=R/'runtime/task13_r1';root=B/'native/quanta';E=Path('/home/ansy/app/quant-diligence');deadline=time.monotonic()+2400
while time.monotonic()<deadline:
 for node in sorted(root.glob('Q[0-9]*')):
  if not (node/'generation.json').exists() or (node/'metrics.json').exists():continue
  out=B/'evaluation'/node.name;out.mkdir(parents=True,exist_ok=True)
  cmd=['docker','run','--rm','--network=none','--cpus=2','--memory=4g','--user','1000:1000','-e','HOME=/work','-e','LITELLM_LOCAL_MODEL_COST_MAP=True','-e','PYTHONDONTWRITEBYTECODE=1','-v',str(E/'task6-quanta-env')+':/venv:ro','-v',str(node)+':/candidate:ro','-v',str(R/'runtime/task13_r0/native')+':/inputs:ro','-v',str(R/'experiments/task13_r1/eval_worker.py')+':/worker.py:ro','-v',str(out)+':/work','-w','/work','quant-research-task6:local','/venv/bin/python','/worker.py']
  p=subprocess.run(cmd,capture_output=True,text=True,timeout=420);(out/'execution.log').write_text(p.stdout+p.stderr)
  if p.returncode:met={'scope':'FIT_ONLY_NO_OUTER_RESULTS','failed':True,'reason':p.stderr[-1500:]}
  else:
   m=json.loads((out/'metrics.json').read_text());met={'scope':'FIT_ONLY_NO_OUTER_RESULTS','candidate':node.name,'code_hash':hashlib.sha256((node/'factor.py').read_bytes()).hexdigest(),'H':20,'IC':m['US']['IC'],'RankIC':m['US']['RankIC'],'all_market_fit_metrics':m,'meaning':'ACTUAL_EVALUATED_H20_nextopen_signal_not_backtest_or_annualized_excess','development_validation':'NOT_YET_QUERIED'}
  (node/'metrics.json').write_text(json.dumps(met,indent=2));print('EVALUATED',node.name,met.get('RankIC'),flush=True)
 if len(list(root.glob('Q*/feedback.json')))>=2 and not (root/'phase2_authorization.json').exists():
  (root/'phase2_authorization.json').write_text(json.dumps({'allow':True,'reason':'Two Original calculations and actual native feedback complete; permit mutation, total20calls650k cap remains. No outer performance used.'}))
 if (root/'failure.json').exists():raise RuntimeError((root/'failure.json').read_text())
 if len(list(root.glob('Q*/feedback.json')))>=4:break
 time.sleep(2)
else:raise TimeoutError('Research pending, preserve checkpoint')
