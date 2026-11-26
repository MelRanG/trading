from shared import *
import subprocess,shutil,ast
E=Path('/home/ansy/app/quant-diligence');IMAGE='quant-research-task6:local'
def docker(env,work,mounts,args,timeout=600):
 work=Path(work);work.mkdir(parents=True,exist_ok=True)
 cmd=['docker','run','--rm','--network=none','--cap-drop=ALL','--security-opt','no-new-privileges','--memory=4g','--cpus=2','--pids-limit=256','--user','1000:1000','-e','HOME=/work','-e','PYTHONDONTWRITEBYTECODE=1','-e','OMP_NUM_THREADS=2','-v',str(E/('task6-'+env+'-env'))+':/venv:ro','-v',str(work)+':/work','-v',str(R/'experiments/task10')+':/code:ro']
 for source,dest,mode in mounts:cmd+=['-v',str(source)+':'+dest+':'+mode]
 cmd+=['-w','/work',IMAGE,'/venv/bin/python',*args];p=subprocess.run(cmd,capture_output=True,text=True,timeout=timeout);(work/'execution.log').write_text(p.stdout+p.stderr)
 if p.returncode:raise RuntimeError('isolatedworkerFAILED:'+str(work)+':'+(p.stdout+p.stderr)[-700:])

def factor(stage,m,fs,code):
 work=B/'factor_execution'/stage/m;result=work/'factor_values.csv'
 if result.exists():
  frozen=work/'candidate/factor.py';assert frozen.exists() and sha(frozen)==sha(code),'factor cache/code fingerprint mismatch'
 if not result.exists():
  inp=work/'input';inp.mkdir(parents=True,exist_ok=True);factor_input(fs,inp/'panel.csv');candidate=work/'candidate';candidate.mkdir(exist_ok=True);shutil.copyfile(code,candidate/'factor.py')
  docker('quanta',work,[(inp,'/input','ro'),(candidate,'/candidate','ro'),(R/'experiments/task6','/oldcode','ro')],['/oldcode/evaluate_worker.py','quanta'])
 values=pd.read_csv(result,parse_dates=['datetime']).set_index(['datetime','instrument']).iloc[:,0].unstack('instrument');return values.reindex(index=next(iter(fs.values())).index)

def train_model(stage,m,fs):
 work=B/'models'/stage/m;out=work/'training.json';inputdir=work/'input';inputdir.mkdir(parents=True,exist_ok=True)
 if not out.exists():
  for s,f in fs.items():
   if 'BENCHMARK' not in s:f.to_csv(inputdir/(s+'.csv'),index_label='date')
  model=E/'task10-rd-work';docker('rd',work,[(inputdir,'/input','ro'),(model,'/candidate','ro')],['/code/train_worker.py','train'])
 meta=json.loads(out.read_text());assert meta['model_code_hash']==sha(E/'task10-rd-work/model.py'),'model cache/code fingerprint mismatch';assert meta['checkpoint_hash']==sha(work/'model.pth'),'checkpoint cache mismatch';return meta

def predict(stage,m,fs,tag=None):
 trained=B/'models'/stage/m;work=B/'predictions'/(tag or stage)/m;inputdir=work/'input';result=work/'predictions.csv';inputdir.mkdir(parents=True,exist_ok=True)
 if not result.exists():
  for s,f in fs.items():
   if 'BENCHMARK' not in s:f.to_csv(inputdir/(s+'.csv'),index_label='date')
  docker('rd',work,[(inputdir,'/input','ro'),(trained,'/trained','ro'),(E/'task10-rd-work','/candidate','ro')],['/code/train_worker.py','predict'])
 return pd.read_csv(result,parse_dates=['datetime']).set_index(['datetime','instrument']).iloc[:,0].unstack('instrument')
