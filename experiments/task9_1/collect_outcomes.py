"""Evaluator-only future data. Refuses execution until all four decisions sealed."""
from common import *
from datetime import datetime,timezone
from urllib.parse import quote
import pandas as pd
from quant_harness.investment.equities import fetch,load_environment
from quant_harness.investment.operations_data import strict_rows
from quant_harness.v72_integration_ready.toss_openapi import TossOpenApiClient
load_environment(R);c=TossOpenApiClient()
seals=json.loads((B/'decision_seals.json').read_text());assert len(seals)==4
for date,end in [('2024-11-29','2025-12-12'),('2025-06-30','2026-07-12')]:
 for market,index in [('US','^GSPC'),('KR','^KS11')]:
  screen=json.loads((B/'screens'/date/(market+'.json')).read_text());items=[(x['symbol'],False) for x in screen['deep']]+[(index,True)]
  for symbol,is_index in items:
   f=B/'evaluator_only'/date/symbol;f.mkdir(parents=True,exist_ok=True)
   if (f/'receipt.json').exists():continue
   try:
    a=int(datetime.fromisoformat(date+'T00:00:00+00:00').timestamp());b=int(datetime.fromisoformat(end+'T00:00:00+00:00').timestamp())
    raw,r=fetch('https://query1.finance.yahoo.com/v8/finance/chart/'+quote(symbol,safe='')+f'?interval=1d&period1={a}&period2={b}&events=div%2Csplits',f/'raw');(f/'chart.json').write_bytes(raw);z=json.loads(raw)['chart']['result'][0];q=z['indicators']['quote'][0];rows=[]
    for i,t in enumerate(z['timestamp']):rows.append({'date':datetime.fromtimestamp(t,timezone.utc).astimezone(__import__('zoneinfo').ZoneInfo('Asia/Seoul' if market=='KR' else 'America/New_York')).date().isoformat(),**{k:q[k][i] for k in ['open','high','low','close','volume']}})
    yf=pd.DataFrame(rows);yf.to_csv(f/'yahoo_bars.csv',index=False);receipts=[]
    if not is_index:
     before=end+'T00:00:00'+('+09:00' if market=='KR' else '-05:00');frames=[]
     for page in range(2):
      query={'symbol':symbol.split('.')[0] if market=='KR' else symbol,'interval':'1d','count':200,'before':before,'adjusted':'false'};p=f/('toss_'+str(page)+'.json')
      if p.exists():payload=json.loads(p.read_text())
      else:payload=c._request('GET',c.endpoint_map.candles_path,query=query);dump(p,payload)
      tf=strict_rows(payload,symbol,'KRW' if market=='KR' else 'USD','Asia/Seoul' if market=='KR' else 'America/New_York',end);assert len(tf)>0;frames.append(tf);receipts.append({'query':query,'sha256':sha(p)})
      if tf.date.min()<=date:break
      before=tf.date.min()+'T00:00:00'+('+09:00' if market=='KR' else '-05:00')
     full=pd.concat(frames).sort_values('date');assert not full.date.duplicated().any();full.to_csv(f/'bars.csv',index=False)
    else:yf.to_csv(f/'bars.csv',index=False)
    dump(f/'receipt.json',{'status':'SAVED','source':r,'toss_receipts':receipts,'events':z.get('events',{}),'outcome_access':'EVALUATOR_ONLY_AFTER_ALL_SEALS','quality':'PARTIAL_PRICE_ONLY_NO_FULL_ACTION_AUDIT'});print(date,symbol,'SAVED',flush=True)
   except Exception as e:dump(f/'receipt.json',{'status':'FAILED','error_type':type(e).__name__});print(date,symbol,'FAILED',type(e).__name__,flush=True)
