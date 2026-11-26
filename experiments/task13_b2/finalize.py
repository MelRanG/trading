"""Seal source-only stop decision. No price input, regression, or alpha optimization."""
from common import *
from collections import Counter,defaultdict
import csv,re

def run():
 rows=json.loads((B/'events_classified.json').read_text());audit=json.loads((B/'source_resource_audit.json').read_text());out=[]
 for row in rows:
  r=dict(row);r['parser_classification_before_scope_audit']=r['classification'];reasons=[]
  if r['classification'] in ['UP','DOWN','UNCHANGED']:
   p,c=r['guidance_parent'],r['guidance_current'];texts=[p['text'],c['text']]
   if any(re.search(r'wireless service|segment|division|excluding covid',t,re.I) for t in texts):reasons.append('NON_TOTAL_REVENUE_SCOPE')
   if any(re.search(r'(?:first|second|third|fourth) quarter',t,re.I) and re.search(r'full.year',t,re.I) for t in texts):reasons.append('MIXED_QUARTER_AND_ANNUAL_TEXT_NEEDS_CONTEXT_REVIEW')
   if any(re.search(r'(?:upper|lower|high|low) end',t,re.I) for t in texts):reasons.append('RANGE_ENDPOINT_QUALIFIER_NOT_FULLY_PARSED')
   metadata=json.loads((B/'collection'/(r['symbol']+'.json')).read_text())['earnings_metadata']
   intervening=[x for x in metadata if x['form']=='8-K' and r['parent_public_date']<x['filingDate']<r['filingDate']]
   r['intervening_original_earnings_filings']=intervening
   if intervening:reasons.append('INTERVENING_UNCOLLECTED_EARNINGS_RELEASE')
   if reasons:r['classification']='AMBIGUOUS';r['scope_audit_exclusions']=reasons
  r['PIT_grade']='PARTIAL_ORIGINAL_FILING_DATE_ONLY_NOT_COMPLETE_EARLIEST_IR'
  r['public_clock_precision']='DATE_ONLY_CONSERVATIVE_NEW_YORK_END_OF_DAY_REQUIRED'
  r['price_quality_gate']='NOT_RUN_SAMPLE_GATE_FAILED'
  r['H20_return']=None;r['return_na_reason']='SOURCE_PAIRED_SAMPLE_BELOW_FROZEN_MINIMUM_NO_RETURN_QUERY'
  out.append(r)
 counts=Counter(r['classification'] for r in out);changes=[r for r in out if r['classification']in ['UP','DOWN']]
 gate={'pass':False,'criterion':'Upper bound before full PIT/price/overlap gates already insufficient; no independent sample count asserted','source_paired_changes_upper_bound':len(changes),'changed_issuers_upper_bound':len({r['symbol'] for r in changes}),'UP_upper_bound':counts['UP'],'DOWN_upper_bound':counts['DOWN'],'UNCHANGED_preliminary':counts['UNCHANGED'],'minimum_changes':30,'minimum_changed_issuers':12,'minimum_UP':8,'minimum_DOWN':8,'after_H20_overlap_dedup':'NOT_RUN_CANNOT_INCREASE_UPPER_BOUND','after_full_PIT_and_price_gates':'NOT_RUN_CANNOT_INCREASE_UPPER_BOUND'}
 assert len(changes)<30 or len({r['symbol']for r in changes})<12 or counts['UP']<8 or counts['DOWN']<8
 dump(B/'events_audited.json',out);dump(B/'final_sample_gate.json',gate)
 table=[]
 for r in out:
  p=r.get('guidance_parent',{});c=r.get('guidance_current',{});s=r['source'];ps=r.get('parent_source',{})
  table.append({'symbol':r['symbol'],'CIK':r['CIK'],'board':r['exchange_board'],'filingDate':r['filingDate'],'accession':r['accession'],'FY':c.get('FY'),'metric_basis':r['metric_basis'],'classification':r['classification'],'parser_classification':r['parser_classification_before_scope_audit'],'prior_value':json.dumps(p.get('value'),ensure_ascii=False),'current_value':json.dumps(c.get('value'),ensure_ascii=False),'original_URL':s.get('url'),'original_SHA':s.get('source_hash'),'observed_at':s.get('observed_at'),'parent_accession':r.get('parent_accession'),'parent_public_date':r.get('parent_public_date'),'parent_URL':ps.get('url'),'parent_SHA':ps.get('source_hash'),'prior_excerpt':p.get('text'),'current_excerpt':c.get('text'),'PIT_grade':r['PIT_grade'],'exclusion_reason':r.get('exclusion_reason') or '|'.join(r.get('scope_audit_exclusions',[])),'H20_return':None})
 with (B/'event_table.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(table[0]));w.writeheader();w.writerows(table)
 by_year={y:dict(Counter(r['classification']for r in out if r['filingDate'].startswith(y)))for y in ['2022','2023','2024']}
 by_issuer={s:dict(Counter(r['classification']for r in out if r['symbol']==s))for s in dict.fromkeys(r['symbol']for r in out)}
 by_sector={s:dict(Counter(r['classification']for r in out if r['sector_current']==s))for s in dict.fromkeys(r['sector_current']for r in out)}
 exclusions=Counter(r.get('exclusion_reason','PAIRED') for r in out)
 paired=[r for r in rows if r['classification']in ['UP','DOWN','UNCHANGED']]
 gaps=[r for r in out if r.get('intervening_original_earnings_filings')]
 diagnostic={'counts':dict(counts),'by_year':by_year,'by_issuer':by_issuer,'by_current_sector_not_PIT':by_sector,'exclusion_reason_counts':dict(exclusions),'scope_audit_exclusion_counts':dict(Counter(x for r in out for x in r.get('scope_audit_exclusions',[]))),'paired_source_rows_reviewed':len(paired),'intervening_original_earnings_gaps':len(gaps),'changed_event_yield_of300':len(changes)/300,'downgrade_yield_of300':counts['DOWN']/300,'missing_to_raw_minimum':{'changes':max(0,30-len(changes)),'changed_issuers':max(0,12-len({r['symbol']for r in changes})),'UP':max(0,8-counts['UP']),'DOWN':max(0,8-counts['DOWN'])},'yield_is_parser_and_sample_design_yield_not_population_prevalence':True}
 dump(B/'sample_diagnostics.json',diagnostic)
 seal={'at':now(),'decision':'STOP_SAMPLE_INSUFFICIENT','no_event_price_or_returns_queried':True,'contract_SHA':sha(B/'contract.json'),'transport_amendment_SHA':sha(B/'transport_amendment.json'),'parser_SHA':sha(R/'experiments/task13_b2/parse_guidance.py'),'event_table_SHA':sha(B/'event_table.csv'),'audited_events_SHA':sha(B/'events_audited.json'),'sample_gate_SHA':sha(B/'final_sample_gate.json'),'source_audit_SHA':sha(B/'source_resource_audit.json')}
 dump(B/'event_stop_seal.json',seal)
 result={'task':'13-B2','technical_verdict':'EXECUTION_PARTIAL','alpha_verdict':'SAMPLE_INSUFFICIENT','stop_reason':'300 target releases reached, same-basis paired upper bound insufficient before PIT/price/independence checks','contract_SHA':seal['contract_SHA'],'stop_seal_SHA':sha(B/'event_stop_seal.json'),'companies_preregistered':40,'companies_visited':audit['companies_visited'],'target_release_events':len(out),'supporting_parents':audit['supporting_parent_releases'],'source_saved_target_events':audit['target_source_statuses']['SAVED'],'classification_counts_after_scope_audit':dict(counts),'sample_gate':gate,'economic_evaluation':{'primary_H20_UP_minus_DOWN_sector_relative':None,'controlled_increment':None,'uncertainty_intervals':None,'reason':'NOT_RUN_FROZEN_SAMPLE_GATE_FAILED; no alpha/no-alpha inference'},'resources':audit,'tests':{'task_local':9,'mandatory':24,'compileall':'PASS'},'follow_on_tasks_started':False,'next_single_action':'Separate go/no-go decision on continuing guidance sampling; do not expand same historical sample automatically'}
 dump(B/'result_summary.json',result)
 print(json.dumps({'verdicts':[result['technical_verdict'],result['alpha_verdict']],'counts':dict(counts),'gate':gate,'years':by_year,'scope_exclusions':diagnostic['scope_audit_exclusion_counts']},ensure_ascii=False))
if __name__=='__main__':run()
