from common import *
import psycopg,subprocess
rows=[]
for m in ['us','kr']:
 url='postgresql://quant_task8b_explore_'+m+'@127.0.0.1:55432/quant_task3_task8b_explore_'+m
 with psycopg.connect(url,options='-c default_transaction_read_only=on') as c:
  accounts=c.execute('SELECT initial,cash FROM stock_account').fetchall();fills=c.execute('SELECT count(*) FROM stock_fill').fetchone()[0];rows.append({'market':m,'accounts':[[str(v) for v in r] for r in accounts],'fills':fills})
active=subprocess.run(['systemctl','--user','is-active','quant-operations.timer'],capture_output=True,text=True)
freeze(B/('operating_state_'+sys.argv[1]+'.json'),{'research_did_not_place_orders':True,'existing_exploratory_accounts':rows,'existing_timer':active.stdout.strip(),'exploration_source_hash':sha(R/'src/quant_harness/investment/exploration.py'),'stockpaper_source_hash':sha(R/'src/quant_harness/investment/stockpaper.py'),'live_execution_enabled_by_task':False})
print('READ_ONLY_OPERATING_STATE',rows)
