from pathlib import Path
import json,hashlib,datetime,subprocess
R=Path(__file__).resolve().parents[2];B=R/'runtime/task13';E=Path('/home/ansy/app/quant-diligence')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
# Freeze source fingerprints before final descriptive evaluator.
cs=[];catalog=json.loads((R/'runtime/task12/factor_catalog.json').read_text())['metadata'];contract=json.loads((B/'contract.json').read_text())
for v in contract['vibe']:
 src=Path(next(x['source'] for x in catalog if x['id']==v['native_id']));cs.append({**v,'source':str(src),'code_hash':sha(src)})
for cid in ['Q0','Q1']:
 p=B/'native/quanta'/cid/'generation.json';v=json.loads(p.read_text());assert sha(p.parent/'factor.py')==v['fingerprint'];cs.append({'id':cid,'H':20,'source':str((p.parent/'factor.py').relative_to(R)),'code_hash':v['fingerprint'],'hypothesis':v['hypothesis']['hypothesis']})
p=B/'native/rd/model.py';g=json.loads((p.parent/'generation.json').read_text());assert sha(p)==g['fingerprint'];cs.append({'id':'RD_SMALL','H':5,'source':str(p.relative_to(R)),'code_hash':sha(p),'hypothesis':g['hypothesis']})
seal=B/'candidate_seal.json'
if not seal.exists():seal.write_text(json.dumps({'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'contract_hash':sha(B/'contract.json'),'candidates':cs,'generation_closed':True,'not_official_paper_or_champion':True},indent=2,default=str)+'\n')
work=B/'diagnostics';work.mkdir(exist_ok=True);cmd=['docker','run','--rm','--network=none','--cap-drop=ALL','--security-opt','no-new-privileges','--cpus=2','--memory=4g','--pids-limit=256','--user','1000:1000','-e','HOME=/work','-e','OMP_NUM_THREADS=2','-e','PYTHONDONTWRITEBYTECODE=1','-e','LITELLM_LOCAL_MODEL_COST_MAP=True','-v',str(E/'task6-rd-env')+':/venv:ro','-v',str(work)+':/work','-v',str(B)+':/evidence:ro','-v',str(R/'experiments/task13')+':/code:ro','-w','/work','quant-research-task6:local','/venv/bin/python','/code/diagnose_worker.py'];p=subprocess.run(cmd,capture_output=True,text=True,timeout=600);(work/'execution.log').write_text(p.stdout+p.stderr);raise SystemExit(p.returncode)
