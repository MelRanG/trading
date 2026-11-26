from common import *
import re,shutil
W=Path('/home/ansy/app/quant-diligence/task9-4-work');K=Path('/home/ansy/app/quant-diligence/vibe-original/agent/src/skills')
startmap={'US_AIR':'January 06, 2026','US_IR':'April 28, 2026','US_MAIR':'May 12, 2026','US_TILE':'May 8, 2026','US_STC':'HOUSTON, April 22, 2026','US_TMHC':'SCOTTSDALE, Ariz., April 22, 2026','US_WATER':'April 30, 2026','US_FREIGHT':'January','US_GEHC':'April','US_USFD':'05/07/2026','US_JNJ':'April','KR_FOOD':'2026-05-14','KR_POWER':'2026.04.28','KR_POWER2':'2026-04-26','KR_CONSTRUCTION':'2026.05.08','KR_SEMIEQUIP':'2026-02-28','KR_KCTECH':'2026.05.13','KR_BIO':'2026-04-22','KR_BIOEXPORT':'2026.04.10'}
records=[];excluded=[]
for p in sorted((B/'sources').glob('*/receipt.json')):
 r=json.loads(p.read_text());ident=r['id']
 if r['status']=='FAILED':excluded.append({'id':ident,'reason':'SOURCE_ACCESS_FAILED_NOT_LOW_ATTRACTIVENESS','error':r.get('error_type')});continue
 pub=r['published_claimed'];assert pub<'2026-05-15';f=p.parent
 q=f/('web_extract.txt' if 'WEB' in ident else 'normalized_v2.txt' if ident=='KR_FOOD' else 'normalized.txt');t=q.read_text();a=0
 if ident in startmap:
  a=t.find(startmap[ident])
  if a<0:
   if ident=='US_FREIGHT':excluded.append({'id':ident,'reason':'DATED_BODY_UNRESOLVED'});continue
   a=0
 body=t[a:]
 # Never pass current news navigation or comments outside the dated article.
 for marker in ['관련기사','함께 읽으면 좋은','당신을 위한 추천','인기 뉴스','ⓒ','Copyright','View source version','Read more about']:
  end=body.find(marker)
  if end>500:body=body[:end]
 limit=6000 if r['market']=='US' else 2600;body=body[:limit]
 # Explicit current header was removed for a dated article.
 if 'UPDATE: 2026-11' in body:raise ValueError('future siteheader in modelbody')
 rec={'source_id':ident,'market':r['market'],'published':pub,'kind':r['kind'],'url':r['url'],'source_hash':sha(q),'raw_hash':r['raw_sha256'],'source_path':str(q.relative_to(R)),'excerpt_start':a,'excerpt':body,'PIT':'PARTIAL_DATED_PUBLISHED_ARTICLE_RETRIEVED_NOW','publication_basis':'source article date / dated official release; no historical first-seen receipt'};records.append(rec)
freeze(B/'curated_sources_initial.json',{'sources':records,'excluded':excluded,'no_future_prices_queried':True,'date_operator_failures':'Future results remain in rawsearchlogs only, not this curated packet'})
for market in ['US','KR']:
 planstage='plan_US' if market=='US' else 'plan_KR_v2';plan=json.loads((W/(planstage+'.json')).read_text());macro=json.loads((R/'runtime/task9_3/macro'/market/('2026-04-29.json' if market=='US' else '2026-04-10.json')).read_text());assert macro['published']<'2026-05-15'
 view={'market':market,'asof':'2026-05-15','original_search_plan':plan,'retrieved_sources':[r for r in records if r['market']==market],'macro':macro,'unresolved_source_access':[r for r in excluded if r['id'].startswith(market)],'scope':'Source led discovery, no predefined candidate list or financial-size exclusion. No price/performance data. Disclosure of priorTask93outcomes known bycoordinator, noneprovidedhere.'}
 req={'messages':[{'role':'system','content':'Team2 original Vibe independent opportunity DISCOVERY. Only supplied preMay15datedsource facts, no futurememory/tools in this inference; emit tool searchrequests for real subsequent retrieval. Find listed businesses whose value/earnings can change from actual observed industrial/customer/product/cost/policy shifts. Identify all relevant named companies as broad_candidates (not arbitrary knownstocks; guide20-50 notquota). Separate confirmed companychange from unverified plausible peers or gaps; infer ticker only markneedsverification if not in source. Choose as many deeper studies as evidence warrants, guide5-10 NOTexactquota; include independentcontrarycases, no list/order/hash/previoustarget constraint. Preserve sparse companies asINSUFFICIENT_DATA rather thanunattractive. Do not claim neverseennews or confidenceprobabilities. For each deep candidate propose 1-3 directpeers,1-3same-theme alternatives with differentbusinessmodels,0-2sector/themeETFs ifgenuinelyapt, all asof existence/relevance toverify, not futureperformance. ETFs are comparators only. Emit at most8 targetedqueries total for latestpreMay15companyprimaryfinancials, peers, ETFexistence/overlap. Do NOT issue repeatedequityselectionbyfuturewinner memory. No buy/sell/weights/entry/exit/portfolioactions. ReturnJSON {market,asof,market_industry_direction:[{theme,evidence_sources,inference,risk}],broad_candidates:[{name,symbol,industry,discovery_evidence_ids,status,reason}],deep_candidates:[{name,symbol,industry,discovery_reason,key_hypothesis,evidence_sources,missing_financial_fields,possible_comparators:[{name,symbol,relation:direct_peer|theme_alternative|sector_ETF,why,needs_verification}],research_questions}],not_selected:[{symbol,reason,status}],search_requests:[{query,purpose,symbols}],limitations}. No forcedDCF or targets.'},{'role':'user','content':json.dumps(view,ensure_ascii=False,separators=(',',':'))}]}
 assert len(json.dumps(req))<176000,('oversized',market,len(json.dumps(req)));stage='discover_'+market;freeze(B/'requests'/(stage+'.request.json'),req);freeze(W/(stage+'.request.json'),req);print(stage,'sources',len(view['retrieved_sources']),'requestchars',len(json.dumps(req)),flush=True)
