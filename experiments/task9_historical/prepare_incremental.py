from pathlib import Path
import json,sys,hashlib
R=Path(__file__).resolve().parents[2];B=R/'runtime/task9_historical';W=Path('/home/ansy/app/quant-diligence/task9-historical-work');mode=sys.argv[1];assert mode in ('B','C')
base=json.loads((W/'A3_202111.request.json').read_text());original=json.loads(base['messages'][1]['content']);packet=original['packet'];a=json.loads((W/'A3_202111.json').read_text());context=[]
for name,key,date in [('fed_20211103','The Federal Reserve is committed','2021-11-03'),('bok_20211125','The Monetary Policy Board','2021-11-25')]:
 text=(B/'audit'/(name+'.txt')).read_text();pos=text.index(key);end=text.find('Voting for',pos) if name.startswith('fed') else text.find('List',pos)
 if end<0:end=pos+6000
 context.append({'source_id':name,'publication_date':date,'quality':'DATED_OFFICIAL_PUBLIC_RELEASE_RETRIEVED_NOW','source_hash':json.loads((B/'audit'/(name+'.receipt.json')).read_text())['sha256'],'text':text[pos:min(end,pos+6000)]})
import pandas as pd
f=pd.read_csv(B/'evaluation/KR_price_index.csv');f=f[(f.date>='2021-11-01')&(f.date<='2021-11-30')]
market={'official_releases':context,'index_price_history_through_cutoff':f[['date','raw_close']].to_dict('records'),'index_limit':'Only available from2021-11-15; no63day sector momentum or flow/consensus inference allowed','missing':['historical analyst consensus','institutional/foreign flow','ETF flows','historical industry classification','complete news archive','verified stock identifier/actions/session chain']}
shared=hashlib.sha256(json.dumps({'foundation':packet,'market':market},sort_keys=True,ensure_ascii=False).encode()).hexdigest()
prior=a if mode=='B' else json.loads((W/'B3_202111.json').read_text())
payload={'mode':mode,'task':('Keep A original operating analysis and add ONLY dated market/catalyst interpretation, mark each decision change with source; no claimed future performance.' if mode=='B' else 'Preserve B and explicitly compare same four companies as alternatives. Record rankings and desired/withheld allocations and opportunity cost. Do not add current/hindsight winners. Missing core execution data still blocks trade, do not force buying.'),'common_foundation':packet,'market_context':market,'original_A':a,'previous_mode_result':prior,'shared_session_hash':shared,'input_hash':packet['input_hash'],'output_contract':original['output_schema_example'],'required_extra_fields':['changes_from_previous','new_information_used','comparison_caveats']}
payload['output_contract']['mode']=mode
request={'messages':[base['messages'][0],{'role':'user','content':json.dumps(payload,ensure_ascii=False)}],'temperature':0,'response_format':{'type':'json_object'}}
p=W/(mode+'3_202111.request.json')
if p.exists():assert json.loads(p.read_text())==request
else:p.write_text(json.dumps(request,ensure_ascii=False))
(B/'packets'/('shared_session_'+mode+'.json')).write_text(json.dumps({'session_input_hash':shared,'foundation_input_hash':packet['input_hash'],'market':market},ensure_ascii=False,indent=2));print(mode,shared,len(json.dumps(request)))
