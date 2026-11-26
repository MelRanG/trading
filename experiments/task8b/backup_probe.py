from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,subprocess
R=Path(__file__).resolve().parents[2];stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ');folder=R/'runtime/task8b/backups'/stamp;folder.mkdir(parents=True,exist_ok=False)
def call(*args,**kw):return subprocess.run(args,check=True,capture_output=True,**kw)
manifest={}
for db in ['quant_task3_task8b_research','quant_task3_task8b_explore_us','quant_task3_task8b_explore_kr']:
 raw=call('docker','exec','quant-task3-postgres','pg_dump','-U','quant_task3','-Fc',db).stdout;(folder/(db+'.dump')).write_bytes(raw);manifest[db]={'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}
import sys,psycopg
sys.path.insert(0,str(R/'src'))
from quant_harness.investment.research import digest
from quant_harness.investment.stockpaper import reconcile
restores=[]
for index,db in enumerate(list(manifest)):
 restored='quant_task3_task8b_restore_'+stamp.lower()+'_'+str(index)
 call('docker','exec','quant-task3-postgres','createdb','-U','quant_task3',restored)
 call('docker','exec','-i','quant-task3-postgres','pg_restore','-U','quant_task3','-d',restored,'--exit-on-error',input=(folder/(db+'.dump')).read_bytes())
 with psycopg.connect('postgresql://quant_task3@127.0.0.1:55432/'+restored) as conn:
  rows=conn.execute('SELECT payload,payload_hash FROM investment_record').fetchall()
  assert all(digest(payload)==fingerprint for payload,fingerprint in rows)
  receipt={'source':db,'database':restored,'records_hash_verified':len(rows),'status':'RESTORED_NEW_ISOLATED_DATABASE'}
  if index:
   assert reconcile(conn)
   receipt.update(ledger_reconciled=True,fills=conn.execute('SELECT count(*) FROM stock_fill').fetchone()[0])
  restores.append(receipt)
manifest['restore']={'databases':restores,'scope':'Per-database snapshots, no cross-account atomicity claim'}
(folder/'manifest.json').write_text(json.dumps(manifest,indent=2))
(R/'runtime/task8b/backup_latest.json').write_text(json.dumps({'folder':str(folder.relative_to(R)),'manifest':manifest},indent=2))
print(json.dumps({'backup':str(folder.relative_to(R)),'restore':manifest['restore']},indent=2))
