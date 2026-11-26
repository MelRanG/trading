"""Reopen the actual recovered authority and retry completed work idempotently."""
from pathlib import Path
import json,hashlib,sys,psycopg
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'))
from quant_harness.investment.research_dispatcher import factory_work
from quant_harness.investment.research import digest
from quant_harness.alpha_research_factory import _hash
B=R/'runtime/task10_1';live=R/'runtime/alpha_research_factory/task4'
def snapshot():return {str(p.relative_to(live)):hashlib.sha256(p.read_bytes()).hexdigest() for p in live.rglob('*') if p.is_file() and p.name!='.registry.lock'}
reg=json.loads((R/'runtime/task9_2/dispatch_registry.json').read_text());assert reg['registry_hash']==digest({k:v for k,v in reg.items() if k!='registry_hash'})
with psycopg.connect('postgresql://quant_task3@127.0.0.1:55432/quant_task3_task8b_research',options='-c default_transaction_read_only=on') as c:
 def get(k):
  p,h=c.execute('SELECT payload,payload_hash FROM investment_record WHERE record_id=%s',(k,)).fetchone();assert digest(p)==h;return p
 proposal,bundle=get(reg['proposal_id']),get(reg['bundle_id'])
before=snapshot();result=factory_work(R,proposal,bundle);after=snapshot();assert before==after;assert result['cached_result'] and not result['experiment_executed']
(B/'live_reopen_check.json').write_text(json.dumps({'status':'PASS_EXISTING_REGISTRATION_RESERVATION_RESULT_REOPEN','before_hashes':before,'after_hashes':after,'result':result,'fresh_experiments':0,'budget_reset':False},indent=2))
print(result['status'], 'CACHED_NO_EXTRA_BUDGET')
