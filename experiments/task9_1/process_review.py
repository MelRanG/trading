"""Existing blinded process-review engine, before evaluator obtains outcomes."""
from common import *
from quant_harness.investment.review import policy,process_review
cfg=policy(R);rows=[];coverage=[]
for date in ['2024-11-29','2025-06-30']:
 foundation=json.loads((B/'model_inputs'/date/'foundation.json').read_text())
 for c in foundation['companies']:
  source=c['source'];packet={'source_decision_id':'TASK91-'+date+'-'+c['symbol'],'market':c['market'],'cutoff':foundation['asof'],'strategy_id':'TASK9_1_RESEARCH','contract_hash':sha(R/'experiments/task9_1/contract.json'),'input_hash':digest(foundation),'algorithm_hash':sha(R/'experiments/task9_1/prepare_model.py'),'registered_policy':{'gross_cap':.6,'single_name_cap':.2},'weights':{},'eligible':False,'intents':[],'analysis':{'missing':foundation['missing_inputs']},'source_receipts':[{'status':source.get('status','FAILED')}],'evidence':[{'evidence_id':source.get('original_sha256',digest(source))}],'company_candidates':[]}
  result=process_review(packet,cfg);rows.append({'packet':packet,'review':result,'sealed_at':now()})
  fullpath=B/'deep'/date/c['symbol']/'original.txt'
  if c['market']=='KR':fullpath=B/'inputs'/date/c['symbol']/'original.txt'
  full=fullpath.read_text() if fullpath.exists() else '';compact=json.loads((B/'compact_requests'/('value2_'+date[:4]+'.request.json')).read_text());worker=next(v for v in json.loads(compact['messages'][1]['content'])['input']['companies'] if v['symbol']==c['symbol'])
  workertext=json.dumps(worker,ensure_ascii=False).lower();full=full.lower();groups={'shares':['weighted average','shares outstanding','발행주식','주당순'], 'debt':['total debt','long-term debt','차입금','부채'], 'cashflow':['cash flow','cash flows','현금흐름'], 'earnings':['earnings','net income','영업이익','당기순']}
  cov={'date':date,'symbol':c['symbol'],'source_status':source.get('status'),'keyword_proxy_only':True,'original_hash':source.get('original_sha256'),'worker_hash':digest(worker)}
  for label,needles in groups.items():cov[label]={'in_original':any(n in full for n in needles),'in_worker':any(n in workertext for n in needles)}
  coverage.append(cov)
freeze(B/'blinded_process_reviews.json',rows);freeze(B/'packet_coverage_audit.json',coverage);print('BLINDED_PROCESS_SEALS',len(rows))
