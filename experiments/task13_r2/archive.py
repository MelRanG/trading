"""Lossless task-local artifact compression; source and archived SHA must match."""
from pathlib import Path
import gzip,hashlib,json,os
R=Path(__file__).resolve().parents[2];B=R/'runtime/task13_r2'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
paths=list((B/'training').glob('*.csv'))+list((B/'training').glob('*/*.h5'))+[B/'training/prepared.pkl']+list((B/'native/rd').glob('*state.pkl'))
receipt=[]
for p in paths:
 if not p.exists():continue
 z=Path(str(p)+'.gz');tmp=Path(str(z)+'.tmp');digest=sha(p);size=p.stat().st_size
 with p.open('rb') as src,tmp.open('wb') as raw,gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0,compresslevel=6) as dst:
  for b in iter(lambda:src.read(1024*1024),b''):dst.write(b)
 h=hashlib.sha256()
 with gzip.open(tmp,'rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 assert h.hexdigest()==digest;os.replace(tmp,z);p.unlink();receipt.append({'original':str(p.relative_to(R)),'archive':str(z.relative_to(R)),'source_sha256':digest,'archive_sha256':sha(z),'original_bytes':size,'archive_bytes':z.stat().st_size,'restore':'gzip -dk '+str(z.relative_to(R))})
(B/'archive_receipt.json').write_text(json.dumps({'scope':'Task13-R2 only. No historical evidence removed; verified lossless compression. Restore compressed prepared.pkl and native states before resuming those stages; do not rerun research by default.','files':receipt,'saved_bytes':sum(a['original_bytes']-a['archive_bytes'] for a in receipt)},indent=2));print(len(receipt),sum(a['original_bytes']-a['archive_bytes'] for a in receipt))
