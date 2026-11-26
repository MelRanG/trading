from common import *
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from unittest.mock import patch
import subprocess
import quant_harness.alpha_research_factory as factory
from quant_harness.investment.store import Store
from quant_harness.investment.review_jobs import Queue
NAME='quant_task3_task10_replay';URL='postgresql://quant_task3@127.0.0.1:55432/'+NAME

def open_store():
 exists=subprocess.check_output(['docker','exec','quant-task3-postgres','psql','-U','quant_task3','-d','postgres','-Atc',"SELECT datname FROM pg_database WHERE datname='"+NAME+"'"],text=True).strip()
 if not exists:subprocess.run(['docker','exec','quant-task3-postgres','createdb','-U','quant_task3',NAME],check=True)
 return Store(URL,'TASK10_RESEARCH_REPLAY_ONLY')

def clock_at(day,m):return datetime.fromisoformat(str(day)[:10]+('T17:00:00' if m=='US' else 'T16:00:00')).replace(tzinfo=ZoneInfo('America/New_York' if m=='US' else 'Asia/Seoul')).astimezone(timezone.utc)
class Clock(datetime):
 value=None
 @classmethod
 def now(cls,tz=None):return cls.value.astimezone(tz) if tz else cls.value.replace(tzinfo=None)

def preregister(m,day,snapshot,review,dates):
 store=open_store();queue=Queue(store);out=B/'factory';out.mkdir(exist_ok=True);worker=digest({p.name:sha(p) for p in Path(__file__).parent.glob('*.py') if p.name in ['shared.py','measure.py','train_worker.py','native_worker.py']});ih=digest(snapshot);name=m+'_'+str(day)[:10];report=B/'experiments'/name/'reservation.json';report.parent.mkdir(parents=True,exist_ok=True)
 if report.exists():
  old=json.loads(report.read_text());assert old['input_hash']==ih and old['worker_hash']==worker,'changed frozen reservation input/worker';return old
 proposal={'problem_evidence':review,'target':'strategy','expected_effect':'Testsingleprefix-onlynativefactor/modelcandidate after sustainedmatured signalweakness, notfitfuturePnl','falsification':'Same-cutoffcandidatefailscost/risk/IC/stability/causalitygate','champion':'TASK10_'+m+'_INITIAL_NATIVE','challenger':'TASK10_'+name+'_ONE_CANDIDATE','input_hash':ih,'budget':{'experiments':1,'parameter_search':0},'stop_conditions':['futuredata','budgetexhaustion','prefixchanged','missinglabels','causalityfailed'],'evaluation_metric':['net_return','MDD','matureRankIC','nonoverlapblocks','leaveoneoutIC'],'minimum_cases':12,'split':'PROCESS_DIAGNOSTIC_ONLY','worker_hash':worker}
 pending=[]
 for d in dates:
  if str(d)[:10]<str(day)[:10]:continue
  Clock.value=clock_at(d,m)
  try:
   with patch.object(factory,'datetime',Clock):a=factory.register_review_proposal(R,proposal,directory=out);reservation=factory.reserve_review_experiment(R,a,directory=out)
   job=queue.enqueue('TASK10_NATIVE_RESEARCH',{'attempt':a,'snapshot_hash':ih,'market':m,'source_asof':str(day)[:10],'processing_day':str(d)[:10]});v={'attempt':a,'reservation':reservation,'input_hash':ih,'worker_hash':worker,'job_id':job,'asof':str(day)[:10],'processing_day':str(d)[:10],'queue_waits':pending,'directory':str(out),'proposal':proposal};freeze(report,v);return v
  except ValueError as e:
   if 'budget' not in str(e):raise
   pending.append({'replay_day':str(d)[:10],'status':'BLOCKED_NORMAL_REPLAY_BUDGET','reason':str(e)})
 raise ValueError('Noeligiblebudgetdatebeforeend')

def record(v,result):
 store=open_store();q=Queue(store);claim=q.claim('task10-worker',lease_seconds=3600,identity=v['job_id'])
 if claim is None:
  import psycopg
  with psycopg.connect(store.url) as conn:current=conn.execute("SELECT status,owner FROM review_job WHERE job_id=%s",(v['job_id'],)).fetchone()
  if current==('RUNNING','task10-worker'):claim={'job_id':v['job_id']}
 if claim is None:
  p=B/'factory/diagnostic_registry.jsonl';rows=[json.loads(x) for x in p.read_text().splitlines()] if p.exists() else [];old=next((r for r in rows if r['attempt_id']==v['attempt']['attempt_id']),None);assert old is not None,'JOB_RUNNING_OR_UNRECORDED';assert old['result']=={'input_hash':v['input_hash'],'worker_hash':v['worker_hash'],**result},'immutable completed experiment conflict';return {'status':'ALREADY_DONE','official_result':old,'result_id':store.put('task10_experiment',old),'followup_done':True}
 Clock.value=clock_at(v['processing_day'],v['proposal']['champion'].split('_')[1])
 with patch.object(factory,'datetime',Clock):saved=factory.record_review_experiment(R,v['attempt'],{'input_hash':v['input_hash'],'worker_hash':v['worker_hash'],**result},directory=B/'factory')
 rid=store.put('task10_experiment',saved);q.finish(v['job_id'],'task10-worker',rid);follow=q.observe(v['job_id'],digest(saved));followclaim=q.claim('task10-followup',identity=follow)
 if followclaim:
  nextreq={'previous_result':rid,'cause':result.get('cause','UNDETERMINED'),'status':'FORWARD_REPLAY_OBSERVATION_REQUIRED' if result['status']=='FORWARD_REQUIRED' else 'MAINTAIN_PARENT_RESEARCH_REJECTED','no_automatic_operating_promotion':True};fr=store.put('task10_followup',nextreq);q.finish(follow,'task10-followup',fr)
 return {'official_result':saved,'result_id':rid,'followup_job':follow,'followup_done':followclaim is not None}
