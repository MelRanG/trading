from common import *
import shutil,time
W=Path('/home/ansy/app/quant-diligence/task9-4-work');markets={};assets={}
for m in ['US','KR']:
 stage='final_US' if m=='US' else 'final_KR_compact';p=W/(stage+'.json');z=json.loads(p.read_text());assert z['market']==m;assert z['selected'];assert len(set(x['symbol'] for x in z['selected']))==len(z['selected']);assert sorted(x['rank'] for x in z['selected'])==list(range(1,len(z['selected'])+1))
 target=B/'research'/(m+'.json');freeze(target,z);request=B/'requests'/(stage+'.request.json');markets[m]={'request':{'path':str(request.relative_to(R)),'sha256':sha(request)},'result':{'path':str(target.relative_to(R)),'sha256':sha(target)}}
 for x in z['selected']:
  assert x['predictions'] and x['hypothesis'];s=x['symbol'];assets[s]={'symbol':s,'name':x['name'],'market':m,'currency':'USD' if m=='US' else 'KRW','kind':'stock','role':'selected'}
  for a in x['comparators']:
   s=a.get('symbol')
   if not s:continue
   am=a['market'];am={'USA':'US','United States':'US','Korea':'KR','South Korea':'KR'}.get(am,am)
   assert a['currency'],'COMPARATOR_CURRENCY_MISSING';rec={'symbol':s,'name':a['name'],'market':am,'currency':a['currency'],'kind':'ETF' if 'ETF' in a['relation'] else 'stock','role':'comparator','relationship_verification':a.get('verification')}
   if s not in assets:assets[s]=rec
 for i in ['^GSPC'] if m=='US' else ['^KS11']:assets[i]={'symbol':i,'name':'S&P500' if m=='US' else 'KOSPI','market':m,'currency':'USD' if m=='US' else 'KRW','kind':'index','role':'benchmark'}
 # Complete all stage outputs for restart, including failed scope planning.
 for p in W.glob('*.json'):
  if not p.name.endswith('.request.json'):freeze(B/'model_outputs'/p.name,json.loads(p.read_text()))
for m in ['US','KR']:
 for x in json.loads((B/'research'/(m+'.json')).read_text())['selected']:
  assets[x['symbol']].update(role='selected',market=m,currency='USD' if m=='US' else 'KRW',kind='stock')
a=sorted(assets.values(),key=lambda x:x['symbol']);freeze(B/'sealed_assets.json',a)
freeze(B/'research_seal.json',{'version':C['version'],'created_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'local_asof':C['asof'],'markets':markets,'contract_hash':sha(Path(__file__).parent/'contract.json'),'asset_list_hash':digest(a),'no_Task94_future_price_queries_before_seal':not (B/'future_collection_authorized.json').exists(),'top_slots':3,'missing_slot_rule':'cash_no_replacement_no_rescale','model_calls_after_seal_forbidden':True,'limitations':'Task93outcomesknown; incidentalfuturewebsnippetsquarantined, coordinatornotfullyblind; originalwebsearch+ChatLLMcomponents notfullAutopilot','methods_hashes':{p.name:sha(p) for p in Path(__file__).parent.glob('*.py')}})
print('SEALED',len(a),'assets',[(m,[x['symbol'] for x in json.loads((B/'research'/(m+'.json')).read_text())['selected']]) for m in ['US','KR']])
