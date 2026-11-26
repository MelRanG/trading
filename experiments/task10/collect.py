from common import *
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from urllib.parse import quote
import pandas as pd,threading,shutil
from quant_harness.investment.equities import load_environment,fetch,equity_revision_gate
from quant_harness.investment.operations_data import strict_rows
from quant_harness.v72_integration_ready.toss_openapi import TossOpenApiClient
load_environment(R);tc=TossOpenApiClient();lock=threading.Lock();manifest=json.loads((R/'runtime/task6/split_manifest.json').read_text());assets=[]
for m in ['US','KR']:
 for a,s in manifest['markets'][m]['aliases'].items():assets.append({'alias':a,'symbol':s,'market':m,'role':'ETF' if 'BENCHMARK' in a else 'stock'})
freeze(B/'universe.json',assets)
def reserve(info):
 with lock:
  p=B/'data_requests.jsonl';n=len(p.read_text().splitlines()) if p.exists() else 0;assert n<C['data']['max_data_requests'],'DATA_BUDGET'
  with p.open('a') as f:f.write(json.dumps({'sequence':n+1,'at':datetime.now(timezone.utc).isoformat(),**info})+'\n')
def run(a):
 s=a['symbol'];m=a['market'];tz='Asia/Seoul' if m=='KR' else 'America/New_York';f=B/'data'/s;f.mkdir(parents=True,exist_ok=True)
 if (f/'quality.json').exists():return
 pieces=[];fail=[]
 for label,before,count in [('prefix','2026-05-16T00:00:00'+('+09:00' if m=='KR' else '-04:00'),200),('evaluator','2026-11-14T00:00:00'+('+09:00' if m=='KR' else '-05:00'),180)]:
  p=f/(label+'.json')
  try:
   if not p.exists():reserve({'provider':'TOSS','symbol':s,'stage':label});dump(p,tc._request('GET',tc.endpoint_map.candles_path,query={'symbol':s.split('.')[0] if m=='KR' else s,'interval':'1d','count':count,'before':before,'adjusted':'false'}))
   d=strict_rows(json.loads(p.read_text()),s,'KRW' if m=='KR' else 'USD',tz,'2026-05-15' if label=='prefix' else '2026-11-13');d.to_csv(f/(label+'.csv'),index=False);pieces.append(d)
  except Exception as e:fail.append({'provider':'TOSS','stage':label,'error':type(e).__name__})
 try:
  p=f/'yahoo.json';t1=int(datetime.fromisoformat('2025-07-01T00:00:00+00:00').timestamp());t2=int(datetime.fromisoformat('2026-11-14T00:00:00+00:00').timestamp())
  if not p.exists():reserve({'provider':'YAHOO','symbol':s,'stage':'evaluator_validation'});raw,r=fetch('https://query1.finance.yahoo.com/v8/finance/chart/'+quote(s,safe='')+f'?interval=1d&period1={t1}&period2={t2}&events=div%2Csplits',f/'raw');p.write_bytes(raw);dump(f/'yahoo_receipt.json',r)
  z=json.loads(p.read_text())['chart']['result'][0];q=z['indicators']['quote'][0];rows=[]
  for i,t in enumerate(z['timestamp']):rows.append({'timestamp':datetime.fromtimestamp(t,timezone.utc).isoformat(),'date':datetime.fromtimestamp(t,timezone.utc).astimezone(ZoneInfo(tz)).date().isoformat(),**{k:q[k][i] for k in ['open','high','low','close','volume']}})
  yf=pd.DataFrame(rows).dropna();yf.to_csv(f/'yahoo.csv',index=False);gate=equity_revision_gate(yf.assign(value_approx=yf.close*yf.volume).rename(columns={k:'raw_'+k for k in ['open','high','low','close']}),s,f,json.loads((f/'yahoo_receipt.json').read_text()));meta=z['meta'];events=z.get('events',{})
 except Exception as e:fail.append({'provider':'YAHOO','error':type(e).__name__});yf=None;events={};gate=None;meta={}
 if pieces:
  d=pd.concat(pieces).sort_values('date');dups=d[d.date.duplicated(False)];conflicts=[]
  for date,g in dups.groupby('date'):
   if len(g[['open','close','volume']].drop_duplicates())>1:conflicts.append(date)
  d=d.drop_duplicates('date',keep='first');d.to_csv(f/'all_toss.csv',index=False)
  if yf is not None:
   j=d.merge(yf,on='date',suffixes=('_t','_y'));diff={k:float((j[k+'_t']/j[k+'_y']-1).abs().max()) for k in ['open','close']};j.to_csv(f/'cross_provider.csv',index=False)
  else:diff={}
 else:conflicts=[];diff={}
 freeze(f/'quality.json',{'asset':a,'failures':fail,'overlap_conflicts':conflicts,'cross_provider_max':diff,'declared_actions':events,'V87':gate,'meta':{k:meta.get(k) for k in ['symbol','currency','firstTradeDate','longName']},'scope':'NOMINAL_DIAGNOSTIC_NOT_FULL_EXCHANGE_PIT_OR_TR','sources':{p.name:sha(p) for p in f.iterdir() if p.is_file()}});print(s,'FAIL',len(fail),'diff',diff,'splits',len(events.get('splits',{})),flush=True)
with ThreadPoolExecutor(max_workers=4) as p:list(p.map(run,assets))
