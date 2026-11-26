"""Seal up to2 actual information-research candidates, no engine/Factory mutations."""
from common import *
from normalize import text,doc,upper,num
from features import policy_context,guidance_change,contract_changes,asof
from decimal import Decimal
from zoneinfo import ZoneInfo
import io,pandas as pd

# Only original dated policy releases may enter historical event context.
macro=[]
for record in json.loads((B/'macro_collection.json').read_text()):
 meta=record['source']
 if meta['status']!='SAVED':macro.append({'kind':record['kind'],'PIT':'UNAVAILABLE','source':meta});continue
 raw=body(meta)
 if record['kind']=='FOMC_TARGET_RATE':
  d=doc(raw);paragraphs=[text(p) for p in d.xpath('//p')];main=next(p for p in paragraphs if 'target range for the federal funds rate' in p and ('5-1/4 to 5-1/2' in p or '4-3/4 to 5 percent' in p));full=text(d);assert '2:00 p.m. EDT' in full
  day=record['date'];day=day[:4]+'-'+day[4:6]+'-'+day[6:8];dt=datetime.datetime.fromisoformat(day+'T14:00:00').replace(tzinfo=ZoneInfo('America/New_York'));lo,hi=(5.25,5.50) if '5-1/4 to 5-1/2' in main else (4.75,5.0)
  macro.append({'kind':'FOMC_TARGET_RATE','public_date':day,'published_at':dt.isoformat(),'precision':'MINUTE_OFFICIAL_RELEASE','available_upper_bound':(dt+datetime.timedelta(minutes=5)).isoformat(),'processing_buffer_minutes_assumed':5,'announced_action_bps':0 if 'maintain the target range' in main else -50,'midpoint_pct':(lo+hi)/2,'target_lower_pct':lo,'target_upper_pct':hi,'PIT':'VERIFIED_DATED_RELEASE','source':meta,'paragraph':main,'role':'Funding/discount-rate context only, no allocation recommendation'})
 else:
  frame=pd.read_csv(io.BytesIO(raw));col=record['kind'];assert col in frame and 'observation_date' in frame;dates=pd.to_datetime(frame['observation_date']);values=pd.to_numeric(frame[col],errors='coerce');assert not dates.duplicated().any();valid=values.dropna();delta=(valid.iloc[-1]-valid.iloc[-6])*100 if len(valid)>5 else None
  macro.append({'kind':col,'PIT':'PIT_PARTIAL','source':meta,'observations':len(frame),'finite':int(values.notna().sum()),'missing':int(values.isna().sum()),'first':str(dates.min().date()),'last':str(dates.max().date()),'last_value_pct':float(valid.iloc[-1]),'last_minus_5_observations_bps':float(delta) if delta is not None else None,'allow_historical_research_input':False,'reason':'Current historical backfill, observation_date is not publication timestamp; no ALFRED vintage pin. Latest value not used in historical event context.'})
dump(B/'macro_normalized.json',macro)

US=json.loads((B/'US_collection.json').read_text());pep=next(x for x in US if x['symbol']=='PEP');guides=[]
for item in pep['earnings_releases']:
 source=item.get('exhibit',{});assert source.get('status')=='SAVED';raw=body(source);d=doc(raw);nodes=[n for n in d.xpath('//p|//div') if 'organic revenue' in text(n).lower() and 'previously' in text(n).lower() and len(text(n))<350];assert nodes;node=min(nodes,key=lambda n:len(text(n)));quote=text(node);day=item['date']
 if day=='2024-07-11':assert 'Approximately 4 percent' in quote and 'at least 4%' in quote;current='approximately_4_percent';previous='at_least_4_percent'
 else:assert 'low-single-digit' in quote and 'previously approximately 4%' in quote;current='low_single_digit';previous='approximately_4_percent'
 eps_nodes=[n for n in d.xpath('//p|//div') if 20<len(text(n))<350 and 'constant currency EPS' in text(n) and '8' in text(n)]
 eps=min(eps_nodes,key=lambda n:len(text(n)));assert 'At least 8 percent increase' in text(eps)
 # Match explicit issuer FY/basis in original release, not an analyst surprise.
 assert '2024' in text(d) and 'non-GAAP' in text(d)
 guides.append({'event_id':item['filing']['accessionNumber']+':organic_revenue_guidance','issuer':'PEP','market':'US','fiscal_year':2024,'metric':'organic_revenue_growth','basis':'ISSUER_NON_GAAP_FX_ACQUISITION_ADJUSTED','current':current,'explicit_previous':previous,'public_date':day,'available_upper_bound':upper(max(day,item['filing']['filingDate']),'US'),'precision':'DATE_BOUND_CONSERVATIVE','acceptance_raw':item['filing'].get('acceptanceDateTime'),'acceptance_timezone_verified':False,'source':source,'primary_8K':item['primary'],'text_locator':{'xpath':node.getroottree().getpath(node),'quote':quote},'no_consensus_surprise_claim':True,'magnitude_numeric':None,'EPS_guidance_locator':{'xpath':eps.getroottree().getpath(eps),'quote':text(eps),'value':'at_least8percent_core_constant_currency_EPS'}})
guides.sort(key=lambda x:x['public_date']);change=guidance_change(guides[0],guides[1]);change.update(event_id=guides[1]['event_id'],available_upper_bound=guides[1]['available_upper_bound'],previous_guidance=guides[0]['current'],new_guidance=guides[1]['current'],EPS_outlook='at_least8percent_constant_currency_core_growth_retained_not_collapsed_into_revenue_signal',macro=policy_context(macro,guides[1]['available_upper_bound']))
# Do not impose a numeric lowering on "at least4" -> "approximately4" beyond issuer wording.
dump(B/'guidance_events.json',{'events':guides,'features':[change],'July_transition':'Lower-bound removal/softening; not assigned a numeric negative return signal'})

# Original B0 archives, mapped chronological amendment chain; later revisions are evaluator-only until their own dates.
old=json.loads((R/'runtime/task13_b0/validation.json').read_text());first=next(e for e in old['contracts'] if e['receipt_no']=='20240123800494');records=[{'event_id':first['receipt_no'],'contract_id':first['receipt_no'],'public_date':first['publication_date'],'available_upper_bound':upper(first['publication_date'],'KR'),'amount':first['contract_amount_KRW'],'currency':'KRW','VAT_included':True,'source_path':first['source_path'],'source_hash':first['source_sha256']}]
for r in sorted(old['revision_audit'],key=lambda x:x['receipt_no']):
 p=next((R/'runtime/task13_b0/revision_audit'/r['receipt_no']).glob('*.xml'));d=doc(p.read_bytes());rows=[' '.join(text(c) for c in row.xpath('./td|./th')) for row in d.xpath('//tr')];newrows=[x for x in rows if '계약금액(원)' in x];current=[re.findall(r'\d{1,3}(?:,\d{3})+',x) for x in newrows];only=next(x[0] for x in current if len(x)==1);comparison=next(x for x in current if len(x)==2);assert num(only)==num(comparison[1]);previous_date=next(re.search(r'\d{4}-\d{2}-\d{2}',x)[0] for x in rows if '정정관련 공시서류제출일' in x);acc=r['receipt_no'];day=acc[:4]+'-'+acc[4:6]+'-'+acc[6:8];whole=text(d);assert ('부가세 포함' in whole or '부가가치세 포함' in whole)
 records.append({'event_id':acc,'contract_id':first['receipt_no'],'public_date':day,'available_upper_bound':upper(day,'KR'),'amount':str(num(only)),'previous_amount':str(num(comparison[0])),'previous_public_date':previous_date,'currency':'KRW','VAT_included':True,'source_path':str(p.relative_to(R)),'source_hash':sha(p),'statement':'계약금액 변경, not automatically new economic scope','new_contract_revenue_recognition_schedule':None})
changes=contract_changes(records,upper('2026-11-16','KR'))
for c in changes:c['macro']=policy_context(macro,c['available_upper_bound'])
dump(B/'contract_events.json',{'events':records,'features':changes,'other_first_contracts':old['contracts'][1:],'partial_old_contract_must_not_be_full_increment':True})

# Confirm only session dates, never open/close/return columns. Existing official DB has2026only.
from quant_harness.investment.exploration import official_sessions
calendar={'official_recent':{},'provider_date_only':{},'NYSE_source':json.loads((B/'calendar_source.json').read_text())}
for market,symbol in [('US','^GSPC'),('KR','^KS11')]:
 try:calendar['official_recent'][market]=official_sessions(market,now())
 except Exception as e:calendar['official_recent'][market]={'status':'UNAVAILABLE','type':type(e).__name__}
 p=R/'runtime/task13_r0/accepted'/market/symbol/'quote.csv';datecol=pd.read_csv(p,usecols=['date'])['date'].tolist();calendar['provider_date_only'][market]={'source':str(p.relative_to(R)),'source_hash':sha(p),'columns_read':['date'],'precision':'Provider observed market sessions, no price data used','dates':datecol}
# Full holiday list from actual NYSE operator announcement, not a weekday assumption.
calmeta=calendar['NYSE_source'];closed=[]
if calmeta['status']=='SAVED':
 d=doc(body(calmeta));tables=d.xpath('//table');rows=[]
 for t in tables:
  rs=[[text(c) for c in r.xpath('./td|./th')] for r in t.xpath('.//tr')]
  if any(r==['HOLIDAY','2024','2025','2026'] for r in rs):rows=rs;break
 assert len(rows)>=11
 for r in rows:
  if len(r)==4 and r[0]!='HOLIDAY' and r[1].strip():
   s=r[1].replace('*','');closed.append(datetime.datetime.strptime(s+', 2024','%A, %B %d, %Y').date().isoformat())
 calendar['NYSE_holiday_dates_2024']=closed
for e in [change]+changes:
 market='US' if e['event_id']==change['event_id'] else 'KR';local=e['available_upper_bound'][:10];days=calendar['provider_date_only'][market]['dates'];nxt=next((d for d in days if d>local),None);e['next_observed_session']=nxt;e['session_provenance']='EXISTING_INDEX_DATE_ONLY'
 if market=='US' and nxt and closed:
  observed_day=datetime.date.fromisoformat(nxt);assert observed_day.weekday()<5 and nxt not in closed;e['calendar_corroboration']='Observed session + official NYSE2024 holiday schedule';e['first_research_entry']=datetime.datetime.fromisoformat(nxt+'T09:30:00').replace(tzinfo=ZoneInfo('America/New_York')).isoformat();e['historical_actual_processing_latency_known']=False
 else:e['first_research_entry']=None;e['calendar_corroboration']='Historical KRX official calendar not verified; provider session only, execution gated'
calendar['provider_date_only']={k:{a:b for a,b in v.items() if a!='dates'} for k,v in calendar['provider_date_only'].items()};dump(B/'calendar_audit.json',calendar)
# Re-save features with entry rules and audited context; no weights or trade intents.
dump(B/'guidance_events.json',{'events':guides,'features':[change],'July_transition':'Lower-bound removal/softening only, no invented percentage magnitude'})
dump(B/'contract_events.json',{'events':records,'features':changes,'other_first_contracts':old['contracts'][1:],'partial_old_contract_must_not_be_full_increment':True})
print('BRIDGE_FEATURES',change['value'],[(x['event_id'],x['delta_contract_KRW']) for x in changes])
