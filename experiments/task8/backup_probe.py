"""One-shot new research/Shadow backup; restore to a fresh DB, no scheduler."""
from pathlib import Path
import json,hashlib,subprocess
R=Path(__file__).resolve().parents[2];b=R/'runtime/task8/backup_final';b.mkdir(exist_ok=True)
def call(*args,**kwargs):return subprocess.run(args,check=True,capture_output=True,**kwargs)
manifest={}
for name in ['quant_task3_task8_research','quant_task3_task8_shadow_us','quant_task3_task8_shadow_kr']:
 p=b/(name+'.dump')
 if not p.exists():p.write_bytes(call('docker','exec','quant-task3-postgres','pg_dump','-U','quant_task3','-Fc',name).stdout)
 manifest[name]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}
restore='quant_task3_task8_restore_final'
exists=call('docker','exec','quant-task3-postgres','psql','-U','quant_task3','-d','postgres','-Atc',"SELECT datname FROM pg_database WHERE datname='"+restore+"'",text=True).stdout.strip()
if not exists:
 call('docker','exec','quant-task3-postgres','createdb','-U','quant_task3',restore)
 call('docker','exec','-i','quant-task3-postgres','pg_restore','-U','quant_task3','-d',restore,'--exit-on-error',input=(b/'quant_task3_task8_research.dump').read_bytes())
result=call('docker','exec','quant-task3-postgres','psql','-U','quant_task3','-d',restore,'-Atc','SELECT count(*) FROM investment_record',text=True).stdout.strip()
manifest['restore']={'database':restore,'research_record_count':int(result),'status':'RESTORED_TO_NEW_DATABASE','scope':'One-shot per-database snapshot; no cross-account atomicity or unattended backup claim'}
(b/'manifest.json').write_text(json.dumps(manifest,indent=2));print(json.dumps(manifest,indent=2))
