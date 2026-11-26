"""Read-only official-cache feasibility audit, not an alpha or price evaluator."""
from pathlib import Path
from collections import defaultdict,Counter
from datetime import date,datetime,timezone
import hashlib,json,sys,importlib.util,resource,time
R=Path(__file__).resolve().parents[2];B=R/'runtime/task13_c2'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(name,x):(B/name).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def original_annual_rows(facts,tag):
 rows=[]
 for f in facts.get('us-gaap',{}).get(tag,{}).get('units',{}).get('USD',[]):
  if f.get('form')!='10-K' or f.get('fp')!='FY' or not f.get('accn') or not f.get('start'):continue
  try:s=date.fromisoformat(f['start']);e=date.fromisoformat(f['end']);d=date.fromisoformat(f['filed'])
  except (ValueError,KeyError):continue
  if not(date(2017,1,1)<=d<=date(2022,12,31) and e<=date(2022,12,31) and 300<=(e-s).days<=430 and 0<=(d-e).days<=180):continue
  rows.append(f)
 return rows


def unique(facts,tag,key):
 out=[]
 for i,f in enumerate(facts.get('us-gaap',{}).get(tag,{}).get('units',{}).get('USD',[])):
  if all(f.get(k)==v for k,v in key.items()):out.append((i,f))
 if len({str(x[1].get('val')) for x in out})!=1:return None
 return out[0] if out else None


def structural_annual_events(facts,candidate):
 """Plausible raw-field coverage only. Never computes or approves a feature."""
 tag=candidate['required_tags'][0];result=[];reject=Counter();seen=set()
 for f in original_annual_rows(facts,tag):
  key=(f['accn'],f['start'],f['end'],f['filed'])
  if key in seen:continue
  seen.add(key);match={'accn':f['accn'],'start':f['start'],'end':f['end'],'filed':f['filed'],'form':'10-K'}
  a=unique(facts,tag,match);other=candidate['required_tags'][1];b=unique(facts,other,match)
  if not a or not b:reject['MISSING_OR_CONFLICTING_SAME_ACCESSION_DURATION']+=1;continue
  opening=date.fromordinal(date.fromisoformat(f['start']).toordinal()-1).isoformat()
  prior=unique(facts,'Assets',{'accn':f['accn'],'end':opening,'filed':f['filed'],'form':'10-K'})
  ending=unique(facts,'Assets',{'accn':f['accn'],'end':f['end'],'filed':f['filed'],'form':'10-K'}) if candidate['id']=='C2_CASH_ACCRUAL_QUALITY' else None
  if not prior or (candidate['id']=='C2_CASH_ACCRUAL_QUALITY' and not ending):reject['MISSING_OR_CONFLICTING_SAME_ACCESSION_ASSETS']+=1;continue
  try:
   if float(prior[1]['val'])<=0 or (ending and float(ending[1]['val'])<=0):raise ValueError()
   # Inspect structural units/sign only; do not synthesize a score.
   for value in [a[1]['val'],b[1]['val']]:
    import math
    if not math.isfinite(float(value)):raise ValueError()
  except (ValueError,TypeError,KeyError):reject['BAD_NUMERIC_FIELD']+=1;continue
  result.append({'accession':f['accn'],'filed':f['filed'],'period_start':f['start'],'period_end':f['end'],'locations':{tag:a[0],other:b[0],'Assets_start':prior[0],**({'Assets_end':ending[0]} if ending else {})},'status':'STRUCTURAL_MATCH_ONLY_NOT_PIT_ORIGINAL_SCOPE_APPROVED'})
 # Do not count a later accession's comparative annual value again as a new event.
 byperiod={}
 for row in sorted(result,key=lambda x:(x['filed'],x['accession'])):byperiod.setdefault((row['period_start'],row['period_end']),row)
 return list(byperiod.values()),dict(reject)


def main():
 start=time.process_time();wall=time.monotonic()
 assert not (B/'selection_seal.json').exists(),'Already completed; no silent repeat'
 plan=json.loads((B/'plan.json').read_text());assert sha(B/'plan.json')==(B/'plan.sha256').read_text().strip()
 # Reuse B1 immutable body/SHA reader, without constructing Sources or invoking fetch.
 spec=importlib.util.spec_from_file_location('c2_b1_readonly_body',R/'experiments/task13_b1/common.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 sources=defaultdict(list);failures=[]
 for p in sorted((R/'runtime').rglob('receipt.json')):
  if 'backups' in p.parts or 'task13_c2' in p.parts:continue
  try:d=json.loads(p.read_text())
  except (ValueError,OSError):continue
  if '/api/xbrl/companyfacts/CIK' not in str(d.get('url','')) or d.get('status')!='SAVED':continue
  if not d.get('storage_path') or not d.get('source_hash'):continue
  sources[d['url']].append((p,d))
 inventory=[];datasets={};inputs={}
 for url,choices in sorted(sources.items()):
  choices=sorted(choices,key=lambda x:(x[1].get('observed_at',''),str(x[0])))
  snapshots=[]
  for p,d in choices:
   try:
    raw=module.body(d);source=R/d['storage_path'];rawdata=json.loads(raw);cik=str(int(rawdata['cik']));assert int(url.split('CIK')[1].split('.')[0])==int(cik)
    if d.get('stored_hash'):assert sha(source)==d['stored_hash']
    inputs[str(p.relative_to(R))]=sha(p);inputs[str(source.relative_to(R))]=sha(source)
    item={'receipt':str(p.relative_to(R)),'body':d['storage_path'],'body_sha256':d['source_hash'],'observed_at':d.get('observed_at'),'CIK':cik,'entity':rawdata.get('entityName'),'schema':'SEC_COMPANYFACTS','scope':'CURRENT_BACKFILL_WITH_ORIGINAL_ACCESSION_ROWS_NOT_HISTORICAL_OBSERVATION'};snapshots.append(item)
    if cik not in datasets:datasets[cik]=(rawdata,item)
   except Exception as e:failures.append({'receipt':str(p.relative_to(R)),'error':type(e).__name__,'detail':str(e)})
  inventory.append({'url':url,'snapshots':snapshots,'selected':'Earliest existing observed_at with valid raw SHA; not based on values or return performance'})
 # Broader prior evidence is read-only; reference C1's already audited campaign.
 prior=json.loads((R/'runtime/task13_c1/campaign.json').read_text())['prior_evidence'];prior.update({p:sha(R/p) for p in ['runtime/task13_c1/contract.json','runtime/task13_c1/evaluation.json','runtime/task13_c1/seal.json','runtime/task13_c1/attempt_ledger.json','runtime/task13_b3_repair/replay_v2/evaluation.json','runtime/task13_r2/native/rd/complete.json']})
 mismatches=[p for p,h in prior.items() if not (R/p).is_file() or sha(R/p)!=h]
 assert not mismatches, 'Prior study changed: '+str(mismatches)
 vibe=Path('/home/ansy/app/quant-diligence/vibe-original/agent/src/factors/zoo');external={str(p):sha(p) for p in [vibe/'fundamental/accruals.py',vibe/'academic/high52w.py']}
 duplicate={'prior_campaign_sha':sha(R/'runtime/task13_c1/campaign.json'),'prior_evidence':prior,'local_source_checks':{'src/quant_harness/v94_universe_agent/engine.py':sha(R/'src/quant_harness/v94_universe_agent/engine.py'),'src/quant_harness/v79_high252_operational_replay.py':sha(R/'src/quant_harness/v79_high252_operational_replay.py')},'Vibe_library':external,'findings':[{'mechanism':'52week-high anchoring','status':'EXCLUDED_EXISTING_HYPOTHESIS_NOT_NEW_C2_ATTEMPT','proof':'v94_universe_agent engine high252_proximity and v79 replay; Vibe academic/high52w. No new calculation.'},{'mechanism':'cash accrual quality','status':'EXISTING_LIBRARY_UNTESTED_RESEARCH_INPUT','proof':'Vibe fund_accruals already implements inverse NI-CFO overassets. Known factor family, not novel intellectual alpha; no previous local return test or same feature identified in cited R/B/C1 attempts.'},{'mechanism':'cash equity financing','status':'NOT_FOUND_IN_PRIOR_TESTED_POOL','proof':'B3 considered valuation/claim denominator; this is annual financing cash flow, not that earnings-yield hypothesis. R1/R2/C1 formulas use prices/volume/range, not financing flows.'}],'full_engine_runs':False,'Factory_interaction':'No registry write/reservation. Reuse existing task/campaign attempt fingerprints only; no new official Factory candidate.'}
 results=[]
 for candidate in plan['hypotheses']:
  byfirm=[];events=[]
  for cik,(d,meta) in sorted(datasets.items()):
   rows,reject=structural_annual_events(d.get('facts',{}),candidate)
   for row in rows:events.append({'CIK':cik,**row})
   byfirm.append({'CIK':cik,'entity':d.get('entityName'),'structural_events':len(rows),'rejections':reject,'receipt':meta['receipt']})
  issuers=len({e['CIK'] for e in events});cohorts=sorted({e['period_end'][:4] for e in events});passed=issuers>=candidate['minimum']['distinct_issuers'] and len(events)>=candidate['minimum']['distinct_issuer_fiscal_years'] and len(cohorts)>=candidate['minimum']['fiscal_cohorts']
  # No price/feature stage if broad eligibility fails. Original tag/scope, first availability
  # and amendments have not been individually certified by merely matching API fields.
  result={'id':candidate['id'],'fingerprint':candidate['fingerprint'],'status':'DATA_INSUFFICIENT' if not passed else 'PIT_REVIEW_REQUIRED','cached_issuer_upper_bound':len(datasets),'raw_field_structural_issuers':issuers,'raw_field_structural_events':len(events),'fiscal_cohorts':cohorts,'by_issuer':byfirm,'events':events,'quality':'PARTIAL_CURRENT_API_BACKFILL; counts are optimistic field-availability upper bounds, not final eligible events','PIT':{'accession_period_USD_dates':'CHECKED_BY_PYTHON','numeric_features_computed':False,'first_original_10K_verified':'NOT_VERIFIED_ALL; API same-accession not original context audit','financial_sector_acquisition_scope':'NOT_VERIFIED','first_earnings_news':'NOT_CLAIMED','seconds_precision':'NOT_VERIFIED; localEOD rule proposed','correction_lineage':'NOT_VERIFIED_ALL; 10-K/A excluded; comparative years confined by <=180day filing delay','historical_listing_actions':'R0 PARTIAL, not repaired; labels not inspected'},'feature_only_duplicates':{'status':'NOT_RUN_DATA_GATE_FAILED' if not passed else 'NOT_RUN_PIT_GATE_NOT_CLEARED','rank_correlations':None,'residual_variance_fraction':None,'top_bottom_overlap':None,'reason':'No data-gated candidate; do not generate price proxy or dilute issuer/sample rules to fill a slot.'},'five_criteria':{'economic_rationale':'PARTIAL','measurement':'PARTIAL','differentiation':'UNKNOWN','validation':'FAIL' if not passed else 'PARTIAL','execution':'UNKNOWN'},'trade_limit':'Annual signal may reduce intended turnover, but no empirical spread/ADV/price-action costs inspected. No zero-cost or tradability certification.'}
  results.append(result)
 dump('cache_inventory.json',{'official_endpoint_groups':len(inventory),'unique_issuers':len(datasets),'snapshots':inventory,'failed_sources':failures});dump('input_hashes.json',inputs);dump('prior_audit.json',duplicate);dump('candidate_data_audit.json',results)
 selected=[]
 dump('selection.json',{'status':'NO_ELIGIBLE_CANDIDATE','selected':selected,'reviewed':len(results),'reason':'Neither candidate clears data breadth and full original-period/PIT-scope gates; qualitative economics does not offset missing measurement/independent issuers. No price/feature correlation run; differentiation remains unknown.','order':[c['id'] for c in plan['hypotheses']],'no_automatic_follow_on':True})
 dump('next_research_contract_draft.json',{'status':'NOT_ISSUED_NO_ELIGIBLE_CANDIDATE','candidate':None,'reason':'No candidate eligible for follow-on alpha evaluation. Definitions in plan are screening specifications, not authorization.'})
 dump('attempt_ledger.json',{'campaign':'Continuation of Task13/R/B/C1 exposed history, not reset independent trials','attempts':[{'order':c['order'],'id':c['id'],'fingerprint':c['fingerprint'],'data_gate':r['status'],'feature_computations':0,'future_return_queries':0,'models_trained':0} for c,r in zip(plan['hypotheses'],results)],'prior_campaign_sha':sha(R/'runtime/task13_c1/campaign.json'),'prior_C1_attempt_sha':sha(R/'runtime/task13_c1/attempt_ledger.json'),'generation_LLM_calls':0,'network':0})
 dump('resources.json',{'CPU_seconds':time.process_time()-start,'wall_seconds':time.monotonic()-wall,'new_HTTP':0,'new_data_downloads':0,'internal_research_LLM_calls':0,'internal_research_tokens':0,'future_return_evaluations':0,'new_price_reads':0,'feature_calculations':0,'models_trained':0,'new_installs':0,'Codex_session_usage':'Not metered, not0','outcome_api_used':False})
 # Final selection seal follows feature-only screening, with NOT_RUN explicitly bound.
 files=['plan.json','plan.sha256','cache_inventory.json','input_hashes.json','prior_audit.json','candidate_data_audit.json','selection.json','next_research_contract_draft.json','attempt_ledger.json','resources.json']
 dump('selection_seal.json',{'at':datetime.now(timezone.utc).isoformat(),'files':{n:sha(B/n) for n in files},'code':{str(p.relative_to(R)):sha(p) for p in (R/'experiments/task13_c2').glob('*.py')},'no_future_returns':True,'selected':[]})
 print('NO_ELIGIBLE_CANDIDATE',len(datasets),'cached issuers',[(r['id'],r['raw_field_structural_issuers'],r['raw_field_structural_events']) for r in results])
if __name__=='__main__':main()
