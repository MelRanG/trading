"""Read-only check of existing Forward plans and accounts; no Task9 V1 reader."""
from pathlib import Path
import hashlib,json,subprocess
import psycopg
R=Path(__file__).resolve().parents[2]
with psycopg.connect('postgresql://quant_task8b_research@127.0.0.1:55432/quant_task3_task8b_research',options='-c default_transaction_read_only=on') as c:
 plans=c.execute("SELECT r.payload FROM investment_record r LEFT JOIN investment_run s ON s.run_id=r.record_id WHERE kind='exploration_plan' AND COALESCE(s.status,'ACTIVE')<>'SUPERSEDED_UNFILLED'").fetchall()
 assert len(plans)==2
 assert all(p[0]['worker_hash']==hashlib.sha256((R/'src/quant_harness/investment/exploration.py').read_bytes()).hexdigest() for p in plans)
accounts=[]
for market in ('us','kr'):
 with psycopg.connect('postgresql://quant_task8b_explore_'+market+'@127.0.0.1:55432/quant_task3_task8b_explore_'+market,options='-c default_transaction_read_only=on') as c:
  initial,cash=c.execute('SELECT initial,cash FROM stock_account').fetchone();n=c.execute('SELECT count(*) FROM stock_fill').fetchone()[0]
  assert cash==initial and n==0
  accounts.append({'market':market,'cash':str(cash),'fills':n})
x={'frozen_plans':len(plans),'worker_hash_unchanged':True,'accounts':accounts,'timer':subprocess.check_output(['systemctl','--user','is-active','quant-operations.timer'],text=True).strip(),'operating_db_writes':False,'actual_reboot':'NOT_PERFORMED'}
(R/'runtime/task9_completion/preservation.json').write_text(json.dumps(x,indent=2));print(json.dumps(x,indent=2))
