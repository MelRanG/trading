from common import *
from quant_harness.investment.financial_packet import verify_fact
from zoneinfo import ZoneInfo
from datetime import datetime,time,timedelta
rows=[];callrows=[]
for p in sorted((B/'packets').glob('*/*.json')):
 x=json.loads(p.read_text());date=x['asof'];facts=0;docs=0
 for c in x['cases']:
  for f in c.get('verified_facts',[]):verify_fact(f,(R/f['source_path']).read_bytes(),date);facts+=1
  for d in c.get('source_documents',[]):
   assert d['published']<date,'same/future ambiguous document';assert sha(R/d['source_path'])==d['source_hash'];docs+=1
  for price in c.get('observed_price_tail',[]):assert price['date']<=date
 for macro in x.get('macro',[]):assert macro['published']<date
 zone=ZoneInfo('America/New_York' if x['market']=='US' else 'Asia/Seoul');close=datetime.combine(datetime.fromisoformat(date).date(),time(16) if x['market']=='US' else time(15,30),zone)
 rows.append({'market':x['market'],'asof':date,'cutoff_local':close.isoformat(),'cutoff_UTC':close.astimezone(__import__('datetime').timezone.utc).isoformat(),'packet_hash':digest(x),'verified_numeric_facts':facts,'dated_documents':docs,'future_input_detected':False})
for p in sorted((B/'model_calls/research').glob('*.reserved.json')):callrows.append(json.loads(p.read_text()))
freeze(B/'input_audit.json',{'packets':rows,'no_future_doc_or_bar_found_in_structured_fields':True,'not_proven':'No guarantee against latent LLM historicalknowledge or unrecognized updatedtext in datedpages','calls':callrows,'tokens':sum(r.get('measured_tokens',0) for r in callrows),'hard_token_cap':False,'subscription_money_cost_unknown':True})
print('PACKETS',len(rows),'FACT_VERSIONS',sum(x['verified_numeric_facts'] for x in rows),'CALLS',len(callrows),'TOKENS',sum(r.get('measured_tokens',0) for r in callrows))
