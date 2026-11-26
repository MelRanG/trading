from common import *
from quant_harness.investment.equities import load_environment
from quant_harness.investment.operations_data import strict_rows
from quant_harness.v72_integration_ready.toss_openapi import TossOpenApiClient
load_environment(R);c=TossOpenApiClient()
for date in ['2024-11-29','2025-06-30']:
 for m in ['US','KR']:
  screen=json.loads((B/'screens'/date/(m+'.json')).read_text())
  for x in screen['deep']:
   s=x['symbol'];f=B/'inputs'/date/s;p=f/'toss_raw.json';q={'symbol':s.split('.')[0] if m=='KR' else s,'interval':'1d','count':200,'before':date+'T23:59:59'+('+09:00' if m=='KR' else '-05:00'),'adjusted':'false'}
   if p.exists():raw=json.loads(p.read_text())
   else:raw=c._request('GET',c.endpoint_map.candles_path,query=q);dump(p,raw)
   try:
    bars=strict_rows(raw,s,'KRW' if m=='KR' else 'USD','Asia/Seoul' if m=='KR' else 'America/New_York',date);bars.to_csv(f/'toss_bars.csv',index=False);last=bars[bars.date==x['last_date']];assert len(last)==1;v=float(last.close.iloc[0]);ratio=v/x['last_close'];dump(f/'nominal_check.json',{'source_sha256':sha(p),'date':x['last_date'],'toss_close':v,'yahoo_close':x['last_close'],'ratio':ratio,'status':'MATCH' if abs(ratio-1)<.005 else 'UNIT_CONFLICT','use_raw_toss_price':True})
   except Exception as e:dump(f/'nominal_check.json',{'status':'BLOCKED','error_type':type(e).__name__})
   print(date,s,json.loads((f/'nominal_check.json').read_text())['status'],flush=True)
