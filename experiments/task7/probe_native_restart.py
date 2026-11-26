from pathlib import Path
import json,os
root=Path('/work/company_history');os.environ['VIBE_TRADING_HYPOTHESES_PATH']=str(root/'hypotheses.json')
from src.hypotheses import HypothesisRegistry
from src.goal import GoalStore
from src.research_artifacts.store import ResearchArtifactStore
hypotheses=HypothesisRegistry().list();store=ResearchArtifactStore(root/'artifacts.db');records=store.search(query='Task7');assert len(records)==2 and len(hypotheses)==2
assert all(GoalStore().get_current_goal('task7-company-'+s) is not None for s in ['NVDA','CRWV'])
print(json.dumps({'status':'NEW_CONTAINER_PROCESS_NATIVE_RECOVERY_PASS','hypotheses':len(hypotheses),'artifacts':len(records),'goals':2,'model_calls':0}))
