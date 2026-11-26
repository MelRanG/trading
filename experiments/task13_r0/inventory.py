from pathlib import Path
import json,hashlib,datetime
R=Path(__file__).resolve().parents[2];B=R/'runtime/task13_r0'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
rows=[]
# Original providers only; skip DBs, backups and model traces.
for root in ['runtime/task3/us','runtime/task3/kr','runtime/task6/data/accepted','runtime/task9_1/researcher_inputs','runtime/task9_2','runtime/task9_3/screen','runtime/task10/data','runtime/task13/adjusted_inputs']:
 p=R/root
 if not p.exists():continue
 for f in p.rglob('*.json'):
  if f.stat().st_size>100_000 or not any(t in f.name for t in ['receipt','quality','manifest']):continue
  try:d=json.loads(f.read_text())
  except Exception:continue
  if isinstance(d,dict) and ('url' in d or ('sha256' in d and 'symbol' in d)):
   rows.append({'path':str(f.relative_to(R)),'url':d.get('url'),'symbol':d.get('symbol'),'start':d.get('start'),'end':d.get('end'),'rows':d.get('rows'),'sha256':sha(f)})
(B/'existing_sources.json').write_text(json.dumps({'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'sources':rows,'old_data_mutated':False,'note':'Metadata audit only, no full data copies; accepted Task6 receipts reused by engine input references'},indent=2)+'\n')
print('EXISTING_RECEIPTS',len(rows))
