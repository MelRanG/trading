"""Normal declared read-only SEC requests, no alternate identities or bypass."""
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from datetime import datetime,timezone
import json,hashlib,gzip,time,sys,os
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'))
from quant_harness.investment.equities import load_environment
load_environment(R);B=R/'runtime/task9_completion/access';identity=os.getenv('SEC_USER_AGENT') or os.getenv('EDGAR_IDENTITY') or 'ansy tpdud285@naver.com'
# Never store or print the configured identity. Valid known contact was authorized.
for name,url in [('sec_index_declared','https://www.sec.gov/Archives/edgar/full-index/2021/QTR4/master.idx'),('sec_submissions_declared','https://data.sec.gov/submissions/CIK0000320193.json'),('sec_fsds_declared','https://www.sec.gov/files/dera/data/financial-statement-data-sets/2021q3.zip')]:
 p=B/(name+'.json')
 if p.exists():print(name,'CACHED');continue
 r={'url':url,'at':datetime.now(timezone.utc).isoformat(),'headers_policy':'Declared previously authorized identity, Accept-Encoding:gzip, no manually overridden Host','status':'RESERVED'};p.write_text(json.dumps(r))
 try:
  with urlopen(Request(url,headers={'User-Agent':identity,'Accept-Encoding':'gzip','Accept':'application/json,text/plain,application/zip,*/*'}),timeout=25) as s:
   raw=s.read(25000001);r.update(http_status=s.status,content_type=s.headers.get('Content-Type'),content_encoding=s.headers.get('Content-Encoding'))
  if len(raw)>25000000:raise ValueError('probe source size limit')
  if r.get('content_encoding')=='gzip':raw=gzip.decompress(raw)
  r.update(status='SAVED',bytes=len(raw))
 except HTTPError as e:raw=e.read(12000);r.update(status='FAILED',http_status=e.code,response_class='UNDECLARED_AUTOMATED_TOOL' if b'Undeclared Automated Tool' in raw else 'HTTP_ERROR')
 except Exception as e:raw=b'';r.update(status='FAILED',error_type=type(e).__name__)
 (B/(name+'.raw')).write_bytes(raw);r['sha256']=hashlib.sha256(raw).hexdigest();p.write_text(json.dumps(r,indent=2));print(name,r.get('http_status'),r['status'],flush=True);time.sleep(1)
