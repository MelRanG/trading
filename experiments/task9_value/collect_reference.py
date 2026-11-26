from pathlib import Path
import sys,json,hashlib
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'))
from quant_harness.investment.equities import load_environment
from quant_harness.investment.operations_data import strict_rows
from quant_harness.v72_integration_ready.toss_openapi import TossOpenApiClient
load_environment(R);client=TossOpenApiClient();B=R/'runtime/task9_value';W=Path('/home/ansy/app/quant-diligence/task9-value-work')
for year in [2021,2022,2023]:
 screen=json.loads((W/('screen_'+str(year)+'.json')).read_text())
 for c in screen['research_priorities']:
  folder=B/'deep'/str(year)/c['symbol'];folder.mkdir(parents=True,exist_ok=True);p=folder/'reference.json'
  if p.exists():continue
  q={'symbol':c['symbol'].split('.')[0] if c['market']=='KR' else c['symbol'],'interval':'1d','count':200,'before':str(year)+'-12-01T00:00:00'+('+09:00' if c['market']=='KR' else '-05:00'),'adjusted':'false'}
  try:
   raw=client._request('GET',client.endpoint_map.candles_path,query=q);data=json.dumps(raw,sort_keys=True).encode();(folder/'toss_reference.raw.json').write_bytes(data);f=strict_rows(raw,c['symbol'],'KRW' if c['market']=='KR' else 'USD','Asia/Seoul' if c['market']=='KR' else 'America/New_York',str(year)+'-11-30');f.to_csv(folder/'toss_reference.csv',index=False);x=f[f.date==str(year)+'-11-30'];assert len(x)==1
   p.write_text(json.dumps({'reference_price':float(x.close.iloc[0]),'currency':'KRW' if c['market']=='KR' else 'USD','date':str(year)+'-11-30','status':'PROVIDER_RAW_REFERENCE','query':q,'raw_sha256':hashlib.sha256(data).hexdigest()},indent=2));print(year,c['symbol'],'SAVED',float(x.close.iloc[0]),flush=True)
  except Exception as e:p.write_text(json.dumps({'status':'FAILED','error_type':type(e).__name__}));print(year,c['symbol'],type(e).__name__,flush=True)
