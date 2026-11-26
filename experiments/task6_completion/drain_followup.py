from pathlib import Path
import sys,json,subprocess
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'))
from quant_harness.investment.store import Store
from quant_harness.investment.review_jobs import Queue
b=ROOT/'runtime/task6_completion';r=json.loads((b/'factory_test/result.json').read_text());store=Store('postgresql://quant_task3@127.0.0.1:55432/quant_task3_completion_test','TASK6_COMPLETION_TEST_ONLY');q=Queue(store);job=q.claim('native-followup-worker',identity=r['followup_job'],lease_seconds=240)
if job:
 source=store.get(r['result_record']);work=Path('/home/ansy/app/quant-diligence/completion-quanta-work');(work/'factory_followup_packet.json').write_text(json.dumps(source,indent=2))
 result=subprocess.run(['bash',str(ROOT/'experiments/task6_completion/run_worker.sh'),'quanta','factory_followup.py'],capture_output=True,text=True,timeout=230);(b/'evidence/factory_followup_worker.log').write_text(result.stdout+result.stderr)
 if result.returncode:q.fail(r['followup_job'],'native-followup-worker','native proposal failed');raise RuntimeError('followup worker failed')
 h=json.loads((work/'factory_followup_hypothesis.json').read_text());identity=store.put('factory_followup_native_hypothesis',{'source_result_id':r['result_record'],'engine':'original QuantaAlpha','hypothesis':h,'strategy_activation':False});q.finish(r['followup_job'],'native-followup-worker',identity)
 assert Queue(store).claim('duplicate-worker',identity=r['followup_job']) is None
 (b/'factory_test/followup_result.json').write_text(json.dumps({'status':'OFFICIAL_ISOLATED_FACTORY_RESULT_TO_NATIVE_PROPOSAL_COMPLETED','job_id':r['followup_job'],'record_id':identity,'hypothesis':h,'duplicate_claim_blocked':True,'operational_registry_modified':False},indent=2));store.export(b/'factory_test/records.jsonl')
