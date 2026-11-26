from pathlib import Path
import json,subprocess,sys,hashlib
R=Path(__file__).resolve().parents[2];B=R/'runtime/task13';E=Path('/home/ansy/app/quant-diligence')
def run(cid,market,track='nominal',fit=False):
 c=json.loads((B/'contract.json').read_text());v=next((x for x in c['vibe'] if x['id']==cid),None);work=B/'calculations'/cid/('fitUS' if fit else track+'_'+market);work.mkdir(parents=True,exist_ok=True)
 cfg={'kind':'vibe' if v else 'quanta','H':v['primary_H'] if v else 20,'warmup':v['warmup'] if v else 63,'fit_only':fit,**({'native_id':v['native_id'],'sign':v['sign']} if v else {})};(work/'spec.json').write_text(json.dumps(cfg))
 if fit:inp=B/'generation_input'
 elif track=='adjusted':inp=B/'adjusted_calculation_inputs'/market
 else:inp=B/'nominal_inputs'/market
 
 if (work/'calculation.json').exists():
  cached=json.loads((work/'calculation.json').read_text());assert cached['input_hash']==hashlib.sha256((inp/'panel.csv').read_bytes()).hexdigest();assert cached['output_hash']==hashlib.sha256((work/'scores.csv').read_bytes()).hexdigest();return cached
 env='task6-quanta-env' 
 cmd=['docker','run','--rm','--network=none','--cap-drop=ALL','--security-opt','no-new-privileges','--cpus=2','--memory=4g','--pids-limit=256','--user','1000:1000','-e','HOME=/work','-e','OMP_NUM_THREADS=2','-e','PYTHONDONTWRITEBYTECODE=1','-e','LITELLM_LOCAL_MODEL_COST_MAP=True','-v',str(E/env)+':/venv:ro','-v',str(work)+':/work','-v',str(work)+':/spec:ro','-v',str(inp)+':/input:ro','-v',str(R/'experiments/task13')+':/code:ro']
 if v:cmd+=['-v',str(E/'vibe-original/agent')+':/native:ro']
 else:cmd+=['-v',str(B/'native/quanta'/cid)+':/candidate:ro']
 cmd+=['-w','/work','quant-research-task6:local','/venv/bin/python','/code/factor_worker.py'];p=subprocess.run(cmd,capture_output=True,text=True,timeout=360);(work/'execution.log').write_text(p.stdout+p.stderr)
 if p.returncode:raise RuntimeError('CALCULATION_FAILED '+str(work))
 return json.loads((work/'calculation.json').read_text())
if __name__=='__main__':print(run(*sys.argv[1:]))
