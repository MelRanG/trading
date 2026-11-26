"""Read archived Task3 files only. No DB, network, model or Factory calls."""
from pathlib import Path
import json,hashlib,sys
import pandas as pd
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'))
from quant_harness.investment.equities import normalize_chart,settings
from quant_harness.investment.research import digest
OUT=Path('/home/ansy/app/quant-diligence/vibe-work/inputs');OUT.mkdir(parents=True,exist_ok=True)
cfg=settings(ROOT);manifest={'purpose':'TASK6_PRE_USER_AUTHORIZED_ISOLATED_DIAGNOSTIC_NOT_FACTORY_PROMOTION','vibe_commit':'0025531f005d4a7aac3fb884cda2fba9318e7158',
 'candidate':'alpha101_012','candidate_reason':'One fixed published price-volume reversal factor, no performance-based selection','mapping':'Positive values ranked, top4 at20% each; nonpositive cash; D-1, long-only; same execution for all.',
 'contract':cfg,'contract_hash':digest(cfg),'parameter_search':0,'markets':{},'limitations':['Current survivor seeds','Repeated history is not independent holdout','Adjustment/dividend conventions not independently certified','Native engine costs differ and must not be ranked against common execution results']}
for market,folder in [('US',ROOT/'runtime/task3/us/final'),('KR',ROOT/'runtime/task3/kr/run3')]:
 comparison=json.loads((folder/'comparison/comparison.json').read_text());names=cfg[market]['seed_symbols']+[cfg[market]['benchmark']];frames={};raws={}
 if market=='US':
  for receipt_path in (folder/'prices').glob('*.receipt.json'):
   receipt=json.loads(receipt_path.read_text());raw=folder/'prices'/(receipt['source_hash']+'.raw');payload=json.loads(raw.read_bytes());symbol=payload['chart']['result'][0]['meta']['symbol']
   if symbol not in names:continue
   if hashlib.sha256(raw.read_bytes()).hexdigest()!=receipt['source_hash']:raise ValueError('raw hash mismatch')
   frame,_=normalize_chart(payload,symbol);frame['date']=pd.to_datetime(frame.timestamp,utc=True).dt.tz_convert('America/New_York').dt.strftime('%Y-%m-%d');frames[symbol]=frame;raws[symbol]={'path':str(raw.relative_to(ROOT)),'sha256':receipt['source_hash'],'available_at':receipt['available_at']}
 else:
  for symbol in names:
   raw=folder/'toss_stocks'/(symbol.split('.')[0]+'.reference.csv');frame=pd.read_csv(raw);frames[symbol]=frame;raws[symbol]={'path':str(raw.relative_to(ROOT)),'sha256':hashlib.sha256(raw.read_bytes()).hexdigest(),'available_at':str(frame.retrieved_at.iloc[0])}
 entries={};dest=OUT/market;dest.mkdir(exist_ok=True)
 for symbol,frame in frames.items():
  frame=frame[frame.date<=comparison['end']].copy();frame=frame[['date','open','high','low','close','volume','value_approx']]
  path=dest/(symbol+'.csv')
  if path.exists():
   expected=frame.to_csv(index=False).encode()
   if path.read_bytes()!=expected:raise ValueError('immutable export conflict')
  else:frame.to_csv(path,index=False)
  entries[symbol]={'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'rows':len(frame),'source':raws[symbol]}
 manifest['markets'][market]={'start':comparison['start'],'end':comparison['end'],'sessions':comparison['sessions'],'symbols':cfg[market]['seed_symbols'],'benchmark':cfg[market]['benchmark'],'files':entries,'original_comparison_hash':digest(comparison)}
path=OUT/'preregistration.json'
if path.exists() and json.loads(path.read_text())!=manifest:raise ValueError('immutable preregistration conflict')
path.write_text(json.dumps(manifest,indent=2));(ROOT/'runtime/task6_pre/evidence/preregistration.json').write_bytes(path.read_bytes())
print(json.dumps({'input_hash':digest(manifest),'markets':{k:v['sessions'] for k,v in manifest['markets'].items()}},indent=2))
