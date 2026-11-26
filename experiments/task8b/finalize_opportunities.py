from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,sys
import pandas as pd
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'))
from quant_harness.investment.opportunity import probe_plan
from quant_harness.investment.research import digest
b=R/'runtime/task8b';w=Path('/home/ansy/app/quant-diligence/task8b-vibe-work');cfg=json.loads((R/'config/task8b_exploration.json').read_text());packet=json.loads((b/'research_packet_v2.json').read_text());review=[]
for stage in ['review_us_resume','review_kr_resume']:review+=json.loads((w/(stage+'.json')).read_text())['cases']
values=json.loads((b/'conditional_values.json').read_text());result=[]
for item in review:
 source=next(c for c in packet['cases'] if c['ticker']==item['ticker']);hashes=[]
 for s in source['sources']:
  h=s.get('receipt',{}).get('source_hash',s.get('sha256'))
  if h:hashes.append(h)
 record={**item,'market':source['market'],'company':source['company'],'sector':source['sector'],'listing_verified':source.get('listing_verified',False),'source_hashes':sorted(set(hashes)),'source_quality':source['source_quality'],'current_price':source['current_price']['value'],'price_event_at':source['current_price']['event_at'],'valuation':values.get(item['ticker']),'official_paper_status':'NOT_ELIGIBLE_UNPROVEN_EDGE','hypothesis_type':'FORWARD_RESEARCH_NOT_VALIDATED_INVESTMENT_EDGE'}
 record['probe']=probe_plan(record,cfg);record['candidate_fingerprint']=digest(record);result.append(record)
selected=[r for r in result if r['probe']['eligible_for_probe']]
if len(selected)>cfg['maximum_names']:raise ValueError('unregistered more probes than allowed')
if selected and len({r['sector'] for r in selected})<3:raise ValueError('probe diversity requirement')
for market in ['US','KR']:
 weights={r['ticker']:r['probe']['weight'] for r in selected if r['market']==market}
 if sum(weights.values())>cfg['gross_cap'] or any(w>cfg['single_name_cap'] for w in weights.values()):raise ValueError('exploration risk cap')
 for sector in {r['sector'] for r in selected if r['market']==market}:
  if sum(r['probe']['weight'] for r in selected if r['market']==market and r['sector']==sector)>cfg['sector_cap']:raise ValueError('sector cap')
# Factual price decomposition, not causal proof or an optimized trading rule.
frames={s:pd.read_csv(b/'prices'/(s+'.csv')).set_index('date').close for s in ['NVDA','CRWV','SPY']};attribution={}
for symbol in ['NVDA','CRWV']:
 pair=pd.DataFrame({'stock':frames[symbol],'market':frames['SPY']}).dropna();rows=[]
 for start,end in [('2026-11-06','2026-11-12'),('2026-11-11','2026-11-12')]:
  if start not in pair.index or end not in pair.index:continue
  r=pair.loc[end]/pair.loc[start]-1;rows.append({'start':start,'end':end,'stock_return':float(r.stock),'SPY_price_return':float(r.market),'arithmetic_market_difference':float(r.stock-r.market)})
 pre=pair.loc[pair.index<'2026-11-06'].pct_change().dropna().tail(63);beta=float(pre.stock.cov(pre.market)/pre.market.var()) if len(pre)>20 else None
 attribution[symbol]={'windows':rows,'pre_event_beta':beta,'beta_samples':len(pre),'limits':'Observed price co-movement/difference, not identified CEO/financing causal effect. Common AI demand, rates, selection and unobserved news confound. Price-only, not total-return. Source time preserved.'}
(b/'price_attribution.json').write_text(json.dumps(attribution,indent=2));out={'version':'TASK8B_OPPORTUNITY_RESEARCH_V1','sealed_research_at':datetime.now(timezone.utc).isoformat(),'input_hash':digest(packet),'policy_hash':digest(cfg),'cases':result,'probe_tickers':[r['ticker'] for r in selected],'official_paper_eligible':0,'forward_performance':'PENDING','prior_cash_analysis':'Original strict Paper evidence criterion remains unmet; first-model missing forecasts cannot establish that every price is unattractive'}
path=b/'final_opportunities.json'
if path.exists():raise ValueError('final opportunity snapshot already exists; preserve immutable original')
path.write_text(json.dumps(out,indent=2,ensure_ascii=False));print(json.dumps({'classifications':{s:sum(r['status']==s for r in result) for s in ['RESEARCH_INCOMPLETE','RESEARCH_SHADOW','PAPER_ELIGIBLE','REJECTED']},'probes':out['probe_tickers'],'attribution':attribution},indent=2))
