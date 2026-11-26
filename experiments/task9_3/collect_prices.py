from common import *
from datetime import datetime,timezone
from urllib.parse import quote
import pandas as pd,numpy as np,ast
from quant_harness.investment.equities import fetch,equity_revision_gate,load_environment
from quant_harness.investment.operations_data import strict_rows
from quant_harness.v72_integration_ready.toss_openapi import TossOpenApiClient
load_environment(R);tc=TossOpenApiClient();W=Path('/home/ansy/app/quant-diligence/task9-3-work')
assert (W/'US_2026-05-15.json').exists(),'first US decision must be sealed before evaluator-only futurecollection'
for m,index in [('US','^GSPC'),('KR','^KS11')]:
 src=W/('discover_US.json' if m=='US' else 'discover_KR_v2.json');names=[c['symbol'] for c in json.loads(src.read_text())['deep']]+[index]
 for s in names:
  f=B/'evaluator_only'/s;f.mkdir(parents=True,exist_ok=True)
  if (f/'quality.json').exists():continue
  try:
   p=f/'chart.json';a=int(datetime.fromisoformat('2026-05-14T00:00:00+00:00').timestamp());b=int(datetime.fromisoformat('2026-11-14T00:00:00+00:00').timestamp())
   if not p.exists():raw,r=fetch('https://query1.finance.yahoo.com/v8/finance/chart/'+quote(s,safe='')+f'?interval=1d&period1={a}&period2={b}&events=div%2Csplits',f/'raw');p.write_bytes(raw);dump(f/'receipt.json',r)
   z=json.loads(p.read_text())['chart']['result'][0];q=z['indicators']['quote'][0];rows=[]
   for i,t in enumerate(z['timestamp']):rows.append({'timestamp':datetime.fromtimestamp(t,timezone.utc).isoformat(),'date':datetime.fromtimestamp(t,timezone.utc).astimezone(__import__('zoneinfo').ZoneInfo('Asia/Seoul' if m=='KR' else 'America/New_York')).date().isoformat(),**{k:q[k][i] for k in ['open','high','low','close','volume']}})
   yf=pd.DataFrame(rows).dropna();yf.to_csv(f/'yahoo.csv',index=False);assert yf.date.max()=='2026-11-13','MISSING_END_SESSION';assert not yf.date.duplicated().any();quality={'market':m,'symbol':s,'declared_events':z.get('events',{}),'scope':'PARTIAL_REDOWLOADED_RAW_PRICE_DIAGNOSTIC_NOT_PIT_OR_TR','action_limit':'Yahoo declared events are not independently complete exchange corporateaction history'}
   if not s.startswith('^'):
    gate=equity_revision_gate(yf.assign(value_approx=yf.close*yf.volume).rename(columns={k:'raw_'+k for k in ['open','high','low','close']}),s,f,json.loads((f/'receipt.json').read_text()));quality['V87']=gate
    pp=f/'toss.json'
    if not pp.exists():dump(pp,tc._request('GET',tc.endpoint_map.candles_path,query={'symbol':s.split('.')[0] if m=='KR' else s,'interval':'1d','count':180,'before':'2026-11-14T00:00:00'+('+09:00' if m=='KR' else '-05:00'),'adjusted':'false'}))
    tf=strict_rows(json.loads(pp.read_text()),s,'KRW' if m=='KR' else 'USD','Asia/Seoul' if m=='KR' else 'America/New_York','2026-11-13');tf.to_csv(f/'toss.csv',index=False);j=yf.merge(tf,on='date',suffixes=('_y','_t'));assert len(j)>=115,'INSUFFICIENT_CROSS_PROVIDER_DAYS';errors={k:float((j[k+'_y']/j[k+'_t']-1).abs().max()) for k in ['open','close']};quality['cross_provider']=errors;quality['compared_sessions']=len(j)
    if m=='KR':
     pp=f/'naver.txt'
     if not pp.exists():raw,r=fetch('https://api.finance.naver.com/siseJson.naver?symbol='+s[:6]+'&requestType=1&startTime=20260514&endTime=20261113&timeframe=day',f/'naver_raw');pp.write_bytes(raw)
     znav=ast.literal_eval(pp.read_text().strip());nf=pd.DataFrame([{'date':pd.Timestamp(str(v[0])).date().isoformat(),'open':v[1],'close':v[4]} for v in znav[1:]]);nf.to_csv(f/'naver.csv',index=False);nj=tf.merge(nf,on='date',suffixes=('_t','_n'));quality['naver_toss_max_relative']=float(max((nj.open_t/nj.open_n-1).abs().max(),(nj.close_t/nj.close_n-1).abs().max()))
    if quality['declared_events'].get('splits'):raise ValueError('DECLARED_SPLIT_REQUIRES_EXPLICIT_RECONCILIATION')
    assert max(errors.values())<.005,'DAILY_PRICE_PROVIDER_CONFLICT'
    if m=='KR':assert quality['naver_toss_max_relative']<.005,'NAVER_TOSS_CONFLICT'
    df=tf[['date','open','high','low','close','volume']];df.to_csv(f/'bars.csv',index=False)
   else:yf.to_csv(f/'bars.csv',index=False)
   quality['status']='ELIGIBLE_PARTIAL';dump(f/'quality.json',quality);print(s,'ELIGIBLE',len(yf),flush=True)
  except Exception as e:
   quality=locals().get('quality',{});dump(f/'quality.json',{**quality,'status':'BLOCKED','error_type':type(e).__name__,'reason':str(e)[:120] if isinstance(e,(AssertionError,ValueError)) else None});print(s,'BLOCKED',type(e).__name__,flush=True)
