"""Abrupt worker-exit probe in the disposable review TEST DB only."""
from pathlib import Path
import json,os,subprocess,sys,time,uuid
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from quant_harness.investment.store import Store
from quant_harness.investment.review_jobs import Queue
from quant_harness.investment.research import digest


def main():
    url=os.environ['TASK4_TEST_DATABASE_URL']
    if not url.endswith('/quant_task3_review_test'):raise ValueError('crash probe test DB only')
    store=Store(url,'TASK4_REVIEW_ONLY');queue=Queue(store)
    payload={'probe':'TASK4_ABRUPT_PROCESS_EXIT_V1','instance':str(uuid.uuid4()),'evidence_class':'SYNTHETIC_CRASH_PROBE'}
    job=queue.enqueue('CRASH_PROBE',payload);stage='CRASH-STAGE-'+digest(payload)
    child='''import os
from quant_harness.investment.store import Store
from quant_harness.investment.review_jobs import Queue
s=Store(os.environ['TASK4_TEST_DATABASE_URL'],'TASK4_REVIEW_ONLY')
with s.lock():
 q=Queue(s)
 assert q.claim('abrupt-worker',lease_seconds=1,identity=os.environ['PROBE_JOB_ID'])
 s.put('review_crash_checkpoint',{'checkpoint':'sealed_before_job_commit','synthetic':True},os.environ['PROBE_STAGE_ID'])
 os._exit(23)
'''
    env={k:v for k,v in os.environ.items() if k in ('PATH','HOME','LANG')}
    env.update(PYTHONPATH=str(ROOT/'src'),TASK4_TEST_DATABASE_URL=url,PROBE_JOB_ID=job,PROBE_STAGE_ID=stage)
    completed=subprocess.run([sys.executable,'-c',child],env=env,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if completed.returncode!=23:raise ValueError('expected injected exit 23')
    time.sleep(1.3)
    with store.lock():
        resumed=queue.claim('replacement-worker',identity=job)
        if not resumed:raise ValueError('abandoned research lease not recovered')
        checkpoint=store.get(stage)
        queue.finish(job,'replacement-worker',stage)
    result={'job_id':job,'injected_worker_exit':23,'replacement_claimed':True,'checkpoint':checkpoint,
            'checkpoint_reexecuted':False,'evidence_class':'SYNTHETIC_CRASH_PROBE','real_forward_performance':False}
    out=ROOT/'runtime/task4/crash_probe.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
