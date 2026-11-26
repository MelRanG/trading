"""As-of worker allowlists; no future companyfacts or evaluator snapshots mounted."""
from common import *
from features import asof,contract_changes,policy_context
G=json.loads((B/'guidance_events.json').read_text());C=json.loads((B/'contract_events.json').read_text());M=json.loads((B/'macro_normalized.json').read_text());out=[]
def store(name,records,cutoff,features,market):
 context=policy_context(M,cutoff);sources=[]
 for r in records:
  if 'source' in r:sources.append({'path':r['source']['storage_path'],'sha256':r['source']['source_hash']})
  else:sources.append({'path':r['source_path'],'sha256':r['source_hash']})
 if context:sources.append({'path':context['source']['storage_path'],'sha256':context['source']['source_hash']})
 payload={'asof':cutoff,'market':market,'classification':'EXPOSED_HISTORICAL_DEVELOPMENT_SOURCE_PILOT','records':records,'features':features,'macro_context':context,'source_mount_allowlist':sources,'forbidden':['US/KR whole normalized2025panels for a2024worker','current companyfacts/submissions bulk JSON','future amendment records or lineage labels','FRED latest historical backfill','price/return/label outcomes'],'operations_permission':False}
 p=B/'worker_packets'/name;dump(p,payload);out.append({'path':str(p.relative_to(R)),'sha256':sha(p),'sources':len(sources)})
cut=G['features'][0]['available_upper_bound'];store('PEP_2024-10-08.json',asof(G['events'],cut),cut,G['features'],'US')
for f in C['features']:
 cut=f['available_upper_bound'];store('KR_'+cut[:10]+'.json',asof(C['events'],cut),cut,contract_changes(C['events'],cut),'KR')
dump(B/'worker_packet_seal.json',{'packets':out,'no_actual_worker_started':True,'no_whole_dataset_mount':True});print('ASOF_PACKETS_SEALED',len(out))
