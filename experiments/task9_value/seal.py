"""Preserve failed transport status; recover only complete, tool-free raw model messages."""
from pathlib import Path
import json,hashlib,shutil
R=Path(__file__).resolve().parents[2];B=R/'runtime/task9_value';W=Path('/home/ansy/app/quant-diligence/task9-value-work');O=B/'decisions';O.mkdir(exist_ok=True)
seals=[]
for year,stage in [(2021,'deep2_2021'),(2022,'deep2_2022'),(2023,'deep3_2023')]:
 original=json.loads((W/(stage+'.request.json')).read_text());expected=json.loads(original['messages'][1]['content'])['input']['session_input_hash'];found=[]
 for p in (B/'model_calls/research').glob('*.request.json'):
  req=json.loads(p.read_text())
  if req['messages']==original['messages']:found.append(p)
 assert len(found)==1
 p=found[0];record=json.loads(p.with_name(p.name.replace('.request.json','.reserved.json')).read_text());restored=False
 if record['status']=='SUCCEEDED':
  response=json.loads(p.with_name(p.name.replace('.request.json','.response.json')).read_text());raw=response['choices'][0]['message']['content'];x=json.loads(raw)
 else:
  assert record['status']=='FAILED' and record['exit_code']==0 and record['measured_tokens']>90000,'Only completed token-limit response can be recovered diagnostically'
  events=[json.loads(z) for z in p.with_name(p.name.replace('.request.json','.trace.jsonl')).read_text().splitlines()];assert not any(e.get('item',{}).get('type') in ['command_execution','web_search','mcp_tool_call'] for e in events),'Tool boundary must remain intact even for recovery'
  messages=[e['item']['text'] for e in events if e.get('item',{}).get('type')=='agent_message'];assert len(messages)==1
  answer=json.loads(messages[0]);assert answer['tool_calls']==[];raw=answer['content'];x=json.loads(raw);restored=True
 assert x['session_input_hash']==expected and x['cutoff']==str(year)+'-11-30T23:00:00Z'
 priorities=json.loads((W/('screen_'+str(year)+'.json')).read_text())['research_priorities'];allowed={(q['market'],q['symbol']) for q in priorities};assert {(q['market'],q['symbol']) for q in x['companies']}==allowed
 for market in ['US','KR']:
  decisions=[q for q in x['companies'] if q['market']==market];assert all(0<=q['policy_weight']<=.2 and (q['policy_action']=='BUY' or q['policy_weight']==0) for q in decisions);assert sum(q['policy_weight'] for q in decisions)<=.6000001
  portfolio=next(z for z in x['portfolios'] if z['market']==market)
  assert abs(portfolio['cash_weight']+sum(q['policy_weight'] for q in decisions)-1)<1e-8
  for field in ['value_only_top2','value_market_top2','relative_final_top2']:
   assert len(portfolio[field])==len(set(portfolio[field]))==2 and all((market,s) in allowed for s in portfolio[field])
 payload={'year':year,'stage':stage,'session_input_hash':expected,'decision':x,'transport_status':record['status'],'recovered_from_complete_raw_trace':restored,'status':'RESEARCH_DIAGNOSTIC_ONLY_NOT_APPROVED_PAPER','output_sha256':hashlib.sha256(raw.encode()).hexdigest(),'model_request_hash':record['request_hash'],'original_attempt_status_unchanged':True}
 target=O/(str(year)+'.json')
 if target.exists():assert json.loads(target.read_text())==payload
 else:target.write_text(json.dumps(payload,ensure_ascii=False,indent=2))
 (O/(str(year)+'.raw.txt')).write_text(raw);seals.append({k:v for k,v in payload.items() if k!='decision'});print(year,record['status'],restored,[(q['symbol'],q['policy_weight']) for q in x['companies']],flush=True)
(B/'decision_seals.json').write_text(json.dumps(seals,indent=2))
