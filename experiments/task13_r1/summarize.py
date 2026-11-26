from pathlib import Path
import json,hashlib,collections
import pandas as pd,numpy as np
def stored(p):return p if p.exists() else p.with_suffix(p.suffix+'.gz')
R=Path(__file__).resolve().parents[2];B=R/'runtime/task13_r1';root=B/'native/quanta';events=json.loads((root/'events.json').read_text());details=[];stability=[]
for e in events:
 node=root/e['attempt_id'];g=json.loads((node/'generation.json').read_text());record={**e,'hypothesis':g['hypothesis'],'factor':g['tasks'][0],'code_hash':hashlib.sha256((node/'factor.py').read_bytes()).hexdigest(),'proposed':len(json.loads((node/'all_proposed_tasks.json').read_text())['tasks']),'metrics':{}}
 for scope,folder in [('fit','evaluation'),('development','validation')]:
  f=B/folder/node.name/'metrics.json'
  if not f.exists():continue
  record['metrics'][scope]=json.loads(f.read_text())
  for m in ['US','KR']:
   pair=pd.read_csv(stored(f.parent/(m+'_paired.csv')),parse_dates=['datetime']);pair['daily_ric']=0
   daily=pair.groupby('datetime')[['score','label']].corr(method='spearman').loc[(slice(None),'score'),'label'].droplevel(1)
   rg=pd.read_csv(R/'runtime/task13_r0'/('US_regimes.csv' if m=='US' else 'KOSPI_regimes.csv'),index_col=0,parse_dates=True)
   for axis in ['AS_OF_REGIME','EX_POST_REGIME']:
    z=daily.rename('RankIC').to_frame().join(rg[[axis]])
    for name,v in z.groupby(axis):stability.append({'candidate':node.name,'scope':scope,'market':m,'axis':axis,'regime':name,'dates':len(v),'mean_RankIC':float(v.RankIC.mean())})
   for year,v in daily.groupby(daily.index.year):stability.append({'candidate':node.name,'scope':scope,'market':m,'axis':'year','regime':str(year),'dates':len(v),'mean_RankIC':float(v.mean())})
   if e['parents']:
    parent=next(x for x in events if x['trajectory_id']==e['parents'][0]);pp=B/folder/parent['attempt_id']/(m+'_paired.csv')
    p=pd.read_csv(stored(pp),parse_dates=['datetime']);j=pair[['datetime','instrument','score']].merge(p[['datetime','instrument','score']],on=['datetime','instrument'],suffixes=('_child','_parent'));corr=j.groupby('datetime')[['score_child','score_parent']].corr(method='spearman').loc[(slice(None),'score_child'),'score_parent'];record.setdefault('parent_correlation',{}).setdefault(scope,{})[m]=float(corr.mean())
 details.append(record)
usage=[json.loads(p.read_text()) for p in (B/'model_calls').rglob('*.reserved.json')];u={'calls':len(usage),'tokens_all_including_cache':sum(x.get('measured_tokens',0) for x in usage),'input_tokens':sum(x.get('usage',{}).get('input_tokens',0) for x in usage),'cached_input_tokens':sum(x.get('usage',{}).get('cached_input_tokens',0) for x in usage),'output_tokens':sum(x.get('usage',{}).get('output_tokens',0) for x in usage),'status':dict(collections.Counter(x['status'] for x in usage)),'model_call_wall_seconds':sum(x.get('elapsed_seconds',0) for x in usage),'CPU_accounting':'No cumulative CPU meter. Offline containers capped2CPU/4GiB.','network_data_requests':0,'model_training':0,'financial_cost':'Existing Codex auth; no separate paid API purchase; money cost not returned'};u['uncached_input_tokens']=u['input_tokens']-u['cached_input_tokens'];assert u['calls']<=20 and u['tokens_all_including_cache']<=650000
(B/'results.json').write_text(json.dumps(details,indent=2));(B/'regime_stability.json').write_text(json.dumps(stability,indent=2));(B/'usage.json').write_text(json.dumps(u,indent=2));print('COMPLETE',len(events),u)
