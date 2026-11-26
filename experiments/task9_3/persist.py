from common import *
import subprocess,shutil
from quant_harness.investment.store import Store
sys.path.insert(0,str(R/'experiments/task9_completion'));from serialization_fix import canonical_zero
store=Store('postgresql://quant_task9_history@127.0.0.1:55432/quant_task3_task9_history','TASK9_HISTORICAL_ONLY')
if (B/'persistence.json').exists():
 p=json.loads((B/'persistence.json').read_text());assert all(store.get(i) for i in p['records']);assert sha(B/'research_state.dump')==p['backup_sha256'];print('PERSISTENCE_READBACK_RESTART_OK',len(p['records']));raise SystemExit()
paths=list((B/'decisions').glob('*/*.json'))+list((B/'process_reviews').glob('*/*.json'))+[B/'evaluation'/m/'results.json' for m in ['US','KR']]+[B/name for name in ['ledger_reconciliation.json','checkpoints.json','input_audit.json','weekly_observations.json','forecast_status.json','feedback.json','factory_registration_observation.json']]
ids=[]
for p in paths:
 v=canonical_zero({'schema':'TASK93_HISTORICAL_RESEARCH_ARTIFACT','path':str(p.relative_to(R)),'sha256':sha(p),'data':json.loads(p.read_text()),'not_forward':True,'no_live_authority':True});i=store.put('task93_historical_artifact',v);assert store.get(i)==v;ids.append(i)
backup=subprocess.run(['docker','exec','quant-task3-postgres','pg_dump','-U','quant_task3','-Fc','quant_task3_task9_history'],capture_output=True,check=True).stdout;(B/'research_state.dump').write_bytes(backup);freeze(B/'persistence.json',{'records':ids,'readback_verified':len(ids),'backup_sha256':sha(B/'research_state.dump'),'DB':'existing quant_task3_task9_history, append-only new research records','operating_paper_live_ledger_mutations':False,'backup_restore_into_newDB':'NOT_RUN','actual_reboot':'NOT_RUN'})
print('APPEND_ONLY_RESEARCH_RECORDS',len(ids))
