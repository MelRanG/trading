"""Single standard installed client comparison AFTER cooldown; no identity impersonation."""
from pathlib import Path
import json,datetime,os,sys,time,hashlib
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'))
from quant_harness.investment.equities import load_environment
load_environment(R);B=R/'runtime/sec_access_diagnostic';dest=B/'httpx2.json'
if dest.exists():raise SystemExit('Existing result, no repeat')
while not (B/'cooldown.json').exists():time.sleep(2)
time.sleep(2)
import httpx2
identity=os.getenv('SEC_USER_AGENT') or os.getenv('EDGAR_IDENTITY');assert identity and '@' in identity
if 'QuantHarness' not in identity:identity='QuantHarness Research '+identity
url='https://data.sec.gov/submissions/CIK0000789019.json';d={'url':url,'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'client':'httpx2 installed dependency of existing edgartools','no_retries':True,'identity_sha256':hashlib.sha256(identity.encode()).hexdigest()}
try:
 with httpx2.Client(headers={'User-Agent':identity,'Accept':'application/json','Accept-Encoding':'gzip, deflate'},timeout=20,follow_redirects=False,trust_env=False) as c:
  r=c.get(url);d.update(status=r.status_code,http_version=r.http_version,headers={k:v for k,v in r.headers.items() if k.lower()!='set-cookie'});(B/'httpx2.body').write_bytes(r.content)
except Exception as e:d['error_type']=type(e).__name__
dest.write_text(json.dumps(d,indent=2));print({k:d.get(k) for k in ['status','error_type','http_version']})
