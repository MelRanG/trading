from pathlib import Path
import subprocess,sys,json
R=Path(__file__).resolve().parents[2];B=R/'runtime/task13_r2';node=B/'native/rd';out=B/'training';out.mkdir(exist_ok=True);mode=sys.argv[1]
cmd=['docker','run','--rm','--network=none','--cap-drop=ALL','--security-opt','no-new-privileges','--cpus=2','--memory=4g','--user','1000:1000','-e','HOME=/work','-e','OMP_NUM_THREADS=2','-e','LITELLM_LOCAL_MODEL_COST_MAP=True','-e','PYTHONDONTWRITEBYTECODE=1','-v','/home/ansy/app/quant-diligence/task6-rd-env:/venv:ro','-v',str(node)+':/candidate:ro','-v',str(R/'runtime/task13_r0/native')+':/inputs:ro','-v',str(R/'experiments/task13_r2')+':/code:ro','-v',str(R/'experiments/task13_r0/loader.py')+':/shared/loader.py:ro','-v',str(R/'runtime/task13/native/rd')+':/baseline:ro','-v',str(out)+':/work','-w','/work','quant-research-task6:local','/venv/bin/python','/code/train.py',mode]
p=subprocess.run(cmd,capture_output=True,text=True,timeout=1500);(B/(mode+'_training.log')).write_text(p.stdout+p.stderr)
if p.returncode:
 (B/(mode+'_training_failure.json')).write_text(json.dumps({'exit':p.returncode,'stderr':p.stderr[-1500:]}));raise SystemExit(p.returncode)
print('QLIB_TRAINED',mode)
