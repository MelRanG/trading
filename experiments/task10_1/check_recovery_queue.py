"""Isolated contract/queue fault probes; never economic research evidence."""
from pathlib import Path
import sys,json,shutil
import psycopg
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'))
from quant_harness.investment.store import Store
from quant_harness.investment.review_jobs import Queue
from quant_harness.alpha_research_factory import register_review_proposal,reserve_review_experiment
B=R/'runtime/task10_1';out=B/'contract_probe';shutil.copytree(B/'restore_probe',out,dirs_exist_ok=True)
a=json.loads((out/'attempt_registry.jsonl').read_text().splitlines()[-1]);p=json.loads((out/'contracts'/(a['proposal_id']+'.json')).read_text())['proposal'];p={**p,'challenger':'TASK101_ISOLATED_BUDGET_TEST_ONLY','input_hash':'f'*64}
registered=register_review_proposal(R,p,directory=out)
assert register_review_proposal(R,p,directory=out)==registered
try:reserve_review_experiment(R,registered,directory=out)
except ValueError as exc:assert 'budget exhausted' in str(exc)
else:raise AssertionError('must preserve current UTC-day reservation limit')
s=Store('postgresql://quant_task3@127.0.0.1:55432/quant_task3_task10_replay','TASK10_RESEARCH_REPLAY_ONLY');q=Queue(s)
j=q.enqueue('TASK101_ISOLATED_QUEUE_PROBE',{'probe':'lease-reopen-v1','classification':'FAULT_INJECTION_NOT_FORWARD'})
assert q.enqueue('TASK101_ISOLATED_QUEUE_PROBE',{'probe':'lease-reopen-v1','classification':'FAULT_INJECTION_NOT_FORWARD'})==j
claim=q.claim('old-owner',120,j);assert claim
with psycopg.connect(s.url) as c:c.execute("UPDATE review_job SET lease_until=now()-interval '1 second' WHERE job_id=%s",(j,))
q2=Queue(s);assert q2.claim('restarted-owner',120,j)
try:q.finish(j,'old-owner','invalid')
except ValueError:pass
else:raise AssertionError('lost owner must not commit')
r=s.put('task101_isolated_queue_test',{'scope':'FAULT_INJECTION_ONLY','reopened_owner':True,'dedup':True,'live':False});q2.finish(j,'restarted-owner',r)
assert not Queue(s).claim('third-owner',120,j)
(B/'queue_budget_probe.json').write_text(json.dumps({'queue':'PASS_LEASE_EXPIRE_RECLAIM_OWNER_DEDUP_PERSISTENT_REOPEN','registration':'PASS_ISOLATED_DUPLICATE','budget':'PASS_EXISTING_DAY_RESERVATION_BLOCK_PRESERVED','economic_or_forward_evidence':False,'actual_OS_reboot':False,'job_id':j},indent=2));print('PASS_ISOLATED_CONTRACT_QUEUE')
