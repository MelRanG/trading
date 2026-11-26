"""Offline evidence verification and stratified audit estimates, not alpha evaluation."""
from read_sources import *
from collections import Counter,defaultdict
from html.parser import HTMLParser
class TextReader(HTMLParser):
 def __init__(self):super().__init__(convert_charrefs=True);self.parts=[]
 def handle_data(self,text):self.parts.append(text)
from scipy.stats import hypergeom
from decimal import Decimal
import numpy as np

def finite_bounds(N,n,y,alpha):
 ks=[k for k in range(N+1) if hypergeom.cdf(y,N,k,n)>=alpha/2 and hypergeom.sf(y-1,N,k,n)>=alpha/2]
 return min(ks),max(ks)

def zero_case_bound(strata,phase1):
 dp=np.array([0.])
 for key,N in strata.items():
  n=sum(x['stratum']==key for x in phase1);prob=hypergeom.logpmf(0,N,np.arange(N-n+1),n);new=np.full(len(dp)+len(prob)-1,-np.inf)
  for k,v in enumerate(dp):new[k:k+len(prob)]=np.maximum(new[k:k+len(prob)],v+prob)
  dp=new
 upper=int(np.where(dp>=np.log(.05))[0].max())
 return {'metric':'Confirmed RECOVERABLE DOWN under audit rules','stage1_sample':len(phase1),'population':sum(strata.values()),'observed_DOWN':0,'method':'Supplementary exact worst-case nuisance allocation: max over per-stratum DOWN counts summing to K of product Hypergeom(N_h,K_h,n_h).pmf(0). Invert zero-observation test at one-sided95%; not an alpha test.','one_sided95_upper_total':upper,'probability_no_DOWN_worst_case_at_bound':float(np.exp(dp[upper])),'probability_no_DOWN_at_bound_plus1':float(np.exp(dp[upper+1])),'probability_no_DOWN_worst_case_at7':float(np.exp(dp[7])) if len(dp)>7 else None,'remaining_population':207,'one_sided95_remaining_DOWN_bound':[0,min(207,upper)],'not_a_bound_on_subjectively_unresolved_true_economic_events':True,'adaptive_stage2_not_used_in_probability_calculation':True,'no_economic_independence_assumption':True,'not_preregistered_primary_estimator':'Supplementary source-count uncertainty diagnostic; frozen primary Bonferroni-stratum results retained.'}

def run():
 rows=json.loads((B/'stage1_first_read.json').read_text())+json.loads((B/'stage2_first_read.json').read_text());assert len(rows)==40 and len({r['event_id']for r in rows})==40
 revision=json.loads((B/'adjudication_revision.json').read_text())
 for row in rows:
  if row['event_id']==revision['event_id']:
   row['initial_category']=row['category'];row['category']='RECOVERABLE';row['direction']='UP';row['explicit_numeric_revision_exception']=True;row['reason']=revision['reason']
 verified=0;proofs=[]
 for r in rows:
  coll=json.loads((R/'runtime/task13_b2/collection'/f"{r['symbol']}.json").read_text());docs=coll.get('parents',[])+coll['targets'];original_by_acc={e['filing']['accessionNumber']:e for e in docs}
  for e in r['evidence']:
   original=original_by_acc[e['accession']];raw=load(original['source']);assert original['source']['source_hash']==e['source_SHA']
   # Separate DOM library; compare complete original source text to locator excerpt.
   src=raw.decode('utf-8','replace')
   if original.get('source_kind')!='EXHIBIT_HTML':
    src='\n'.join(d for d in re.findall(r'<DOCUMENT>(.*?)</DOCUMENT>',src,re.S|re.I) if re.search(r'<TYPE>EX-99(?:\.1)?\s',d,re.I))
   reader=TextReader();reader.feed(src);text=' '.join(' '.join(reader.parts).split());quote=' '.join(e['text'].split())
   assert quote in text,(r['event_id'],e['role'],e['n']);verified+=1
  if r['category']=='RECOVERABLE':
   assert {'CURRENT','PREVIOUS_COLLECTED'}<={e['role']for e in r['evidence']}
   assert r['direction']in ['UP','DOWN','UNCHANGED'] and r['in_contract_current_guidance']
   if r['direction']in ['UP','DOWN']:
    nums=lambda s:[Decimal(x)for x in re.findall(r'\d+(?:\.\d+)?',s)]
    a,b=nums(r['prior_literal']),nums(r['current_literal'])
    if r.get('explicit_numeric_revision_exception'):
     assert len(a)==2 and len(b)==1 and b[0]>a[1] and r['direction']=='UP'
     proofs.append({'event_id':r['event_id'],'old_upper':str(a[1]),'new_lower':str(b[0]),'direction':'UP','no_invented_new_upper':True});continue
    assert len(a)==len(b)==2
    assert ((b[0]>=a[0] and b[1]>=a[1] and b!=a) if r['direction']=='UP' else (b[0]<=a[0] and b[1]<=a[1] and b!=a))
    proofs.append({'event_id':r['event_id'],'prior_bounds':list(map(str,a)),'current_bounds':list(map(str,b)),'direction':r['direction'],'minimum_one_endpoint_strict':True})
  # Unresolved conditions do not enter confirmed recovery or direction estimates.
  if r['category']=='UNRESOLVED':assert r['direction']is None
 b2m=json.loads((R/'runtime/task13_b2/artifact_manifest.json').read_text());bad=[]
 for e in b2m['files']:
  p=R/e['path']
  if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest()!=e['sha256']:bad.append(e['path'])
 assert not bad
 phase1=[r for r in rows if r['stage']==1];strata=P['strata_population'];weights={k:len([r for r in phase1 if r['stratum']==k])for k in strata};metrics={'RECOVERABLE':lambda r:r['category']=='RECOVERABLE','CURRENT_IN_CONTRACT':lambda r:r['in_contract_current_guidance'],'UP':lambda r:r['category']=='RECOVERABLE'and r['direction']=='UP','DOWN':lambda r:r['category']=='RECOVERABLE'and r['direction']=='DOWN'}
 estimates={}
 for name,fn in metrics.items():
  cells=[]
  for k,N in sorted(strata.items()):
   cell=[r for r in phase1 if r['stratum']==k];n=len(cell);y=sum(bool(fn(r))for r in cell);lo,hi=finite_bounds(N,n,y,.05/len(strata));cells.append({'stratum':k,'N':N,'n_stage1':n,'y':y,'sample_probability':n/N,'expanded_total':N*y/n,'exact_total_bounds':[lo,hi]})
  t=sum(c['expanded_total']for c in cells);lo=sum(c['exact_total_bounds'][0]for c in cells);hi=sum(c['exact_total_bounds'][1]for c in cells);observed=sum(bool(fn(r))for r in rows);remainingN=247-len(rows)
  estimates[name]={'stage1_HT_estimated_total_in247':t,'stage1_estimated_rate':t/247,'first20_raw_positive_count':sum(bool(fn(r))for r in phase1),'observed_positive_in40':observed,'simultaneous_strata_95_bounds_total':[max(lo,observed),min(hi,observed+remainingN)],'unreviewed207_point_projection':max(0,t-observed),'unreviewed207_95_bounds':[max(0,lo-observed),min(remainingN,hi-observed)],'CI_interpretation':'Per quantity Bonferroni-exact finite-population hypergeometric stratum intervals. Stage1 design only; stage2 observed facts intersect bounds. Very conservative; no independent economic-sample inference. Subtracting adaptive observed40 gives descriptive remaining projection, not conditional-unbiased estimate.','cells':cells}
 rec=[r for r in rows if r['category']=='RECOVERABLE'];changes=[r for r in rec if r['direction']in ['UP','DOWN']];base=json.loads((R/'runtime/task13_b2/events_audited.json').read_text());old=[r for r in base if r['classification']in ['UP','DOWN']];base_ids={r['symbol']+':'+r['accession']for r in old};assert not base_ids & {r['event_id']for r in changes};basefirms={r['symbol']for r in old};newfirms={r['symbol']for r in changes}-basefirms
 counts=Counter(r['category']for r in rows);result={'task':'13-B2.1','verdict':'INDETERMINATE','collection_decision':'NO_NEW_COLLECTION_AUTHORIZED_OR_RECOMMENDED_FROM_THIS_SAMPLE; pause guidance track pending separate decision','reason':'Real extraction misses confirmed, but none is a DOWN revision; remaining event/issuer and DOWN counts cannot be established with small stratified sample and very wide bounds. Neither conditional continuation nor statistical/persistent rejection of guidance mechanism justified.','audited_events':40,'groups':{g:{'population':sum(N for k,N in strata.items()if k.startswith(g+'|')),'sample':sum(r['group']==g for r in rows),'categories':dict(Counter(r['category']for r in rows if r['group']==g))}for g in ['AMBIGUOUS','NO_COMPARABLE_GUIDANCE']},'categories':dict(counts),'in_contract_current_guidance':sum(r['in_contract_current_guidance']for r in rows),'recoverable':len(rec),'directions':dict(Counter(r['direction']for r in rec)),'changed_issuers':sorted({r['symbol']for r in changes}),'new_changed_issuers_vs_B2':sorted(newfirms),'recovered_by_year':{y:dict(Counter(r['direction']for r in rec if r['date'].startswith(y)))for y in ['2022','2023','2024']},'recovered_by_sector':{s:dict(Counter(r['direction']for r in rec if r['sector']==s))for s in sorted({r['sector']for r in rec})},'source_only_union_upper_bound_not_B2_revision':{'changes':len(old)+len(changes),'changed_issuers':len(basefirms|newfirms),'UP':sum(r['classification']=='UP'for r in old)+sum(r['direction']=='UP'for r in changes),'DOWN':sum(r['classification']=='DOWN'for r in old)+sum(r['direction']=='DOWN'for r in changes),'all_minimums_met':False,'full_PIT_price_overlap_gates':'NOT_RUN'},'verified_original_excerpts':verified,'numeric_direction_proofs':proofs,'B2_unchanged_manifest_files':len(b2m['files']),'B2_changed_or_missing':bad,'new_SEC_HTTP':0,'new_price_queries':0,'new_model_training':0,'Quanta_RD_engine_runs':0,'H20_or_rankIC_or_portfolio_computations':0,'Codex_main_usage':'NOT_METERED_NOT_ZERO','follow_on_tasks_started':False}
 records=[json.loads(p.read_text())for p in(B/'second_reader').glob('*/*.reserved.json')];tokens=sum(r.get('measured_tokens',0)for r in records);assert len(records)<=4 and tokens<=80000
 result['internal_LLM']={'attempts':len(records),'status_counts':dict(Counter(r['status']for r in records)),'model':'gpt-6-luna','effort':'medium explicit CLI setting','purpose':'source second reading only; transport scope name rd does not invoke RD-Agent','input_tokens':sum(r.get('usage',{}).get('input_tokens',0)for r in records),'output_tokens':sum(r.get('usage',{}).get('output_tokens',0)for r in records),'cached_input_tokens':sum(r.get('usage',{}).get('cached_input_tokens',0)for r in records),'total_tokens_including_cache':tokens,'currency_cost':'NOT_AVAILABLE','failure_note':'One generated CLI response exit0; existing transport post-call per-request40000-token guard rejected55180. No accepted response, retry or further LLM call. Trace retained as fallible auxiliary opinion only.'}
 if not any(r['direction']=='DOWN'for r in phase1):
  (B/'down_zero_case_bound.json').write_text(json.dumps(zero_case_bound(strata,phase1),indent=2))
 (B/'stratified_estimates.json').write_text(json.dumps(estimates,indent=2));(B/'result_summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));(B/'audit_readings.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in result.items()if k not in ['numeric_direction_proofs']},ensure_ascii=False));print('ESTIMATES',[(k,{q:v[q]for q in ['stage1_HT_estimated_total_in247','observed_positive_in40','unreviewed207_95_bounds']})for k,v in estimates.items()])
if __name__=='__main__':run()
