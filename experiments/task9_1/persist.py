from common import *
import subprocess,shutil
from quant_harness.investment.store import Store
from quant_harness.investment.review_jobs import Queue
sys.path.insert(0,str(R/'experiments/task9_completion'))
from serialization_fix import canonical_zero
store=Store('postgresql://quant_task9_history@127.0.0.1:55432/quant_task3_task9_history','TASK9_HISTORICAL_ONLY');ids=[]
if (B/'persistence.json').exists():
 prior=json.loads((B/'persistence.json').read_text());assert all(store.get(i) for i in prior['records']);assert sha(B/'research_state.dump')==prior['backup_sha256'];print('EXISTING_PERSISTENCE_READBACK_OK',len(prior['records']));raise SystemExit(0)
paths=list((B/'decisions').glob('*.json'))+[B/n for n in ['blinded_process_reviews.json','packet_coverage_audit.json','selected_allocation_seal.json','followup_preregistered.json','followup_result.json','factory_handoff.json','forward_check.json','forward_watch.json','enriched_packets/coverage_result.json','evaluation/2024-11-29.json','evaluation/2025-06-30.json','evaluation_v3/2024-11-29.json','evaluation_v3/2025-06-30.json','evaluation_endpoint/portfolios.json','selected_allocation/portfolios.json']]
for p in paths:
 payload={'schema':'TASK91_RESEARCH_ARTIFACT_V1','path':str(p.relative_to(R)),'sha256':sha(p),'payload':json.loads(p.read_text()),'not_forward_evidence':True,'operating_orders':False};identity=store.put('task91_research_artifact',canonical_zero(payload));assert store.get(identity)==canonical_zero(payload);ids.append(identity)
queue=Queue(store);followup=queue.enqueue('TASK91_GROUNDED_PACKET_RESEARCH',{'artifacts':ids,'candidate':'SOURCE_COVERAGE_FIRST_V2','evidence':sha(B/'packet_coverage_audit.json'),'source_spans':sha(B/'enriched_packets/coverage_result.json'),'expected_effect':'Restore omitted capital and cash-flow evidence before further investment analysis. Span coverage improvement is not forecast/alpha success.','next_LLM_calls':'NOT_RESERVED_NEEDS_NORMAL_BUDGET_AND_FRESH_CASES','capital_authority':'NONE'})
watch=queue.enqueue('TASK91_FRESH_FORWARD_RESEARCH',{'monitor_hash':sha(B/'forward_watch.json'),'status':'PENDING_FRESH_ASOF_COMPANY_RESEARCH','no_order_authority':True})
backup=subprocess.run(['docker','exec','quant-task3-postgres','pg_dump','-U','quant_task3','-Fc','quant_task3_task9_history'],capture_output=True,check=True).stdout;(B/'research_state.dump').write_bytes(backup)
freeze(B/'persistence.json',{'records':ids,'readback_verified':len(ids),'new_packet_research_job':followup,'forward_research_job':watch,'backup_sha256':sha(B/'research_state.dump'),'source_paper_live_DB_writes':False,'existing_research_DB_append_only':True})
W=Path('/home/ansy/app/quant-diligence/task9-1-work')
for name in ['value2_2024','market2_2024','value2_2025','market2_2025','allocation_selected']:
 for suffix in ['.json','.raw.txt','.request.json']:
  p=W/(name+suffix)
  if p.exists():
   target=B/'model_outputs'/p.name;target.parent.mkdir(exist_ok=True)
   if target.exists():assert sha(p)==sha(target)
   else:shutil.copyfile(p,target)
print('PERSISTED_READBACK',len(ids),'FOLLOWUPS',followup,watch)
