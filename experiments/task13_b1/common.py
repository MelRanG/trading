"""Small adapters around existing fetch/OpenDART, task-local immutable receipts."""
from pathlib import Path
import sys,json,hashlib,datetime,gzip,os,time,re
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'));B=R/'runtime/task13_b1';B.mkdir(exist_ok=True)
from quant_harness.investment.equities import load_environment,fetch
from quant_harness.v72_integration_ready.opendart import OpenDartClient
load_environment(R);P=json.loads((B/'plan.json').read_text());assert hashlib.sha256((B/'plan.json').read_bytes()).hexdigest()==(B/'plan.sha256').read_text()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,d):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);t=Path(str(p)+'.tmp');t.write_text(json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False));os.replace(t,p)
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def body(meta):
 p=R/meta['storage_path'];raw=gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes();assert hashlib.sha256(raw).hexdigest()==meta['source_hash'],'SOURCE_REVISION_OR_CORRUPTION';return raw
class Sources:
 def __init__(self):
  self.identity=os.getenv('SEC_USER_AGENT') or os.getenv('EDGAR_IDENTITY');assert self.identity and '@' in self.identity
  self.client=OpenDartClient(transport=self.dart_transport);self.old={}
  for root in [R/'runtime/task13_b0/sources',R/'runtime/sec_access_recovery',R/'runtime/task9_2/sources']:
   for p in list(root.rglob('*.receipt.json'))+list(root.rglob('receipt.json')):
    try:
     d=json.loads(p.read_text());u=d.get('url') or d.get('source');h=d.get('source_hash') or d.get('sha256')
     if not isinstance(u,str) or not h or d.get('status')=='FAILED':continue
     choices=[p.parent/'original.bin',p.parent/(h+'.raw')];raw=next((x for x in choices if x.exists() and sha(x)==h),None)
     if raw:self.old[u]={'storage_path':str(raw.relative_to(R)),'source_hash':h,'observed_at':d.get('observed_at') or d.get('available_at'),'original_receipt':str(p.relative_to(R))}
    except (ValueError,KeyError):continue
 def get(self,name,url=None,*,endpoint=None,params=None,fresh=False):
  path=B/'sources'/name/'receipt.json';public={'endpoint':endpoint,'params':params} if endpoint else {'url':url}
  if path.exists():
   meta=json.loads(path.read_text());return (body(meta),meta) if meta['status']=='SAVED' else (None,meta)
  if not endpoint and url in self.old and not fresh:
   old=self.old[url];raw=body(old);meta={**public,**old,'status':'SAVED','reused':True,'bytes':len(raw)};dump(path,meta);return raw,meta
  folder=path.parent;folder.mkdir(parents=True,exist_ok=True);meta={**public,'requested_at':now(),'status':'RESERVED','reused':False};dump(path,meta)
  for retry in range(2):
   calls=list((B/'requests').glob('*.json'));used=sum(json.loads(p.read_text()).get('bytes',0) for p in calls)
   if len(calls)>=P['HTTP_max'] or used>=P['total_download_cap_bytes']:raise RuntimeError('FROZEN_NETWORK_BUDGET')
   rec={'id':len(calls)+1,'source':public,'at':now(),'status':'RESERVED'};rp=B/'requests'/f'{len(calls)+1:03d}.json';dump(rp,rec);start=time.monotonic()
   try:
    if endpoint:
     self.pending={'folder':folder,'public':public};raw=self.client._request(endpoint,params,binary=True)
    else:
     raw,native=fetch(url,folder/'native_fetch',identity=self.identity,limit=P['per_response_max_bytes']);meta['native_receipt']=native
    if len(raw)>P['per_response_max_bytes']:raise ValueError('RESPONSE_LIMIT')
    h=hashlib.sha256(raw).hexdigest();z=folder/(h+'.raw.gz');tmp=Path(str(z)+'.tmp')
    with tmp.open('wb') as f,gzip.GzipFile(filename='',fileobj=f,mode='wb',mtime=0) as g:g.write(raw)
    assert hashlib.sha256(gzip.decompress(tmp.read_bytes())).hexdigest()==h;os.replace(tmp,z)
    # Existing fetch source and native receipt are retained by hash, storage is verified gzip.
    for p in (folder/'native_fetch').glob('*.raw'):
     if sha(p)==h:p.unlink()
    meta.update(status='SAVED',source_hash=h,stored_hash=sha(z),storage_path=str(z.relative_to(R)),bytes=len(raw),observed_at=now(),revision_gate='NEW_TASK_SNAPSHOT; reuse SHA immutable; not operating V87 admission');rec.update(status='SAVED',bytes=len(raw),source_hash=h)
   except Exception as e:
    code=getattr(e,'code',None);m=re.search(r'HTTP (\d+)',str(e));code=code or (int(m[1]) if m else None);rec.update(status='FAILED',error_type=type(e).__name__,http_status=code);meta.update(status='FAILED',error_type=type(e).__name__,http_status=code)
   rec['seconds']=time.monotonic()-start;dump(rp,rec);dump(path,meta)
   if meta['status']=='SAVED':time.sleep(.5);return raw,meta
   if rec.get('http_status') in [400,401,403,404,429] or rec['error_type'] in ['ValueError','JSONDecodeError']:break
   if retry==0:time.sleep(1)
  return None,meta
 def dart_transport(self,req,timeout):return OpenDartClient._default_transport(req,timeout)
 def dart(self,name,endpoint,params):
  raw,meta=self.get(name,endpoint=endpoint,params=params)
  if raw is None:return None,meta
  if endpoint.endswith('.json'):
   d=json.loads(raw)
   if d.get('status') not in ['000','013']:return None,{**meta,'application_error':d.get('status')}
   return d,meta
  return raw,meta
