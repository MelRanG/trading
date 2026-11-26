"""Seal exploratory targets, not official eligibility or backdated virtual fills."""
from pathlib import Path
from datetime import datetime,timezone
import json,sys,hashlib
import psycopg,pandas as pd
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'))
from quant_harness.investment.exploration import research_store,account_store,official_sessions
from quant_harness.investment.equities import load_environment,settings
from quant_harness.investment.stockpaper import seal,initialize
from quant_harness.investment.operations_data import strict_rows,ZONES
from quant_harness.investment.review_jobs import Queue
from quant_harness.investment.research import digest
from quant_harness.v72_integration_ready.toss_openapi import TossOpenApiClient
b=R/'runtime/task8b'
if (b/'sealed_plans.json').exists():print('Frozen initial seals exist; use current active plans/restart probe, preserve guard reseal history');raise SystemExit(0)
opps=json.loads((b/'final_opportunities.json').read_text());load_environment(R);client=TossOpenApiClient();store,cfg=research_store(R);queue=Queue(store);original_id=store.put('opportunity_snapshot',opps);out=[];root=b/'seal_prices';root.mkdir(exist_ok=True)
for c in opps['cases']:
 record=store.put('company_opportunity',c);review={'candidate_id':record,'classification':c['status'],'source_hashes':c['source_hashes'],'valuation_status':'CONDITIONAL_SENSITIVITY_NOT_ESTABLISHED_EXPECTATION','official_paper_status':'NOT_ELIGIBLE','future_accuracy':'PENDING','cause_taxonomy':['UNDETERMINED'],'process_reason':c['research_reason']};review_id=store.put('opportunity_process_review',review)
 request={'version':'TASK9_RESEARCH_REQUEST_V1','candidate_id':record,'review_id':review_id,'ticker':c['ticker'],'requests':c.get('most_material_missing',c.get('what_changes_decision')),'hypothesis':c['bull_thesis'],'counter':c['bear_thesis'],'falsification':c['falsification'],'next_checkpoints_sessions':[21,63,126],'budget':'UNALLOCATED','official_strategy_change':False};req=store.put('task9_opportunity_request',request);job=queue.enqueue('TASK9_OPPORTUNITY_FOLLOWUP',{'request_id':req});claimed=queue.claim('task8b-seal',identity=job)
 if claimed:queue.finish(job,'task8b-seal',review_id,'PENDING_EVIDENCE')
for market in ['US','KR']:
 account=account_store(cfg,market);initialize(account,settings(R),market)
 with psycopg.connect(store.url) as conn:existing=conn.execute("SELECT record_id,payload FROM investment_record WHERE kind='exploration_plan' AND payload->>'market'=%s",(market,)).fetchone()
 if existing:out.append({'market':market,'plan_id':existing[0],'status':'SEALED_ALREADY'});continue
 selected=[c for c in opps['cases'] if c['market']==market and c['probe']['eligible_for_probe']];weights={c['ticker']:c['probe']['weight'] for c in selected};prices={};marks={};adv={};receipts=[];clock=datetime.now(timezone.utc).isoformat();sessions=official_sessions(market,clock);eligible=[s for s in sessions if s['closing']<clock] # ISO offsets may differ; use aware comparison below.
 from quant_harness.investment.discovery import instant
 eligible=[s for s in sessions if instant(s['closing'])<instant(clock)]
 if not eligible:raise ValueError('official completed session unavailable')
 session=eligible[-1]
 for symbol in weights:
  p=root/(symbol+'.json');meta=root/(symbol+'.receipt.json')
  if p.exists():raw=json.loads(p.read_text());receipt=json.loads(meta.read_text())
  else:
   payload=client._request('GET',client.endpoint_map.candles_path,query={'symbol':symbol.split('.')[0] if market=='KR' else symbol,'interval':'1d','count':21,'before':session['closing'],'adjusted':'false'});encoded=json.dumps(payload,sort_keys=True).encode();p.write_bytes(encoded);receipt={'source_hash':hashlib.sha256(encoded).hexdigest(),'available_at':datetime.now(timezone.utc).isoformat(),'session':session,'raw_price_reference_only':True};meta.write_text(json.dumps(receipt));raw=payload
  frame=strict_rows(raw,symbol,'USD' if market=='US' else 'KRW',ZONES[market],session['day'])
  if len(frame)<20 or frame.date.iloc[-1]!=session['day']:raise ValueError('fresh raw D1 reference/ADV missing')
  marks[symbol]=float(frame.close.iloc[-1]);adv[symbol]=float((frame.close*frame.volume).tail(20).mean());prices[symbol]={'meta':{'instrumentType':'EQUITY'}};receipts.append(receipt)
 analysis={'status':'CANDIDATES' if weights else 'ABSTAIN','weights':weights,'execution_eligible':bool(weights),'prior_marks':marks,'adv20_d1':adv,'strategy_id':'TASK8B_RESEARCH_SHADOW_FIXED_PROBE_V1','input_hash':opps['input_hash'],'reason':'PRESEALED_FALSIFIABLE_RESEARCH_NOT_PROVEN_ALPHA','research_only':True}
 catalog_id=store.put('exploration_listing_and_sources',{'candidates':selected,'price_receipts':receipts});identity,payload=seal(account,R,market,analysis,prices,catalog_id)
 plan={'version':cfg['version'],'market':market,'weights':weights,'paper_decision_id':identity,'catalog_id':catalog_id,'benchmark':cfg['benchmarks'][market],'candidate_fingerprints':[c['candidate_fingerprint'] for c in selected],'research_snapshot_id':original_id,'exploration_policy_hash':digest(cfg),'worker_hash':hashlib.sha256((R/'src/quant_harness/investment/exploration.py').read_bytes()).hexdigest(),'sealed_at':payload['sealed_at'],'entry_rule':cfg['entry_rule'],'exit_rule':cfg['exit_rule'],'holding_checkpoints_sessions':cfg['holding_checkpoints_sessions'],'effective_decision_lifetime_hours':min(96,settings(R)['decision_lifetime_hours']),'policy_scope':'Separate exploration only; official Paper eligibility unchanged','cost_assumptions':settings(R)['US_execution_assumptions'] if market=='US' else settings(R)['execution_assumptions'],'bid_ask_verification':'NOT_AVAILABLE; synthetic Paper cost model only','separate_cash_control':settings(R)[market]['initial_capital'],'price_reference_hash':digest(receipts)}
 plan_id=store.put('exploration_plan',plan);out.append({'market':market,'plan_id':plan_id,'weights':weights,'cash_weight':1-sum(weights.values()),'paper_id':identity,'sealed_at':payload['sealed_at'],'status':'WAIT_NEXT_ELIGIBLE_PRICE'})
(b/'sealed_plans.json').write_text(json.dumps(out,indent=2));store.export(b/'research_records.jsonl');print(json.dumps(out,indent=2))
