"""Original Vibe durable company hypotheses/artifacts, without backtest fiction."""
from pathlib import Path
import os,json,hashlib
root=Path('/work/company_history');root.mkdir(exist_ok=True)
os.environ['VIBE_TRADING_HYPOTHESES_PATH']=str(root/'hypotheses.json')
from src.hypotheses import HypothesisRegistry
from src.goal import GoalStore
from src.goal.models import EvidenceInput
from src.research_artifacts.store import ResearchArtifactStore
registry=HypothesisRegistry();goals=GoalStore();artifacts=ResearchArtifactStore(root/'artifacts.db');result=[]
for symbol in ['NVDA','CRWV']:
 path=Path('/evidence/comparison/vibe_component')/symbol/'analysis.json';record=json.loads(path.read_text());title='Task7 '+symbol+' source-grounded company hypothesis'
 prior=[h for h in registry.list() if h.title==title]
 hypothesis=prior[0] if prior else registry.create(title=title,thesis=json.dumps(record['hypothesis']),universe=symbol+' common equity, research only',signal_definition='No execution signal; observe next quarterly revenue and recorded falsification conditions',data_sources=[symbol+'_IR'],skills=['earnings-forecast'],invalidation_notes=json.dumps(record['falsification']))
 session='task7-company-'+symbol;goal=goals.get_current_goal(session)
 if goal is None:goal=goals.replace_goal(session_id=session,objective='Evaluate source quality and preserve the company forecast until actual issuer release; no trading',criteria=['Preserve source and model evidence','Review contradictory facts','Wait for actual matching quarterly revenue release; date alone is insufficient'],source='task7-company-adapter',ui_summary=title)
 fingerprint=hashlib.sha256(path.read_bytes()).hexdigest()
 # Stable artifact revision; repeated identical save must not make a new revision.
 request={'subject':title,'universe':symbol,'content':json.dumps(record,sort_keys=True),'data_as_of':'2026-11-13','evidence':[{'path':str(path),'sha256':fingerprint}],'verification_status':'unverified','hypothesis_id':hypothesis.hypothesis_id,'goal_id':goal.goal_id}
 a=artifacts.save(**request);b=artifacts.save(**request)
 evidence=goals.append_evidence(session_id=session,goal_id=goal.goal_id,expected_goal_id=goal.goal_id,evidence=EvidenceInput(text='Frozen issuer analysis, source audit pending independent broader review. Future accuracy PENDING; no backtest or realized return.',artifact_path=str(path),artifact_hash=fingerprint,source_type='analysis',data_as_of='2026-11-13'))
 result.append({'ticker':symbol,'hypothesis_id':hypothesis.hypothesis_id,'goal_id':goal.goal_id,'evidence_id':evidence.evidence_id,'revision_id':a.revision.revision_id,'duplicate_revision_stable':a.revision.revision_id==b.revision.revision_id,'goal_status':'ACTIVE_PENDING_RELEASE','accuracy':'PENDING'})
artifacts.close();reopened=ResearchArtifactStore(root/'artifacts.db');count=len(reopened.search(query='Task7'));reopened.close()
assert count>=2 and all(x['duplicate_revision_stable'] for x in result)
(root/'result.json').write_text(json.dumps({'records':result,'reopened_artifacts':count,'model_calls':0,'autopilot_backtest_scaffold':'NOT_USED_COMPANY_FORECAST_IS_NOT_BACKTEST'},indent=2));print((root/'result.json').read_text())
