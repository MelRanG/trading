from pathlib import Path
import sys,json,hashlib,psycopg
from datetime import datetime,timezone
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'))
from quant_harness.investment.exploration import research_store,account_store,run_tick,official_sessions
from quant_harness.investment.stockpaper import reconcile,algorithm_fingerprint
from quant_harness.investment.research import digest
b=R/'runtime/task8b';store,cfg=research_store(R);count=store.export(b/'research_records.jsonl');records=[json.loads(l) for l in (b/'research_records.jsonl').read_text().splitlines()]
assert all(store.get(r['record_id'])==r['payload'] for r in records)
with psycopg.connect(store.url) as conn:plans=conn.execute("SELECT r.record_id,r.payload FROM investment_record r LEFT JOIN investment_run s ON s.run_id=r.record_id WHERE r.kind='exploration_plan' AND COALESCE(s.status,'ACTIVE')<>'SUPERSEDED_UNFILLED' ORDER BY r.created_at").fetchall()
assert len(plans)==2
accounts=[];clock=datetime.now(timezone.utc).isoformat()
from quant_harness.investment.discovery import instant
for identity,plan in plans:
 account=account_store(cfg,plan['market'])
 with psycopg.connect(account.url) as conn:
  assert reconcile(conn);fills=conn.execute('SELECT count(*) FROM stock_fill').fetchone()[0];cash,currency=conn.execute('SELECT cash,currency FROM stock_account').fetchone()
 assert fills==0 and plan['worker_hash']==hashlib.sha256((R/'src/quant_harness/investment/exploration.py').read_bytes()).hexdigest()
 future=[s for s in official_sessions(plan['market'],clock) if instant(s['opening'])>instant(clock)];next_session=future[0] if future else None
 accounts.append({'market':plan['market'],'plan_id':identity,'weights':plan['weights'],'cash':str(cash),'currency':currency,'fills':fills,'status':'WAIT_NEXT_REGULAR_PRICE','next_observed_official_session':next_session,'sealed_at':plan['sealed_at']})
 first=account.export(b/(plan['market'].lower()+'_paper_records.jsonl'))
result=run_tick(R);assert all(r['status']=='WAIT_NEXT_REGULAR_PRICE' for r in result['markets'])
# Operating algorithm and strict eligibility are unchanged; only official source allowlist was repaired.
with psycopg.connect('postgresql://quant_paper_us@127.0.0.1:55432/quant_task3_us',options='-c default_transaction_read_only=on') as conn:prior=conn.execute("SELECT payload->>'algorithm_hash' FROM investment_record WHERE kind='stock_decision' AND created_at<%s ORDER BY created_at DESC LIMIT1".replace('LIMIT1','LIMIT 1'),(datetime.fromtimestamp((b/'evidence/start.diff').stat().st_mtime,timezone.utc),)).fetchone()
old_cfg=json.loads((b/'source_repair/task8_portfolio.before.json').read_text());new_cfg=json.loads((R/'config/task8_portfolio.json').read_text());strict_same={k:v for k,v in old_cfg.items() if k!='outcome_observation'}=={k:v for k,v in new_cfg.items() if k!='outcome_observation'}
report={'status':'RECOVERED_NEW_PROCESS','records_hash_checked':count,'accounts':accounts,'current_tick':result,'operating_stock_algorithm_matches_prior':bool(prior and prior[0]==algorithm_fingerprint()),'strict_paper_eligibility_unchanged':strict_same,'real_forward_fills':0,'real_mature_checkpoints':0,'real_broker_orders':0,'actual_reboot':'NOT_PERFORMED'};(b/'restart_probe.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
