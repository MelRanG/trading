"""Normal official Factory registration, preserving earlier pending families."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import json,sys,hashlib
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'))
from quant_harness.alpha_research_factory import register_review_proposal,reserve_review_experiment,record_review_experiment
from quant_harness.investment.exploration import research_store
from quant_harness.investment.review_jobs import Queue
from quant_harness.investment.research import digest
b=R/'runtime/task8b';store,cfg=research_store(R);queue=Queue(store);packet=json.loads((b/'research_packet_v2.json').read_text());opps=json.loads((b/'final_opportunities.json').read_text());worker=hashlib.sha256(Path(__file__).read_bytes()).hexdigest();receipts=[]
# The user previously authorized these registrations after normal UTC renewal.
# Keep their immutable original proposals and record NEW receipts here, not rewrite old BLOCKED evidence.
for label,path in [('Task6',R/'runtime/task6/factory_handoff.json'),('Task7',R/'runtime/task7/review/factory_proposal.json')]:
 prior=json.loads(path.read_text());proposal=prior.get('proposal',prior)
 try:attempt=register_review_proposal(R,proposal);receipts.append({'task':label,'status':'REGISTERED_UNCHANGED_PROPOSAL','attempt':attempt,'source':str(path.relative_to(R))})
 except ValueError as exc:receipts.append({'task':label,'status':'BLOCKED','reason':str(exc)})
proposal={'problem_evidence':{'packet_hash':digest(packet),'research_snapshot_hash':digest(opps),'source_quality':'12 full original issuer/regulatory capture,2 explicitly partial primary-web excerpts'},'target':'review','expected_effect':'Test native Vibe research outputs against identical-input deterministic authority, capital-bridge, source and timing gates; no assumed return improvement','falsification':'No incremental integrity value or inconsistent gates; independent alpha remains unproven','champion':'TASK8B_NATIVE_VIBE_VALUATION_REVIEW_FROZEN','challenger':'TASK8B_HYBRID_EXPLORATION_GATES_V1','input_hash':digest(packet),'budget':{'experiments':1,'parameter_search':0},'stop_conditions':['missing original source or current identity','less than12 full source-grounded independent companies','budget exhausted','attempt to promote hypothetical sensitivities'],'evaluation_metric':['source quality','EV equity bridge integrity','decision trace and research permission','future price-return/cost after observed sessions only'],'minimum_cases':12,'split':'PROCESS_DIAGNOSTIC_ONLY','worker_hash':worker}
(b/'factory_proposal.json').write_text(json.dumps(proposal,indent=2))
try:
 attempt=register_review_proposal(R,proposal);status={'status':'REGISTERED','attempt':attempt}
 # Earlier Task5 used today's normal experiment slot. Do not steal later priority.
 try:
  reserve_review_experiment(R,attempt)
  prior_unexecuted=[r for r in receipts if r['status']=='REGISTERED_UNCHANGED_PROPOSAL']
  if prior_unexecuted:raise ValueError('older registered hypotheses must execute first; no lower-priority evaluation')
  result={'status':'FORWARD_REQUIRED','cases':12,'input_hash':digest(packet),'worker_hash':worker,'scope':'Retrospective process diagnostic, not independent investment efficacy','total_researched':14,'primary_full_cases':12,'partial_excerpt_cases':2,'research_shadow_cases':5,'conditional_probes':4,'official_paper_eligible':0,'forward_returns':'PENDING'};status['result']=record_review_experiment(R,attempt,result)
 except ValueError as exc:status.update(execution='BLOCKED_NORMAL_BUDGET_OR_OLDER_PRIORITY',reason=str(exc))
except ValueError as exc:status={'status':'BLOCKED_REGISTRATION','reason':str(exc)}
# No official experiment result is substituted with prior model outputs.
next_day=datetime.combine(datetime.now(timezone.utc).date()+timedelta(days=1),datetime.min.time(),tzinfo=timezone.utc).isoformat();job=queue.enqueue('FACTORY_OPPORTUNITY_FOLLOWUP',{'proposal_hash':digest(proposal),'official_status':status.get('status'),'priority_after':['Task5','Task6','Task7'],'requires':'Normal budget, registered worker and eligible source snapshot'},next_day)
receipt={'observed_at':datetime.now(timezone.utc).isoformat(),'older_registrations':receipts,'task8b':status,'followup_job':job,'old_handoff_files_unchanged':True,'automatic_promotion':False};store.put('factory_opportunity_receipt',receipt);(b/'factory_status.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt,indent=2))
