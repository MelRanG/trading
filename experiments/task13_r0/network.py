"""Bounded Python-only GET transport; existing fetch, immutable request cache."""
from pathlib import Path
import json,hashlib,time,datetime,fcntl
from urllib.error import HTTPError,URLError
from quant_harness.investment.equities import fetch
R=Path(__file__).resolve().parents[2];B=R/'runtime/task13_r0';B.mkdir(exist_ok=True)
class PermanentError(RuntimeError):pass
class CircuitOpen(RuntimeError):pass
class Network:
 def __init__(self):self.last=0
 def get(self,url,category='data'):
  key=hashlib.sha256(url.encode()).hexdigest();folder=B/'http'/key;folder.mkdir(parents=True,exist_ok=True);meta=folder/'receipt.json';stop=B/'provider_blocks.json'
  if meta.exists():
   d=json.loads(meta.read_text());p=R/d['path'];assert hashlib.sha256(p.read_bytes()).hexdigest()==d['source_hash'];return p.read_bytes(),d
  # Frozen terminal failures require an explicit new run for a new probe.
  for failure in sorted(folder.glob('failure_*.json')):
   cached=json.loads(failure.read_text())
   if cached.get('status') in [400,404,410,422]:raise PermanentError('CACHED_HTTP_'+str(cached['status']))
  host=url.split('/')[2];blocks=json.loads(stop.read_text()) if stop.exists() else {}
  if host in blocks:raise CircuitOpen(host+': '+blocks[host]['reason'])
  for attempt in range(3):
   ledger=B/'requests.jsonl';lock=B/'.request.lock'
   with lock.open('a') as f:
    fcntl.flock(f,fcntl.LOCK_EX);count=len(ledger.read_text().splitlines()) if ledger.exists() else 0
    if count>=500:raise CircuitOpen('GLOBAL_REQUEST_BUDGET_500')
    rec={'id':count+1,'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'host':host,'url':url,'category':category,'attempt':attempt,'status':'RESERVED'}
    with ledger.open('a') as q:q.write(json.dumps(rec)+'\n')
   time.sleep(max(0,1-(time.monotonic()-self.last)));self.last=time.monotonic()
   try:
    raw,receipt=fetch(url,folder/'raw',identity='QuantHarness private research contact ansy',limit=4_000_000);path=folder/'raw'/(receipt['source_hash']+'.raw');item={**receipt,'path':str(path.relative_to(R)),'HTTP_200':True};meta.write_text(json.dumps(item,indent=2));return raw,item
   except HTTPError as exc:
    permanent=exc.code in [400,401,403,404,410,422,429]
    error={'status':exc.code,'reason':'HTTP_'+str(exc.code),'at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    (folder/('failure_'+str(attempt)+'.json')).write_text(json.dumps(error))
    if exc.code in [401,403,429]:blocks[host]=error;stop.write_text(json.dumps(blocks,indent=2))
    if permanent:raise PermanentError(str(exc.code)) from exc
    if attempt==2:raise
   except (TimeoutError,URLError,ConnectionError) as exc:
    (folder/('failure_'+str(attempt)+'.json')).write_text(json.dumps({'reason':type(exc).__name__}))
    if attempt==2:raise
   time.sleep(2**(attempt+1))
