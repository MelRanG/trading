from common import *
W=Path('/home/ansy/app/quant-diligence/task9-1-work');seals=[]
for date in ['2024-11-29','2025-06-30']:
 foundation=json.loads((B/'model_inputs'/date/'foundation.json').read_text())
 for arm in ['value','market']:
  stage=arm+'2_'+date[:4];p=W/(stage+'.json');x=json.loads(p.read_text());assert x['foundation_hash']==digest(foundation);assert x['asof']==foundation['asof'];assert x['arm']==arm
  assert {(c['market'],c['symbol']) for c in x['companies']}=={(c['market'],c['symbol']) for c in foundation['companies']}
  for port in x['portfolios']:
   m=port['market'];allowed={c['symbol'] for c in foundation['companies'] if c['market']==m};rank=port['ranked_top3'];assert len(rank)==len(set(rank))==3 and set(rank)<=allowed
   weights=port['fixed_basket_weights'];assert set(weights)<=set(foundation['fixed_allocation_basket'][m]);assert all(0<=v<=.2 for v in weights.values());assert sum(weights.values())<=.6+1e-9
  reservations=[json.loads(q.read_text()) for q in (B/'model_calls/research').glob('*.reserved.json')];matches=[r for r in reservations if r['status']=='SUCCEEDED' and (B/'model_calls/research'/(r['request_hash']+'.request.json')).exists() and json.loads((B/'model_calls/research'/(r['request_hash']+'.request.json')).read_text())['messages']==json.loads((W/(stage+'.request.json')).read_text())['messages']];assert len(matches)==1,'transport must succeed, no failed trace recovery'
  result={'date':date,'arm':arm,'decision':x,'output_sha256':sha(p),'request_sha256':sha(W/(stage+'.request.json')),'foundation_hash':digest(foundation),'transport':matches[0],'sealed_at':now()};freeze(B/'decisions'/(date+'_'+arm+'.json'),result);seals.append({k:v for k,v in result.items() if k!='decision'})
freeze(B/'decision_seals.json',seals);print('SEALED',len(seals))
