"""One restart-safe research Queue job; deterministic candidate evaluation, no orders."""
from common import *
import importlib.util,pandas as pd,uuid
from quant_harness.investment.store import Store
from quant_harness.investment.review_jobs import Queue
sys.path.insert(0,str(R/'experiments/task9_completion'))
from serialization_fix import canonical_zero
spec=importlib.util.spec_from_file_location('followup_parent',R/'experiments/task9_1/evaluate.py');ev=importlib.util.module_from_spec(spec);spec.loader.exec_module(ev)
spec=importlib.util.spec_from_file_location('endpoint_worker',R/'experiments/task9_1/evaluate_endpoint.py');ep=importlib.util.module_from_spec(spec);spec.loader.exec_module(ep)
store=Store('postgresql://quant_task9_history@127.0.0.1:55432/quant_task3_task9_history','TASK9_HISTORICAL_ONLY');queue=Queue(store);handoff=json.loads((B/'factory_handoff.json').read_text());job=handoff['research_job'];owner=str(uuid.uuid4());claim=queue.claim(owner,120,job)
if not claim:
 print('NO_RECLAIM_COMPLETED_OR_WAITING_JOB');raise SystemExit(0)
try:
 rows=[];date='2025-06-30';preregister=json.loads((B/'followup_preregistered.json').read_text());assert preregister['selection_change'] is False
 for market,index in [('US','^GSPC'),('KR','^KS11')]:
  arms,preview=ev.baskets(date,market);weights=arms['ALLOC_FIXED60'];champion=arms['ALLOC_AI_MARKET'];idx,_=ev.valid_prices(pd.read_csv(B/'evaluator_only'/date/index/'bars.csv'))
  for months in [3,6,12]:
   a,z=ev.window(idx.index,date,months);ds=idx.loc[a:z].index if market=='US' else pd.DatetimeIndex([a,z]);bench=idx.loc[ds,'close']/float(idx.loc[a,'open']);bench.loc[z]=float(idx.loc[z,'open']/idx.loc[a,'open'])
   if market=='US':bench.loc[a-pd.Timedelta(seconds=1)]=1.;bench=bench.sort_index()
   else:bench.loc[a]=1.
   paths={}
   for s in set(weights)|set(champion):
    if market=='US':paths[s],_=ev.path_for(date,s,a,z,ds)
    else:r,_=ep.endpoints(date,s,a,z);paths[s]=pd.Series([1.,r],index=ds)
   metrics={}
   for name,w in [('champion_AI',champion),('candidate_fixed60',weights)]:
    if w:m,_=ev.mix(paths,w,bench,6.5 if market=='KR' else 6,29.5 if market=='KR' else 6)
    else:m,_=ev.mix({'CASH':pd.Series(1.,index=bench.index)},{'CASH':0},bench,0,0);m['positions']={}
    if market=='KR':m.update(mdd_observed_marks=None,sharpe_rf0_diagnostic=None,missing_index_marks=None)
    metrics[name]=m
   rows.append({'market':market,'months':months,'fixed_basket':list(weights),'evaluation':metrics,'candidate_minus_champion':metrics['candidate_fixed60']['net_price_return']-metrics['champion_AI']['net_price_return'],'judgment':'HISTORICAL_DIAGNOSTIC_ONLY_NOT_ADOPTED'})
 result={'job':job,'preregistration_hash':sha(B/'followup_preregistered.json'),'worker_hash':sha(__file__),'unchanged_evaluator_hash':sha(R/'experiments/task9_1/evaluate.py'),'data_repair_contract':sha(R/'experiments/task9_1/endpoint_contract.json'),'results':rows,'status':'INSUFFICIENT_EVIDENCE','independent_market_date_cases':4,'minimum_unchanged':12,'operating_factory':handoff['official'],'no_promotion':True,'execution':'EXISTING_RESEARCH_QUEUE_CLAIM_AND_DETERMINISTIC_EVALUATION','created_at':now()};identity=store.put('task91_followup_result',canonical_zero(result));queue.finish(job,owner,identity,'DONE');freeze(B/'followup_result.json',result)
 pending=queue.enqueue('TASK91_FACTORY_REGISTRATION_RETRY',{'proposal_hash':digest(handoff['proposal']),'artifact':'runtime/task9_1/factory_handoff.json','previous_research_job':job,'no_budget_bypass':True},__import__('datetime').datetime.combine(__import__('datetime').datetime.now(__import__('datetime').timezone.utc).date()+__import__('datetime').timedelta(days=1),__import__('datetime').time(),tzinfo=__import__('datetime').timezone.utc));freeze(B/'factory_retry.json',{'job':pending,'status':'READY_FUTURE_OBSERVATION','dispatcher':'Task9.1 explicit worker needed; current production Operations does not automatically execute unknown Task91 kind','operating_factory_state_unchanged':True});print('QUEUE_EVALUATION_DONE',job,identity)
except Exception as exc:queue.fail(job,owner,type(exc).__name__);raise
