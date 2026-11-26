from common import *
import shutil
W=Path('/home/ansy/app/quant-diligence/task9-3-work');m,date=sys.argv[1:];stage=m+'_'+date;W=W if (W/(stage+'.json')).exists() else B/'model_outputs';obj=json.loads((W/(stage+'.json')).read_text());packet=json.loads((B/'packets'/m/(date+'.json')).read_text());assert obj['input_hash']==digest(packet),'input hash mismatch';assert obj['asof'][:10]==date and obj['market']==m
assert {x['symbol'] for x in obj['cases']}=={x['symbol'] for x in packet['cases']}
weights={c['symbol']:float(c['weight']) for c in obj['cases']};assert all(0<=v<=.25 for v in weights.values());assert sum(weights.values())<=.900001;assert abs(obj['cash_weight']+sum(weights.values())-1)<1e-5
assert len(obj['selection_top3'])==3 and set(obj['selection_top3'])<=set(weights)
for c in obj['cases']:
 assert c['state'] in ['RESEARCH_INCOMPLETE','UNATTRACTIVE','WATCH','INVESTABLE']
 if c['weight']>0:assert c['state']=='INVESTABLE' and c.get('valuation',{}).get('base') is not None,'incomplete investment'
# Scope known sectors conservatively: unknowns a single unknown group.
sector={c['symbol']:c.get('sector','UNKNOWN') for c in packet['cases']};groups={}
for s,v in weights.items():groups[sector[s]]=groups.get(sector[s],0)+v
assert all(v<=.500001 for v in groups.values()),'sector cap'
freeze(B/'decisions'/m/(date+'.json'),obj)
f=B/'model_outputs';f.mkdir(exist_ok=True)
for suffix in ['.json','.raw.txt']:
 p=W/(stage+suffix)
 if p.exists() and p.resolve()!=(f/p.name).resolve():shutil.copyfile(p,f/p.name)
record={'market':m,'asof':date,'decision_hash':digest(obj),'packet_hash':digest(packet),'request_hash':sha(W/(stage+'.request.json')),'output_hash':sha(W/(stage+'.json')),'historical_not_forward':True,'call_success':True}
freeze(B/'seals'/m/(date+'.json'),record);print(m,date,'SEALED',weights,flush=True)
