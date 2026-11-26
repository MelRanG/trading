"""Task7 source-only review adapter: dedicated DB, immutable forecasts, no orders."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,subprocess,sys,psycopg
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src'))
from quant_harness.investment.store import Store
from quant_harness.investment.review_jobs import Queue
from quant_harness.alpha_research_factory import register_review_proposal
from company_contract import score_forecast,scenarios_of
R=Path(__file__).resolve().parents[2];B=R/'runtime/task7';out=B/'review';out.mkdir(exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def sql(statement):
 return subprocess.run(['docker','exec','quant-task3-postgres','psql','-U','quant_task3','-d','postgres','-Atc',statement],check=True,text=True,capture_output=True).stdout.strip()
label=subprocess.run(['docker','inspect','-f','{{index .Config.Labels "quant-harness.scope"}}','quant-task3-postgres'],check=True,text=True,capture_output=True).stdout.strip()
assert label=='task3-isolated'
name='quant_task3_task7_research'
if not sql("SELECT datname FROM pg_database WHERE datname='"+name+"'"):
 subprocess.run(['docker','exec','quant-task3-postgres','createdb','-U','quant_task3',name],check=True)
# New research-only role; no privileges added to existing operational databases.
if not sql("SELECT rolname FROM pg_roles WHERE rolname='quant_task7_research'"):
 sql('CREATE ROLE quant_task7_research LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE')
subprocess.run(['docker','exec','quant-task3-postgres','psql','-U','quant_task3','-d',name,'-v','ON_ERROR_STOP=1','-c','GRANT CONNECT ON DATABASE quant_task3_task7_research TO quant_task7_research; GRANT USAGE,CREATE ON SCHEMA public TO quant_task7_research'],check=True,capture_output=True)
url='postgresql://quant_task7_research@127.0.0.1:55432/'+name
store=Store(url,'TASK7_COMPANY_RESEARCH_ONLY');queue=Queue(store)
eval=json.loads((B/'comparison/evaluation.json').read_text());packet_hash=sha(B/'company/packet.json');records=[]
for arm,cases in eval['arms'].items():
 for symbol,audit in cases.items():
  path=B/'comparison'/arm/symbol/'analysis.json';analysis=json.loads(path.read_text())
  # Seal the persisted research now, without backdating model/source observation.
  identity='task7-company-'+arm+'-'+symbol
  with psycopg.connect(url) as conn:exists=conn.execute('SELECT record_id FROM investment_record WHERE record_id=%s',(identity,)).fetchone()
  if exists:forecast=store.get(identity)
  else:
   scenarios=scenarios_of(analysis);forecast={'ticker':symbol,'arm':arm,'metric':'quarterly_revenue','unit':'USD_million','period_end':analysis['forecast_target']['period_end'],'period_label':analysis['forecast_target']['period_label'],'base_value':scenarios['base']['revenue_million'],'bear_value':scenarios['bear']['revenue_million'],'bull_value':scenarios['bull']['revenue_million'],'probabilities':{k:v['probability'] for k,v in scenarios.items()},'assumptions':{k:v['assumptions'] for k,v in scenarios.items()},'sealed_at':datetime.now(timezone.utc).isoformat(),'earliest_review_date':analysis['forecast_target']['earliest_review_date'],'review_date_authority':'Research schedule only; not a verified earnings-release calendar','input_hash':packet_hash,'analysis_hash':sha(path),'code_hash':sha(Path(__file__)),'model':'gpt-6.1-terra','analysis':analysis,'future_accuracy':'PENDING','order_authority':False}
   store.put('COMPANY_FORECAST',forecast,identity)
  job=queue.enqueue('COMPANY_PROCESS_REVIEW',{'forecast_id':identity,'input_hash':packet_hash,'analysis_hash':sha(path)})
  claimed=queue.claim('task7-source-evaluator',identity=job)
  if claimed:
   review={'forecast_id':identity,'process_audit':audit['forecast_process'],'source_audit':audit,'outcome':score_forecast(forecast),'taxonomy':['UNDETERMINED'],'profit_loss_seen':False,'decision':'NO_STRATEGY_CHANGE','needs':['Verified actual issuer release for target period','Broader independent companies before efficacy judgment']}
   review_id=store.put('SEALED_COMPANY_PROCESS_REVIEW',review)
   next_at=forecast['earliest_review_date']+'T00:00:00+00:00'
   queue.finish(job,'task7-source-evaluator',review_id,'PENDING_LABELS',next_at)
  # Follow-up evidence task is deduplicated and scheduled, not an immediate loop.
  follow=queue.enqueue('COMPANY_RELEASE_OBSERVATION',{'forecast_id':identity,'required_metric':'quarterly_revenue','required_period_end':forecast['period_end'],'source_policy':'issuer official release; preserve original first observation; no date-only maturity'},forecast['earliest_review_date']+'T00:00:00+00:00')
  records.append({'forecast_id':identity,'job_id':job,'followup_job':follow,'outcome':score_forecast(forecast)})
# Existing official Factory only: no alternate directory to evade daily budget.
proposal={'problem_evidence':[packet_hash,sha(B/'comparison/evaluation.json')],'target':'prompt','expected_effect':'Test independent bull/bear source omission detection across at least12 independent issuers; two pilot cases are insufficient','falsification':'No incremental verified material facts, more factual errors, or excessive cost','champion':'TASK7_VIBE_EARNINGS_COMPONENT','challenger':'TASK7_TRADINGAGENTS_BULL_BEAR','input_hash':packet_hash,'budget':{'experiments':1,'parameter_search':0},'stop_conditions':['Any source/time mismatch','Budget exhausted','Fewer than12 independent issuers: no efficacy conclusion'],'evaluation_metric':'verified material incremental facts, factual errors, calibrated forward forecast error and token usage','minimum_cases':12,'split':'PROCESS_DIAGNOSTIC_ONLY','worker_hash':sha(R/'experiments/task7/evaluate_company.py')}
(out/'factory_proposal.json').write_text(json.dumps(proposal,indent=2))
# Keep earlier tasks ahead of this candidate. Registration does not reserve execution.
try:factory={'status':'REGISTERED_NOT_EXECUTED','attempt':register_review_proposal(R,proposal),'execution':'PENDING_PRIOR_QUEUE_AND_12_CASES'}
except ValueError as e:factory={'status':'BLOCKED_REGISTRATION','reason':str(e),'execution':'NOT_RUN','retry_policy':'Use unchanged proposal after normal UTC budget renewal; preserve earlier queue priority'}
(out/'factory_status.json').write_text(json.dumps(factory,indent=2))
count=store.export(out/'records.jsonl')
reopened=Store(url,'TASK7_COMPANY_RESEARCH_ONLY');assert all(reopened.get(x['forecast_id'])['input_hash']==packet_hash for x in records)
assert Queue(reopened).claim('restart-probe') is None
result={'status':'SOURCE_REVIEW_AND_PENDING_FORECASTS_PERSISTED','database':name,'forecast_count':len(records),'immutable_record_count':count,'reopened_hash_check':True,'no_due_duplicate_jobs':True,'records':records,'factory':factory,'mature_labels':0,'orders':0,'model_calls':0,'scheduler_added':False,'automatic_release_fetch':'NOT_IMPLEMENTED_TASK7_OBSERVATION_QUEUE_ONLY'}
(out/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
