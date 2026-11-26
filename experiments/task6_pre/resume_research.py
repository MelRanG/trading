"""New-process recovery of original hypothesis, goal and research artifact stores."""
from pathlib import Path
import json,os,hashlib
root=Path('/work/poc');os.environ['VIBE_TRADING_HYPOTHESES_PATH']=str(root/'hypotheses.json')
os.environ['VIBE_TRADING_ALLOWED_RUN_ROOTS']=str(root)
from src.hypotheses import HypothesisRegistry
from src.goal import GoalStore
from src.goal.models import EvidenceInput
from src.research_artifacts.store import ResearchArtifactStore
hyp=HypothesisRegistry().list()[0]
goals=GoalStore();goal=goals.get_current_goal('task6-pre-isolated');snapshot=goals.get_goal_snapshot(goal.goal_id)
card=root/'US_native/run_card.json';cardhash=hashlib.sha256(card.read_bytes()).hexdigest()
evidence=goals.append_evidence(session_id='task6-pre-isolated',goal_id=goal.goal_id,expected_goal_id=goal.goal_id,
 evidence=EvidenceInput(text='Original frozen-input backtest finished; historical diagnostic, not independent Forward.',artifact_path=str(card),artifact_hash=cardhash,source_type='backtest',data_as_of='2026-11-11'))
store=ResearchArtifactStore(root/'artifacts.db')
request={'subject':'alpha101_012 frozen diagnostic','universe':'US Task3 seeds','content':json.dumps({'run_card_sha256':cardhash,'hypothesis_id':hyp.hypothesis_id}),
 'data_as_of':'2026-11-11','evidence':[{'path':str(card),'sha256':cardhash}],'verification_status':'unverified','hypothesis_id':hyp.hypothesis_id,'goal_id':goal.goal_id}
a=store.save(**request);b=store.save(**request);store.close();reopened=ResearchArtifactStore(root/'artifacts.db');records=reopened.search(query='alpha101_012')
result={'status':'RECOVERED_IN_NEW_PROCESS','hypothesis_id':hyp.hypothesis_id,'linked_backtests':len(hyp.run_cards),'goal_id':goal.goal_id,'goal_status':snapshot.get('status',snapshot.get('goal',{}).get('status')),
 'evidence_id':evidence.evidence_id,'artifact_revision':a.revision.revision_id,'duplicate_save_same_revision':a.revision.revision_id==b.revision.revision_id,'second_save_created':b.created,'artifact_status':a.revision.verification_status,'reopened_search_count':len(records),'model_calls':0,'tokens':0,'limitations':'Human-selected fixed hypothesis and adapter; no autonomous LLM discovery demonstrated.'}
(root/'research_recovery.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
