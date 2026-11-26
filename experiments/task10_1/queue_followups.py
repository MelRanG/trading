"""Persist separated prospective research requests; never executes unknown code.

A Queue request is not Factory approval, reservation, or a completed experiment.
No prospective native research executor is enabled by this adapter.
"""
from pathlib import Path
import json,sys
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'))
from quant_harness.investment.research import digest
from quant_harness.investment.store import Store
from quant_harness.investment.review_jobs import Queue

def submit(root=R):
 root=Path(root);folder=root/'runtime/task10_1/forward';requests=[]
 for p in sorted((folder/'reviews').glob('*/*.json')):
  review=json.loads(p.read_text())
  for r in review.get('research_requests',[]):
   if r['target'] not in ('QUANTA_ALONE','RD_RETRAIN_ALONE'):raise ValueError('unsupported research target')
   requests.append((p,review,r))
 if not requests:return {'status':'PENDING_MATURE_FORWARD_REVIEW','requests':0,'experiments_executed':0}
 # Existing official review DB; no trade/coin DB or new service/database.
 store=Store('postgresql://quant_task3@127.0.0.1:55432/quant_task3_review','TASK4_REVIEW_ONLY');queue=Queue(store);out=[]
 with store.lock():
  for p,review,r in requests:
   family={'contract_hash':digest(json.loads((folder/'contract.json').read_text())),'market':review['market'],'arm':r['arm'],'target':r['target']};key='task101-family-'+digest(family)
   try:request=store.get(key)
   except ValueError:
    request={'family':family,'review_path':str(p.relative_to(root)),'review_hash':digest(review),'classification':'PROSPECTIVE_SHADOW_RESEARCH_REQUEST','authority':'REQUEST_ONLY_PENDING_FACTORY_PREREGISTRATION_BUDGET_AND_TYPED_EXECUTOR','automatic_promotion':False,'status':'PENDING_REGISTERED_EXECUTOR'};store.put('task101_forward_research_request',request,key)
   job=queue.enqueue('TASK101_QUANTA_RESEARCH_REQUEST' if r['target']=='QUANTA_ALONE' else 'TASK101_RD_RETRAIN_REQUEST',{'request_id':key});out.append({'job_id':job,'request_id':key,'status':'PENDING_REGISTERED_EXECUTOR'})
 return {'status':'REQUESTS_QUEUED_NOT_EXECUTED','requests':len(out),'jobs':out,'experiments_executed':0,'promotion':False}
if __name__=='__main__':print(json.dumps(submit(),indent=2))
