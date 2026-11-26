"""Evaluator-only selected-name raw prices; never mounted in research worker."""
from pathlib import Path
import sys,json,hashlib
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'))
from quant_harness.investment.equities import load_environment
from quant_harness.investment.operations_data import strict_rows
from quant_harness.v72_integration_ready.toss_openapi import TossOpenApiClient
load_environment(R);c=TossOpenApiClient();B=R/'runtime/task9_value';assert len(json.loads((B/'decision_seals.json').read_text()))==3
items={}
for year in [2021,2022,2023]:
 for x in json.loads((B/'decisions'/(str(year)+'.json')).read_text())['decision']['companies']:items[x['symbol']]=x['market']
for s,m in items.items():
 folder=B/'evaluator_only'/s;folder.mkdir(parents=True,exist_ok=True);p=folder/'receipt.json'
 if p.exists():continue
 q={'symbol':s.split('.')[0] if m=='KR' else s,'interval':'1d','count':1000,'before':'2024-12-10T00:00:00'+('+09:00' if m=='KR' else '-05:00'),'adjusted':'false'}
 try:
  raw=c._request('GET',c.endpoint_map.candles_path,query=q);data=json.dumps(raw,sort_keys=True).encode();(folder/'raw.json').write_bytes(data);f=strict_rows(raw,s,'KRW' if m=='KR' else 'USD','Asia/Seoul' if m=='KR' else 'America/New_York','2024-12-09');f.to_csv(folder/'bars.csv',index=False);p.write_text(json.dumps({'status':'SAVED','query':q,'rows':len(f),'sha256':hashlib.sha256(data).hexdigest(),'first':f.date.iloc[0],'last':f.date.iloc[-1]},indent=2));print(s,'SAVED',len(f),f.date.iloc[0],flush=True)
 except Exception as e:p.write_text(json.dumps({'status':'FAILED','query':q,'error_type':type(e).__name__}));print(s,type(e).__name__,flush=True)
