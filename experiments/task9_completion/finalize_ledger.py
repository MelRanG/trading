"""Recover already-computed results; preserve V1 receipts and append canonical V2."""
from pathlib import Path
import json,sys,hashlib
import psycopg
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'));sys.path.insert(0,str(Path(__file__).parent))
from quant_harness.investment.store import Store
from quant_harness.investment.research import digest
from serialization_fix import canonical_zero
B=R/'runtime/task9_completion';store=Store('postgresql://quant_task9_history@127.0.0.1:55432/quant_task3_task9_history','TASK9_HISTORICAL_ONLY');results=json.loads((B/'results/summary.json').read_text());replacements=[]
for original in results:
 original_id=digest(original);clean=canonical_zero(original)
 with psycopg.connect(store.url,options='-c default_transaction_read_only=on') as conn:row=conn.execute('SELECT payload,payload_hash FROM investment_record WHERE record_id=%s',(original_id,)).fetchone()
 assert row and row[1]==original_id and row[0]==original,'Only sign-of-zero JSON representation may differ'
 new={'serialization_version':'LOCAL_CANONICAL_ZERO_V2','original_record_id':original_id,'original_artifact':str((B/'results'/(original['market']+'_'+original['mode'])/'result.json').relative_to(R)),'original_bytes_sha256':hashlib.sha256((B/'results'/(original['market']+'_'+original['mode'])/'result.json').read_bytes()).hexdigest(),'result':clean,'economic_values_changed':False};new_id=store.put('completion_historical_result_canonical',new);assert store.get(new_id)==new
 if digest(row[0])!=row[1]:store.state(original_id,'SUPERSEDED_SERIALIZATION_ONLY',{'canonical_result':new_id,'reason':'JSONB cannot preserve negative zero; original payload artifact and original hash preserved'})
 replacements.append({'original_record_id':original_id,'canonical_record_id':new_id,'original_roundtrip_mismatch':digest(row[0])!=row[1]})
# Export ALL rows with explicit, verifiable reconstruction for the six legacy
# numeric-zero receipts. No SQL payload/hash UPDATE and no deletion.
artifacts={digest(r):r for r in results};export=[];reconstructed=[]
with psycopg.connect(store.url,options='-c default_transaction_read_only=on') as conn:
 for identity,kind,p,h,created in conn.execute('SELECT record_id,kind,payload,payload_hash,created_at FROM investment_record ORDER BY created_at,record_id'):
  if digest(p)!=h:
   original=artifacts.get(identity);assert original and digest(original)==h and canonical_zero(original)==canonical_zero(p)
   p=original;reconstructed.append(identity)
  export.append({'record_id':identity,'kind':kind,'payload':p,'payload_hash':h,'created_at':str(created)})
(B/'research_records_recovered.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in export));receipt={'status':'RECOVERED_NO_NEW_TRADES','canonical_results':replacements,'reconstructed_original_signed_zero_records':reconstructed,'global_store_changed':False,'original_payloads_or_hashes_modified':False,'new_fills_created':0,'export_rows':len(export)};(B/'ledger_recovery.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt,indent=2))
