from pathlib import Path
import json,subprocess,hashlib
R=Path(__file__).resolve().parents[2];B=R/'runtime/task13_r1_1';root=R/'runtime/task13_r1/native/quanta';E=Path('/home/ansy/app/quant-diligence')
for node in sorted(root.glob('Q[0-9]*')):
  out=B/'evaluation'/node.name;out.mkdir(parents=True,exist_ok=True)
  cmd=['docker','run','--rm','--network=none','--cpus=2','--memory=4g','--user','1000:1000','-e','HOME=/work','-e','LITELLM_LOCAL_MODEL_COST_MAP=True','-e','PYTHONDONTWRITEBYTECODE=1','-v',str(E/'task6-quanta-env')+':/venv:ro','-v',str(node)+':/candidate:ro','-v',str(R/'runtime/task13_r0/native')+':/inputs:ro','-v',str(R/'experiments/task13_r1/eval_worker.py')+':/worker.py:ro','-v',str(out)+':/work','-w','/work','quant-research-task6:local','/venv/bin/python','/worker.py']
  p=subprocess.run(cmd,capture_output=True,text=True,timeout=420);(out/'execution.log').write_text(p.stdout+p.stderr)
  if p.returncode:met={'scope':'FIT_ONLY_NO_OUTER_RESULTS','failed':True,'reason':p.stderr[-1500:]}
  else:
   m=json.loads((out/'metrics.json').read_text());met={'scope':'FIT_ONLY_NO_OUTER_RESULTS','candidate':node.name,'code_hash':hashlib.sha256((node/'factor.py').read_bytes()).hexdigest(),'H':20,'IC':m['US']['IC'],'RankIC':m['US']['RankIC'],'all_market_fit_metrics':m,'meaning':'ACTUAL_EVALUATED_H20_nextopen_signal_not_backtest_or_annualized_excess','development_validation':'NOT_YET_QUERIED'}
  (out/'bound_metrics.json').write_text(json.dumps(met,indent=2));print('REPLAYED',node.name,met.get('RankIC'),flush=True)
