from pathlib import Path
import sys,json,hashlib,subprocess
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'));sys.path.insert(0,str(R/'experiments/task9_completion'))
from serialization_fix import canonical_zero
from quant_harness.investment.store import Store
from quant_harness.investment.review_jobs import Queue
B=R/'runtime/task9_value';store=Store('postgresql://quant_task9_history@127.0.0.1:55432/quant_task3_task9_history','TASK9_HISTORICAL_ONLY');ids=[]
for year in [2021,2022,2023]:
 x=json.loads((B/'decisions'/(str(year)+'.json')).read_text());i=store.put('value_research_decision',canonical_zero(x));ids.append(i);assert store.get(i)==canonical_zero(x)
for name in ['portfolios.json','forecast_scores_v2.json','chained.json','attribution.json']:
 p=B/'evaluation'/name;x={'version':'TASK9_VALUE_RESEARCH_V1','artifact':str(p.relative_to(R)),'artifact_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'results':json.loads(p.read_text()),'not_forward':True,'not_approved_paper':True,'not_alpha_proof':True};i=store.put('value_research_evaluation',canonical_zero(x));ids.append(i);assert store.get(i)==canonical_zero(x)
feedback=json.loads((B/'followup_requests.json').read_text());job=Queue(store).enqueue('VALUE_RESEARCH_FOLLOWUP',{'decision_and_evaluation_ids':ids,'requests':feedback['requests'],'no_auto_promotion':True,'new_LLM_calls':'BLOCKED_OWN_BUDGET_STOP','official_factory':'Respect existing queue/budget/approval; this is not a new registered or scheduled Factory experiment'})
backup=subprocess.run(['docker','exec','quant-task3-postgres','pg_dump','-U','quant_task3','-Fc','quant_task3_task9_history'],capture_output=True,check=True).stdout;(B/'value_research.dump').write_bytes(backup);(B/'research_handoff.json').write_text(json.dumps({'records':ids,'followup_job':job,'readback_verified':len(ids),'official_factory_new_experiments':0,'backup_sha256':hashlib.sha256(backup).hexdigest(),'operating_db_modified':False},indent=2));print('CANONICAL_RECORDS_READBACK',len(ids),'FOLLOWUP',job)
