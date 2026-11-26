"""Read-only paired prediction diagnostics; no fitting, selection or LLM calls."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
R=Path(__file__).resolve().parents[2];B=R/'runtime/task13_r2';T=B/'training'
def interval(v):
 v=np.asarray(v);v=v[np.isfinite(v)];n=len(v);rng=np.random.default_rng(42);out=[]
 for _ in range(2000):
  starts=rng.integers(0,n,size=(n+19)//20);idx=((starts[:,None]+np.arange(20))%n).ravel()[:n];out.append(v[idx].mean())
 return {'mean':float(v.mean()),'circular_20_session_block_95pct':np.quantile(out,[.025,.975]).tolist(),'sessions':n,'nonoverlap_H20_upper_bound':n//20}
def daily(frame):
 return frame.groupby(level=0).apply(lambda x:x['prediction'].rank().corr(x['target'].rank()))
result={'method':'Paired same-date/same-instrument RankIC differences; 2000 circular session-block bootstrap, block20, seed42. Descriptive exposed historical analysis, no multiplicity-adjusted confirmation. No training or selection.'}
for phase,suffix in [('internal',''),('development','_development')]:
 result[phase]={}
 for market in ['US','KR']:
  frames={}
  for n in 'ABCD':
   path=T/f'{market}_{n}{suffix}_predictions.csv'
   if not path.exists():path=Path(str(path)+'.gz')
   frames[n]=pd.read_csv(path,index_col=[0,1],parse_dates=[0])
  first=frames['A'];assert all(f.index.equals(first.index) and np.allclose(f.target,first.target) for f in frames.values())
  ranks=pd.DataFrame({n:daily(f) for n,f in frames.items()});r={}
  for pair in ['CA','DB','DC']:
   a,b=pair;r[pair]=interval(ranks[a]-ranks[b])
  r['years']={str(year):{n:{'RankIC':float(ranks[n].loc[ranks.index.year==year].mean()),'MSE':float(((f.prediction-f.target)**2).loc[f.index.get_level_values(0).year==year].mean())} for n,f in frames.items()} for year in ranks.index.year.unique()}
  r['prediction_correlations']={pair:float(frames[pair[0]].prediction.corr(frames[pair[1]].prediction)) for pair in ['AB','AC','BD','CD']}
  # Cross-sectional residualisation is contemporaneous descriptive analysis, not a new trained signal.
  for pair in ['CA','DB','DC']:
   a,b=pair;joined=pd.DataFrame({'a':frames[a].prediction,'b':frames[b].prediction,'y':first.target});vals=[]
   for date,g in joined.groupby(level=0):
    z=g.b.to_numpy();x=g.a.to_numpy();y=g.y.to_numpy();z=z-z.mean();res=x-x.mean()-z*(np.dot(z,x-x.mean())/np.dot(z,z));vals.append(pd.Series(res).rank().corr(pd.Series(y).rank()))
   r[pair]['residual_rankIC']=interval(vals)
  result[phase][market]=r
hist=json.loads((T/'histories.json').read_text());result['training']={}
for name,h in hist.items():
 info={k:v for k,v in h.items() if k!='native_score_history'}
 if 'native_score_history' in h:
  scores=h['native_score_history'];info['best_epoch_zero_based']=int(np.argmin(scores['valid']));info['best_valid_MSE']=float(min(scores['valid']));info['first_train_MSE']=scores['train'][0];info['last_train_MSE']=scores['train'][-1]
 result['training'][name]=info
usage={};records=[]
for p in sorted((B/'model_calls').glob('*/*.reserved.json')):
 d=json.loads(p.read_text());m=d['model'];u=d.get('usage',{});s=usage.setdefault(m,{'calls':0,'input_tokens':0,'cached_input_tokens':0,'output_tokens':0,'total_tokens':0,'seconds':0})
 s['calls']+=1
 for k in ['input_tokens','cached_input_tokens','output_tokens']:s[k]+=u.get(k,0)
 s['total_tokens']+=d.get('measured_tokens',0);s['seconds']+=d.get('elapsed_seconds',0);records.append({'request_hash':d['request_hash'],'role':d['engine'],'model':m,'status':d['status'],'tokens':d.get('measured_tokens',0)})
result['LLM']={'by_model':usage,'calls':len(records),'total_tokens':sum(v['total_tokens'] for v in usage.values()),'records':records,'cached_included_in_input':True,'reasoning_tokens_subset_of_output':True,'billing_cost_available':False}
(B/'analysis.json').write_text(json.dumps(result,indent=2,allow_nan=False));print(json.dumps({'LLM':result['LLM'],'training':result['training'],'development':result['development']},indent=2))
