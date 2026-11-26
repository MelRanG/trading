"""Lossless compression of this task's large audit exports, verified by restore."""
from pathlib import Path
import gzip,hashlib,json,tempfile,shutil
B=Path(__file__).resolve().parents[2]/'runtime/task10_1';out=[]
for p in sorted(B.glob('db_*.json')):
 oldhash=hashlib.sha256(p.read_bytes()).hexdigest();target=p.with_suffix(p.suffix+'.gz')
 with p.open('rb') as inp,target.open('wb') as raw:
  with gzip.GzipFile(filename='',fileobj=raw,mode='wb',mtime=0) as compressed:shutil.copyfileobj(inp,compressed)
 with tempfile.TemporaryDirectory(dir=B) as tmp:
  restored=Path(tmp)/p.name
  with gzip.open(target,'rb') as inp,restored.open('wb') as f:shutil.copyfileobj(inp,f)
  assert hashlib.sha256(restored.read_bytes()).hexdigest()==oldhash
 out.append({'original_path':str(p),'original_bytes':p.stat().st_size,'original_sha256':oldhash,'compressed_path':str(target),'compressed_bytes':target.stat().st_size,'archive_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'isolated_restored_bytes_match':True})
 assert hashlib.sha256(p.read_bytes()).hexdigest()==oldhash;p.unlink()
(B/'export_archive_receipt.json').write_text(json.dumps({'scope':'Only newly created Task10.1 read-only DB audit exports; old Task6~10 evidence untouched','archived':out,'net_saved_bytes':sum(x['original_bytes']-x['compressed_bytes'] for x in out),'reader_fallback':'audit.read_export supports gzip; cleanup reference audit reads gzip; recovery refuses existing authority before any work'},indent=2))
print('VERIFIED_EXPORT_ARCHIVES',len(out),'SAVED_BYTES',sum(x['original_bytes']-x['compressed_bytes'] for x in out))
