"""Verify original application collector with actual .env settings; no new fetcher."""
from pathlib import Path
import os,json,sys,time,hashlib,datetime
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'))
from quant_harness.investment.equities import load_environment,fetch
load_environment(R);B=R/'runtime/sec_access_recovery';identity=os.getenv('SEC_USER_AGENT') or os.getenv('EDGAR_IDENTITY');assert identity==os.getenv('EDGAR_IDENTITY')
for name,url,cik in [('python_submissions','https://data.sec.gov/submissions/CIK0000789019.json',789019),('python_companyfacts','https://data.sec.gov/api/xbrl/companyfacts/CIK0000789019.json',789019)]:
 p=B/(name+'.json')
 if p.exists():continue
 record={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'url':url,'original_function':'quant_harness.investment.equities.fetch','identity_sha256':hashlib.sha256(identity.encode()).hexdigest(),'source_settings':'.env'}
 try:
  raw,receipt=fetch(url,B/name,identity=identity);data=json.loads(raw);assert int(data['cik'])==cik
  if name.endswith('companyfacts'):assert 'us-gaap' in data['facts']
  record.update(status='SUCCESS',http_status='2xx (original urlopen completed without HTTPError)',receipt=receipt,bytes=len(raw),validated_CIK=cik,fields=list(data)[:12])
 except Exception as e:record.update(status='FAILED',error_type=type(e).__name__)
 p.write_text(json.dumps(record,indent=2));print(name,record['status'],record.get('bytes'));time.sleep(1)
