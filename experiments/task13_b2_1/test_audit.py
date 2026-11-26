import json,hashlib,runpy
from read_sources import B,P,R
from verify_and_summarize import finite_bounds,zero_case_bound

def test_frozen_stratified_sample_is_reproducible_and_disjoint():
 before=(B/'plan.json').read_bytes();runpy.run_path(str(R/'experiments/task13_b2_1/seal.py'))
 assert (B/'plan.json').read_bytes()==before
 a,b=P['stage1'],P['conditional_stage2'];assert len(a)==len(b)==20
 assert not {x['event_id']for x in a}&{x['event_id']for x in b}
 assert sum(P['strata_population'].values())==247
 for g in ['AMBIGUOUS','NO_COMPARABLE_GUIDANCE']:
  assert sum(x['group']==g for x in a)==10
  assert sum(x['group']==g for x in b)==10
 assert all(any(x['stratum']==key for x in a)for key in P['strata_population'])

def test_exact_finite_bounds_against_small_hand_calculated_case():
 # N10,n2,y0: K7 gives P0=3/45; K8 gives1/45, below two-sided tail .025.
 assert finite_bounds(10,2,0,.05)==(0,7)
 assert finite_bounds(10,2,2,.05)==(3,10)
 assert zero_case_bound({'only':10},[{'stratum':'only'},{'stratum':'only'}])['one_sided95_upper_total']==7

def test_recovery_requires_two_originals_and_source_scope():
 r=json.loads((B/'audit_readings.json').read_text());assert len(r)==40
 recovered=[x for x in r if x['category']=='RECOVERABLE'];assert len(recovered)==10
 for x in recovered:
  assert {'CURRENT','PREVIOUS_COLLECTED'}<={e['role']for e in x['evidence']}
  assert x['in_contract_current_guidance']
 for x in r:
  if x['category']!='RECOVERABLE':assert x['direction']is None
 assert all(x['category']!='RECOVERABLE'for x in r if x['symbol']in ['ABT','TMO','LOW','JNJ','PFGC','VZ','USFD','DE'])

def test_original_B2_counts_not_overwritten_and_no_economic_promotion():
 b2=json.loads((R/'runtime/task13_b2/result_summary.json').read_text());assert b2['classification_counts_after_scope_audit']['UP']==18 and b2['classification_counts_after_scope_audit']['DOWN']==1
 current=json.loads((B/'result_summary.json').read_text());assert not current['source_only_union_upper_bound_not_B2_revision']['all_minimums_met']
 assert current['new_SEC_HTTP']==current['new_price_queries']==current['H20_or_rankIC_or_portfolio_computations']==0
 assert current['internal_LLM']['status_counts']=={'FAILED':1}
 assert current['internal_LLM']['total_tokens_including_cache']<=80000
