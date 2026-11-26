from pathlib import Path
import json,sys,hashlib,subprocess
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'))
from quant_harness.investment.store import Store
from quant_harness.investment.review_jobs import Queue
from quant_harness.investment.research import digest
B=R/'runtime/task9_historical';store=Store('postgresql://quant_task9_history@127.0.0.1:55432/quant_task3_task9_history','TASK9_HISTORICAL_ONLY');queue=Queue(store);handoff=json.loads((B/'review_handoff.json').read_text());job=handoff['research_jobs'][2]
score=json.loads((B/'evaluation/forecast_scores.json').read_text());extra=json.loads((B/'evaluation/additional_forecast_scores.json').read_text());review={'kind':'HISTORICAL_OUTCOME_REVIEW_NOT_BLIND_PROCESS_REVIEW','forecast_scores_hash':digest(score),'additional_scores_hash':digest(extra),'outcome_pairs':len(score['results'])+len(extra['results']),'companies':3,'taxonomy':[{'cause':'DATA_OR_TIMING','status':'CONFIRMED_DATA_LIMITATION','evidence':'PIT/action/session gates blocked trading'}, {'cause':'FORECAST_ERROR','status':'OBSERVED_POINT_ERROR_NOT_ENGINE_CAUSAL_ATTRIBUTION','evidence':'Image2022 operating-profit error35.54% versus naive18.06%; TSI2025 point error51.61%'}, {'cause':'SELECTION_VALUATION_TIMING_PORTFOLIO_COST','status':'UNDETERMINED','evidence':'No eligible portfolio replay; no price-return winner attribution'}],'next_action':'Archive source versions and collect presealed Forward financial forecasts against naive and dated consensus; do not retune these historical cases','promotion':False};rid=store.put('historical_outcome_review',review)
row=queue.claim('TASK9_OUTCOME_REVIEW',identity=job)
if row:queue.finish(job,'TASK9_OUTCOME_REVIEW',rid,status='PENDING_EVIDENCE')
follow=queue.enqueue('TASK9_FORWARD_FORECAST_VALIDATION_REQUEST',{'previous_job':job,'review_result':rid,'requires':'New source-qualified multi-company observations, frozen budgets, dated guidance/consensus; no automatic strategy or portfolio changes'})
store.export(B/'research_records_final.jsonl');result={'review_result':rid,'reviewed_job':job,'status':'PENDING_EVIDENCE','next_job':follow,'factory_experiment':'NOT_EXECUTED','operating_writes':False};(B/'review_cycle.json').write_text(json.dumps(result,indent=2))
# Preserve the already-submitted blocked proposal's exact worker version.
expected=json.loads((B/'factory_proposal.json').read_text())['worker_hash'];raw=(Path(__file__).parent/'replay_contract.py').read_bytes();folder=B/'code_versions';folder.mkdir(exist_ok=True)
if hashlib.sha256(raw).hexdigest()==expected:(folder/(expected+'.py')).write_bytes(raw)
else:
 marker=raw.index(b'def run_existing_replay')
 for cut in range(marker-8,marker+1):
  if hashlib.sha256(raw[:cut]).hexdigest()==expected:(folder/(expected+'.py')).write_bytes(raw[:cut]);break
 else:raise ValueError('original proposal worker bytes could not be reconstructed exactly')
backup=subprocess.run(['docker','exec','quant-task3-postgres','pg_dump','-U','quant_task3','-Fc','quant_task3_task9_history'],check=True,capture_output=True).stdout;(B/'research_database.dump').write_bytes(backup);result['backup_sha256']=hashlib.sha256(backup).hexdigest();(B/'review_cycle.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
