"""Offline stratified source audit. Uses metadata only, before any document reading."""
from pathlib import Path
import json,hashlib,datetime,random,math
R=Path(__file__).resolve().parents[2];B=R/'runtime/task13_b2_1';B.mkdir(exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):
 data=json.dumps(x,ensure_ascii=False,indent=2).encode()
 if p.exists():assert p.read_bytes()==data,'IMMUTABLE_PLAN'
 else:p.write_bytes(data)
rows=json.loads((R/'runtime/task13_b2/events_audited.json').read_text());groups=['AMBIGUOUS','NO_COMPARABLE_GUIDANCE'];seed=20261117
bucket=lambda s:'STAPLES' if s=='Consumer Staples' else 'INDUSTRIAL_MATERIALS' if s in ['Industrials','Materials'] else 'OTHER_SECTORS'
strata={}
for x in rows:
 if x['classification']in groups and x['source']['status']=='SAVED':
  key='|'.join([x['classification'],bucket(x['sector_current']),x['filingDate'][:4]])
  strata.setdefault(key,[]).append({'event_id':x['symbol']+':'+x['accession'],'symbol':x['symbol'],'accession':x['accession'],'date':x['filingDate'],'sector':x['sector_current'],'group':x['classification'],'source_SHA':x['source']['source_hash'],'source_path':x['source']['storage_path']})
queues={}
for k,vs in sorted(strata.items()):
 vs=sorted(vs,key=lambda x:x['event_id']);rng=random.Random(int.from_bytes(hashlib.sha256((str(seed)+'|'+k).encode()).digest()[:8],'big'));rng.shuffle(vs);queues[k]=vs
allocation={k:0 for k in queues};samples={1:[],2:[]}
for stage in [1,2]:
 for group in groups:
  keys=[k for k in sorted(queues) if k.startswith(group+'|')];added={k:0 for k in keys}
  for k in keys:
   if allocation[k]<len(queues[k]):added[k]+=1
  while sum(added.values())<10:
   opts=[k for k in keys if allocation[k]+added[k]<len(queues[k])];k=max(opts,key=lambda k:(math.sqrt(len(queues[k]))/(added[k]+1),k));added[k]+=1
  for k,n in added.items():
   start=allocation[k]
   for x in queues[k][start:start+n]:samples[stage].append({**x,'stratum':k,'stage':stage,'N_h':len(queues[k]),'stage1_n_h': n if stage==1 else None})
   allocation[k]+=n
plan={'task':'13-B2.1','seed':seed,'source_population_SHA':sha(R/'runtime/task13_b2/events_audited.json'),'original_B2_manifest_SHA':sha(R/'runtime/task13_b2/artifact_manifest.json'),'contract_SHA':sha(R/'runtime/task13_b2/contract.json'),'groups':{'AMBIGUOUS':71,'NO_COMPARABLE_GUIDANCE_saved_only':176,'unavailable_excluded':24},'stratification':'B2 group x 3 fixed sector buckets x filing calendar year; SRS without replacement inside each stratum. Three buckets assure coverage within n=10/group, not PIT sector classification.','allocation':'Per stage/group: one to each nonempty/nonexhausted stratum, remainder largest sqrt(N_h)/(added_n_h+1), lexical key breaks ties. Fixed seeded per-stratum random permutation, stages disjoint prefixes.','first_stage':20,'max_total':40,'extension_gate':'Run preselected second20 only if first20 has >=1 confirmed RECOVERABLE (including UNCHANGED) OR >=4 UNRESOLVED with concrete contract/parser mismatch evidence. Otherwise stop. No response to price/returns.','inference':'Stage1 design-based stratified expansion only; exact finite population hypergeometric intervals, simultaneous Bonferroni across18strata; n=1/2 very wide. Adaptive second-stage pooled summaries descriptive, no naive fixed-n inference. Do not multiply by300. Bounds on unaudited remainder via total population bounds minus directly observed positives. Issuer/event clusters not independent economic samples.','classification':['NO_ANNUAL_REVENUE_GROWTH_GUIDANCE','OUTSIDE_B2_CONTRACT','RECOVERABLE','UNRESOLVED','MISSING_PREVIOUS_SOURCE'],'RECOVERABLE':'Same issuer/FY/predeclared metric/basis, two original source excerpts, comparable UP/DOWN/UNCHANGED. New guidance alone without parent is not recoverable. No absolute-sales/EPS/qualitative-number conversion.','limits':{'SEC_HTTP':0,'price_queries':0,'training':0,'engine_calls':0,'internal_LLM_calls_max':4,'internal_tokens_max':80000},'review':'First pass reads full original exhibit sections and tables without B2 parsed snippets. Second pass independently extracts plain-text/table numeric evidence, source locator+SHA and parent original; unresolved scope stays UNRESOLVED. No single model opinion as ground truth.','stage1':samples[1],'conditional_stage2':samples[2],'strata_population':{k:len(v) for k,v in queues.items()}}
p=B/'plan.json';write(p,plan);write(B/'plan.sha256.json',{'sha256':sha(p)});stamp=B/'sealed_at.json'
if not stamp.exists():stamp.write_text(json.dumps({'sealed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'plan_SHA':sha(p),'before_selected_source_reading':True},indent=2))
print(json.dumps({'plan_SHA':sha(p),'stage1':[(x['symbol'],x['date'],x['group'],x['stratum'])for x in samples[1]]},ensure_ascii=False))
