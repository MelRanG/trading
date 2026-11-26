"""Two independently called views; common foundation hash, distinct actual message hashes."""
from common import *
W=Path('/home/ansy/app/quant-diligence/task9-1-work');W.mkdir(exist_ok=True);(W/'home').mkdir(exist_ok=True)
V=Path('/home/ansy/app/quant-diligence/vibe-original/agent/src/skills')
for date in ['2024-11-29','2025-06-30']:
 companies=[];allocation={};screen_hashes={}
 for market in ['US','KR']:
  screen=json.loads((B/'screens'/date/(market+'.json')).read_text());allocation[market]=screen['allocation_basket'];screen_hashes[market]=sha(B/'screens'/date/(market+'.json'))
  for x in screen['deep']:
   s=x['symbol'];p=B/'deep'/date/s/'packet.json';facts=json.loads(p.read_text());nom=json.loads((B/'inputs'/date/s/'nominal_check.json').read_text());assert nom['status'] in ['MATCH','UNIT_CONFLICT'];record={k:x[k] for k in ['market','symbol','name','sector','size_status']};record.update(price_at_cutoff=nom['toss_close'],currency='USD' if market=='US' else 'KRW',price_receipt_hash=nom['source_sha256'],past_momentum63=x['momentum63'],past_vol63=x['vol63'],source=facts)
   if facts.get('text'):record['source']={**facts,'text':facts['text'][:7000]}
   if s=='SMCI':record['source_update']=json.loads((B/'deep'/date/'SMCI_update/packet.json').read_text())
   if s=='FIX':record['source_web_fallback']=json.loads((B/'deep'/date/s/'web_facts.json').read_text())
   if market=='KR':record['dated_shares_proxy']=x['dated_report_shares'];record['original_financial_warning']='API future amendment rejected if API_matches_original=false; rely only on original excerpts. Annualization is a hypothesis, not recorded fact.'
   companies.append(record)
 foundation={'asof':date+'T23:00:00Z','companies':companies,'screen_hashes':screen_hashes,'fixed_allocation_basket':allocation,'historical_knowledge_warning':'Reconstruction with modern LLM; never claim independent historical prediction. No outcome input or tool access.','missing_inputs':['point-in-time consensus','institutional net flows','full delisting universe','complete corporate action audit']}
 h=digest(foundation);freeze(B/'model_inputs'/date/'foundation.json',foundation)
 context={m:json.loads((B/'context'/date/(m+'.json')).read_text()) for m in ['US','KR']}
 for arm in ['value','market']:
  view=json.loads(json.dumps(foundation));view['foundation_hash']=h
  if arm=='value':
   for x in view['companies']:x.pop('past_momentum63');x.pop('past_vol63')
  else:view['market_context']=context
  skills={name:{'sha256':sha(V/name/'SKILL.md'),'method_excerpt':(V/name/'SKILL.md').read_text()[:1100]} for name in ['valuation-model','earnings-forecast']+(['sector-rotation','macro-analysis'] if arm=='market' else [])}
  sysmsg='Use ONLY supplied dated evidence, never historical memory/later outcomes/tools/web. You are original Vibe ChatLLM research component applying the provided upstream research methods, not its full Autopilot. Output concise English JSON only. Separate facts/guidance/independent forecasts. Assess growth, financial claims, debt/EV-to-equity, dilution, price-implied expectations, bull/base/bear valuation ranges or null when unsupported. Missing information is RESEARCH_INCOMPLETE, not proof an investment is unattractive. Rank exactly3 research-quality candidates per market from supplied deep list, without claiming these are buys. This top3 ranking supports a counterfactual stock-selection test even when investment policy is cash. For policy weights, allocate only within each frozen fixed_allocation_basket: each0..0.20 total<=0.60, cash is valid. Do NOT invent unsupported probabilities or consensus. Value arm excludes macro/price trends; market arm uses supplied macro, momentum, catalysts and relative opportunity, identifying exactly what changes the decision. For EACH company give a single future annual numerical forecast only if defensible, metric/unit/targetFY/range and independent_from_guidance flag; otherwise null with missing evidence. Keep total output under6500tokens.'
  schema={'asof':foundation['asof'],'foundation_hash':h,'arm':arm,'companies':[{'market':'US/KR','symbol':'input symbol','thesis':'brief','facts_used':['specific provided evidence'],'missing':['unresolved'],'valuation_price_range_12m':{'bear':None,'base':None,'bull':None,'method':'or unsupported'},'forecast':None,'invalidation':'specific','market_increment':'only market arm','status':'RESEARCH_INCOMPLETE/RESEARCH_SHADOW/REJECTED'}],'portfolios':[{'market':'US/KR','ranked_top3':['symbol1','symbol2','symbol3'],'fixed_basket_weights':{'input symbol':0.0},'cash_reason':'evidence-based, distinguish incomplete vs negative value','decision_changers':[]} ]}
  request={'messages':[{'role':'system','content':sysmsg},{'role':'user','content':json.dumps({'input':view,'upstream_methods':skills,'output_schema':schema},ensure_ascii=False)}]};stage=arm+'_'+date[:4];freeze(W/(stage+'.request.json'),request);freeze(B/'model_inputs'/date/(arm+'.json'),{'request':request,'foundation_hash':h,'request_hash':digest(request),'candidate_fingerprint':digest([(x['market'],x['symbol']) for x in companies]),'created_at':now()});print(stage,len(json.dumps(request)),h,flush=True)
