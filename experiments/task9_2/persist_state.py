from common import *
import subprocess,psycopg,xml.etree.ElementTree as ET
from quant_harness.investment.exploration import research_store
sys.path.insert(0,str(R/'experiments/task9_completion'))
from serialization_fix import canonical_zero
store,_=research_store(R);ids=[]
if (B/'persistence.json').exists():
 old=json.loads((B/'persistence.json').read_text());assert all(store.get(i) for i in old['new_artifact_ids']);assert sha(B/'research_state.dump')==old['backup_sha256'];print('PERSISTED_RECORDS_RECHECKED',old['readback_verified']);raise SystemExit(0)
for name in ['historical_numeric_packet_v3.json','current_numeric_packet_v2.json','financial_reconciliations.json','entity_scope_audit.json','model_seals.json','valuation_annual_diagnostics.json','current_timed_valuations.json','current_expectations.json','limited_historical_audit/result.json','dispatch_migration.json']:
 p=B/name;payload={'schema':'TASK92_RESEARCH_EVIDENCE_V1','artifact':str(p.relative_to(R)),'sha256':sha(p),'data':json.loads(p.read_text()),'not_realized_forward_accuracy':True};identity=store.put('task92_research_artifact',canonical_zero(payload));assert store.get(identity)==canonical_zero(payload);ids.append(identity)
manifest=json.loads((B/'dispatch_registry.json').read_text());assert all(store.get(i) for i in manifest['decision_ids'])
with psycopg.connect(store.url,options='-c default_transaction_read_only=on') as c:
 counts=c.execute("SELECT kind,status,count(*) FROM review_job WHERE kind LIKE 'TASK92%' GROUP BY kind,status ORDER BY kind,status").fetchall()
plans=[]
with psycopg.connect(store.url,options='-c default_transaction_read_only=on') as c:
 old=c.execute("SELECT r.payload FROM investment_record r LEFT JOIN investment_run s ON s.run_id=r.record_id WHERE kind='exploration_plan' AND COALESCE(s.status,'ACTIVE')<>'SUPERSEDED_UNFILLED'").fetchall()
 for (p,) in old:plans.append({'market':p['market'],'original_worker_hash_unchanged':p['worker_hash']==sha(R/'src/quant_harness/investment/exploration.py')})
accounts=[]
for m in ['us','kr']:
 with psycopg.connect('postgresql://quant_task8b_explore_'+m+'@127.0.0.1:55432/quant_task3_task8b_explore_'+m,options='-c default_transaction_read_only=on') as c:
  initial,cash=c.execute('SELECT initial,cash FROM stock_account').fetchone();fills=c.execute('SELECT count(*) FROM stock_fill').fetchone()[0];accounts.append({'market':m,'initial':str(initial),'cash':str(cash),'fills':fills})
forecast_status=[]
for market in ['US','KR']:
 dec=json.loads((B/'forward_decisions'/(market+'.json')).read_text())
 for case in dec['companies']:
  for f in case['forecasts']:forecast_status.append({'symbol':case['symbol'],'forecast':f,'status':'PENDING_POST_SEAL_MATCHED_ACTUAL','scope':'Recorded original projection, not mature result'})
freeze(B/'forward_forecast_status.json',forecast_status)
backup=subprocess.run(['docker','exec','quant-task3-postgres','pg_dump','-U','quant_task3','-Fc','quant_task3_task8b_research'],capture_output=True,check=True).stdout;(B/'research_state.dump').write_bytes(backup)
freeze(B/'persistence.json',{'new_artifact_ids':ids,'readback_verified':len(ids),'current_decisions':manifest['decision_ids'],'active_dispatch_registry':manifest['registry_hash'],'queue_states':counts,'backup_sha256':sha(B/'research_state.dump'),'existing_plans':plans,'existing_accounts':accounts,'trading_ledger_writes_by_Task92':False,'actual_reboot':'NOT_PERFORMED'})
print('READBACK',len(ids),'QUEUES',counts,'OLD_PLAN_HASHES',plans,'ACCOUNTS',accounts)
