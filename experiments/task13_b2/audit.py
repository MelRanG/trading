"""Read-only source/revision/resource audit. Never opens price files."""
from common import *
from collections import Counter

def run():
 records=[json.loads(p.read_text()) for p in sorted((B/'requests').glob('*.json'))]
 sources=[json.loads(p.read_text()) for p in sorted((B/'sources').glob('*/receipt.json'))]
 errors=[]
 for r in sources:
  if r.get('status')=='SAVED':
   try:body(r)
   except Exception as e:errors.append({'storage_path':r.get('storage_path'),'error':type(e).__name__})
 companies=[json.loads(p.read_text()) for p in (B/'collection').glob('*.json') if not p.name.endswith('.target_seal.json')]
 target=[x for c in companies for x in c.get('targets',[])];parents=[x for c in companies for x in c.get('parents',[])]
 assert len(target)<=300 and len(companies)<=40
 targets_sealed=True
 for c in companies:
  p=B/'collection'/(c['company']['symbol']+'.target_seal.json');s=json.loads(p.read_text())
  assert s['target_filings']==[x['filing'] for x in c['targets']]
  assert s['parent_filings']==[x['filing'] for x in c['parents']]
 manifests=[R/f'runtime/{n}/artifact_manifest.json' for n in ['task13_r0','task13_r1','task13_r1_1','task13_r1_2','task13_r2','task14','task13_b0','task13_b1']]
 protected={}
 for p in manifests:
  d=json.loads(p.read_text())
  for x in d.get('files',[]):
   path=x['path'];h=x['sha256']
   if path in protected:assert protected[path]==h
   protected[path]=h
 bad=[]
 for p,h in protected.items():
  actual=R/p
  if not actual.exists() or sha(actual)!=h:bad.append(p)
 result={'at':now(),'official_HTTP_attempts_including_failures':len(records),'request_statuses':dict(Counter(r['status'] for r in records)),'request_failures':[r for r in records if r['status']!='SAVED'],'download_bytes_recorded':sum(r.get('bytes',0) for r in records),'source_receipts':len(sources),'reused_sources':sum(bool(r.get('reused')) for r in sources),'original_source_hashes_verified':sum(r.get('status')=='SAVED' for r in sources),'source_hash_errors':errors,'companies_visited':len(companies),'target_release_events':len(target),'supporting_parent_releases':len(parents),'target_source_statuses':dict(Counter(r['source']['status'] for r in target)),'original_document_source_kinds':dict(Counter(r.get('source_kind') for r in target+parents)),'targets_match_pre_document_seals':targets_sealed,'protected_manifest_unique_files':len(protected),'protected_missing_or_changed':bad,'internal_LLM_calls':0,'LLM_tokens_including_cached':0,'models_trained':0,'Quanta_RD_calls':0,'price_requests_or_event_return_evaluations':0,'all_event_return_metrics':'NOT_RUN_PENDING_SAMPLE_GATE','operations_changed':False,'http_cap':750,'raw_download_cap':500000000,'additional_transport_cost_note':'Raw bytes are successful response bytes; four failed HTTP/size attempts have no full payload accounting. Existing fetch reads at most per-response limit+1 byte before raising; conservative additional upper bound recorded below.','failed_attempt_max_payload_upper_bound':12000001*sum(r['status']!='SAVED' for r in records)}
 result['raw_bytes_conservative_upper_bound']=result['download_bytes_recorded']+result['failed_attempt_max_payload_upper_bound']
 assert not errors and not bad
 assert len(records)<=C['HTTP_max'] and result['raw_bytes_conservative_upper_bound']<=C['total_download_cap_bytes']
 dump(B/'source_resource_audit.json',result)
 print(json.dumps({k:v for k,v in result.items() if k not in ['request_failures']},ensure_ascii=False))
if __name__=='__main__':run()
