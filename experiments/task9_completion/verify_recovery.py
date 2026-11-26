from pathlib import Path
import json,sys,hashlib,subprocess
from datetime import datetime,timezone
import psycopg
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'))
from quant_harness.investment.store import Store
from quant_harness.investment.research import digest
from quant_harness.investment.review_jobs import Queue
B=R/'runtime/task9_completion';store=Store('postgresql://quant_task9_history@127.0.0.1:55432/quant_task3_task9_history','TASK9_HISTORICAL_ONLY');recovery=json.loads((B/'ledger_recovery.json').read_text());exports=[json.loads(s) for s in (B/'research_records_recovered.jsonl').read_text().splitlines()];assert all(digest(r['payload'])==r['payload_hash'] for r in exports)
for r in recovery['canonical_results']:assert store.get(r['canonical_record_id'])['economic_values_changed'] is False
with psycopg.connect(store.url,options='-c default_transaction_read_only=on') as conn:
 fills=conn.execute("SELECT record_id,payload FROM investment_record WHERE kind='completion_historical_fill'").fetchall();assert len(fills)==4 and len({p['client_order_id'] for i,p in fills})==4
 results=conn.execute("SELECT count(*) FROM investment_record WHERE kind='completion_historical_result_canonical'").fetchone()[0];assert results==8
backup=subprocess.run(['docker','exec','quant-task3-postgres','pg_dump','-U','quant_task3','-Fc','quant_task3_task9_history'],capture_output=True,check=True).stdout;(B/'historical_research.dump').write_bytes(backup)
restored='quant_task3_completion_restore_'+datetime.now(timezone.utc).strftime('%H%M%S');subprocess.run(['docker','exec','quant-task3-postgres','createdb','-U','quant_task3',restored],capture_output=True,check=True);subprocess.run(['docker','exec','-i','quant-task3-postgres','pg_restore','-U','quant_task3','-d',restored,'--exit-on-error'],input=backup,capture_output=True,check=True)
with psycopg.connect('postgresql://quant_task3@127.0.0.1:55432/'+restored,options='-c default_transaction_read_only=on') as conn:
 assert conn.execute("SELECT count(*) FROM investment_record WHERE kind='completion_historical_fill'").fetchone()[0]==4
 for r in recovery['canonical_results']:
  payload,h=conn.execute('SELECT payload,payload_hash FROM investment_record WHERE record_id=%s',(r['canonical_record_id'],)).fetchone();assert digest(payload)==h
receipt={'status':'FRESH_PROCESS_AND_NEW_DB_RESTORE_PASS','canonical_results':results,'unique_control_fills':4,'AI_fills':0,'export_original_payload_hashes_verified':len(exports),'negative_zero_V1_requires_artifact_rehydration':len(recovery['reconstructed_original_signed_zero_records']),'restored_database':restored,'database_dump_sha256':hashlib.sha256(backup).hexdigest(),'existing_timer':subprocess.check_output(['systemctl','--user','is-active','quant-operations.timer'],text=True).strip(),'actual_reboot':'NOT_PERFORMED','operating_changes':False};(B/'recovery_verification.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt,indent=2))
queue=Queue(store);job=queue.enqueue('HISTORICAL_COMPLETION_FOLLOWUP',{'source_hash':digest(receipt),'canonical_result_ids':[x['canonical_record_id'] for x in recovery['canonical_results']],'diagnosis':'A/B/C cash only; avoid interpreting market-decline avoidance or diagnostic-control selection residual as proven alpha','next':'Expand only source-qualified cap-filtered candidate cohort, independent Forward forecasts, separate signed-zero Store compatibility bugfix; no promotion','needs_new_budget':True});(B/'followup.json').write_text(json.dumps({'job_id':job,'official_factory':'Existing normal daily budget/priority remains; no new reservation or experiment','auto_promotion':False},indent=2))
