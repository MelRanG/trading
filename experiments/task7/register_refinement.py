"""Append a corrected process-review finding; never rewrite the sealed review."""
from pathlib import Path
import json,hashlib,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src'))
from quant_harness.investment.store import Store
from quant_harness.investment.review_jobs import Queue
R=Path(__file__).resolve().parents[2];B=R/'runtime/task7';path=B/'comparison/information_audit_refinement.json';refinement=json.loads(path.read_text());fingerprint=hashlib.sha256(path.read_bytes()).hexdigest()
store=Store('postgresql://quant_task7_research@127.0.0.1:55432/quant_task3_task7_research','TASK7_COMPANY_RESEARCH_ONLY');queue=Queue(store)
review=json.loads((B/'review/result.json').read_text());prior=review['records'][0]['job_id'];job=queue.observe(prior,fingerprint);claimed=queue.claim('task7-refinement',identity=job)
result={'kind':'PROCESS_MEASUREMENT_CORRECTION','prior_review_job':prior,'evidence_hash':fingerprint,'refinement':refinement,'future_accuracy':'PENDING','strategy_decision':'NO_CHANGE','research_request':'Use full-report coverage, not just facts-array set difference, on subsequent independent issuers','outcome_seen':False}
identity=store.put('COMPANY_REVIEW_REFINEMENT',result)
if claimed:queue.finish(job,'task7-refinement',identity,'NO_CHANGE')
assert store.get(identity)==result
store.export(B/'review/records.jsonl')
(B/'review/refinement_connection.json').write_text(json.dumps({'record_id':identity,'followup_job':job,'status':'NO_CHANGE','reopened_hash_verified':True,'original_reviews_preserved':True,'model_calls':0},indent=2));print((B/'review/refinement_connection.json').read_text())
