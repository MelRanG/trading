"""Independent masked discovery-priority packets, not a trading decision."""
from pathlib import Path
import pandas as pd,json,hashlib
R=Path(__file__).resolve().parents[2];B=R/'runtime/task9_value';W=Path('/home/ansy/app/quant-diligence/task9-value-work');W.mkdir(exist_ok=True);(W/'home').mkdir(exist_ok=True)
contract=json.loads((Path(__file__).parent/'contract.json').read_text());cohort=json.loads((B/'cohort.json').read_text());(B/'screen_inputs').mkdir(exist_ok=True)
for date in contract['dates']:
 cases=[]
 for c in cohort:
  x=dict(c);p=B/'prices'/c['symbol']/'bars.csv'
  if not p.exists():x['status']='MISSING_PRICE';cases.append(x);continue
  f=pd.read_csv(p);f=f[f.date<=date];v=f.dropna(subset=['close','volume']);v=v[(v.close>0)&(v.volume>0)]
  x['status']='AVAILABLE_BOUNDED' if len(v)>=120 and v.date.iloc[-1]==date else 'STALE_OR_SHORT';x['precutoff_bars']=len(v)
  if x['status']=='AVAILABLE_BOUNDED':
   x['past_price_returns']={str(n):float(v.close.iloc[-1]/v.close.iloc[-n-1]-1) for n in [21,63,126] if len(v)>n};x['observations_until']=date;x['nominal_price']='Withheld until raw/split-unit crosscheck';x['flow_data']='Trading volume is not net institutional flows';x['financials']='Not collected yet: select research priorities, not an investment based on unknown financials'
  cases.append(x)
 gate={m:{'candidates':sum(c['market']==m for c in cases),'price_covered':sum(c['market']==m and c['status']=='AVAILABLE_BOUNDED' for c in cases),'sectors':len({c['sector'] for c in cases if c['market']==m and c['status']=='AVAILABLE_BOUNDED'})} for m in ['US','KR']}
 assert all(v['price_covered']>=20 and v['sectors']>=5 for v in gate.values()),gate
 payload={'cutoff':date+'T23:00:00Z','cohort_origin':'US2020/21dated Dow30; KR2021-11-01dated broker24 industry seeds. Fixed bounded opportunity set, not whole market or currently surviving stocks. New as-of dated financial evidence required before final selection.','candidates':cases,'gate':gate,'exclude_future_outcomes':True}
 fingerprint=hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest();payload['session_input_hash']=fingerprint
 name='screen_'+date[:4];request={'messages':[{'role':'system','content':'You are the original Vibe research component. Use supplied as-of evidence only. No tools, web, files, memory or later outcomes. This is RESEARCH PRIORITIZATION, not stock purchases. Broadly compare the dated candidates across industries. Select exactly3 research priorities per market, in distinct sectors, to obtain original financial evidence. Avoid merely picking past-price winners or famous current winners. State missing evidence, economic question, contrarian and bullish thesis to investigate. The30/24 seed cohort is limited and stale across dates; do not claim open-ended whole-market discovery. Output JSON only.'},{'role':'user','content':json.dumps({'input':payload,'schema':{'cutoff':payload['cutoff'],'session_input_hash':fingerprint,'research_priorities':[{'market':'US or KR','symbol':'provided code','rank':1,'reason_to_investigate':'not an established fact','required_evidence':[],'why_not_momentum_only':'','sector':'from input'}],'excluded_notes':[]}},ensure_ascii=False)}]}
 p=W/(name+'.request.json')
 if p.exists():assert json.loads(p.read_text())==request
 else:p.write_text(json.dumps(request,ensure_ascii=False))
 (B/'screen_inputs'/(name+'.json')).write_text(json.dumps(payload,ensure_ascii=False,indent=2));print(name,gate,fingerprint)
