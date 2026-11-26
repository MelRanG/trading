from pathlib import Path
import sys,json,hashlib,subprocess
import psycopg
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'))
from quant_harness.investment.research import digest
B=R/'runtime/task9_historical'
with psycopg.connect('postgresql://quant_task9_history@127.0.0.1:55432/quant_task3_task9_history',options='-c default_transaction_read_only=on') as conn:
 rows=conn.execute('SELECT payload,payload_hash FROM investment_record').fetchall();assert all(digest(p)==h for p,h in rows)
 jobs=conn.execute('SELECT status,count(*) FROM review_job GROUP BY status').fetchall()
with psycopg.connect('postgresql://quant_task8b_research@127.0.0.1:55432/quant_task3_task8b_research',options='-c default_transaction_read_only=on') as conn:
 plans=conn.execute("SELECT r.payload FROM investment_record r LEFT JOIN investment_run s ON s.run_id=r.record_id WHERE kind='exploration_plan' AND COALESCE(s.status,'ACTIVE')<>'SUPERSEDED_UNFILLED'").fetchall()
 assert len(plans)==2
 for row in plans:assert row[0]['worker_hash']==hashlib.sha256((R/'src/quant_harness/investment/exploration.py').read_bytes()).hexdigest()
accounts=[]
for market in ('us','kr'):
 with psycopg.connect('postgresql://quant_task8b_explore_'+market+'@127.0.0.1:55432/quant_task3_task8b_explore_'+market,options='-c default_transaction_read_only=on') as conn:
  initial,cash=conn.execute('SELECT initial,cash FROM stock_account').fetchone();n=conn.execute('SELECT count(*) FROM stock_fill').fetchone()[0];accounts.append({'market':market,'cash':str(cash),'fills':n});assert cash==initial and n==0
result={'new_process':'PASS','task9_payloads_hash_verified':len(rows),'task9_queue_states':dict(jobs),'task8b_plans_still_frozen':True,'task8b_accounts':accounts,'original_timer':subprocess.check_output(['systemctl','--user','is-active','quant-operations.timer'],text=True).strip(),'actual_server_reboot':'NOT_PERFORMED','operating_db_writes':False};(B/'restart_probe.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
