"""Three accession-selected symbols, not current-universe selection. Mapping PARTIAL."""
from pathlib import Path
import sys,json,hashlib
from datetime import datetime,timezone
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'))
from quant_harness.investment.equities import load_environment
from quant_harness.investment.operations_data import strict_rows
from quant_harness.v72_integration_ready.toss_openapi import TossOpenApiClient
load_environment(R);c=TossOpenApiClient();b=R/'runtime/task9_historical';out=b/'representative_prices';out.mkdir(exist_ok=True)
originals=[m for m in json.loads((b/'originals/manifest.json').read_text()) if m['month']=='202111'];rows=json.loads((b/'audit/dart_202111.json').read_text())['list'];result=[]
for m in originals:
 row=next(x for x in rows if x['rcept_no']==m['rcept_no']);symbol=row['stock_code'];p=out/(m['rcept_no']+'.receipt.json')
 if p.exists():result.append(json.loads(p.read_text()));continue
 r={'accession':m['rcept_no'],'symbol_current_alias_only':symbol,'historical_identity_mapping':'UNVERIFIED_CURRENT_DART_CODE_TO_ORIGINAL_ISSUER','status':'MISSING_CODE','query':{'symbol':symbol,'interval':'1d','count':200,'before':'2021-12-01T00:00:00+09:00','adjusted':'false'},'observed_at':datetime.now(timezone.utc).isoformat()}
 if symbol:
  try:
   raw=c._request('GET',c.endpoint_map.candles_path,query=r['query']);data=json.dumps(raw,sort_keys=True).encode();(out/(m['rcept_no']+'.raw.json')).write_bytes(data);r['source_hash']=hashlib.sha256(data).hexdigest();f=strict_rows(raw,symbol,'KRW','Asia/Seoul','2021-11-30');f=f[f.date<='2021-11-30'];f.to_csv(out/(m['rcept_no']+'.csv'),index=False);r.update(status='PARTIAL',last_date=f.date.iloc[-1],rows=len(f),reference_close=float(f.close.iloc[-1]),official_session='UNVERIFIED',corporate_actions='UNVERIFIED')
  except Exception as e:r.update(status='FAILED',error_type=type(e).__name__)
 p.write_text(json.dumps(r,indent=2));result.append(r);print(m['rcept_no'],r['status'],r.get('reference_close'),flush=True)
(out/'manifest.json').write_text(json.dumps(result,indent=2))
