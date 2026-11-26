from pathlib import Path
import sys,json,hashlib
from datetime import datetime,timezone
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'))
from quant_harness.investment.equities import load_environment
from quant_harness.investment.operations_data import strict_rows
from quant_harness.v72_integration_ready.toss_openapi import TossOpenApiClient
load_environment(R);c=TossOpenApiClient();B=R/'runtime/task9_completion/pilot_prices';B.mkdir(exist_ok=True)
for symbol in ['248070','950170']:
 p=B/(symbol+'.receipt.json')
 if p.exists():continue
 query={'symbol':symbol,'interval':'1d','count':200,'before':'2022-03-15T00:00:00+09:00','adjusted':'false'};r={'symbol':symbol,'query':query,'available_at':datetime.now(timezone.utc).isoformat(),'source':'TOSS_UNADJUSTED_STOCK_CANDLES'}
 try:
  data=c._request('GET',c.endpoint_map.candles_path,query=query);raw=json.dumps(data,sort_keys=True).encode();(B/(symbol+'.raw.json')).write_bytes(raw);r['sha256']=hashlib.sha256(raw).hexdigest();f=strict_rows(data,symbol,'KRW','Asia/Seoul','2022-03-14');f.to_csv(B/(symbol+'.csv'),index=False);r.update(status='SAVED',rows=len(f))
 except Exception as e:r.update(status='FAILED',error_type=type(e).__name__)
 p.write_text(json.dumps(r,indent=2));print(symbol,r['status'],flush=True)
