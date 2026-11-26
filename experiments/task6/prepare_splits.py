"""Freeze accepted source files and physically separate worker/evaluator inputs."""
from pathlib import Path
import json,hashlib
import pandas as pd
ROOT=Path(__file__).resolve().parents[2];folder=ROOT/'runtime/task6';manifest=json.loads((folder/'data/manifest.json').read_text());contract=json.loads((Path(__file__).parent/'research_contract.json').read_text())
train=folder/'worker_train';validation=folder/'evaluator_validation';final=folder/'private_final'
for p in (train,validation,final):p.mkdir(parents=True,exist_ok=True,mode=0o700)
info={'contract_hash':manifest['contract_hash'],'train_end':contract['train_end'],'validation_end':contract['validation_end'],'final_start':contract['final_start'],'markets':{},'excluded':[]}
for market in ('US','KR'):
 m=manifest['markets'][market];aliases={};parts={};index=0
 for symbol,entry in m['symbols'].items():
  if entry['status']!='ACCEPTED':info['excluded'].append({'market':market,'symbol':symbol,'reason':entry.get('reason')});continue
  source=folder/'data/accepted'/(symbol+'.csv')
  if hashlib.sha256(source.read_bytes()).hexdigest()!=entry['sha256']:raise ValueError('source hash mismatch')
  benchmark=symbol==contract['benchmarks'][market]
  if benchmark:alias=market+'_BENCHMARK'
  else:index+=1;alias=f'{market}{index:03}'
  aliases[alias]=symbol;frame=pd.read_csv(source);frame['symbol']=alias
  splitframes={'train':frame[frame.date<=contract['train_end']],'validation':frame[(frame.date>contract['train_end'])&(frame.date<=contract['validation_end'])], 'final':frame[frame.date>=contract['final_start']]}
  counts={}
  for name,part in splitframes.items():
   destination={'train':train,'validation':validation,'final':final}[name]/(alias+'.csv');part.to_csv(destination,index=False);counts[name]={'rows':len(part),'sha256':hashlib.sha256(destination.read_bytes()).hexdigest()}
  parts[alias]={'counts':counts,'source_sha256':entry['sha256'],'benchmark_only':benchmark}
 info['markets'][market]={'assets':index,'aliases':aliases,'parts':parts}
# Names are omitted from worker metadata; no validation/final values or returns.
worker={'train_end':contract['train_end'],'source':'newly observed public adjusted OHLCV backfill','universe_type':'current named cohort, not historical PIT membership','markets':{m:{'assets':v['assets'],'symbols':[a for a,p in v['parts'].items() if not p['benchmark_only']]} for m,v in info['markets'].items()},
 'columns':['date','open','high','low','close','volume','value_approx'],'target':'factor at close t predicts return close(t+1)/open(t+1)-1; validation labels computed in a separate worker; final never exposed','risk':'long-only, top4 positive values at20% each, 80% gross, D1 next-open fixed costs; no data/parameter search after final'}
(train/'README.json').write_text(json.dumps(worker,indent=2));(folder/'split_manifest.json').write_text(json.dumps(info,indent=2));print(json.dumps({'markets':{m:v['assets'] for m,v in info['markets'].items()},'excluded':info['excluded'],'final_mounted_to_research':False},indent=2))
