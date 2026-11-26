from pathlib import Path
import subprocess,json,sys
R=Path(__file__).resolve().parents[2];E=Path('/home/ansy/app/quant-diligence');B=R/'runtime/task12';results=[]
for name,env in [('vibe','vibe-env'),('rd','task6-rd-env'),('qa','task6-quanta-env')]:
 if len(sys.argv)>1 and sys.argv[1]!=name:continue
 cmd=['docker','run','--rm','--network=none','--cap-drop=ALL','--security-opt','no-new-privileges','--cpus=2','--memory=4g','--pids-limit=256','--user','1000:1000','-w','/out','-e','HOME=/tmp','-e','PYTHONDONTWRITEBYTECODE=1','-e','OMP_NUM_THREADS=2','-e','LITELLM_LOCAL_MODEL_COST_MAP=True','-v',str(E/env)+':/venv:ro','-v',str(R/'experiments/task12')+':/code:ro','-v',str(R/'experiments/task12')+':/repo/experiments/task12:ro','-v',str(R/'src')+':/repo/src:ro','-v',str(R/'runtime/task6_completion/native/quanta')+':/qa_saved:ro','-v',str(R/'runtime/task10/tape')+':/data:ro','-v',str(B)+':/out','-v',str(E/'vibe-original/agent')+':/native:ro','-v',str(E/'task10-rd-work')+':/model:ro','-v',str(R/'runtime/task10/models/initial/US')+':/checkpoint:ro','quant-research-task6:local','/venv/bin/python','/code/engine_probe.py',name]
 p=subprocess.run(cmd,capture_output=True,text=True,timeout=240);(B/(name+'_probe.log')).write_text(p.stdout+p.stderr);results.append({'probe':name,'exit_code':p.returncode})
status=B/'probe_status.json';prior=json.loads(status.read_text()) if status.exists() else [];names={x['probe'] for x in results};results=[x for x in prior if x['probe'] not in names]+results;status.write_text(json.dumps(results,indent=2));print(results)
