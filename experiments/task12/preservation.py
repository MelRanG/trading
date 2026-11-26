"""Read-only old evidence comparison and bounded new artifact inventory."""
from pathlib import Path
import json,hashlib,datetime
R=Path(__file__).resolve().parents[2];B=R/'runtime/task12'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
rows=[]
for n,path in [('task6_completion','runtime/task6_completion/evidence/artifact_manifest.json'),('task10','runtime/task10/artifact_manifest.json'),('task10_1','runtime/task10_1/artifact_manifest.json')]:
 m=json.loads((R/path).read_text());bad=[]
 for item in m['files']:
  p=R/item['path'];actual=sha(p) if p.exists() else None
  if actual!=item['sha256']:bad.append({'path':item['path'],'expected':item['sha256'],'actual':actual})
 rows.append({'manifest':path,'sha256':sha(R/path),'entries':len(m['files']),'mismatches':bad})
patch=json.loads((B/'forward_patch.json').read_text());allowed='experiments/task10_1/forward.py'
assert all(not r['mismatches'] for r in rows[:2]),rows[:2]
assert len(rows[2]['mismatches'])==1 and rows[2]['mismatches'][0]['path']==allowed,rows[2]
assert rows[2]['mismatches'][0]['expected']==sha(B/'forward_before.py')==patch['old_source_hash']
assert sha(R/allowed)==patch['new_source_hash']
assert sha(R/'runtime/task10_1/forward/contract.json')==patch['initial_contract_hash']
(B/'preservation.json').write_text(json.dumps({'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'manifests':rows,'only_authorized_change':allowed,'original_source_preserved':'runtime/task12/forward_before.py','initial_contract_unchanged':True,'note':'Task10.1 mismatch is retained as explicit technical amendment, old manifest never rewritten; old plans/accounts matched. Independent timer may append new files.'},indent=2)+'\n')
print([(r['manifest'],r['entries'],len(r['mismatches'])) for r in rows])
