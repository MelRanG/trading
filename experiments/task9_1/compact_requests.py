from common import *
W=Path('/home/ansy/app/quant-diligence/task9-1-work')
for p in sorted(W.glob('*.request.json')):
 if '2_' in p.name:continue
 x=json.loads(p.read_text());body=json.loads(x['messages'][1]['content'])
 for c in body['input']['companies']:
  source=c['source'];text=source.get('text','')
  if c['market']=='KR':
   source['text']=text[:700]+'\nFINANCIAL_EXCERPTS:\n'+text[-1800:];source['facts']=source.get('facts',[])[:16]
  else:source['text']=text[:4700]
  if 'source_update' in c:c['source_update']['text']=c['source_update'].get('text','')[:1300]
 for value in body['upstream_methods'].values():value['method_excerpt']=value['method_excerpt'][:600]
 if 'market_context' in body['input']:
  for v in body['input']['market_context'].values():
   if 'text' in v:v['text']=v['text'][:2700]
 x['messages'][1]['content']=json.dumps(body,ensure_ascii=False);target=p.with_name(p.name.replace('_','2_',1));freeze(target,x);freeze(B/'compact_requests'/target.name,x);print(target.name,len(json.dumps(x)),flush=True)
