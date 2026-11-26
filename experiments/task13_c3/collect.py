"""Bounded pilot and conditional extension, no price returns or alpha evaluator."""
from common import *
from accounting import structural,api_facts,verify_original
from collections import Counter
from zoneinfo import ZoneInfo
import argparse,math,resource,csv

def records(a):return [{k:v[i] for k,v in a.items()} for i in range(len(a.get('accessionNumber',[])))]
def request_count():return len(list((B/'requests').glob('*.json')))

def company(src,a,max_original=1):
 symbol=a['symbol'];p=B/'companies'/(symbol+'.json');saved=json.loads(p.read_text()) if p.exists() else {'company':a,'events':[],'excluded':[],'attempted_accessions':[]}
 if saved.get('original_attempts_completed',0)>=max_original:return saved
 cfraw,cm=src.get(symbol+'_companyfacts',f"https://data.sec.gov/api/xbrl/companyfacts/CIK{a['CIK']}.json")
 if not cfraw:saved['status']='COMPANYFACTS_'+cm['status'];dump('companies/'+symbol+'.json',saved);return saved
 cf=json.loads(cfraw);assert int(cf['cik'])==int(a['CIK']),'COMPANYFACTS_CIK';events,rejections=structural(cf);saved.update(companyfacts=cm,structural_events=len(events),structural_rejections=rejections)
 if not events:saved['status']='NO_STRUCTURAL_ANNUAL_PAIR';dump('companies/'+symbol+'.json',saved);return saved
 sr,sm=src.get(symbol+'_submissions',f"https://data.sec.gov/submissions/CIK{a['CIK']}.json")
 if not sr:saved['status']='SUBMISSIONS_'+sm['status'];dump('companies/'+symbol+'.json',saved);return saved
 sub=json.loads(sr);assert int(sub['cik'])==int(a['CIK']),'SUBMISSIONS_CIK'
 tickers=sub.get('tickers',[]);saved.update(submissions=sm,identity={'CIK':a['CIK'],'current_submissions_name':sub.get('name'),'tickers_current':tickers,'exchanges_current':sub.get('exchanges'),'formerNames':sub.get('formerNames',[]),'stock_mapping':'Same immutable CIK+current SEC symbol, R0 conservative native boundary; no current exchange projected into past','historical_ticker_tape':'PARTIAL_NOT_FULL_CORPORATE_ACTION_CERTIFICATE'})
 if symbol.replace('.','-') not in [str(t).replace('.','-') for t in tickers]:saved['status']='CURRENT_TICKER_CIK_MISMATCH';dump('companies/'+symbol+'.json',saved);return saved
 byacc={x['accessionNumber']:x for x in records(sub['filings']['recent'])};priority=json.loads((B/'plan.json').read_text())['financials']['period_priority_filing_years'];events.sort(key=lambda e:(priority.index(int(e['filed'][:4])) if int(e['filed'][:4]) in priority else 99,e['filed'],e['accession']))
 wanted=[e for e in events if e['accession'] not in saved['attempted_accessions']]
 histories=saved.get('history_sources',[])
 for event in wanted:
  if saved.get('original_attempts_completed',0)>=max_original or request_count()>=298:break
  acc=event['accession'];f=byacc.get(acc)
  if f is None:
   for hist in sorted(sub['filings'].get('files',[]),key=lambda x:x['name']):
    if not hist['filingFrom']<=event['filed']<=hist['filingTo']:continue
    hr,hm=src.get('history_'+hist['name'],'https://data.sec.gov/submissions/'+hist['name'])
    if hm not in histories:histories.append(hm)
    if hr:byacc.update({x['accessionNumber']:x for x in records(json.loads(hr))})
    f=byacc.get(acc)
    if f:break
  if f is None:saved['excluded'].append({'accession':acc,'reason':'ORIGINAL_SUBMISSION_METADATA_MISSING'});saved['attempted_accessions'].append(acc);continue
  if f['form']!='10-K' or f['filingDate']!=event['filed'] or f['reportDate']!=event['period_end']:
   saved['excluded'].append({'accession':acc,'reason':'NOT_CURRENT_ORIGINAL_ANNUAL_SUBMISSION'});saved['attempted_accessions'].append(acc);continue
  saved['attempted_accessions'].append(acc);saved['original_attempts_completed']=saved.get('original_attempts_completed',0)+1
  facts=api_facts(cf,cfraw,cm,event);base=f"https://www.sec.gov/Archives/edgar/data/{int(a['CIK'])}/{acc.replace('-','')}/";legacy=f.get('isInlineXBRL') in [0,'0',False] and f.get('isXBRL') in [1,'1',True]
  raw,meta=src.get(('submission_' if legacy else 'original_')+acc,base+(acc+'.txt' if legacy else f['primaryDocument']));qualified=None;proof={'reason':'ORIGINAL_UNAVAILABLE','source_status':meta['status']}
  if raw:qualified,proof=verify_original(facts,raw,a['CIK'],meta)
  if raw and not legacy and qualified is None and proof.get('reason') in ['ORIGINAL_VALUE_UNIT_SCOPE_OR_PERIOD_MISMATCH','ORIGINAL_CIK_NOT_CONFIRMED'] and request_count()<298:
   # Official filing package with legacy XBRL, exactly one bounded fallback.
   raw2,meta2=src.get('submission_'+acc,base+acc+'.txt')
   if raw2:
    q2,p2=verify_original(facts,raw2,a['CIK'],meta2)
    if q2 is not None:qualified,proof,raw,meta=q2,p2,raw2,meta2
    else:proof['SGML_fallback']=p2
  if qualified:
   day=event['filed'];public=datetime.datetime.fromisoformat(day+'T23:59:59').replace(tzinfo=ZoneInfo('America/New_York')).isoformat()
   # Only calendar/mask strings, never numerical prices or returns.
   with (R/a['R0_asset']['eligibility_path']).open() as file:eligible=[r['date'] for r in csv.DictReader(file) if r['eligible']=='True']
   first=next((d for d in eligible if d>day),None)
   row={'symbol':symbol,'CIK':a['CIK'],'event_id':acc,'period_start':event['period_start'],'period_end':event['period_end'],'filed':day,'public_available_upper_bound':public,'clock_precision':'OFFICIAL_FILING_DATE_ONLY_CONSERVATIVE_LOCAL_EOD; not first earnings release','raw_acceptanceDateTime':f.get('acceptanceDateTime'),'first_R0_native_eligible_session_after_publication':first,'source':meta,'companyfacts_source_hash':cm['source_hash'],'source_grade':'ORIGINAL_DIMENSIONLESS_USD_CIK_FOUR_VALUES_VERIFIED','form':'10-K','version':'FIRST_CURRENT_PERIOD_ORIGINAL_10K; amendments/comparative duplicates not merged','accounting_scope':'Dimensionless entity-wide USGAAP; M&A/discontinued operations/noncash risks unresolved','sector_current':a['sector_current'],'size_current':a['size_current'],**qualified}
   saved['events'].append(row)
  else:saved['excluded'].append({'accession':acc,'reason':proof['reason'],'proof':proof,'source':meta})
  saved['history_sources']=histories;saved['status']='PROCESSED';dump('companies/'+symbol+'.json',saved)
 saved['history_sources']=histories;dump('companies/'+symbol+'.json',saved);return saved

def summary(group):
 rows=[json.loads((B/'companies'/(a['symbol']+'.json')).read_text()) for a in group if (B/'companies'/(a['symbol']+'.json')).exists()];return {'companies':len(rows),'companyfacts_success':sum('companyfacts'in r for r in rows),'structural_issuers':sum(r.get('structural_events',0)>0 for r in rows),'source_verified_issuers':sum(bool(r['events']) for r in rows),'verified_periods':sum(len(r['events']) for r in rows),'structural_periods':sum(r.get('structural_events',0)for r in rows),'sector_missing':{s:{'companies':sum(r['company']['sector_current']==s for r in rows),'source_verified':sum(r['company']['sector_current']==s and bool(r['events']) for r in rows)}for s in sorted({r['company']['sector_current']for r in rows})}}

def main():
 parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['pilot','decide','expand','panel']);args=parser.parse_args();P=json.loads((B/'plan.json').read_text());src=sources();started=time.process_time();before=request_count()
 if args.stage=='pilot':
  for a in P['pilot']:
   try:row=company(src,a,1);print(a['symbol'],row.get('status'),len(row['events']),flush=True)
   except Exception as e:dump('failures/'+a['symbol']+'.json',{'type':type(e).__name__,'detail':str(e)});print(a['symbol'],'ERROR',type(e).__name__,flush=True)
   if (B/'circuit_stop.json').exists():break
  dump('pilot_summary.json',summary(P['pilot']))
 elif args.stage=='decide':
  # Existing cache accounting is reused, but original confirmation is newly graded, not newcompany collection.
  for a in P['cache_reuse']:
   if request_count()>=290:break
   company(src,a,1)
  pilot=summary(P['pilot']);cache=summary(P['cache_reuse']);yieldrate=pilot['source_verified_issuers']/20;per=(before or request_count())/max(1,pilot['companies']);remaining=300-request_count();needed=max(0,50-cache['source_verified_issuers']-pilot['source_verified_issuers']);new_needed=math.ceil(needed/max(yieldrate,.01))+3;project_new=min(new_needed,60)
  # Conservative incremental estimate: new companyfacts+2metadata+1firstoriginal,
  # plus2more originals for50issuers. Actual remaining-cost decision is preserved.
  observed_average=before/max(1,pilot['companies'])
  estimated=project_new*math.ceil(observed_average)+100
  ok=pilot['source_verified_issuers']>=14 and pilot['structural_issuers']/20>=.75 and estimated<=remaining
  status='BLOCKED_SOURCE' if (B/'circuit_stop.json').exists() else ('EXPAND' if ok else 'STOP_LOW_YIELD')
  dump('expansion_decision.json',{'at':now(),'decision':status,'pilot':pilot,'cache_original_confirmation':cache,'requests_so_far':request_count(),'remaining':remaining,'observed_pilot_request_upper':before,'projected_new_needed':project_new,'conservative_remaining_request_estimate':estimated,'additional_new_cap':project_new if ok else 0,'source_rate':yieldrate,'reason':'Original-source yield and remainingrequestbudget; no prices or outcomes. If insufficient requests remain, do not force sample criteria.'});print(status,flush=True)
 elif args.stage=='expand':
  d=json.loads((B/'expansion_decision.json').read_text());assert d['decision']=='EXPAND';group=P['conditional_extension'][:d['additional_new_cap']]
  for i,a in enumerate(group):
   row=company(src,a,1);print(a['symbol'],row.get('status'),len(row['events']),flush=True)
   if (B/'circuit_stop.json').exists():break
   if i>=9 and (i+1)%10==0 and summary(group[max(0,i-9):i+1])['source_verified_issuers']<5:
    dump('extension_stop.json',{'at':now(),'reason':'last10 verifiedrate<.5'});break
 elif args.stage=='panel':
  d=json.loads((B/'expansion_decision.json').read_text())if(B/'expansion_decision.json').exists()else{'additional_new_cap':0};group=P['cache_reuse']+P['pilot']+P['conditional_extension'][:d['additional_new_cap']]
  # Level-order originals avoids spending all remaining budget on first few names.
  for level in [2,3,4]:
   for a in group:
    if request_count()>=298 or (B/'circuit_stop.json').exists():break
    p=B/'companies'/(a['symbol']+'.json')
    if not p.exists()or not json.loads(p.read_text())['events']:continue
    company(src,a,level)
   if (B/'circuit_stop.json').exists():break
  dump('panel_collection_summary.json',summary(group))
 dump('stage_'+args.stage+'_resource.json',{'at':now(),'CPU_seconds':time.process_time()-started,'new_wire_requests':request_count()-before,'cache_hits':src.cache_hits,'total_requests':request_count(),'future_return_queries':0,'LLM_calls':0})
if __name__=='__main__':main()
