"""Guarded evaluator-only prices: sealed assets, bounded dates, original collectors."""
from protocol import *
from datetime import datetime,timezone
from urllib.parse import quote
from zoneinfo import ZoneInfo
import pandas as pd,ast,shutil
from concurrent.futures import ThreadPoolExecutor
from quant_harness.investment.equities import fetch,equity_revision_gate,load_environment
from quant_harness.investment.operations_data import strict_rows
from quant_harness.v72_integration_ready.toss_openapi import TossOpenApiClient
load_environment(R);tc=TossOpenApiClient();assets=asset_list()
if not (B/'future_collection_authorized.json').exists():freeze(B/'future_collection_authorized.json',{'research_seal_hash':sha(B/'research_seal.json'),'asset_list_hash':digest(assets),'evaluated_after_both_seals':True,'first_invoked_UTC':datetime.now(timezone.utc).isoformat()})

def collect(a):
 s=a['symbol'];m=a['market'];f=B/'evaluator_only'/s;f.mkdir(parents=True,exist_ok=True);end=f/'quality.json'
 if end.exists():return
 ql={'symbol':s,'market':m,'identity':a,'status':'PARTIAL','failures':[],'first_observed_now':True,'price_not_total_return':True};data={}
 try:
  p=f/'chart.json'
  old=R/'runtime/task9_3/evaluator_only'/s
  if not p.exists():
   if (old/'chart.json').exists():shutil.copyfile(old/'chart.json',p);dump(f/'reuse.json',{'source_path':str(old/'chart.json'),'sha256':sha(old/'chart.json'),'read_after_seal':True})
   else:
    start=int(datetime.fromisoformat('2026-05-14T00:00:00+00:00').timestamp());stop=int(datetime.fromisoformat('2026-11-14T00:00:00+00:00').timestamp());raw,receipt=fetch('https://query1.finance.yahoo.com/v8/finance/chart/'+quote(s,safe='')+f'?interval=1d&period1={start}&period2={stop}&events=div%2Csplits',f/'raw');p.write_bytes(raw);dump(f/'receipt.json',receipt)
  z=json.loads(p.read_text())['chart']['result'][0];q=z['indicators']['quote'][0];rows=[];tz='Asia/Seoul' if m=='KR' else 'America/New_York' if m=='US' else z['meta'].get('exchangeTimezoneName','UTC')
  for i,t in enumerate(z['timestamp']):rows.append({'timestamp':datetime.fromtimestamp(t,timezone.utc).isoformat(),'date':datetime.fromtimestamp(t,timezone.utc).astimezone(ZoneInfo(tz)).date().isoformat(),**{k:q[k][i] for k in ['open','high','low','close','volume']}})
  yf=pd.DataFrame(rows);yf=yf[(yf.date>='2026-05-18')&(yf.date<='2026-11-13')];assert not yf.date.duplicated().any();yf.to_csv(f/'yahoo.csv',index=False);data['YAHOO']=yf.set_index('date');ql['meta']={k:z['meta'].get(k) for k in ['symbol','longName','shortName','currency','exchangeName','firstTradeDate','instrumentType']};ql['events']=z.get('events',{})
  if a['currency']!=z['meta'].get('currency'):raise ValueError('CURRENCY_IDENTITY_MISMATCH')
  receipt=json.loads((f/'receipt.json' if (f/'receipt.json').exists() else old/'receipt.json').read_text());ql['V87']={'status':'NOT_APPLICABLE_INDEX'} if s.startswith('^') else equity_revision_gate(yf.dropna().assign(value_approx=yf.close*yf.volume).rename(columns={k:'raw_'+k for k in ['open','high','low','close']}),s,f,receipt)
 except Exception as e:ql['failures'].append({'provider':'YAHOO','error_type':type(e).__name__,'reason':str(e)[:130] if isinstance(e,(AssertionError,ValueError)) else None})
 if m in ['US','KR'] and not s.startswith('^'):
  try:
   p=f/'toss.json';old=R/'runtime/task9_3/evaluator_only'/s/'toss.json'
   if not p.exists():
    if old.exists():shutil.copyfile(old,p)
    else:dump(p,tc._request('GET',tc.endpoint_map.candles_path,query={'symbol':s.split('.')[0] if m=='KR' else s,'interval':'1d','count':180,'before':'2026-11-14T00:00:00'+('+09:00' if m=='KR' else '-05:00'),'adjusted':'false'}))
   tf=strict_rows(json.loads(p.read_text()),s,a['currency'],tz,'2026-11-13');tf=tf[(tf.date>='2026-05-18')&(tf.date<='2026-11-13')];tf.to_csv(f/'toss.csv',index=False);data['TOSS']=tf.set_index('date')
  except Exception as e:ql['failures'].append({'provider':'TOSS','error_type':type(e).__name__})
 if m=='KR' and not s.startswith('^'):
  try:
   p=f/'naver.txt'
   if not p.exists():raw,_=fetch('https://api.finance.naver.com/siseJson.naver?symbol='+s[:6]+'&requestType=1&startTime=20260518&endTime=20261113&timeframe=day',f/'naver_raw');p.write_bytes(raw)
   z=ast.literal_eval(p.read_text().strip());nf=pd.DataFrame([{'date':pd.Timestamp(str(v[0])).date().isoformat(),'open':v[1],'high':v[2],'low':v[3],'close':v[4],'volume':v[5]} for v in z[1:]]);nf.to_csv(f/'naver.csv',index=False);data['NAVER']=nf.set_index('date')
  except Exception as e:ql['failures'].append({'provider':'NAVER','error_type':type(e).__name__})
 if m=='KR' and s=='^KS11':
  p=R/'runtime/task9_3/benchmark_verification/KR.json'
  if p.exists():
   z=pd.DataFrame(json.loads(p.read_text()));z['date']=pd.to_datetime(z.timestamp,utc=True).dt.tz_convert('Asia/Seoul').dt.date.astype(str);data['TOSS']=z.set_index('date');ql['secondary_index_source']={'path':str(p),'sha256':sha(p)}
 rows=[];proof=[]
 dates=sorted(set(d for df in data.values() for d in df.index if '2026-05-18'<=d<='2026-11-13'))
 for d in dates:
  row={'date':d};pr={'date':d}
  for k in ['open','close']:
   vals={n:float(df.loc[d,k]) for n,df in data.items() if d in df.index and pd.notna(df.loc[d,k])};v,note=choose_observation(vals)
   if (s.startswith('^') and m=='US') or m not in ['US','KR']:
    # Single-source comparison remains explicitly unverified, not exchange-certified.
    v=vals.get('YAHOO');note={'status':'SINGLE_SOURCE_UNVERIFIED','values':vals}
   row[k]=v;pr[k]=note
  rows.append(row);proof.append(pr)
 if rows:pd.DataFrame(rows).to_csv(f/'bars.csv',index=False)
 ql['rows']=len(rows);ql['field_provenance']=proof;ql['files']={p.name:sha(p) for p in f.iterdir() if p.is_file()};dump(end,ql);print(s,len(rows),'failures',len(ql['failures']),flush=True)
with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(collect,assets))
