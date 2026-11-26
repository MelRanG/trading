from pathlib import Path
import json,time,subprocess,hashlib
R=Path(__file__).resolve().parents[2];B=R/'runtime/task13_r1';root=B/'native/quanta'
# No outer evaluation before the entire campaign is frozen.
for _ in range(1200):
 if (root/'failure.json').exists():raise RuntimeError((root/'failure.json').read_text())
 if len(list(root.glob('Q*/feedback.json')))>=4:break
 time.sleep(2)
else:raise TimeoutError('Native loop not complete')
files=list(root.glob('Q*/factor.py'));seal={str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files};(B/'candidate_seal.json').write_text(json.dumps(seal,indent=2))
s=(R/'experiments/task13_r1/eval_worker.py').read_text().replace("pair=pair.loc[pair.index.get_level_values(0).isin(n[n>=50].index)];ic,ric=", "pair=pair.loc[pair.index.get_level_values(0).isin(n[n>=50].index)];pair=pair.loc[pair.index.get_level_values(0)>=pd.Timestamp('2023-04-03')];ic,ric=").replace("'scope':'FIT_ONLY_NO_OUTER_RESULTS'","'scope':'DEVELOPMENT_2023_2024_AFTER_FREEZE'")
worker=B/'validation_worker.py';worker.write_text(s)
for node in sorted(root.glob('Q[0-9]*')):
 out=B/'validation'/node.name;out.mkdir(parents=True,exist_ok=True)
 cmd=['docker','run','--rm','--network=none','--cpus=2','--memory=4g','--user','1000:1000','-e','HOME=/work','-e','LITELLM_LOCAL_MODEL_COST_MAP=True','-e','PYTHONDONTWRITEBYTECODE=1','-v','/home/ansy/app/quant-diligence/task6-quanta-env:/venv:ro','-v',str(node)+':/candidate:ro','-v',str(B/'evaluator_inputs')+':/inputs:ro','-v',str(worker)+':/worker.py:ro','-v',str(out)+':/work','-w','/work','quant-research-task6:local','/venv/bin/python','/worker.py']
 p=subprocess.run(cmd,capture_output=True,text=True,timeout=420);(out/'execution.log').write_text(p.stdout+p.stderr);assert p.returncode==0,p.stderr[-1200:];print('DEVELOPMENT_EVALUATED',node.name,flush=True)
assert all(hashlib.sha256((R/p).read_bytes()).hexdigest()==h for p,h in seal.items())
(B/'validation_complete.json').write_text(json.dumps({'candidate_hashes_unchanged':True,'scope':'EXPOSED_DEVELOPMENT_NOT_INDEPENDENT_HOLDOUT','LLM_after_freeze':0}))
# Remove the reproducible evaluator input copy after score/paired evidence is preserved.
for p in (B/'evaluator_inputs').glob('*.h5'):p.unlink()
