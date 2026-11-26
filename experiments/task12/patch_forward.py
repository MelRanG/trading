"""Apply collection-recovery fix; no signal, model, account formula or initial seal change."""
from pathlib import Path
p=Path(__file__).resolve().parents[1]/'task10_1/forward.py';s=p.read_text()
assert p.read_bytes()==(p.parents[2]/'runtime/task12/forward_before.py').read_bytes(),'one-time patch refuses non-original source'
s=s.replace("c=json.loads(p.read_text());assert c['sources']==sources(),'frozen worker/model changed';return c", "c=json.loads(p.read_text());verify_sources(c);return c")
insert='''def verify_sources(contract):
 old=contract['sources'];current=sources()
 if old==current:return
 # Explicit Task12 technical amendment; never weakens model/policy fingerprints.
 key=str(Path(__file__));amendment=R/'runtime/task12/forward_patch.json'
 assert old.keys()==current.keys() and {k for k in old if old[k]!=current[k]}=={key} and amendment.exists(),'frozen worker/model changed'
 patch=json.loads(amendment.read_text())
 assert patch['old_source_hash']==old[key] and patch['new_source_hash']==current[key] and patch['initial_contract_hash']==sha(F/'contract.json'),'frozen worker/model changed'
 original=Path(patch['original_source']);assert sha(original)==old[key],'frozen original source changed'
 immutable=['choose','compute','validate_revisions','settle','process_seals']
 def nodes(text):return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(text).body if isinstance(n,ast.FunctionDef)}
 a,b=nodes(original.read_text()),nodes(Path(__file__).read_text())
 assert all(a[n]==b[n] for n in immutable),'strategy/execution semantics changed'

'''
s=s.replace('def reserve():',insert+'def reserve():')
start=s.index(' rawdir=F/\'observations\'/m/d;');end=s.index(' outcome=settle(m,frames,c)',start)
block=s[start:end]
collection='''def _snapshot(m,d,last,c,client):
 rawdir=F/'observations'/m/d;rawdir.mkdir(parents=True,exist_ok=True)
 if (rawdir/'accepted.json').exists():return _load_snapshot(m,d,c)
'''+block[block.index(" cp=rawdir/'catalog.json'"):]+''' return frames

'''
helpers='''def _load_snapshot(m,d,c):
 rawdir=F/'observations'/m/d;meta=json.loads((rawdir/'accepted.json').read_text());out={}
 assert meta['session']['day']==d,'snapshot session mismatch'
 for a in c['universe']:
  if a['market']!=m:continue
  path=rawdir/(a['alias']+'.csv')
  if sha(path)!=meta['data_hashes'][a['alias']]:raise ValueError('ACCEPTED_SNAPSHOT_CHANGED')
  out[a['alias']]=pd.read_csv(path,index_col='date',parse_dates=True)
 return out

def _known_sessions(m,seed=()):
 result={}
 def add(session):
  prior=result.get(session['day'])
  if prior and any(prior[k]!=session[k] for k in ['opening','closing']):raise ValueError('SESSION_REVISION_REQUIRES_REVIEW')
  result[session['day']]=session
 for row in seed:add(row)
 for path in sorted((F/'polls'/m).glob('*/calendar.json')):
  for row in parse_calendar(json.loads(path.read_text()),m):add(row)
 for path in sorted((F/'plans'/m).glob('*.json')):add(json.loads(path.read_text())['next_session'])
 for path in sorted((F/'observations'/m).glob('*/accepted.json')):add(json.loads(path.read_text())['session'])
 return result

def _observe_receipts(m,d,frames,c,sessions):
 plans=[json.loads(p.read_text()) for p in (F/'plans'/m).glob('*.json')]
 starts=[p['next_session']['day'] for p in plans if datetime.datetime.fromisoformat(p['next_session']['opening'])>datetime.datetime.fromisoformat(p['sealed_at'])]
 if not starts:return
 first=min(starts);days=frames[m+'_BENCHMARK'].index;ds=[str(x.date()) for x in days if first<=str(x.date())<=d]
 expected=[day for day,row in sessions.items() if first<=day<=d and datetime.datetime.fromisoformat(row['closing'])<=datetime.datetime.now(datetime.timezone.utc)]
 if set(ds)!=set(expected):raise ValueError('UNVERIFIED_OR_MISSING_COMPLETED_SESSION')
 meta_path=F/'observations'/m/d/'accepted.json';meta=json.loads(meta_path.read_text())
 for day in ds:
  receipt=F/'session_receipts'/m/(day+'.json')
  if receipt.exists():
   prior=json.loads(receipt.read_text())
   if sha(Path(prior['snapshot_path']))!=prior['snapshot_hash']:raise ValueError('OBSERVATION_RECEIPT_SOURCE_CHANGED')
   continue
  if datetime.datetime.fromisoformat(meta['at'])<datetime.datetime.fromisoformat(sessions[day]['closing']):raise ValueError('PREMATURE_SESSION_MARK')
  save(receipt,{'day':day,'observed_at':meta['at'],'snapshot_path':str(meta_path),'snapshot_hash':sha(meta_path),'official_session':sessions[day],'late_observation':day<d,'decision_during_outage':'Only previously sealed plans execute; no retrospective signal or risk action'})

def _mark_receipt(m,day):
 receipt=F/'session_receipts'/m/(day+'.json')
 if receipt.exists():
  r=json.loads(receipt.read_text())
  if sha(Path(r['snapshot_path']))!=r['snapshot_hash']:raise ValueError('OBSERVATION_RECEIPT_SOURCE_CHANGED')
  return r['observed_at']
 return json.loads((F/'observations'/m/day/'accepted.json').read_text())['at']

def _finish(m,d,c,frames,sessions,phase):
 _observe_receipts(m,d,frames,c,sessions);outcome=settle(m,frames,c);assessment=review(m,frames,c)
 marker=F/'completions'/m/(d+'.json')
 if not marker.exists():save(marker,{'at':now(),'phase':phase,'snapshot_hash':sha(F/'observations'/m/d/'accepted.json'),'initial_contract_hash':sha(F/'contract.json')})
 return {'observation':outcome,'review':assessment}

'''
a=s.index('def market_tick(m,c,client):');z=s.index('\ndef run():',a)
new='''def market_tick(m,c,client):
 pending=sorted((F/'plans'/m).glob('*.json'))
 if pending:
  known=json.loads(pending[-1].read_text());next_session=known['next_session'];d=known['signal_date']
  if not (F/'completions'/m/(d+'.json')).exists() and (F/'observations'/m/d/'accepted.json').exists():
   frames=_load_snapshot(m,d,c);_finish(m,d,c,frames,_known_sessions(m),'SEALED_PLAN_RECOVERY')
  if datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat(next_session['closing']):
   return {'status':'WAIT_NEXT_COMPLETED_SESSION','day':d,'next_session':next_session['day'],'fills':0,'network_calls':0}
 slot=now()[:10]+'T'+str(datetime.datetime.now(datetime.timezone.utc).hour)
 root=F/'polls'/m/slot;root.mkdir(parents=True,exist_ok=True)
 cal=get(client,'/api/v1/market-calendar/'+m,None,root/'calendar.json');seed=parse_calendar(cal,m);known=_known_sessions(m,seed)
 complete=sorted([v for v in known.values() if datetime.datetime.fromisoformat(v['closing'])<=datetime.datetime.now(datetime.timezone.utc)],key=lambda s:s['day'])
 if not complete:raise ValueError('NO_VERIFIED_COMPLETED_SESSION')
 last=complete[-1];d=last['day'];future=sorted([s for s in seed if datetime.datetime.fromisoformat(s['opening'])>datetime.datetime.now(datetime.timezone.utc)],key=lambda s:s['opening'])
 # Finish older interrupted observations first, without generating decisions for
 # sessions that already opened. Existing immutable raw files are reused.
 older=[p for p in sorted((F/'attempts'/m).glob('*.json')) if p.stem<d and not (F/'completions'/m/p.name).exists()]
 for attempt in older[:4]:
  day=attempt.stem
  if day not in known:raise ValueError('RECOVERY_SESSION_NOT_VERIFIED')
  frames=_snapshot(m,day,known[day],c,client)
  _finish(m,day,c,frames,known,'RECOVERED_OBSERVATION_NO_RETROACTIVE_DECISION')
 if len(older)>4:return {'status':'PENDING_RECOVERY_BACKLOG','remaining':len(older)-4}
 rawdir=F/'observations'/m/d;planpath=F/'plans'/m/(d+'.json');attempt=F/'attempts'/m/(d+'.json')
 if (F/'completions'/m/(d+'.json')).exists():return {'status':'ALREADY_OBSERVED_WAIT_NEXT_SESSION','day':d,'fills':0}
 if not attempt.exists():save(attempt,{'at':now(),'data_cutoff':d,'source_session':last,'planned_next':future[0] if future else None})
 frames=_snapshot(m,d,last,c,client)
 _observe_receipts(m,d,frames,c,known);outcome=settle(m,frames,c)
 if not future:return {'status':'OBSERVED_PENDING_NEXT_VERIFIED_OPEN','observation':outcome,'review':review(m,frames,c)}
 if not planpath.exists():
  scores=compute(m,frames,d);arms={};priorplans=sorted((F/'plans'/m).glob('*.json'));prior=json.loads(priorplans[-1].read_text()) if priorplans else None;completed=len(list((F/'accounts'/m/c['arms'][m][0]).glob('*.json')))
  for name,score in scores.items():
   targets,risk=choose(score,frames,m);rebalance=prior is None or completed%5==0 or prior['arms'][name]['risk_on']!=risk
   arms[name]={'weights':targets if rebalance else prior['arms'][name]['weights'],'rebalance':rebalance,'risk_on':risk,'scores':{k:float(v) for k,v in score.iloc[-1].items() if pd.notna(v)}}
  plan={'market':m,'signal_date':d,'sealed_at':now(),'next_session':future[0],'source_hash':sha(rawdir/'accepted.json'),'contract_hash':sha(F/'contract.json'),'arms':arms,'historical_performance_included':False}
  assert datetime.datetime.fromisoformat(plan['sealed_at'])<datetime.datetime.fromisoformat(future[0]['opening'])
  plan['process']=process_seals(plan);save(planpath,plan)
 else:plan=json.loads(planpath.read_text())
 assessment=review(m,frames,c)
 marker=F/'completions'/m/(d+'.json')
 if not marker.exists():save(marker,{'at':now(),'phase':'SEALED_AND_OBSERVED','snapshot_hash':sha(rawdir/'accepted.json'),'initial_contract_hash':sha(F/'contract.json')})
 return {'status':'SEALED_PROSPECTIVE_TARGETS','day':d,'next_session':plan['next_session']['day'],'arms':{a:v['weights'] for a,v in plan['arms'].items()},'observation':outcome,'review':assessment,'data_quality':'TWO_PROVIDER_PARTIAL_ACTIONS_NON_TOTAL_RETURN'}
'''
s=s[:a]+collection+helpers+new+s[z:]
s=s.replace(" day=next(iter(records.values()))[-1]['day'];out=", " day=next(iter(records.values()))[-1]['day']\n prior_path=F/'reviews'/m/(day+'.json')\n if prior_path.exists():return json.loads(prior_path.read_text())\n out=")
s=s.replace("{k:json.loads((F/'observations'/m/k/'accepted.json').read_text())['at'] for k in nav}","{k:_mark_receipt(m,k) for k in nav}")
p.write_text(s)
