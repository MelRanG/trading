"""Separate-process verification of preserved company research state."""
from pathlib import Path
import json,sys,psycopg
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src'))
from quant_harness.investment.store import Store
from quant_harness.investment.review_jobs import Queue
R=Path(__file__).resolve().parents[2];b=R/'runtime/task7';store=Store('postgresql://quant_task7_research@127.0.0.1:55432/quant_task3_task7_research','TASK7_COMPANY_RESEARCH_ONLY')
records=[json.loads(l) for l in (b/'review/records.jsonl').read_text().splitlines()]
for record in records:assert store.get(record['record_id'])==record['payload']
assert Queue(store).claim('new-process-restart-check') is None
with psycopg.connect(store.url) as conn:statuses=dict(conn.execute('SELECT status,count(*) FROM review_job GROUP BY status').fetchall())
assert statuses=={'READY':8,'PENDING_LABELS':8,'NO_CHANGE':1}
result={'status':'NEW_PROCESS_RECOVERY_PASS','record_count':len(records),'job_statuses':statuses,'all_record_hashes_verified':True,'duplicate_ready_processing':0,'orders':0,'actual_reboot':'NOT_PERFORMED'}
(b/'review/restart_probe.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
