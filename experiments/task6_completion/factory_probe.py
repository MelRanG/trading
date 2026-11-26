"""Official Factory + existing PostgreSQL queue in an isolated test database.
Clock injection is scoped to this disposable Factory path, never production.
"""
from pathlib import Path
from datetime import datetime,timezone,timedelta
from unittest.mock import patch
import sys,json,hashlib,subprocess,copy
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(Path(__file__).parent))
import quant_harness.alpha_research_factory as f
from quant_harness.investment.store import Store
from quant_harness.investment.review_jobs import Queue
from aligned import evaluate
import importlib.util,pandas as pd
BASE=ROOT/'runtime/task6_completion';folder=BASE/'factory_test';folder.mkdir(exist_ok=True)
def rows(p):return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []
oper=ROOT/'runtime/alpha_research_factory/task4';today=datetime.now(timezone.utc).date().isoformat()
state={'observed_utc':datetime.now(timezone.utc).isoformat(),'proposal_used_today':sum(x['timestamp_utc'][:10]==today for x in rows(oper/'attempt_registry.jsonl')),'reservations_today':sum(x['timestamp_utc'][:10]==today for x in rows(oper/'experiment_reservations.jsonl')),'policy':json.loads((ROOT/'config/task4_review_contract.json').read_text()),'priority':['existing Task5 pending common experiment','previous Task6 proposal','completion followups'],'operational_mutations':False,'operational_status':'WAIT_NORMAL_BUDGET_RESET'}
(BASE/'evidence/operational_factory_status.json').write_text(json.dumps(state,indent=2))
name='quant_task3_completion_test';exists=subprocess.check_output(['docker','exec','quant-task3-postgres','psql','-U','quant_task3','-d','postgres','-Atc',"SELECT datname FROM pg_database WHERE datname='"+name+"'"],text=True).strip()
if not exists:subprocess.run(['docker','exec','quant-task3-postgres','createdb','-U','quant_task3',name],check=True)
store=Store('postgresql://quant_task3@127.0.0.1:55432/'+name,'TASK6_COMPLETION_TEST_ONLY');q=Queue(store)
node=BASE/'evaluation/validation/US/quanta0/factor_values.csv';assert node.exists()
hashdata=hashlib.sha256(node.read_bytes()).hexdigest();worker_hash=hashlib.sha256((Path(__file__).parent/'aligned.py').read_bytes()).hexdigest()
proposal={'problem_evidence':{'source':'actual original evolution node0 and aligned evaluation contract'},'target':'strategy','expected_effect':'Functional validation of native generated factor and continuation; no alpha claim','falsification':'Causality, execution horizon or accounting mismatch','champion':'TASK6_COMPLETION_BASELINE','challenger':'QUANTA_EVOLUTION_NODE0','input_hash':hashdata,'budget':{'experiments':1,'parameter_search':0},'stop_conditions':['budget exhausted','missing source'],'evaluation_metric':['IC','net_return','cost','alignment'],'minimum_cases':12,'split':'PROCESS_DIAGNOSTIC_ONLY','worker_hash':worker_hash}
# Only fresh test directory is accepted; reruns read prior immutable report.
if (folder/'result.json').exists():print((folder/'result.json').read_text());raise SystemExit()
class Clock(datetime):
 day=13
 @classmethod
 def now(cls,tz=None):return datetime(2026,11,cls.day,12,tzinfo=timezone.utc)
with patch.object(f,'datetime',Clock):
 seed=copy.deepcopy(proposal);seed['champion']='ISOLATED_BUDGET_SEED';seed['challenger']='ISOLATED_SEED_ATTEMPT';a0=f.register_review_proposal(ROOT,seed,directory=folder);f.reserve_review_experiment(ROOT,a0,directory=folder)
 a=f.register_review_proposal(ROOT,proposal,directory=folder);job=q.enqueue('FACTORY_EVALUATION',{'attempt':a,'snapshot_hash':hashdata});assert q.enqueue('FACTORY_EVALUATION',{'attempt':a,'snapshot_hash':hashdata})==job
 try:f.reserve_review_experiment(ROOT,a,directory=folder);raise AssertionError('budget did not block')
 except ValueError as e:blocked=str(e)
 Clock.day=14
 reservation=f.reserve_review_experiment(ROOT,a,directory=folder);q.claim('worker-before-crash',lease_seconds=-1,identity=job)
 # New store/queue, expired lease; existing reservation is reused.
 q=Queue(Store(store.url,'TASK6_COMPLETION_TEST_ONLY'));claim=q.claim('worker-recovered',identity=job);assert claim is not None;assert f.reserve_review_experiment(ROOT,a,directory=folder)==reservation
 spec=importlib.util.spec_from_file_location('old',ROOT/'experiments/task6/evaluation.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);frames=module.load_frames('US','validation');v=pd.read_csv(node,parse_dates=['datetime']).set_index(['datetime','instrument']).iloc[:,0].unstack('instrument');metrics,nav,fills=evaluate(v,frames)
 nav.to_csv(folder/'evaluated_nav.csv',index=False);fills.to_csv(folder/'evaluated_fills.csv',index=False)
 result={'status':'INSUFFICIENT_EVIDENCE','cases':len(nav),'independent_forward_cases':0,'input_hash':hashdata,'worker_hash':worker_hash,'metrics':metrics,'evidence_class':'REPEATED_2025_FUNCTIONAL_DIAGNOSTIC','classification':['COST_PROBLEM','INSUFFICIENT_EVIDENCE'],'promotion_status':'NOT_ELIGIBLE'}
 recorded=f.record_review_experiment(ROOT,a,result,directory=folder);assert f.record_review_experiment(ROOT,a,result,directory=folder)==recorded
 rid=store.put('factory_research_result',recorded);q.finish(job,'worker-recovered',rid);follow=q.observe(job,hashlib.sha256(json.dumps(metrics,sort_keys=True).encode()).hexdigest());assert q.observe(job,hashlib.sha256(json.dumps(metrics,sort_keys=True).encode()).hexdigest())==follow
 payload={'status':'PASS_ISOLATED_SAME_FACTORY_CONTRACT_AND_POSTGRES_QUEUE','simulated_dates':['2026-11-13','2026-11-14'],'clock_simulation_only':True,'actual_wait_for_next_operating_day':False,'budget_block':blocked,'reservation_reused_after_crash':True,'registration_idempotent':f.register_review_proposal(ROOT,proposal,directory=folder)==a,'result_idempotent':True,'result_record':rid,'followup_job':follow,'database':name,'operational_factory_status':state,'metrics':metrics}
 (folder/'result.json').write_text(json.dumps(payload,indent=2,allow_nan=False));store.export(folder/'records.jsonl');print(json.dumps(payload,indent=2))
