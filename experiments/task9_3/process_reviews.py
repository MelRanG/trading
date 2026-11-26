from common import *
from quant_harness.investment.review import policy,process_review
cfg=policy(R);count=0
for p in sorted((B/'decisions').glob('*/*.json')):
 dec=json.loads(p.read_text());m=dec['market'];asof=dec['asof'];source=json.loads((B/'packets'/m/(asof+'.json')).read_text());identity='TASK93-'+m+'-'+asof;weights={c['symbol']:c['weight'] for c in dec['cases'] if c['weight']>0};receipts=[];evidence=[]
 for c in source['cases']:
  for d in c['source_documents']:evidence.append({'evidence_id':d['source_hash']});receipts.append({'status':'SAVED','source_hash':d['source_hash']})
  if not c['source_documents']:receipts.append({'status':'MISSING_PRIMARY','symbol':c['symbol']})
 packet={'source_decision_id':identity,'market':m,'cutoff':asof,'strategy_id':'TASK93_HISTORICAL_DIAGNOSTIC','contract_hash':sha(Path(__file__).parent/'contract.json'),'input_hash':digest(source),'algorithm_hash':sha(Path(__file__).parent/'prepare_research.py'),'registered_policy':{'gross_cap':.9,'single_name_cap':.25},'weights':weights,'eligible':bool(weights),'intents':[{'symbol':s,'target':w,'execution':'NEXT_ELIGIBLE_SESSION'} for s,w in weights.items()],'analysis':{'missing':[c['symbol'] for c in dec['cases'] if c['state']=='RESEARCH_INCOMPLETE' and c['weight']>0]},'source_receipts':receipts,'evidence':evidence,'company_candidates':[],'information_scope':'AT_DECISION_ONLY_NO_OUTCOMES'}
 result=process_review(packet,cfg);freeze(B/'process_reviews'/m/(asof+'.json'),{'packet':packet,'review':result,'outcome_access':False});count+=1
print('BLINDED_PROCESS_REVIEWS',count)
