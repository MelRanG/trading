"""Only unreferenced import caches, after archive+isolated restore verification."""
from pathlib import Path
import json,hashlib,tarfile,tempfile,shutil
R=Path(__file__).resolve().parents[2];B=R/'runtime/task10_1'
records=json.loads((B/'artifact_inventory.json').read_text());candidates=[x for x in records if x['classification']=='DISPOSABLE_CANDIDATE'];accepted=[];blocked=[]
references=list((R/'runtime').rglob('*manifest*.json'))+list((R/'experiments').rglob('*.py'))+list((R/'scripts').glob('*.py'))+list((R/'deploy').rglob('*'))
import gzip
dbtext=''.join(p.read_text() for p in B.glob('db_*.json'))+''.join(gzip.open(p,'rt').read() for p in B.glob('db_*.json.gz'))
for x in candidates:
 p=R/x['path'];refs=[]
 for ref in references:
  if not ref.is_file() or 'task10_1' in ref.parts:continue
  try:t=ref.read_text()
  except (UnicodeError,OSError):continue
  if x['path'] in t or str(p) in t:refs.append(str(ref.relative_to(R)))
 if x['path'] in dbtext:refs.append('DB_EXPORT_PATH_REFERENCE')
 source=p.parent.parent/'signal_engine.py'
 if refs or not source.exists() or p.is_symlink():blocked.append({'path':x['path'],'references':refs,'source_exists':source.exists()});continue
 accepted.append(x)
archive=B/'disposable_cache_backup.tar.gz'
if accepted:
 with tarfile.open(archive,'w:gz') as t:
  for x in accepted:t.add(R/x['path'],arcname=x['path'])
 with tempfile.TemporaryDirectory(dir=B) as tmp:
  with tarfile.open(archive) as t:t.extractall(tmp,filter='data')
  for x in accepted:
   restored=Path(tmp)/x['path'];assert hashlib.sha256(restored.read_bytes()).hexdigest()==x['sha256']
 # Recheck unchanged content before unlink. No experiment source/raw/model/manifest deleted.
 for x in accepted:
  p=R/x['path'];assert hashlib.sha256(p.read_bytes()).hexdigest()==x['sha256'];p.unlink()
out={'removed':accepted,'blocked_retained':blocked,'restored_hashes_verified':True,'archive':str(archive.relative_to(R)) if accepted else None,'logical_removed_bytes':sum(x['bytes'] for x in accepted),'archive_bytes':archive.stat().st_size if accepted else 0,'destructive_evidence_deletions':0}
(B/'cleanup_result.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps(out))
