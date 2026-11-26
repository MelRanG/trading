"""One declared request after >=10 minutes; no retry, rotation or bypass."""
from pathlib import Path
import sys,os,json,datetime,time,gzip,hashlib
from urllib.request import Request,urlopen
from urllib.error import HTTPError
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'))
from quant_harness.investment.equities import load_environment
load_environment(R);B=R/'runtime/sec_access_diagnostic';dest=B/'cooldown.json'
if dest.exists():raise SystemExit('Existing result retained, no repeat')
at=datetime.datetime.fromisoformat(json.loads((B/'curl.json').read_text())['at']).timestamp();until=at+610
while time.time()<until:time.sleep(min(30,until-time.time()))
identity=os.getenv('SEC_USER_AGENT') or os.getenv('EDGAR_IDENTITY');assert identity and '@' in identity
identity=('QuantHarness Research '+identity) if 'QuantHarness' not in identity else identity
row={'url':'https://data.sec.gov/submissions/CIK0000789019.json','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'seconds_since_previous_diagnostic_request':time.time()-at,'identity_sha256':hashlib.sha256(identity.encode()).hexdigest(),'request_count':1}
try:
 try:r=urlopen(Request(row['url'],headers={'User-Agent':identity,'Accept':'application/json','Accept-Encoding':'gzip, deflate'}),timeout=20)
 except HTTPError as e:r=e
 with r as response:
  raw=response.read(2000001);row.update(http_status=response.status,headers={k:v for k,v in response.headers.items() if k.lower()!='set-cookie'})
 if row['headers'].get('Content-Encoding')=='gzip':raw=gzip.decompress(raw)
 (B/'cooldown.body').write_bytes(raw);row['sha256']=hashlib.sha256(raw).hexdigest()
except Exception as e:row['error_type']=type(e).__name__
dest.write_text(json.dumps(row,indent=2));print(json.dumps({'http_status':row.get('http_status'),'seconds_since_previous':row['seconds_since_previous_diagnostic_request']}))
