from pathlib import Path
import json,hashlib
from src.goal import GoalStore
from src.goal.models import EvidenceInput
w=Path('/work');feedback=w/'home/.vibe-trading/runs/20261113_060317_98_ca4bdc/feedback.json';goals=GoalStore();goal=goals.get_current_goal('task6-completion');assert goal is not None
snapshot=goals.get_goal_snapshot(goal.goal_id);h=hashlib.sha256(feedback.read_bytes()).hexdigest();evidence=goals.append_evidence(session_id='task6-completion',goal_id=goal.goal_id,expected_goal_id=goal.goal_id,evidence=EvidenceInput(text='Persisted original AI feedback: actual repeated2025 evaluation, NO_CHANGE; CLI terminal response later failed at subscription quota. Not independent Forward.',artifact_path=str(feedback),artifact_hash=h,source_type='analysis',data_as_of='2025-12-31'))
(w/'goal_recovery.json').write_text(json.dumps({'status':'ORIGINAL_GOAL_RECOVERED_BY_ORIGINAL_SESSION_ID','goal_id':goal.goal_id,'evidence_id':evidence.evidence_id,'feedback_hash':h,'cli_terminal_status':'FAILED_SUBSCRIPTION_QUOTA_AFTER_ARTIFACT_SAVED','snapshot':snapshot},indent=2,default=str));print(goal.goal_id)
