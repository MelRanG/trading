from common import *
import io,json
from datetime import datetime,timezone
sys.path.insert(0,'/home/ansy/app/quant-diligence/task6-quanta-env/lib/python3.12/site-packages')
from pypdf import PdfReader
from quant_harness.investment.equities import fetch,equity_revision_gate,load_environment
from quant_harness.investment.company_outcomes import Document
from quant_harness.investment.operations_data import strict_rows
from quant_harness.v72_integration_ready.toss_openapi import TossOpenApiClient
plans=[('SAMYANG_Q3','2026-11-06','https://www.samyangfoods.com/upload/ir/20261106/20261106163220235008.pdf'),('DECK_10Q','2026-10-29','https://ir.deckers.com/sec-filings/all-sec-filings/content/0001628280-26-068116/deck-20260930.htm')]
for name,pub,url in plans:
 f=B/'sources'/name;f.mkdir(parents=True,exist_ok=True)
 if (f/'receipt.json').exists():continue
 try:
  raw,r=fetch(url,f/'raw');(f/'original.bin').write_bytes(raw)
  if raw.startswith(b'%PDF'):text='\n'.join(p.extract_text(extraction_mode='layout') or '' for p in PdfReader(io.BytesIO(raw)).pages)
  else:d=Document();d.feed(raw.decode());text='\n'.join(d.text)
  (f/'original.txt').write_text(text);dump(f/'receipt.json',{'status':'SAVED','published':pub,'url':url,'receipt':r,'raw_sha256':sha(f/'original.bin'),'text_sha256':sha(f/'original.txt')});print(name,'SAVED',len(text),flush=True)
 except Exception as e:dump(f/'receipt.json',{'status':'FAILED','error_type':type(e).__name__});print(name,'FAILED',type(e).__name__,flush=True)
load_environment(R);c=TossOpenApiClient();import pandas as pd,numpy as np
for s,m in [('PH','US'),('DECK','US'),('033780.KS','KR'),('003230.KS','KR'),('^GSPC','US'),('^KS11','KR')]:
 f=B/'current_prices'/s;f.mkdir(parents=True,exist_ok=True)
 if (f/'summary.json').exists():continue
 try:
  raw,r=fetch('https://query1.finance.yahoo.com/v8/finance/chart/'+s.replace('^','%5E')+'?range=1y&interval=1d&events=div%2Csplits',f/'raw');(f/'chart.json').write_bytes(raw);z=json.loads(raw)['chart']['result'][0];q=z['indicators']['quote'][0];rows=[]
  for i,t in enumerate(z['timestamp']):
   if t>datetime.now(timezone.utc).timestamp():raise ValueError('FUTURE_PRICE')
   day=datetime.fromtimestamp(t,timezone.utc).astimezone(__import__('zoneinfo').ZoneInfo('Asia/Seoul' if m=='KR' else 'America/New_York')).date().isoformat();rows.append({'date':day,'timestamp':datetime.fromtimestamp(t,timezone.utc).isoformat(),**{k:q[k][i] for k in ['open','high','low','close','volume']}})
  frame=pd.DataFrame(rows).dropna();frame=frame[(frame[['open','high','low','close']]>0).all(axis=1)&(frame.volume>=0)];assert (pd.Timestamp(datetime.now(timezone.utc).date())-pd.Timestamp(frame.date.iloc[-1])).days<=4,'STALE';frame.to_csv(f/'bars.csv',index=False)
  if not s.startswith('^'):
   gate=equity_revision_gate(frame.assign(value_approx=frame.close*frame.volume).rename(columns={k:'raw_'+k for k in ['open','high','low','close']}),s,f,r);payload=c._request('GET',c.endpoint_map.candles_path,query={'symbol':s.split('.')[0] if m=='KR' else s,'interval':'1d','count':200,'adjusted':'false'});dump(f/'toss.json',payload);tf=strict_rows(payload,s,'KRW' if m=='KR' else 'USD','Asia/Seoul' if m=='KR' else 'America/New_York',datetime.now(timezone.utc).date().isoformat());tf.to_csv(f/'toss_bars.csv',index=False);assert frame.date.iloc[-1]==tf.date.iloc[-1],'PROVIDER_DATE_MISMATCH';assert abs(float(tf.close.iloc[-1]/frame.close.iloc[-1])-1)<.005,'PROVIDER_PRICE_MISMATCH'
  dump(f/'summary.json',{'status':'SAVED','symbol':s,'market':m,'currency':'KRW' if m=='KR' else 'USD','price':float(frame.close.iloc[-1]),'price_date':frame.date.iloc[-1],'source_hash':r['source_hash'],'observed_at':r['available_at'],'momentum63':float(frame.close.iloc[-1]/frame.close.iloc[-64]-1),'vol63':float(frame.close.pct_change().tail(63).std()*np.sqrt(252)),'corporate_actions':z.get('events',{}),'quant_origin':'CAUSAL_MOM63_REFERENCE_NOT_VERIFIED_QUANTA_RD_ALPHA'});print(s,'PRICE_SAVED',flush=True)
 except Exception as e:dump(f/'summary.json',{'status':'BLOCKED','symbol':s,'error_type':type(e).__name__,'reason':str(e)[:80] if isinstance(e,(AssertionError,ValueError)) else None});print(s,'BLOCKED',type(e).__name__,flush=True)
