"""Persistent, capped, credential-free historical feasibility requests."""
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from datetime import datetime,timezone
import hashlib,json,time
R=Path(__file__).resolve().parents[2];B=R/'runtime/task9_historical/audit';B.mkdir(parents=True,exist_ok=True)
SOURCES=[('sec_2021q3','https://www.sec.gov/files/dera/data/financial-statement-data-sets/2021q3.zip'),('sec_index','https://www.sec.gov/Archives/edgar/full-index/2021/QTR4/master.idx'),('sec_submission_access_probe_only','https://data.sec.gov/submissions/CIK0000320193.json'),('krx_public','https://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd?bld=dbms/MDC/STAT/standard/MDCSTAT01901&mktId=ALL&trdDd=20211130'),('yahoo_index','https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC?interval=1d&range=5y&events=div%2Csplits'),('yahoo_kospi','https://query1.finance.yahoo.com/v8/finance/chart/%5EKS11?interval=1d&range=5y&events=div%2Csplits'),('nyse_2021','https://www.ice.com/publicdocs/2021_NYSE_Trading_Calendar.pdf'),('fed_20211103','https://www.federalreserve.gov/newsevents/pressreleases/monetary20211103a.htm')]
def fetch(name,url):
 p=B/(name+'.receipt.json')
 if p.exists():return json.loads(p.read_text())
 if len(list(B.glob('*.receipt.json')))-len(list(B.glob('dart_*.receipt.json')))>=24:raise ValueError('public request budget')
 receipt={'name':name,'url':url,'observed_at':datetime.now(timezone.utc).isoformat(),'status':'RESERVED'};p.write_text(json.dumps(receipt))
 try:
  with urlopen(Request(url,headers={'User-Agent':'ansy tpdud285@naver.com'}),timeout=25) as response:raw=response.read(35000001);receipt['http_status']=response.status
  if len(raw)>35000000:raise ValueError('source size cap')
  (B/(name+'.raw')).write_bytes(raw);receipt.update(status='SAVED',bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
 except HTTPError as e:
  (B/(name+'.error.raw')).write_bytes(e.read(5000));receipt.update(status='FAILED',http_status=e.code,error_type=type(e).__name__)
 except Exception as e:receipt.update(status='FAILED',error_type=type(e).__name__)
 p.write_text(json.dumps(receipt,indent=2));return receipt
if __name__=='__main__':
 for name,url in SOURCES:print(name,fetch(name,url)['status'],flush=True);time.sleep(.3)
