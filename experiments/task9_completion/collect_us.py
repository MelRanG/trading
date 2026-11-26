"""Four issuers from dated2021-11-01 release discovery, not current winners."""
from pathlib import Path
import sys,json,hashlib
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'))
from quant_harness.investment.equities import load_environment,fetch
from quant_harness.investment.company_outcomes import Document
from quant_harness.investment.operations_data import strict_rows
from quant_harness.v72_integration_ready.toss_openapi import TossOpenApiClient
load_environment(R);c=TossOpenApiClient();B=R/'runtime/task9_completion/us';B.mkdir(exist_ok=True)
sources=[('ON','https://investor.onsemi.com/news-releases/news-release-details/onsemi-reports-record-revenue-and-non-gaap-earnings-share-third'),('ANET','https://d18rn0p25nwr6d.cloudfront.net/CIK-0001596532/b999dc9a-4f34-4bfd-a794-be53f2838c57.pdf'),('VNO','https://investors.vno.com/static-files/0061df60-eb51-4899-81ba-0ec600e6fada'),('SPG','https://annualmeeting.simon.com/news-releases/news-release-details/simon-property-group-reports-third-quarter-2021-results')]
plan={'queries':['"November1,2021" "financial results" businesswire/prnewswire'],'selection':'First4 US issuer results with dated primary source after filtering foreign listings and post-cutoff releases','candidates':[x[0] for x in sources],'cap_floor_USD':2000000000,'max_new_price_get':10,'source_raw':True,'not_whole_market_discovery':True}
p=B/'cohort_contract.json'
if p.exists():assert json.loads(p.read_text())==plan
else:p.write_text(json.dumps(plan,indent=2))
for symbol,url in sources:
 folder=B/symbol;folder.mkdir(exist_ok=True);p=folder/'ir.receipt.json'
 if not p.exists():
  try:
   raw,receipt=fetch(url,folder/'raw');(folder/'ir.raw').write_bytes(raw)
   if raw.startswith(b'%PDF'):(folder/'ir.pdf').write_bytes(raw)
   else:
    d=Document();d.feed(raw.decode());(folder/'ir.txt').write_text('\n'.join(d.text))
   p.write_text(json.dumps({'status':'SAVED',**receipt},indent=2));print(symbol,'IR_SAVED',flush=True)
  except Exception as e:p.write_text(json.dumps({'status':'FAILED','error_type':type(e).__name__}));print(symbol,'IR_FAILED',flush=True)
for symbol in [x[0] for x in sources]+['^GSPC']:
 folder=B/symbol;folder.mkdir(exist_ok=True)
 p=folder/'yahoo.receipt.json'
 if not p.exists():
  try:
   raw,receipt=fetch('https://query1.finance.yahoo.com/v8/finance/chart/'+symbol.replace('^','%5E')+'?interval=1d&period1=1612137600&period2=1648771200&events=div%2Csplits',folder/'raw');(folder/'yahoo.json').write_bytes(raw);p.write_text(json.dumps({'status':'SAVED',**receipt}));print(symbol,'YAHOO_SAVED',flush=True)
  except Exception as e:p.write_text(json.dumps({'status':'FAILED','error_type':type(e).__name__}));print(symbol,'YAHOO_FAILED',flush=True)
 if symbol=='^GSPC':continue
 p=folder/'toss.receipt.json'
 if not p.exists():
  query={'symbol':symbol,'interval':'1d','count':200,'before':'2022-03-15T00:00:00-04:00','adjusted':'false'}
  try:
   raw=c._request('GET',c.endpoint_map.candles_path,query=query);data=json.dumps(raw,sort_keys=True).encode();(folder/'toss.raw.json').write_bytes(data);f=strict_rows(raw,symbol,'USD','America/New_York','2022-03-14');f.to_csv(folder/'toss.csv',index=False);p.write_text(json.dumps({'status':'SAVED','query':query,'sha256':hashlib.sha256(data).hexdigest(),'rows':len(f)}));print(symbol,'TOSS_SAVED',flush=True)
  except Exception as e:p.write_text(json.dumps({'status':'FAILED','query':query,'error_type':type(e).__name__}));print(symbol,'TOSS_FAILED',flush=True)
