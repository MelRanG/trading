from common import *
import subprocess
from quant_harness.investment.store import Store
from quant_harness.investment.review_jobs import Queue
sys.path.insert(0,str(R/'experiments/task9_completion'));from serialization_fix import canonical_zero
s=Store('postgresql://quant_task9_history@127.0.0.1:55432/quant_task3_task9_history','TASK9_HISTORICAL_ONLY');q=Queue(s)
if (B/'persistence_supplement.json').exists():
 old=json.loads((B/'persistence_supplement.json').read_text());assert s.get(old['record_id']);assert sha(B/'research_state_final.dump')==old['backup_sha256'];print('SUPPLEMENT_READBACK_OK');raise SystemExit()
a=json.loads((B/'valuation_arithmetic_audit.json').read_text());r=s.put('task93_valuation_arithmetic_review',canonical_zero({'audit':a,'historical_not_forward':True,'no_policy_replacement':True}));job=q.enqueue('TASK93_VALUATION_CONTRACT_REPAIR',{'evidence_record':r,'worker':'Vibe structuredvaluation adapter + Task92timed nativeDCF code','required':'explicit futurecashflowenddates/stub/debt/shares/FCFFvsFCFE convention and deterministic price reconstruction before new decision','minimum_independent_cases':12,'future_efficacy':'NEW_PREREGISTERED_CASES_OR_FORWARD','capital_authority':'NONE','budget':'NOT_RESERVED','dispatcher':'UNSUPPORTED_MANUAL_RESEARCH_WORKER_REQUIRED'});raw=subprocess.run(['docker','exec','quant-task3-postgres','pg_dump','-U','quant_task3','-Fc','quant_task3_task9_history'],capture_output=True,check=True).stdout;(B/'research_state_final.dump').write_bytes(raw);freeze(B/'persistence_supplement.json',{'record_id':r,'followup_job':job,'status':'REGISTERED_RESEARCH_QUEUE_ONLY_NOT_AUTO_EXECUTED','backup_sha256':sha(B/'research_state_final.dump'),'prior_backup_preserved':True});assert s.get(r);print('VALUATION_REVIEW_QUEUED',job)
