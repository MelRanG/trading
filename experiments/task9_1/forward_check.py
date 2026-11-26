from common import *
import psycopg,subprocess
with psycopg.connect('postgresql://quant_task8b_research@127.0.0.1:55432/quant_task3_task8b_research',options='-c default_transaction_read_only=on') as c:
 plans=c.execute("SELECT r.payload FROM investment_record r LEFT JOIN investment_run s ON s.run_id=r.record_id WHERE kind='exploration_plan' AND COALESCE(s.status,'ACTIVE')<>'SUPERSEDED_UNFILLED'").fetchall()
 planinfo=[{'worker_hash_unchanged':p[0]['worker_hash']==sha(R/'src/quant_harness/investment/exploration.py'),'payload_hash':digest(p[0])} for p in plans]
accounts=[]
for market in ['us','kr']:
 with psycopg.connect('postgresql://quant_task8b_explore_'+market+'@127.0.0.1:55432/quant_task3_task8b_explore_'+market,options='-c default_transaction_read_only=on') as c:
  initial,cash=c.execute('SELECT initial,cash FROM stock_account').fetchone();n=c.execute('SELECT count(*) FROM stock_fill').fetchone()[0];accounts.append({'market':market,'initial':str(initial),'cash':str(cash),'fills':n})
timer=subprocess.run(['systemctl','--user','is-active','quant-operations.timer'],capture_output=True,text=True)
freeze(B/'forward_check.json',{'checked_at':now(),'existing_plans':planinfo,'accounts':accounts,'timer':timer.stdout.strip(),'operating_db_writes':False,'actual_reboot':'NOT_PERFORMED'})
selected=json.loads((B/'decisions/2025-06-30_market.json').read_text())['decision']['portfolios'];watch={'version':'TASK91_MONITOR_ONLY_V1','sealed_at':now(),'subjects':[{ 'market':x['market'],'symbols':x['ranked_top3']} for x in selected],'status':'PENDING_FRESH_ASOF_COMPANY_RESEARCH','investment_signal':'NONE_HISTORICAL_THESIS_IS_STALE','entry':'DISABLED until new as-of financial/price eligibility and independently sealed investment thesis','future_evaluation_months':[1,3,6],'triggers':['new financial release','guidance change','debt/dilution disclosure','valuation bridge supplied','unexpected trading cost'],'execution_authority':'NONE','automatic_promotion':False};freeze(B/'forward_watch.json',watch);print('READ_ONLY_FORWARD',len(plans),accounts,timer.stdout.strip())
