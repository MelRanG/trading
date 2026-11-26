"""Only pre-cutoff bars and dated facts. Raw receipts immutable; no evaluator prices."""
from common import *
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone,timedelta
from urllib.parse import quote
import pandas as pd,numpy as np
from quant_harness.investment.equities import fetch,equity_revision_gate,load_environment
from quant_harness.v72_integration_ready.opendart import OpenDartClient
load_environment(R);c=OpenDartClient()
def collect(task):
 date,item=task;s=item['symbol'];f=B/'inputs'/date/s;f.mkdir(parents=True,exist_ok=True)
 if (f/'summary.json').exists():return
 try:
  end=int(datetime.fromisoformat(date+'T23:59:59+00:00').timestamp());start=end-370*86400
  u='https://query1.finance.yahoo.com/v8/finance/chart/'+quote(s,safe='')+f'?interval=1d&period1={start}&period2={end}&events=div%2Csplits'
  p=f/'chart.json'
  if p.exists():raw=p.read_bytes();receipt=json.loads((f/'price_receipt.json').read_text())
  else:raw,receipt=fetch(u,f/'raw');p.write_bytes(raw);dump(f/'price_receipt.json',receipt)
  r=json.loads(raw)['chart']['result'][0];q=r['indicators']['quote'][0];rows=[]
  for i,t in enumerate(r.get('timestamp',[])):
   day=datetime.fromtimestamp(t,timezone.utc).astimezone(__import__('zoneinfo').ZoneInfo('Asia/Seoul' if item['market']=='KR' else 'America/New_York')).date().isoformat()
   if day>date:raise ValueError('FUTURE_BAR')
   rows.append({'timestamp':datetime.fromtimestamp(t,timezone.utc).isoformat(),'date':day,**{k:q[k][i] for k in ['open','high','low','close','volume']}})
  x=pd.DataFrame(rows);good=x.dropna(subset=['open','high','low','close','volume']);good=good[(good[['open','high','low','close']]>0).all(axis=1)&(good.volume>=0)];good=good[(good.high>=good[['open','close','low']].max(axis=1))&(good.low<=good[['open','close','high']].min(axis=1))]
  x.to_csv(f/'all_bars.csv',index=False);good.to_csv(f/'bars.csv',index=False);assert len(good)>=64,'NO_64_DATED_BARS';assert (pd.Timestamp(date)-pd.Timestamp(good.date.iloc[-1])).days<=4,'STALE'
  gate=equity_revision_gate(good.assign(value_approx=good.close*good.volume).rename(columns={k:'raw_'+k for k in ['open','high','low','close']}),s,f,receipt)
  result={**item,'asof':date,'status':'PRICE_ELIGIBLE','last_close':float(good.close.iloc[-1]),'last_date':good.date.iloc[-1],'momentum63':float(good.close.iloc[-1]/good.close.iloc[-64]-1),'vol63':float(good.close.pct_change().tail(63).std()*np.sqrt(252)),'adv20_local':float((good.close*good.volume).tail(20).mean()),'price_hash':sha(p),'gate':gate,'quality':'PARTIAL_REDOWNLOADED_PRICE_NO_HISTORICAL_RECEIPT'}
  if item['market']=='KR':
   sp=f/'shares.json'
   if sp.exists():z=json.loads(sp.read_text())
   else:z=c._request('stockTotqySttus.json',{'corp_code':item['corp_code'],'bsns_year':date[:4],'reprt_code':'11014' if date[:4]=='2024' else '11013'});dump(sp,z)
   dated=[v for v in z.get('list',[]) if v.get('rcept_no','9999')[:8]<=date.replace('-','') and v.get('se')=='보통주']
   def num(v):
    try:return int(v.replace(',',''))
    except:return 0
   shares=sum(num(v.get('istc_totqy','')) for v in dated);cap=shares*result['last_close'];result.update(dated_report_shares=shares,dated_share_accessions=[v['rcept_no'] for v in dated],cap_proxy=cap,size_status='PASS_DATED_REPORTED_SHARES_PROXY' if cap>=500e9 else 'FAIL_OR_UNKNOWN_SIZE')
  dump(f/'summary.json',result);print(date,s,result['status'],result['size_status'],flush=True)
 except Exception as e:dump(f/'summary.json',{**item,'asof':date,'status':'BLOCKED','error_type':type(e).__name__,'reason':str(e)[:100] if isinstance(e,AssertionError) else None});print(date,s,'BLOCKED',type(e).__name__,flush=True)
tasks=[]
for date in ['2024-11-29','2025-06-30']:
 for market in ['US','KR']:
  for x in json.loads((B/'cohorts'/date/('US.json' if market=='US' else 'KR_mainboard_v2.json')).read_text()):tasks.append((date,x))
with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(collect,tasks))
