"""Restart probe: new process, immutable record hashes and untouched Shadow fills."""
from pathlib import Path
import json,sys,psycopg
from datetime import datetime,timezone
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'))
from quant_harness.investment.store import Store
from quant_harness.investment.stockpaper import reconcile,algorithm_fingerprint
from quant_harness.investment.company_outcomes import run_tick
from quant_harness.investment.shadow_portfolio import observe_shadow_accounts,execute_shadow
b=R/'runtime/task8';cfg=json.loads((R/'config/task8_portfolio.json').read_text());store=Store('postgresql://quant_task8_research@127.0.0.1:55432/'+cfg['research_database'],'TASK8_RESEARCH_ONLY');count=store.export(b/'research_records.jsonl');rows=[json.loads(l) for l in (b/'research_records.jsonl').read_text().splitlines()]
assert all(store.get(r['record_id'])==r['payload'] for r in rows)
accounts={}
for market,database in cfg['market_accounts'].items():
 url='postgresql://quant_task8_shadow_'+market.lower()+'@127.0.0.1:55432/'+database
 with psycopg.connect(url) as conn:
  assert reconcile(conn)
  cash,currency=conn.execute('SELECT cash,currency FROM stock_account').fetchone();fills=conn.execute('SELECT count(*) FROM stock_fill').fetchone()[0];positions=conn.execute('SELECT count(*) FROM stock_position WHERE quantity>0').fetchone()[0]
 account=Store(url,'TASK8_SHADOW_'+market);link=store.get('task8-initial-shadow-'+market)
 recovered=execute_shadow(account,R,link['decision_id'],[])
 assert recovered.get('idempotent')
 assert fills==positions==0;accounts[market]={'cash':str(cash),'currency':currency,'fills':fills,'positions':positions,'reconciled':True}
observations=observe_shadow_accounts(R);tick=run_tick(R);assert tick['status']=='NOT_DUE' and tick['requests']==0
# Compare active stock execution fingerprint to a preexisting operational seal, read-only.
with psycopg.connect('postgresql://quant_paper_us@127.0.0.1:55432/quant_task3_us',options='-c default_transaction_read_only=on') as conn:
 old=conn.execute("SELECT payload->>'algorithm_hash' FROM investment_record WHERE kind='stock_decision' AND created_at<%s ORDER BY created_at DESC LIMIT 1",(datetime.fromtimestamp((b/'evidence/start.diff').stat().st_mtime,timezone.utc),)).fetchone()
result={'status':'NEW_PROCESS_RECOVERY_PASS','records_hash_checked':count,'accounts':accounts,'observer_repeat':tick,'shadow_observation_repeat':observations,'operating_stock_fingerprint_matches_existing_seal':bool(old and old[0]==algorithm_fingerprint()),'actual_reboot':'NOT_PERFORMED','new_broker_calls':0};(b/'restart_probe.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
