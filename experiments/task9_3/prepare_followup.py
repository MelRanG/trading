from common import *
from quant_harness.investment.review import policy,process_review
from quant_harness.investment.research_dispatcher import factory_work,worker_hash,digest as factory_digest
from quant_harness.investment.store import Store
from quant_harness.investment.review_jobs import Queue
import uuid
sys.path.insert(0,str(R/'experiments/task9_completion'));from serialization_fix import canonical_zero
store=Store('postgresql://quant_task9_history@127.0.0.1:55432/quant_task3_task9_history','TASK9_HISTORICAL_ONLY');queue=Queue(store)
if (B/'feedback.json').exists():
 old=json.loads((B/'feedback.json').read_text());assert store.get(old['result_record']);print('FEEDBACK_ALREADY_DONE_READBACK',old['job']);raise SystemExit()
results=[x for m in ['US','KR'] for x in json.loads((B/'evaluation'/m/'results.json').read_text())];diagnosis=[]
for market in ['US','KR']:
 r={x['arm']:x for x in results if x['market']==market};p=r['POLICY'];s=r['SELECTION_EQUAL90'];fixed=r['INITIAL_SELECTION_HOLD90']
 diagnosis.append({'market':market,'measured':{'policy_net':p['net_price_return'],'selection_net':s['net_price_return'],'index':p['benchmark_price_return'],'policy_average_exposure':p['average_equity_exposure'],'dynamic_minus_initial_hold':s['net_price_return']-fixed['net_price_return'],'cost_drag_selection':s['gross_price_return']-s['net_price_return']},'confirmed':[{'category':'SIZING','evidence':'Observed cash opportunity cost and selected basket counterfactual, not evidence that forced purchases were rational'},{'category':'INFORMATION_MISSING','evidence':'Bounded universe, missing issuerprimary/consensus/capital claims and some price disagreements'}],'selection_interpretation':'Selected basket underperforms index at fixed90%exposure' if s['net_price_return']<p['benchmark_price_return']*.9 else 'Selected basket outperforms90%index in this diagnostic only','forecast_error':'UNDETERMINED_NO_MATCHED_MATURE_ANNUAL_ACTUAL','engine_method_inferiority':'UNDETERMINED_LIMITED_BUDGET_AND_PIT_SAMPLE'})
request={'schema':'TASK93_REVIEW_REQUEST_V1','diagnosis':diagnosis,'evidence_hashes':{m:sha(B/'evaluation'/m/'results.json') for m in ['US','KR']},'followup':'Reconcile current capital claims and PIT source coverage before a new independent company-discovery/valuation experiment; do not lower entry thresholds or force gross exposure from these historical results','engine_routes':{'company':'original Vibe financial/valuation + source adapter','quant':'QuantaAlpha/RD only new preregistered research; no retroactive native alpha','review':'Quant Harness independent evaluation'},'minimum_independent_companies':12,'current_independent_deep_companies':10,'promotion':'NONE','capital_authority':'NONE'}
freeze(B/'followup_request.json',request);identity=store.put('task93_historical_review_request',canonical_zero(request));
import psycopg
with psycopg.connect(store.url) as conn:
 oldjobs=conn.execute("SELECT job_id,payload FROM review_job WHERE kind='TASK93_HISTORICAL_REVIEW' AND payload->>'request_id'=%s AND status='RETRY'",(identity,)).fetchall()
for oldjob,oldpayload in oldjobs:
 claimold=queue.claim('task93-adapter-retirement',120,oldjob)
 if claimold:
  failed=store.put('task93_adapter_failure',{'status':'FAILED_BEFORE_FACTORY_REGISTRATION','error':'canonical JSON digest differed; corrected adapter version creates a new job','old_worker_hash':oldpayload['worker_hash'],'no_official_experiment_ran':True});queue.finish(oldjob,'task93-adapter-retirement',failed)
job=queue.enqueue('TASK93_HISTORICAL_REVIEW',{'request_id':identity,'worker_hash':sha(Path(__file__)),'operating_orders':False,'adapter_version':'V2_CANONICAL_FACTORY_HASH'});owner='task93-'+str(uuid.uuid4());claim=queue.claim(owner,120,job)
if not claim:raise ValueError('inspect existing job state')
bundle={'asof':'2026-05-15','cases':[]}
for market in ['US','KR']:
 packet=json.loads((B/'packets'/market/'2026-05-15.json').read_text())
 for c in packet['cases']:bundle['cases'].append({'symbol':c['symbol'],'facts':c['verified_facts']})
freeze(B/'factory_bundle.json',bundle)
proposal={'problem_evidence':{'historical_review_record':identity,'evidence_hash':digest(request)},'target':'source','expected_effect':'Prevent missing/time-misaligned capital facts from being treated as weak investment value; verify source provenance before an independent future experiment','falsification':'Complete sources may still yield cash or weak selected portfolios; no efficiency or investment advantage inferred from fact count','champion':'TASK93_BOUNDED_DATED_PRIMARY','challenger':'TASK93_SOURCE_COMPLETENESS_AND_CAPITAL_TIMING_AUDIT_V1','input_hash':factory_digest(bundle),'budget':{'experiments':1,'parameter_search':0},'stop_conditions':['sourcehashchanged','futurepublication','missingdata','budgetexhausted'],'evaluation_metric':'Source-linked numeric correctness only; subsequent investment efficacy requires separate12independentcompanies and Forward','minimum_cases':12,'split':'PROCESS_DIAGNOSTIC_ONLY','worker_hash':worker_hash()};freeze(B/'factory_proposal_v2.json',proposal)
try:
 result=factory_work(R,proposal,bundle);payload=canonical_zero({'request_id':identity,'diagnosis':diagnosis,'official_factory':result,'source_audit_is_not_strategy_performance':True});resultid=store.put('task93_historical_review_result',payload);queue.finish(job,owner,resultid);follow=queue.enqueue('TASK93_INDEPENDENT_COMPANY_RESEARCH',{'review_id':resultid,'required_independent_cases':12,'no_order_authority':True,'status':'NEEDS_PREREGISTERED_DATA_BUDGET','dispatcher':'NOT_AUTOMATICALLY_SUPPORTED_BY_OPERATIONS'});freeze(B/'feedback.json',{'job':job,'request_record':identity,'result_record':resultid,'followup_job':follow,'factory':result,'dispatcher':'Explicit Task93 historical worker ran; future unknownkind is queued, not automatically executed','no_budget_bypass':True,'not_independent_investment_improvement':True});print('REVIEW_DONE',job,'FACTORY',result['status'])
except Exception as e:queue.fail(job,owner,type(e).__name__);raise
