from common import *
import pandas as pd,numpy as np,ast,threading
from concurrent.futures import ThreadPoolExecutor
from quant_harness.investment.equities import fetch
from quant_harness.v87_actual_data_ingestion.engine import ProviderBatch,_validate_batch,_revision_audit
freeze(B/'price_resolution_contract.json',{'before_signal_or_economic_evaluation':True,'OHLC':'Require2ofYahoo/Naver/Toss within0.5%, fixedpairsYahooNaver,TossNaver,YahooToss; lastvaluechosen, nevermean. Geometryrevalidated. MissingremainsNaN.','volume':'Tossobservedvolume, positiveandfinite required; usedasproviderobservationnotexchange-certified; sourcevolumehistoriespreserved.','source_tag':'TASK10_RECONCILED_RAW_OBSERVED','unresolved_action':'Dailypriceeligibilityblockedfromactioneventuntilindependentreconciliation; no universe removal selectedusinglaterreturns','operating_contract_changes':False})
lock=threading.Lock()
def reserve(s):
 with lock:
  p=B/'data_requests.jsonl';n=len(p.read_text().splitlines());assert n<200
  with p.open('a') as f:f.write(json.dumps({'sequence':n+1,'provider':'NAVER','symbol':s,'at':datetime.datetime.now(datetime.timezone.utc).isoformat()})+'\n')
def run(a):
 s=a['symbol'];f=B/'data'/s;out=f/'resolution.json'
 if out.exists():return
 frames={};yp=f/'yahoo.csv';tp=f/'all_toss.csv'
 if yp.exists():frames['YAHOO']=pd.read_csv(yp).set_index('date')
 if tp.exists():frames['TOSS']=pd.read_csv(tp).set_index('date')
 if a['market']=='KR' and a['role']=='stock':
  p=f/'naver.bin'
  try:
   if not p.exists():reserve(s);raw,r=fetch('https://api.finance.naver.com/siseJson.naver?symbol='+s[:6]+'&requestType=1&startTime=20250701&endTime=20261113&timeframe=day',f/'naver_raw');p.write_bytes(raw);dump(f/'naver_receipt.json',r)
   try:t=p.read_bytes().decode('utf-8')
   except UnicodeDecodeError:t=p.read_bytes().decode('cp949')
   x=ast.literal_eval(t.strip());nf=pd.DataFrame([{'date':pd.Timestamp(str(r[0])).date().isoformat(),'open':r[1],'high':r[2],'low':r[3],'close':r[4],'volume':r[5]} for r in x[1:]]);nf.to_csv(f/'naver.csv',index=False);frames['NAVER']=nf.set_index('date')
  except Exception as e:dump(f/'naver_failure.json',{'error':type(e).__name__})
 if not frames:return
 dates=frames.get('TOSS',frames['YAHOO']).index;proof=[];rows=[]
 for d in dates:
  row={'date':d,'symbol':a['alias']};pr={'date':d}
  for field in ['open','high','low','close']:
   row[field]=np.nan;pr[field]=None
   for aa,bb in [('YAHOO','NAVER'),('TOSS','NAVER'),('YAHOO','TOSS')]:
    A,D=frames.get(aa),frames.get(bb)
    if A is None or D is None or d not in A.index or d not in D.index:continue
    v,w=float(A.loc[d,field]),float(D.loc[d,field])
    if np.isfinite(v+w) and min(v,w)>0 and abs(v/w-1)<=.005:row[field]=w;pr[field]={'pair':[aa,bb],'values':[v,w]};break
  row['volume']=float(frames['TOSS'].loc[d,'volume']) if 'TOSS' in frames and d in frames['TOSS'].index else np.nan
  if not np.isfinite([row[k] for k in ['open','high','low','close','volume']]).all() or row['volume']<=0 or row['high']<max(row['open'],row['close'],row['low']) or row['low']>min(row['open'],row['close'],row['high']):
   for k in ['open','high','low','close','volume']:row[k]=np.nan
   pr['status']='UNRESOLVED_NO_IMPUTATION'
  else:pr['status']='TWO_PROVIDER_OHLC'
  rows.append(row);proof.append(pr)
 df=pd.DataFrame(rows);df.to_csv(f/'resolved.csv',index=False);good=df.dropna();cfg=json.loads((R/'config/task3_equity_price_contract.json').read_text());cfg['provider_contract']['required_source_tag']='TASK10_RECONCILED_RAW_OBSERVED'
 recs=good.assign(ticker=s.zfill(6),value_approx=good.close*good.volume).to_dict('records');batch=ProviderBatch('TASK10_TWO_PROVIDER',s.zfill(6),tuple(recs),False,'TASK10_RECONCILED_RAW_OBSERVED',datetime.datetime.now(datetime.timezone.utc).isoformat(),{})
 valid=_validate_batch(batch,cfg);audit=_revision_audit(valid,f/'resolved.reference.csv',cfg)
 if not (f/'resolved.reference.csv').exists():valid.to_csv(f/'resolved.reference.csv',index=False)
 freeze(out,{'rows':len(df),'valid_rows':len(good),'missing_rows':int(df.close.isna().sum()),'policy_hash':sha(B/'price_resolution_contract.json'),'V87':audit,'field_provenance':proof,'source_hashes':{k:sha(f/('yahoo.csv' if k=='YAHOO' else 'naver.csv' if k=='NAVER' else 'all_toss.csv')) for k in frames}});print(s,len(good),len(df),'VALID',flush=True)
with ThreadPoolExecutor(max_workers=4) as p:list(p.map(run,json.loads((B/'universe.json').read_text())))
