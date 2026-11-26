"""Frozen-source comparative decision run; no performance invented for company arms."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import json,hashlib,sys
import pandas as pd
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'))
from quant_harness.investment.company_analysis import parse_response,judgment
from quant_harness.investment.decision import decide
from quant_harness.investment.store import Store
from quant_harness.investment.review_jobs import Queue
from quant_harness.investment.shadow_portfolio import seal_shadow,execute_shadow
from quant_harness.investment.research import digest
B=R/'runtime/task8';cfg=json.loads((R/'config/task8_portfolio.json').read_text());packet=json.loads((R/'runtime/task7/company/packet.json').read_text());w=Path('/home/ansy/app/quant-diligence/task8-vibe-work');raw=(w/'earnings_component.json').read_text();analyses=parse_response(raw,packet);(B/'company_response.json').write_text(raw)
store=Store('postgresql://quant_task8_research@127.0.0.1:55432/'+cfg['research_database'],'TASK8_RESEARCH_ONLY');queue=Queue(store)
market=json.loads((B/'market/inputs.json').read_text());existing=store.put('task8_source_packet',packet);at=datetime.now(timezone.utc).isoformat();signals=[];quant=[]
# First judgments use disjoint inputs: issuer packet vs only observed price history.
for analysis in analyses:
 case=next(c for c in packet['cases'] if c['ticker']==analysis['ticker']);signal=judgment(analysis,case);signal['research_generated_at']=at;signal['input_observed_at']=case['observed_at'];signals.append(signal)
for symbol,item in market['prices'].items():
 path=B/'market'/(symbol+'.csv');frame=pd.read_csv(path) if path.exists() else None;momentum=float(frame.close.iloc[-1]/frame.close.iloc[-64]-1) if frame is not None and len(frame)>=64 else None
 seen=item.get('receipt',{}).get('available_at',at);reason='UNPROVEN_EXPECTED_NET_EDGE' if momentum is not None else 'INSUFFICIENT_63_SESSION_HISTORY'
 signal={'ticker':symbol,'market':'US','currency':'USD','team':'quant','engine':'FROZEN_MOM63_PRICE_ADAPTER','version':'TASK8_QUANT_INPUT_ONLY_V1','source_hashes':[item.get('receipt',{}).get('source_hash',digest(item))],'available_at':seen,'valid_until':(datetime.fromisoformat(seen)+timedelta(days=3)).isoformat(),'horizon_sessions':1,'direction':'LONG' if momentum is not None and momentum>0 else 'ABSTAIN','status':'RESEARCH_ONLY','expected_return':None,'downside':None,'round_trip_cost':None,'liquidity_verified':False,'sector':None,'edge_evidence':'UNPROVEN','hypothesis':{'momentum63':momentum,'reason':reason,'not_expected_return':True},'falsification':'Insufficient independent prediction evidence; do not autoactivate','cost_status':'Original5bp halfspread assumption; observed quote lacks verified bid/ask; no expected return created'};quant.append(signal)
signals+=quant
frozen=store.put('task8_independent_signals',{'at':at,'signals':signals,'source_packet_id':existing,'market_inputs_hash':digest(market),'policy_hash':digest(cfg)})
comparisons={}
for name,mode in [('B_QUANT','quant'),('C_COMPANY','company'),('D_INTEGRATED','integrated')]:
 decision=decide(signals,cfg,'US',at,mode=mode);identity=store.put('task8_portfolio_decision',decision);comparisons[name]={'id':identity,'decision':decision,'performance':'PENDING_FORWARD_NO_HISTORICAL_COMPANY_FORECASTS'}
comparisons['A_CASH']={'weights':{},'cash_weight':1,'status':'REGISTERED_FORWARD_CASH_REFERENCE','historical_control':'Task6/7 results preserved separately; no new historical company backtest'}
kr=decide([],cfg,'KR',at);comparisons['KR_DATA_ABSTENTION']={'decision':kr,'reason':'No independently eligible Korean company/quant packet; account remains KRW cash'}
shadow=[]
for m in ['US','KR']:
 target=comparisons['D_INTEGRATED']['decision'] if m=='US' else kr
 account=Store('postgresql://quant_task8_shadow_'+m.lower()+'@127.0.0.1:55432/'+cfg['market_accounts'][m],'TASK8_SHADOW_'+m)
 # Existing stockpaper is reused unchanged. Actual targets are cash; no forced orders.
 analysis={'status':'ABSTAIN','weights':target['weights'],'execution_eligible':False,'prior_marks':{},'adv20_d1':{},'strategy_id':'TASK8_SHADOW_V1','input_hash':frozen,'reason':target['status']}
 prior_id='task8-initial-shadow-'+m
 try:link=store.get(prior_id);identity=link['decision_id']
 except ValueError:
  identity,payload=seal_shadow(account,R,target,{},existing);store.put('task8_shadow_link',{'market':m,'decision_id':identity,'portfolio_decision_hash':target['decision_hash']},prior_id)
 outcome=execute_shadow(account,R,identity,[]);again=execute_shadow(account,R,identity,[])
 shadow.append({'market':m,'decision_id':identity,'outcome':outcome,'repeat_idempotent':again.get('idempotent',False),'target_weights':target['weights'],'currency':target['currency']})
# Copy sealed forecasts as immutable references, keeping original dates and payloads.
forecast_count=0
for line in (R/'runtime/task7/review/records.jsonl').read_text().splitlines():
 record=json.loads(line)
 if record['kind']!='COMPANY_FORECAST':continue
 f=record['payload'];f={**f,'original_record_id':record['record_id'],'original_payload_hash':record['payload_hash'],'guidance_comparison':'EQUALS_ISSUER_GUIDANCE_MIDPOINT' if f['ticker']=='NVDA' and f['base_value']==108000 else 'CONDITIONAL_ASSUMPTION_NOT_PROVEN_INDEPENDENT_OF_GUIDANCE'}
 forecast_id=store.put('imported_task7_forecast',f)
 queue.enqueue('OFFICIAL_COMPANY_RELEASE_OBSERVATION',{'forecast_id':forecast_id,'period_end':f['period_end'],'metric':f['metric']},f['earliest_review_date']+'T00:00:00Z');forecast_count+=1
requests=[]
for kind,reason in [('VALUATION_INPUT_GAP','Missing equity bridge/consensus; no invented stock-return probability'),('QUANT_EDGE_WEAKNESS','Task7 unproven prediction quality and high cost/turnover'),('CROSS_HORIZON_REVIEW','Company63sessions versus quant1session; no automatic cross-team veto')]:
 payload={'version':'TASK9_RESEARCH_REQUEST_V1','event':kind,'evidence_id':frozen,'reason':reason,'requested_research':'SOURCE_OR_MODEL_RESEARCH','budget_status':'UNALLOCATED_TASK9','automatic_strategy_change':False};request_id=store.put('task9_research_request',payload);job=queue.enqueue('TASK9_RESEARCH_REQUEST',{'request_id':request_id});claimed=queue.claim('task8-contract-probe',identity=job)
 if claimed:queue.finish(job,'task8-contract-probe',request_id,'PENDING_EVIDENCE')
 requests.append({'request_id':request_id,'job_id':job})
result={'at':at,'input_id':frozen,'signals':signals,'comparisons':comparisons,'shadow':shadow,'task7_forecasts_imported':forecast_count,'task9_requests':requests,'orders':0,'llm_usage':'See native/model reservations; no model calls in this runner'}
(B/'comparison.json').write_text(json.dumps(result,indent=2,default=str));store.export(B/'research_records.jsonl');print(json.dumps({'comparisons':{k:v.get('decision',v).get('status') for k,v in comparisons.items()},'shadow':shadow,'forecasts':forecast_count,'task9_requests':len(requests)},indent=2,default=str))
