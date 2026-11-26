from common import *
import psycopg,shutil
from quant_harness.investment.exploration import research_store
from quant_harness.investment.review_jobs import Queue
from quant_harness.investment.research import digest as qdigest
from quant_harness.investment.review import process_review,policy
from quant_harness.investment import research_dispatcher
from quant_harness.investment.equities import load_environment
sys.path.insert(0,str(R/'experiments/task9_completion'))
from serialization_fix import canonical_zero
load_environment(R);W=Path('/home/ansy/app/quant-diligence/task9-2-work');store,cfg=research_store(R);queue=Queue(store)
for stage in ['history_before','history_after','history_lg_repair','current_research','current_repair','current_timing']:
 for suffix in ['.json','.raw.txt','.request.json']:
  p=W/(stage+suffix);out=B/'model_outputs'/p.name;out.parent.mkdir(exist_ok=True)
  if out.exists():assert sha(p)==sha(out)
  else:shutil.copyfile(p,out)
seals=[]
for stage in ['history_before','history_after','history_lg_repair','current_research','current_repair','current_timing']:
 req=json.loads((W/(stage+'.request.json')).read_text());matches=[]
 for p in (B/'model_calls/research').glob('*.reserved.json'):
  rec=json.loads(p.read_text());body=json.loads(p.with_name(p.name.replace('.reserved.json','.request.json')).read_text())
  if body['messages']==req['messages']:matches.append(rec)
 assert len(matches)==1 and matches[0]['status']=='SUCCEEDED';seals.append({'stage':stage,'output_hash':sha(W/(stage+'.json')),'request_hash':sha(W/(stage+'.request.json')),'transport':matches[0]})
freeze(B/'model_seals.json',seals)
packet=json.loads((B/'current_numeric_packet.json').read_text());rep=json.loads((B/'current_numeric_packet_v2.json').read_text());first=json.loads((W/'current_research.json').read_text());repaired=json.loads((W/'current_repair.json').read_text());timed=json.loads((W/'current_timing.json').read_text());valuation=json.loads((B/'current_timed_valuations.json').read_text());decision_ids=[]
if (B/'dispatch_registry.json').exists():raise SystemExit('Existing dispatch registry preserved; do not reseal')
clock=now()
for market,index in [('US','^GSPC'),('KR','^KS11')]:
 companies=[]
 for c in packet['cases']:
  if c['market']!=market:continue
  base=next(x for x in first['cases'] if x['symbol']==c['symbol']);detail=next((x for x in repaired['cases'] if x['symbol']==c['symbol']),base);timing=next((x for x in timed['cases'] if x['symbol']==c['symbol']),None)
  assert detail['decision_state'] in ['RESEARCH_INCOMPLETE','UNATTRACTIVE','WATCH','INVESTABLE'];assert detail['weight']==0,'No eligible buy signalled in this frozen research'
  companies.append({'symbol':c['symbol'],'research_priority':base['research_priority'],'state':detail['decision_state'],'weight':0,'reason':detail['decision_reason'],'entry_condition':detail.get('entry_condition'),'forecasts':detail.get('forecasts',base['forecasts']),'valuation':[r for r in valuation if r['symbol']==c['symbol']],'unresolved':detail.get('missing_fields',[]),'quant':c['price_observation'],'not_buy_from_rank':True,'official_paper':'NOT_ELIGIBLE','price_snapshot':c['price_observation'],'current_signal_only':True})
 issuer={}
 if market=='KR':
  for c in companies:issuer[c['symbol']]=json.loads((B/'sources'/c['symbol'].split('.')[0]/'identity.json').read_text())['corp_code']
 process={'source_decision_id':'TASK92-'+market+'-'+digest(companies)[:20],'market':market,'cutoff':clock,'strategy_id':'TASK92_RESEARCH_ONLY','contract_hash':sha(R/'experiments/task9_2/contract.json'),'input_hash':digest(packet),'algorithm_hash':sha(R/'src/quant_harness/investment/financial_packet.py'),'registered_policy':{'gross_cap':cfg['gross_cap'],'single_name_cap':cfg['single_name_cap']},'weights':{},'eligible':False,'intents':[],'analysis':{'missing':sorted({s for c in companies for s in c['unresolved']})},'source_receipts':[{'status':'SAVED'}],'evidence':[],'company_candidates':[]}
 decision={'schema':'TASK92_CURRENT_RESEARCH_DECISION_V1','market':market,'sealed_at':clock,'symbols':[c['symbol'] for c in companies],'companies':companies,'weights':{},'cash_weight':1,'portfolio_kind':'RESEARCH_SHADOW_WATCH_POLICY_NOT_OFFICIAL_PAPER','benchmark_symbol':index,'benchmarks_are_indices_not_tradable_orders':True,'benchmark_snapshot':json.loads((B/'current_prices'/index/'summary.json').read_text()),'issuer_codes':issuer,'process_packet':process,'forward_horizons_months':[1,3,6],'entry_authority':'No INV​ESTABLE signal. Existing Paper/Shadow entry rules unchanged. No new order.','capital_authority':'NONE','future_results':'PENDING'}
 identity=store.put('task92_current_decision',canonical_zero(decision));decision_ids.append(identity);freeze(B/'forward_decisions'/(market+'.json'),decision);store.put('task92_process_review',canonical_zero(process_review(process,policy(R))))
 # Actual observed process change, not a fabricated trading loss.
 request=store.put('task92_followup_request',{'decision_id':identity,'category':'INFORMATION_MISSING','evidence_hash':digest({'before':sha(B/'requests/history_before.request.json'),'after':sha(B/'requests/history_after.request.json'),'typed':sha(B/'historical_numeric_packet_v3.json')}),'reason':'Observed input transmission gap and capital/period repair; independent price effect undetermined'});queue.enqueue('TASK92_EVIDENCE_REVIEW',{'request_id':request})
hist=json.loads((B/'historical_numeric_packet_v3.json').read_text());cases=[{'symbol':c['symbol'],'facts':c.get('verified_facts',[])+c.get('annual_verified_facts',[])} for c in hist['cases']];bundle={'asof':'2025-06-30','cases':cases,'purpose':'NUMERIC_PROVENANCE_TECHNICAL_DIAGNOSTIC_NOT_ALPHA'};bundle_id=store.put('task92_numeric_experiment_bundle',canonical_zero(bundle));worker=sha(R/'src/quant_harness/investment/research_dispatcher.py')
proposal={'problem_evidence':{'before_request_hash':sha(B/'requests/history_before.request.json'),'after_source_packet_hash':sha(B/'historical_numeric_packet_v3.json')},'target':'source','expected_effect':'Preserve verified numeric accounting fields and source locators before valuation; not an investment-performance claim','falsification':'Wrong amount/unit/period/source mapping or no improvement in structured coverage','champion':'TASK91_PREFIX_EXCERPT_PACKET','challenger':'TASK92_VERIFIED_NUMERIC_CAPITAL_PERIOD_PACKET','input_hash':qdigest(bundle),'budget':{'experiments':1,'parameter_search':0},'stop_conditions':['source hash mismatch','future data','wrong accounting period','daily budget exhausted','worker changed'],'evaluation_metric':'numeric provenance accuracy and transmission coverage; min12 independent company cases for efficacy','minimum_cases':12,'split':'PROCESS_DIAGNOSTIC_ONLY','worker_hash':worker};proposal_id=store.put('task92_factory_proposal',canonical_zero(proposal));manifest={'schema':'TASK92_DISPATCH_V1','decision_ids':decision_ids,'proposal_id':proposal_id,'bundle_id':bundle_id,'worker_hash':worker,'automatic_promotion':False,'live':False};manifest['registry_hash']=qdigest(manifest);freeze(B/'dispatch_registry.json',manifest);freeze(B/'forward_handoff.json',{'decisions':decision_ids,'proposal':proposal_id,'bundle':bundle_id,'existing_paper_orders':0,'readback_verified':all(store.get(i) for i in decision_ids)});print('SEALED_CURRENT_MARKET_DECISIONS',len(decision_ids),'MODEL_CALLS',len(seals))
