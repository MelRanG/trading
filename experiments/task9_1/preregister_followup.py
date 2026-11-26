from common import *
from quant_harness.investment.store import Store
from quant_harness.investment.review_jobs import Queue
from quant_harness.alpha_research_factory import register_review_proposal
sys.path.insert(0,str(R/'experiments/task9_completion'))
from serialization_fix import canonical_zero
results=json.loads((B/'evaluation/2024-11-29.json').read_text());year12=[x for x in results if x['months']==12];summary=[]
for m in ['US','KR']:
 rows={x['arm']:x for x in year12 if x['market']==m};a=rows['ALLOC_AI_MARKET'];b=rows['ALLOC_FIXED60'];summary.append({'market':m,'AI_return':a.get('net_price_return'),'fixed60_return':b.get('net_price_return'),'fixed60_status':b['status'],'classification':'SIZING_OPPORTUNITY_COST_ACCOUNTING_NOT_CAUSAL_ERROR' if b['status']=='CALCULATED_PARTIAL' else 'DATA_LIMITATION','evidence_hash':sha(B/'evaluation/2024-11-29.json'),'confidence':'MECHANICAL_ACCOUNTING_ONLY','causal_rationality':'UNDETERMINED_EX_ANTE_INCOMPLETE_EVIDENCE'})
request={'schema':'TASK9_1_FOLLOWUP_V1','observed_diagnosis':summary,'candidate':'FIXED60_SAME_EXANTE_FIRST3_BASKET','champion':'AI_CONDITIONAL_SAME_BASKET','parameters':{'gross':.6,'per_name':.2,'search':0},'selection_change':False,'evaluation_date':'2025-06-30','horizons':[3,6,12],'prices':'separate evaluator-only frozen input; no2025metric readout before this seal','expected_effect':'Measure opportunity cost of cash separately from chosen companies, not force deployment','falsification':'Fixed60 can lose or underperform; do not adopt from small historical sample','minimum_independent_cases':12,'available_market_date_cases':4,'approval':'NO_AUTOMATIC_PROMOTION','created_at':now()}
p=B/'followup_preregistered.json'
if p.exists():request=json.loads(p.read_text())
else:freeze(p,request)
store=Store('postgresql://quant_task9_history@127.0.0.1:55432/quant_task3_task9_history','TASK9_HISTORICAL_ONLY');record=store.put('task91_followup_preregistration',canonical_zero(request));queue=Queue(store);job=queue.enqueue('TASK91_ALLOCATION_FOLLOWUP',{'preregistration_id':record,'worker_hash':sha(R/'experiments/task9_1/evaluate.py'),'operating_orders':False})
proposal={'problem_evidence':{'record_id':record,'process_reviews_hash':sha(B/'blinded_process_reviews.json'),'diagnosis_hash':digest(summary)},'target':'strategy','expected_effect':request['expected_effect'],'falsification':request['falsification'],'champion':request['champion'],'challenger':request['candidate'],'input_hash':digest({'2024':sha(B/'model_inputs/2024-11-29/foundation.json'),'2025':sha(B/'model_inputs/2025-06-30/foundation.json')}),'budget':{'experiments':1,'parameter_search':0},'stop_conditions':['missing price','source conflict','budget exhausted','code changed'],'evaluation_metric':'paired allocation accounting and cash opportunity cost; not alpha proof','minimum_cases':12,'split':'PROCESS_DIAGNOSTIC_ONLY','worker_hash':sha(R/'experiments/task9_1/evaluate.py')}
try:attempt=register_review_proposal(R,proposal);status={'status':'REGISTERED','attempt':attempt}
except ValueError as e:status={'status':'BLOCKED_REGISTRATION','reason':str(e),'no_isolated_bypass':True}
freeze(B/'factory_handoff.json',{'proposal':proposal,'official':status,'research_job':job,'record_id':record,'bounded_historical_readout':'User-authorized Task9.1 research diagnostic; not a reserved official Factory experiment','created_at':now()});print(status['status'],job)
