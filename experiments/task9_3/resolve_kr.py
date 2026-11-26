from common import *
import pandas as pd,numpy as np,ast
for f in (B/'evaluator_only').glob('*.KS'):
 out=f/'resolution_v2.json'
 if out.exists():continue
 y=pd.read_csv(f/'yahoo.csv').set_index('date');t=pd.read_csv(f/'toss.csv').set_index('date');z=ast.literal_eval((f/'naver.txt').read_text().strip());n=pd.DataFrame([{'date':pd.Timestamp(str(v[0])).date().isoformat(),'open':v[1],'high':v[2],'low':v[3],'close':v[4],'volume':v[5]} for v in z[1:]]).set_index('date');data={'YAHOO':y,'TOSS':t,'NAVER':n};rows=[];proof=[]
 for d in y.index:
  r={'date':d};pr={'date':d}
  for k in ['open','close']:
   r[k]=np.nan;pr[k]={'status':'UNRESOLVED'}
   for aa,bb in [('YAHOO','NAVER'),('TOSS','NAVER'),('YAHOO','TOSS')]:
    a,b=data[aa],data[bb]
    if d not in a.index or d not in b.index:continue
    v,w=float(a.loc[d,k]),float(b.loc[d,k])
    if v>0 and w>0 and abs(v/w-1)<=.005:
     r[k]=w;pr[k]={'status':'TWO_SOURCE_MATCH','pair':[aa,bb],'values':[v,w],'chosen':w};break
  r['volume']=min(float(a.loc[d,'volume']) for a in data.values() if d in a.index);r['high']=np.nan;r['low']=np.nan;rows.append(r);proof.append(pr)
 frame=pd.DataFrame(rows);frame.to_csv(f/'bars_v2.csv',index=False);freeze(out,{'version':'V2_TWO_SOURCE_FIELD_PROVENANCE','protocol_hash':sha(Path(__file__).parent/'price_resolution.json'),'original_status_preserved':sha(f/'quality.json'),'rows':proof,'missing_open':int(frame.open.isna().sum()),'missing_close':int(frame.close.isna().sum()),'no_action_inside_hold_interval':not any('2026-05-18'<=__import__('datetime').datetime.fromtimestamp(v['date'],__import__('datetime').timezone.utc).date().isoformat()<='2026-11-13' for v in json.loads((f/'quality.json').read_text()).get('declared_events',{}).get('splits',{}).values())});print(f.name,'missing',int(frame.open.isna().sum()),int(frame.close.isna().sum()),flush=True)
