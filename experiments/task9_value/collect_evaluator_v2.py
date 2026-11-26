"""Supported200-bar pagination for only the already sealed14 issuers."""
from pathlib import Path
import sys,json,hashlib
import pandas as pd
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'))
from quant_harness.investment.equities import load_environment
from quant_harness.investment.operations_data import strict_rows
from quant_harness.v72_integration_ready.toss_openapi import TossOpenApiClient
load_environment(R);c=TossOpenApiClient();B=R/'runtime/task9_value';assert len(json.loads((B/'decision_seals.json').read_text()))==3
items={}
for y in [2021,2022,2023]:
 for x in json.loads((B/'decisions'/(str(y)+'.json')).read_text())['decision']['companies']:items[x['symbol']]=x['market']
for s,m in items.items():
 folder=B/'evaluator_only'/s;p=folder/'receipt_v2.json'
 if p.exists():continue
 zone='Asia/Seoul' if m=='KR' else 'America/New_York';offset='+09:00' if m=='KR' else '-05:00';before='2024-12-10T00:00:00'+offset;frames=[];receipts=[]
 try:
  for page in range(5):
   q={'symbol':s.split('.')[0] if m=='KR' else s,'interval':'1d','count':200,'before':before,'adjusted':'false'};rawp=folder/('page_'+str(page)+'.json')
   if rawp.exists():raw=json.loads(rawp.read_text())
   else:raw=c._request('GET',c.endpoint_map.candles_path,query=q);rawp.write_text(json.dumps(raw,sort_keys=True))
   f=strict_rows(raw,s,'KRW' if m=='KR' else 'USD',zone,'2024-12-09');assert len(f)>0;frames.append(f);receipts.append({'query':q,'sha256':hashlib.sha256(rawp.read_bytes()).hexdigest(),'rows':len(f)})
   if f.date.min()<='2021-11-30':break
   new=f.date.min()+'T00:00:00'+offset;assert new<before,'pagination stalled';before=new
  full=pd.concat(frames).sort_values('date');duplicates=full[full.duplicated('date',keep=False)]
  for d,g in duplicates.groupby('date'):assert len(g[['open','high','low','close','volume']].drop_duplicates())==1,'revision conflict'
  full=full.drop_duplicates('date');full.to_csv(folder/'bars.csv',index=False);p.write_text(json.dumps({'status':'SAVED','pages':receipts,'rows':len(full),'first':full.date.min(),'last':full.date.max()},indent=2));print(s,'SAVED',len(full),full.date.min(),flush=True)
 except Exception as e:p.write_text(json.dumps({'status':'FAILED','pages':receipts,'error_type':type(e).__name__}));print(s,type(e).__name__,flush=True)
