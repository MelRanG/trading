from common import *
import pandas as pd
from quant_harness.investment.equities import load_environment
from quant_harness.v72_integration_ready.toss_openapi import TossOpenApiClient
load_environment(R);client=TossOpenApiClient();rows=[]
for m,index,code,tz in [('KR','^KS11','KOSPI','Asia/Seoul'),('US','^GSPC','SP500','America/New_York')]:
 p=B/'benchmark_verification'/(m+'.json');p.parent.mkdir(exist_ok=True)
 try:
  if p.exists():raw=json.loads(p.read_text())
  else:
   raw,nextpage=client.get_market_indicator_candles_page(code,count=180,before='2026-11-14T00:00:00'+('+09:00' if m=='KR' else '-05:00'));dump(p,raw)
  frame=pd.DataFrame(raw)
  for field in ['open','close']:frame[field]=pd.to_numeric(frame[field],errors='raise')
  frame['date']=pd.to_datetime(frame.timestamp,utc=True).dt.tz_convert(tz).dt.date.astype(str);y=pd.read_csv(B/'evaluator_only'/index/'bars.csv');z=y.merge(frame,on='date',suffixes=('_y','_t'));assert len(z)>=115;error={k:float((z[k+'_y']/z[k+'_t']-1).abs().max()) for k in ['open','close']};first=z[z.date=='2026-05-18'].iloc[0];last=z[z.date=='2026-11-13'].iloc[0];rows.append({'market':m,'code':code,'status':'MATCH' if max(error.values())<.005 else 'CONFLICT','max_relative_error':error,'matched_days':len(z),'independent_return':float(last.close_t/first.open_t-1),'source_hash':sha(p),'not_total_return':True})
 except Exception as e:rows.append({'market':m,'code':code,'status':'UNVERIFIED','error_type':type(e).__name__,'no_response_substitution':True})
freeze(B/'benchmark_verification/result_v2.json',rows);print(rows)
