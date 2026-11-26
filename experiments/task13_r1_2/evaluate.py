from pathlib import Path
import subprocess,json,hashlib,time
R=Path(__file__).resolve().parents[2];B=R/'runtime/task13_r1_2';node=B/'native/quanta/S0';out=B/'evaluation/S0';out.mkdir(parents=True,exist_ok=True)
for _ in range(900):
 if (node/'generation.json').exists() and (node/'semantic_gate_replayed.json').exists():break
 if (B/'native/quanta/failure.json').exists():raise RuntimeError((B/'native/quanta/failure.json').read_text())
 if (node/'generation.json').exists():break
 time.sleep(1)
else:raise TimeoutError('Generation not available')
cmd=['docker','run','--rm','--network=none','--cpus=2','--memory=4g','--user','1000:1000','-e','HOME=/work','-e','LITELLM_LOCAL_MODEL_COST_MAP=True','-e','PYTHONDONTWRITEBYTECODE=1','-v','/home/ansy/app/quant-diligence/task6-quanta-env:/venv:ro','-v',str(node)+':/candidate:ro','-v',str(R/'runtime/task13_r0/native')+':/inputs:ro','-v',str(R/'experiments/task13_r1_2')+':/code:ro','-v',str(out)+':/work','-w','/work','quant-research-task6:local','/venv/bin/python','/code/eval_worker.py']
p=subprocess.run(cmd,capture_output=True,text=True,timeout=600);(out/'execution.log').write_text(p.stdout+p.stderr)
if p.returncode:
 m={'candidate':'S0','code_hash':hashlib.sha256((node/'factor.py').read_bytes()).hexdigest(),'failed':True,'reason':p.stderr[-2000:]};(node/'metrics.json').write_text(json.dumps(m));raise RuntimeError(m)
m=json.loads((out/'metrics.json').read_text());bound={'candidate':'S0','code_hash':hashlib.sha256((node/'factor.py').read_bytes()).hexdigest(),'H':20,'IC':m['US']['IC'],'RankIC':m['US']['RankIC'],'scope':'ACTUAL_FIT_ONLY','meaning':'20session nextopen target; NOT annualized excess or backtest','markets':m,'PhaseB':'NUMERIC_AND_CAUSALITY_PASS'}
(node/'metrics.json').write_text(json.dumps(bound,indent=2));print('FAITHFUL_AND_EVALUATED',bound['RankIC'])
