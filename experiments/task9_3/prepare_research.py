from common import *
import re,copy
from quant_harness.investment.financial_packet import model_numeric_view
W=Path('/home/ansy/app/quant-diligence/task9-3-work');K=Path('/home/ansy/app/quant-diligence/vibe-original/agent/src/skills')
methods={n:(K/n/'SKILL.md').read_text()[:1400] for n in ['earnings-forecast','valuation-model','macro-analysis','sector-rotation']}
def view_packet(packet):
 v=copy.deepcopy(packet)
 for c in v['cases']:
  c['verified_facts']=model_numeric_view(c['verified_facts'])
  for d in c['source_documents']:
   t=d['text']
   if v['market']=='KR':
    d['text']=t[:1400];d['narrative_excerpt_only']=True;d['full_numeric_facts_retained']=True
    continue
   if len(t)>18000:
    windows=[(0,5500)]
    for pattern in [r'CONSOLIDATED.*?(?:BALANCE|FINANCIAL POSITION)',r'CONSOLIDATED.*?STATEMENTS OF.*?(?:INCOME|EARNINGS|CASH)',r'Consolidated.*?(?:balance sheet|statement.*cash)',r'RECONCILIATION OF NET INCOME',r'CONSOLIDATED BALANCE',r'Cash and cash equivalents',r'Weighted.average.*?shares',r'Average.*?shares',r'Share capital',r'Total Debt']:
     hits=list(re.finditer(pattern,t,re.I))
     if hits:
      a=hits[0].start();windows.append((max(0,a-250),min(len(t),a+5000)))
    windows=sorted(windows);merged=[]
    for a,b in windows:
     if merged and a<=merged[-1][1]:merged[-1]=(merged[-1][0],max(merged[-1][1],b))
     else:merged.append((a,b))
    d['text']='\n[ORIGINAL_RANGE]\n'.join(t[a:b] for a,b in merged);d['retained_source_ranges']=merged;d['full_original_chars']=len(t)
 return v
system='''You are the original Vibe financial/market investment research component in a strictly bounded historical diagnostic. Use ONLY supplied documents/facts/price history asof the supplied LOCAL REGULAR CLOSE. NO tools, outside memory, future news/results or invented consensus. Prior model analysis can be revised with new evidence, never secretly edited. Risk/gross/name caps are research caps, not targets. Selection quality ranking is NOT a buy. Explain missing data separately from proven unattractiveness. Each company requires source-grounded business drivers, independent next3FY revenue/earnings/cashflow forecasts (not guidance repetition), Bear/Base/Bull conditional per-share valuations or expected-return ranges with accounting method, debt/cash/shares/leases/FCFF vs FCFE bridge. Use suitable method for financial/insurance businesses; do not force genericDCF. Numeric assumptions explicit, no arbitrary EPS multiple. If sufficient primary economics supports a defensible conditional valuation, make it and separately state capital/dilution uncertainty; do not demand impossible perfect information just to avoid judgment. If not sufficient, null with exactmissingfields. Do not invent numeric facts, share counts, market prices or macro news.
Decide a concrete research-only portfolio for the NEXT eligible regular-session OPEN: weights0..0.25 each, total<=0.90, max5names, sector<=.50 (uncertain sector disclose). NoETF. Valid states RESEARCH_INCOMPLETE,UNATTRACTIVE,WATCH,INVESTABLE. Only INVESTABLE receives positiveweight; WATCH stays0 until separately researched, no invented autoentry. Cash has real benchmark opportunity cost. Do not force buys. Investing at a conditionally attractive valuation with disclosed assumptions is allowed in this HISTORICAL RESEARCH account, not officialPaper promotion. Same price/guidance alone is not a valid investment edge. For positiveweights explicitly state entry_price_ceiling or null (nextopenanyprice thesis), exitconditions, catalysts and information sufficient to act. Fullstop policy fixedclose25%drawdown fromentry->nextopen, no parameterchanges. Holding priorweights is allowed only if thesisstillvalid. Tradeonly onmonthlyorimportantmaterialevent reevaluation; no churntofillquota.
Return concise JSON only {asof,market,input_hash,market_context:{observed,unknown,decision_effect},cases:[{symbol,rank,research_priority,thesis,source_facts:[{metric,value,unit,source_hash}],forecasts:[{FY,revenue,operating_income,net_income,cashflow,unit,currency,basis,drivers,guidance_vs_independent}],valuation:{method,bear,base,bull,per_share_currency,horizon_years,assumptions,capital_bridge,missing},state,decision_reason,weight,entry_price_ceiling,invalidation,catalysts,change_from_prior}],selection_top3:[symbols],cash_weight,portfolio_reason,relative_alternatives,uncertainty}. Expectedreturnranges are assumptions, not validated alpha.'''
if __name__=='__main__':
 m,date=sys.argv[1:];packet=json.loads((B/'packets'/m/(date+'.json')).read_text());view=view_packet(packet);h=digest(packet);view['input_hash']=h;req={'messages':[{'role':'system','content':system+'\nPinnedmethodexcerpts:'+json.dumps(methods,ensure_ascii=False)},{'role':'user','content':json.dumps(view,ensure_ascii=False,separators=(',',':'))}]};name=m+'_'+date
 # Refuse before transport/model reservation; never hide truncation.
 assert len(json.dumps(req))<176000,('request too large',len(json.dumps(req)))
 freeze(B/'requests'/(name+'.request.json'),req);freeze(W/(name+'.request.json'),req);print(name,'REQUEST_BYTES',len(json.dumps(req)),flush=True)
