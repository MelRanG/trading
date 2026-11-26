"""Research-only prospective observations. No model training, LLM, or broker calls.

Sealed decisions feed the existing replay_targets execution kernel only after
future completed sessions arrive. Old inputs never count as Forward NAV.
"""
from pathlib import Path
import sys,json,hashlib,datetime,fcntl,subprocess,math,ast
from urllib.parse import quote
from zoneinfo import ZoneInfo
import pandas as pd,numpy as np
R=Path(__file__).resolve().parents[2];sys.path[:0]=[str(R/'src'),str(R/'experiments/task10')]
from quant_harness.investment.research import digest,replay_targets,metrics
from quant_harness.investment.equities import load_environment,us_catalog,kr_catalog,fetch
from quant_harness.investment.operations_data import parse_calendar,strict_rows
from quant_harness.v72_integration_ready.toss_openapi import TossOpenApiClient
from quant_harness.v77_corrected_price_allocation.engine import ExecutionSpec
F=R/'runtime/task10_1/forward';OLD=R/'runtime/task10'
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);encoded=json.dumps(x,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False,default=str)+'\n'
 if p.exists():
  if p.read_text()!=encoded:raise ValueError('immutable conflict '+str(p))
 else:
  tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(encoded);tmp.replace(p)
 return x
def sources():
 paths=[OLD/'universe.json',OLD/'initial_strategy_seal.json',R/'config/task3_equity_contract.json',Path(__file__),R/'experiments/task10/train_worker.py',R/'experiments/task10/components.py',R/'experiments/task6/evaluate_worker.py',R/'src/quant_harness/investment/review.py',R/'src/quant_harness/investment/research.py',R/'src/quant_harness/v77_corrected_price_allocation/engine.py',OLD/'native_full/quanta/initial/factor.py',OLD/'native_full/quanta/mutation/factor.py',Path('/home/ansy/app/quant-diligence/task10-rd-work/model.py')]
 for stage,m in [('initial','US'),('initial','KR'),('US_2026-07-15','US')]:paths.extend([OLD/'models'/stage/m/'model.pth',OLD/'models'/stage/m/'training.json'])
 return {str(p):sha(p) for p in paths}
def enroll():
 p=F/'contract.json'
 if p.exists():
  c=json.loads(p.read_text());verify_sources(c);return c
 c={'schema':'TASK101_FORWARD_SHADOW_V6','sealed_at':now(),'sources':sources(),'historical_evidence_excluded':True,'automatic_promotion':False,'live':False,'capital':{'US':100000,'KR':10000000},'arms':{'US':['INITIAL_STATIC','ADAPTIVE_COMBINED','QUANTA_MUTATION_ONLY'],'KR':['INITIAL_STATIC','MOM63']},'Q_ONLY':'Mutation+initialRD, posthoc hypothesis selected after seeing Task10 results; not a promoted alpha','US_candidate_status':'FORWARD_REQUIRED','KR_retrain_status':'REJECTED_NOT_USED','universe':json.loads((OLD/'universe.json').read_text()),'execution':'Existing V77/replay_targets; D-1 sizing, next verified session open, fees/spread/impact same across arms. Nominal price-only; no unverified corporate actions.','allocation':'positive top4 each20%, target gross80%, 63sessionETF riskgate. Five completed Forward sessions per rebalance/review; daily risk transition. Target caps can drift.','budget':{'wire_calls_per_UTC_day':160,'LLM':0,'training':0,'poll_minutes':60},'data':'Bootstrap sealed Task10 feature context only. Fresh Toss/Yahoo/Naver two-provider OHLC agreement within0.5%, same fixed pair order as Task10. No imputation; V87 and overlap revision gate. Current catalog/session required; partial corporate-action coverage, price-only.','benchmarks':{'US':['^GSPC','SPY'],'KR':['^KS11','069500.KS']},'nontradable_index_adapter':'Separate bounded benchmark collector; primary index availability remains explicit, ETF never called identical index','review':'5 Forward sessions; mature t+1 to t+6 labels only from prospectively sealed scores. 20session warmup and two weak reviews (matchedETF active<-2pp and IC<0) before separate Quanta/RD requests; no automatic research worker activation.','factory':'Require recovered official authority and separate preregistration/budget. Quanta change and RD retrain are separate requests; neither auto-approved nor auto-dispatched by this adapter.'}
 return save(p,c)
def verify_sources(contract):
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

def reserve():
 p=F/'wire_reservations.jsonl';day=now()[:10];rows=[json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []
 if sum(r['at'][:10]==day for r in rows)>=160:raise ValueError('TASK101_DAILY_WIRE_BUDGET')
 with p.open('a') as f:f.write(json.dumps({'at':now(),'sequence':len(rows)+1})+'\n')
def get(client,path,query,p):
 if p.exists():return json.loads(p.read_text())
 reserve();value=client._request('GET',path,query=query);save(p,value);return value

def choose(scores,frames,m):
 names=sorted(s for s in frames if 'BENCHMARK' not in s);close=pd.DataFrame({s:f.close for s,f in frames.items()});last=close.index[-1];bench=close[m+'_BENCHMARK'];risk=bool(bench.iloc[-1]>=bench.rolling(63,min_periods=63).mean().iloc[-1])
 if not risk:return {},risk
 s=scores.reindex(columns=names).loc[last];good=s[s.notna()&(s>0)&close.loc[last,names].notna()];return {x:.2 for x in good.sort_values(ascending=False,kind='stable').index[:4]},risk

def compute(m,frames,tag):
 import components as comp
 comp.B=F/'compute'
 q=comp.factor(tag+'_q0',m,frames,OLD/'native_full/quanta/initial/factor.py')
 def prediction(stage):
  work=F/'compute'/tag/stage/m;inp=work/'input';inp.mkdir(parents=True,exist_ok=True);result=work/'predictions.csv'
  if not result.exists():
   for s,f in frames.items():
    if 'BENCHMARK' not in s:f.to_csv(inp/(s+'.csv'),index_label='date')
   comp.docker('rd',work,[(inp,'/input','ro'),(OLD/'models'/stage/m,'/trained','ro'),(Path('/home/ansy/app/quant-diligence/task10-rd-work'),'/candidate','ro')],['/code/train_worker.py','predict'])
  return pd.read_csv(result,parse_dates=['datetime']).set_index(['datetime','instrument']).iloc[:,0].unstack('instrument')
 rd=prediction('initial');out={'INITIAL_STATIC':comp.target_scores(q,rd)}
 if m=='US':
  nq=comp.factor(tag+'_qm',m,frames,OLD/'native_full/quanta/mutation/factor.py');nr=prediction('US_2026-07-15');out.update(ADAPTIVE_COMBINED=comp.target_scores(nq,nr),QUANTA_MUTATION_ONLY=comp.target_scores(nq,rd))
 else:out['MOM63']=pd.DataFrame({s:f.close.pct_change(63,fill_method=None) for s,f in frames.items() if 'BENCHMARK' not in s})
 return out

def validate_revisions(old,new):
 overlap=old.index.intersection(new.index)
 if len(overlap)==0:raise ValueError('no overlap for revision gate')
 for field in ['open','high','low','close','volume']:
  a=old.loc[overlap,field];b=new.loc[overlap,field];ok=a.notna()&b.notna()
  if ((a[ok]-b[ok]).abs()>np.maximum(a[ok].abs()*.005,1e-8)).any():raise ValueError('SOURCE_REVISION_OR_ACTION_'+field)

def settle(m,frames,c):
 """Replay only already sealed target events. No retrospective target generation."""
 from shared import make_panel
 plans=[json.loads(p.read_text()) for p in sorted((F/'plans'/m).glob('*.json'))]
 dates=frames[m+'_BENCHMARK'].index
 # Eligibility is checked against actual plan seal/open timestamps below.
 # Include seal-day session only when its OPEN was after the seal; plan does that.
 validplans={p['next_session']['day']:p for p in plans if datetime.datetime.fromisoformat(p['next_session']['opening'])>datetime.datetime.fromisoformat(p['sealed_at'])}
 if not validplans:return {'status':'PENDING_FIRST_SEALED_TARGET','fills':0}
 first=min(validplans);dates=dates[dates>=pd.Timestamp(first)]
 if not len(dates):return {'status':'PENDING_NEXT_COMPLETED_SESSION','fills':0,'first_eligible_session':first}
 panel=make_panel(frames);cfg=json.loads((R/'config/task3_equity_contract.json').read_text());raw=cfg['US_execution_assumptions'] if m=='US' else cfg['execution_assumptions'];cap=c['capital'][m];spec=ExecutionSpec(**{k:v for k,v in raw.items() if k!='minimum_order_nav_fraction'},minimum_order_notional_krw=cap*raw['minimum_order_nav_fraction']);results={}
 for arm in c['arms'][m]:
  ledger=[];rebals=set();last={}
  for d in dates:
   p=validplans.get(str(d.date()))
   if p:
    last=p['arms'][arm]['weights']
    if p['arms'][arm]['rebalance']:rebals.add(d)
   # Unknown missed sessions hold last known positions; do not create unsealed decisions.
   ledger.append({'date':d,'target_weights_json':json.dumps(last)})
  account,fills,intents=replay_targets(panel,dates,pd.DataFrame(ledger),cap,spec,rebalance_dates=rebals,allow_unpriced_hold=False)
  for day in dates:
   nav=account[account.date==day].iloc[0].to_dict();nav['date']=str(day.date());ff=fills[fills.date==day].copy() if len(fills) else fills
   if len(ff):ff['date']=ff.date.astype(str)
   record={'schema':'ACTUAL_PROSPECTIVE_SHADOW_MARK','market':m,'arm':arm,'day':str(day.date()),'nav':nav,'fills':ff.to_dict('records'),'scope':'RESEARCH_ONLY_NOT_OFFICIAL_PAPER'}
   save(F/'accounts'/m/arm/(str(day.date())+'.json'),record)
  results[arm]={'metrics':metrics(account,fills,cap),'completed_sessions':len(dates)}
 return {'status':'FORWARD_OBSERVED','arms':results}

def review(m,frames,c):
 records={a:[json.loads(p.read_text()) for p in sorted((F/'accounts'/m/a).glob('*.json'))] for a in c['arms'][m]};n=len(next(iter(records.values())))
 if not n:return {'status':'PENDING_FIRST_FORWARD_SESSION'}
 if n%5:return {'status':'PENDING_WEEKLY_BOUNDARY','completed_sessions':n}
 day=next(iter(records.values()))[-1]['day']
 prior_path=F/'reviews'/m/(day+'.json')
 if prior_path.exists():return json.loads(prior_path.read_text())
 out={'market':m,'day':day,'status':'MAINTAIN','cause':'UNDETERMINED','completed_sessions':n,'arms':{},'research_requests':[],'factory_execution':False}
 plans=[json.loads(p.read_text()) for p in sorted((F/'plans'/m).glob('*.json'))]
 for arm,rs in records.items():
  nav=pd.Series({r['day']:r['nav']['nav_krw'] for r in rs},dtype=float);etf=frames[m+'_BENCHMARK'].close;recent=nav.iloc[-21:];net=float(recent.iloc[-1]/recent.iloc[0]-1) if len(recent)>1 else None;ic=[]
  for p in plans:
   signal=p['signal_date'];ds=frames[m+'_BENCHMARK'].index;idx=ds.get_indexer([pd.Timestamp(signal)])[0]
   if idx<0 or idx+6>=len(ds) or str(ds[idx+6].date())>day:continue
   vals=p['arms'][arm]['scores'];pred=pd.Series(vals,dtype=float);actual=pd.Series({s:f.open.loc[ds[idx+6]]/f.open.loc[ds[idx+1]]-1 for s,f in frames.items() if s in vals});joined=pd.concat([pred,actual],axis=1).dropna()
   if len(joined)>=8 and joined.iloc[:,0].nunique()>1:ic.append(float(joined.iloc[:,0].rank().corr(joined.iloc[:,1].rank())))
  # No historical signal rows are added to the mature Forward IC sample.
  exposure=pd.Series({r['day']:sum(float(q)*float(frames[k].close.loc[r['day']]) for k,q in json.loads(r['nav']['holdings_json']).items() if q)/float(r['nav']['nav_krw']) for r in rs},dtype=float)
  br=etf.reindex(pd.to_datetime(recent.index)).pct_change(fill_method=None);br.index=recent.index
  matched=float((1+br*exposure.reindex(recent.index).shift(1).fillna(0.)).prod()-1);active=net-matched if net is not None else None
  model_errors=[]
  for p in plans:
   ds=frames[m+'_BENCHMARK'].index;idx=ds.get_indexer([pd.Timestamp(p['signal_date'])])[0]
   if idx<0 or idx+6>=len(ds) or str(ds[idx+6].date())>day:continue
   stage='US_2026-07-15' if arm=='ADAPTIVE_COMBINED' else 'initial';fp=F/'compute'/p['signal_date']/stage/m/'predictions.csv'
   if fp.exists():
    pred=pd.read_csv(fp,parse_dates=['datetime']).set_index(['datetime','instrument']).iloc[:,0].unstack('instrument')
    if pd.Timestamp(p['signal_date']) in pred.index:
     for name,v in pred.loc[pd.Timestamp(p['signal_date'])].dropna().items():
      actual=frames[name].open.loc[ds[idx+6]]/frames[name].open.loc[ds[idx+1]]-1
      if math.isfinite(actual):model_errors.append((float(v)-actual)**2)
  out['arms'][arm]={'matched_ETF20':matched,'matched_active20':active,'model_MSE':float(np.mean(model_errors)) if model_errors and arm!='MOM63' else None,'model_error_cases':len(model_errors) if arm!='MOM63' else 0,'exposure':float(exposure.iloc[-1]),'net20':net,'mature_forward_rankIC':float(np.mean(ic[-20:])) if len(ic)>=10 else None,'mature_labels':len(ic),'model_error':'SAME_FIVE_SESSION_OPEN_TARGET','performance':'PENDING_20SESSIONS' if n<20 else 'OBSERVED_NO_CAUSAL_FAILURE_ASSERTION'}
  if n>=20 and len(ic)>=10 and np.mean(ic[-20:])<0 and active is not None and active<-.02:
   prior=sorted((F/'reviews'/m).glob('*.json'));weakprior=False
   if prior:
    old=json.loads(prior[-1].read_text());weakprior=old.get('arms',{}).get(arm,{}).get('weak',False)
   out['arms'][arm]['weak']=True
   if weakprior:
    out['status']='RESEARCH';out['research_requests'].extend([{'arm':arm,'target':x,'status':'PENDING_FACTORY_PREREGISTRATION_AND_BUDGET','automatic_execution':False} for x in ['QUANTA_ALONE','RD_RETRAIN_ALONE']])
 from quant_harness.investment.review import score_mature_outcome
 for arm,rs in records.items():
  pp=plans[0]['process'][arm];nav={r['day']:r['nav']['nav_krw'] for r in rs};labels={'decision_id':pp['packet']['source_decision_id'],'calendar_verified':True,'calendar_verification_scope':'Contemporaneously archived provider regular sessions, not independent exchange certification','source_hash':digest(nav),'available_at':now(),'sessions':list(nav),'entry_session':next(iter(nav)),'nav':nav,'observed_at_by_session':{r['day']:str(datetime.datetime.fromisoformat(c['sealed_at'])+datetime.timedelta(days=0)) for r in []},'benchmark':{k:float(etf.loc[k]) for k in nav}}
  labels['observed_at_by_session']={k:_mark_receipt(m,k) for k in nav}
  labels['evidence_class']='PROSPECTIVE_FORWARD_SHADOW_SINCE_TASK101_SEAL'
  labels['available_at']=now()
  out['arms'][arm]['native_outcome_review']=score_mature_outcome(pp['result'],pp['packet'],pp['policy'],labels)
 save(F/'reviews'/m/(day+'.json'),out);return out

def process_seals(plan):
 from quant_harness.investment.review import process_review,policy
 cfg=policy(R);cfg={**cfg,'strategy_horizons':{**cfg['strategy_horizons'],'TASK101_FORWARD':[5,20,60]}}
 out={}
 for arm,data in plan['arms'].items():
  packet={'source_decision_id':'TASK101-'+plan['market']+'-'+arm+'-'+plan['signal_date'],'market':plan['market'],'strategy_id':'TASK101_FORWARD','cutoff':plan['sealed_at'],'contract_hash':plan['contract_hash'],'input_hash':plan['source_hash'],'algorithm_hash':sha(__file__),'registered_policy':{'gross_cap':.8,'single_name_cap':.2},'weights':data['weights'],'eligible':True,'intents':[],'analysis':{'missing':[]},'source_receipts':[{'status':'TWO_PROVIDER_PARTIAL_ACTIONS'}],'evidence':[],'company_candidates':[]}
  out[arm]={'packet':packet,'policy':cfg,'result':process_review(packet,cfg)}
 return out

def _snapshot(m,d,last,c,client):
 rawdir=F/'observations'/m/d;rawdir.mkdir(parents=True,exist_ok=True)
 if (rawdir/'accepted.json').exists():return _load_snapshot(m,d,c)
 cp=rawdir/'catalog.json'
 if cp.exists():catalog=json.loads(cp.read_text())
 else:
  catalog=us_catalog(rawdir/'catalog') if m=='US' else kr_catalog(rawdir/'catalog');save(cp,catalog)
 listed={r['symbol'] for r in catalog['rows'] if r.get('common_stock_verified')} if m=='US' else {r['stock_code']+'.KS' for r in catalog['rows']}
 assets=[a for a in c['universe'] if a['market']==m];notlisted=[a['symbol'] for a in assets if a['role']=='stock' and a['symbol'] not in listed]
 if notlisted:raise ValueError('LISTING_NOT_VERIFIED:'+','.join(notlisted))
 frames={};gates={}
 # Use previous immutable accepted observation as context. No forward prices from Task10.
 past=sorted((F/'observations'/m).glob('*/accepted.json'))
 for a in assets:
  s=a['symbol'];alias=a['alias'];raw=get(client,client.endpoint_map.candles_path,{'symbol':s.split('.')[0] if m=='KR' else s,'interval':'1d','count':8,'before':last['closing'],'adjusted':'false'},rawdir/(alias+'.raw.json'))
  new=strict_rows(raw,s,'KRW' if m=='KR' else 'USD','Asia/Seoul' if m=='KR' else 'America/New_York',d).assign(date=lambda x:pd.to_datetime(x.date)).set_index('date')[['open','high','low','close','volume']]
  if str(new.index[-1].date())!=d:raise ValueError('STALE_COMPLETED_SESSION_'+s)
  provider_frames={'TOSS':new};zone=ZoneInfo('Asia/Seoul' if m=='KR' else 'America/New_York')
  yp=rawdir/(alias+'.yahoo.json')
  if not yp.exists():
   reserve();data,receipt=fetch('https://query1.finance.yahoo.com/v8/finance/chart/'+quote(s,safe='')+'?range=1mo&interval=1d&events=div%2Csplits',rawdir/'raw_yahoo');yp.write_bytes(data);save(rawdir/(alias+'.yahoo_receipt.json'),receipt)
  try:
   chart=json.loads(yp.read_text())['chart']['result'][0];quotes=chart['indicators']['quote'][0]
   if chart['meta']['symbol'].upper()!=s.upper():raise ValueError('Yahoo symbol mismatch')
   provider_frames['YAHOO']=pd.DataFrame([{'date':pd.Timestamp(datetime.datetime.fromtimestamp(t,datetime.timezone.utc).astimezone(zone).date()),**{k:quotes[k][i] for k in ['open','high','low','close','volume']}} for i,t in enumerate(chart['timestamp'])]).set_index('date').loc[:d]
   if chart.get('events',{}).get('splits'):raise ValueError('NEW_SPLIT_REQUIRES_ACTION_RECONCILIATION')
  except (KeyError,TypeError,IndexError):pass
  if m=='KR' and a['role']=='stock':
   npth=rawdir/(alias+'.naver.raw')
   if not npth.exists():
    reserve();data,receipt=fetch('https://api.finance.naver.com/siseJson.naver?symbol='+s[:6]+'&requestType=1&startTime='+str(new.index.min().date()).replace('-','')+'&endTime='+d.replace('-','')+'&timeframe=day',rawdir/'raw_naver');npth.write_bytes(data);save(rawdir/(alias+'.naver_receipt.json'),receipt)
   try:text=npth.read_bytes().decode('utf-8')
   except UnicodeDecodeError:text=npth.read_bytes().decode('cp949')
   nr=ast.literal_eval(text.strip());provider_frames['NAVER']=pd.DataFrame([{'date':pd.Timestamp(str(r[0])),'open':r[1],'high':r[2],'low':r[3],'close':r[4],'volume':r[5]} for r in nr[1:]]).set_index('date').loc[:d]
  provenance=[]
  for dt in new.index:
   for field in ['open','high','low','close']:
    selected=None
    for aa,bb in [('YAHOO','NAVER'),('TOSS','NAVER'),('YAHOO','TOSS')]:
     pa,pb=provider_frames.get(aa),provider_frames.get(bb)
     if pa is None or pb is None or dt not in pa.index or dt not in pb.index:continue
     v,w=float(pa.loc[dt,field]),float(pb.loc[dt,field])
     if math.isfinite(v+w) and min(v,w)>0 and abs(v/w-1)<=.005:selected=w;provenance.append({'date':str(dt.date()),'field':field,'pair':[aa,bb],'values':[v,w]});break
    if selected is None:raise ValueError('TWO_PROVIDER_PRICE_UNRESOLVED_'+s+'_'+str(dt.date())+'_'+field)
    new.loc[dt,field]=selected
  save(rawdir/(alias+'.field_provenance.json'),provenance)
  oldpath=past[-1].parent/(alias+'.csv') if past else OLD/'tape'/m/(alias+'.csv')
  old=pd.read_csv(oldpath,index_col='date',parse_dates=True);validate_revisions(old,new)
  # Retain original overlapping observations, append only truly new bars.
  frame=pd.concat([old,new.loc[new.index>old.index.max()]]).sort_index();frame=frame.loc[:d]
  from quant_harness.v87_actual_data_ingestion.engine import ProviderBatch,_validate_batch,_revision_audit
  gatecfg=json.loads((R/'config/task3_equity_price_contract.json').read_text());gatecfg['provider_contract']['required_source_tag']='TASK101_TOSS_RAW_OBSERVED'
  numerical=new.reset_index();numerical['date']=numerical.date.dt.strftime('%Y-%m-%d');numerical['ticker']=s; numerical['value_approx']=numerical.close*numerical.volume
  batch=ProviderBatch('TOSS_RAW',s.zfill(6),tuple(numerical.to_dict('records')),False,'TASK101_TOSS_RAW_OBSERVED',now(),{})
  accepted=_validate_batch(batch,gatecfg);reference=rawdir/(alias+'.reference.csv');gate=_revision_audit(accepted,reference,gatecfg)
  if not reference.exists():accepted.to_csv(reference,index=False)
  if not gate['passed']:raise ValueError('V87_OR_REVISION_GATE_'+s)
  frame.to_csv(rawdir/(alias+'.csv'),index_label='date');frames[alias]=frame;gates[alias]=gate
 save(rawdir/'accepted.json',{'at':now(),'session':last,'source':'TWO_PROVIDER_RAW_OBSERVED_PARTIAL_ACTIONS','catalog_hash':digest(catalog),'gates':gates,'data_hashes':{a['alias']:sha(rawdir/(a['alias']+'.csv')) for a in assets},'preseal_history_is_context_not_forward':True})
 return frames

def _load_snapshot(m,d,c):
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

def market_tick(m,c,client):
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

def run():
 F.mkdir(parents=True,exist_ok=True)
 with (F/'.lock').open('a') as lock:
  if not trylock(lock):return {'status':'CONCURRENT_TICK_SKIPPED'}
  c=enroll();load_environment(R);client=TossOpenApiClient();rows={}
  for m in ['US','KR']:
   try:rows[m]=market_tick(m,c,client)
   except Exception as e:rows[m]={'status':'FAILED_CLOSED','reason':str(e)[:180],'error_type':type(e).__name__}
  result={'at':now(),'scope':'PROSPECTIVE_RESEARCH_SHADOW_ONLY','markets':rows,'LLM_calls':0,'broker_orders':0,'factory_experiments':0}
  # One receipt per hour/status; no repeated full-data copies on five-minute ticks.
  p=F/'ticks'/(digest({'hour':now()[:13],'markets':rows})+'.json')
  if not p.exists():save(p,result)
  return result

def trylock(handle):
 try:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB);return True
 except BlockingIOError:return False
if __name__=='__main__':print(json.dumps(run(),ensure_ascii=False,indent=2))
