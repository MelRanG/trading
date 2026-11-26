"""Reuse B1 transport/immutable SHA bodies. Isolated C3 budget and cache only."""
from pathlib import Path
import importlib.util,json,hashlib,gzip,datetime,time,sys,re
R=Path(__file__).resolve().parents[2];B=R/'runtime/task13_c3'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def dump(name,d):
 p=B/name;p.parent.mkdir(parents=True,exist_ok=True);t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False)+'\n');t.replace(p)
def module(name,p):
 spec=importlib.util.spec_from_file_location(name,R/p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
native=module('c3_b1_sources','experiments/task13_b1/common.py')
body=native.body

def sources():
 plan=json.loads((B/'plan.json').read_text());assert sha(B/'plan.json')==(B/'plan.sha256').read_text().strip()
 effective=dict(plan)
 override=B/'execution_byte_budget.json'
 if override.exists():
  e=json.loads(override.read_text());assert e['plan_sha256']==sha(B/'plan.json') and e['HTTP_max']==plan['HTTP_max']==300
  assert e['remaining_authorized_requests']==300-e['requests_at_stop']
  assert e['total_download_cap_bytes']<=1206300000+e['remaining_authorized_requests']*plan['per_response_max_bytes']
  effective['total_download_cap_bytes']=e['total_download_cap_bytes']
 native.B=B;native.P=effective
 class Cache(native.Sources):
  def __init__(self):
   super().__init__();self.cache_hits=0
   for root in ['task13_b1','task13_b2','task13_b3']:
    for p in sorted((R/'runtime'/root/'sources').glob('*/receipt.json')):
     d=json.loads(p.read_text())
     if d.get('url') and d.get('status')=='SAVED':self.old.setdefault(d['url'],d)
  def get(self,name,url=None,**kwargs):
   cached=B/'sources'/name/'receipt.json'
   if cached.exists():
    existing=json.loads(cached.read_text())
    if existing.get('status')=='SAVED':
     self.cache_hits+=1;return body(existing),existing
   elif url in self.old:
    self.cache_hits+=1;return super().get(name,url,**kwargs)
   if (B/'circuit_stop.json').exists():return None,{'status':'CIRCUIT_OPEN'}
   requests=sorted((B/'requests').glob('*.json'))
   if len(requests)>=plan['HTTP_max']:return None,{'status':'BUDGET_STOP'}
   recent=[json.loads(p.read_text()) for p in requests[-3:]]
   if len(recent)==3 and all(x.get('http_status') in [401,403,429] for x in recent):
    dump('circuit_stop.json',{'at':now(),'reason':'3consecutive authorization/throttle failures; no identity/proxy changes'});return None,{'status':'CIRCUIT_OPEN'}
   p=B/'sources'/name/'receipt.json'
   if p.exists():
    old=json.loads(p.read_text())
    if old.get('status')=='RESERVED':
     # Archive interrupted reservation, one bounded new attempt, budget still counts old request.
     prior=p.with_name('interrupted_receipt.json')
     if prior.exists():return None,{'status':'INTERRUPTED_RETRY_ALREADY_USED'}
     p.replace(prior)
   before=len(requests);raw,meta=super().get(name,url,**kwargs)
   after=len(list((B/'requests').glob('*.json')))
   if after==before:self.cache_hits+=1
   return raw,meta
 return Cache()
