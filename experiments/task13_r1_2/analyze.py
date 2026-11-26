from pathlib import Path
import json,hashlib
import pandas as pd,numpy as np
def stored(p):return p if p.exists() else p.with_suffix(p.suffix+'.gz')
R=Path(__file__).resolve().parents[2];B=R/'runtime/task13_r1_2';metrics=json.loads((B/'evaluation/S0/metrics.json').read_text());rows=[];pool=[];uncertainty=[]
for m in ['US','KR']:
 pair=pd.read_csv(stored(B/'evaluation/S0'/(m+'_paired.csv')),parse_dates=['datetime']).set_index(['datetime','instrument']);daily=pair.groupby(level=0)[['score','label']].corr(method='spearman').loc[(slice(None),'score'),'label'].droplevel(1)
 rg=pd.read_csv(R/'runtime/task13_r0'/('US_regimes.csv' if m=='US' else 'KOSPI_regimes.csv'),index_col=0,parse_dates=True)
 for year,x in daily.groupby(daily.index.year):rows.append({'market':m,'axis':'year','period':str(year),'dates':len(x),'RankIC':x.mean()})
 for axis in ['AS_OF_REGIME','EX_POST_REGIME']:
  f=daily.rename('ric').to_frame().join(rg[[axis]])
  for name,g in f.groupby(axis):rows.append({'market':m,'axis':axis,'period':name,'dates':len(g),'RankIC':g.ric.mean()})
 # Descriptive dependent-data uncertainty only, not a fresh preregistered significance test.
 rng=np.random.default_rng(42);x=daily.dropna().to_numpy();block=20;means=[]
 for _ in range(1000):
  starts=rng.integers(0,len(x),size=(len(x)+block-1)//block);idx=np.concatenate([(s+np.arange(block))%len(x) for s in starts])[:len(x)];means.append(x[idx].mean())
 uncertainty.append({'market':m,'block':block,'bootstrap_replications':1000,'descriptive_RankIC_CI95':np.quantile(means,[.025,.975]).tolist(),'dates':len(x),'date_blocks_arithmetic_not_independent_effectiveN':len(x)//20})
 for q in ['Q0','Q1','Q2','Q3']:
  prior=pd.read_csv(R/'runtime/task13_r1/evaluation'/q/(m+'_paired.csv.gz'),parse_dates=['datetime']).set_index(['datetime','instrument']);z=pair[['score']].join(prior[['score']],lsuffix='_new',rsuffix='_prior').dropna();c=z.groupby(level=0)[['score_new','score_prior']].corr(method='spearman').loc[(slice(None),'score_new'),'score_prior'];pool.append({'market':m,'prior':q,'dates':len(c),'mean_daily_rank_correlation':float(c.mean()),'duplicate_abs_ge90':bool(abs(c.mean())>=.90)})
records=[]
for p in (B/'model_calls/quanta').glob('*.reserved.json'):
 r=json.loads(p.read_text());records.append(r)
usage={'calls':len(records),'tokens_all_including_cached':sum(x.get('measured_tokens',0) for x in records),'input':sum(x.get('usage',{}).get('input_tokens',0) for x in records),'cached_input':sum(x.get('usage',{}).get('cached_input_tokens',0) for x in records),'output':sum(x.get('usage',{}).get('output_tokens',0) for x in records),'transport_successes':sum(x['status']=='SUCCEEDED' for x in records),'transport_failures':sum(x['status']!='SUCCEEDED' for x in records),'money':'Not returned; existing Codex auth, no separate purchase','cumulative_CPU':'Unmetered; per container CPU2 memory4GiB','extra_LLM_after_actual_response_replay':0};assert usage['calls']<=8 and usage['tokens_all_including_cached']<=180000
proposals=[]
for p in (B/'model_calls/quanta').glob('*.response.json'):
 try:d=json.loads(json.loads(p.read_text())['choices'][0]['message']['content'])
 except Exception:continue
 if not isinstance(d,dict):continue
 for name,t in d.items():
  if isinstance(t,dict) and 'expression' in t:proposals.append({'response':str(p.relative_to(R)),'name':name,'expression':t['expression'],'status':'EXECUTED_S0' if t['expression']==json.loads((B/'native/quanta/S0/generation.json').read_text())['tasks'][0]['factor_expression'] else 'UNEXECUTED_CONVERTER_RETRY_VARIANT'})
(B/'analysis.json').write_text(json.dumps({'metrics':metrics,'periods':rows,'uncertainty':uncertainty,'pool':pool,'usage':usage,'proposal_returns':proposals,'execution_candidates':1,'new_mutations':0,'development2023_24':'NOT_RUN: fit no consistent positive sign or residual edge; do not seek a favorable historical slice','generation':'FAITHFUL_GENERATION_VERIFIED_WITH_EXACT_COMPLETED_RESPONSE_REPLAY','alpha':'NO_INCREMENTAL_ALPHA_IN_THIS_FIT_DIAGNOSTIC'},indent=2));print(json.dumps({'usage':usage,'pool':pool,'uncertainty':uncertainty},indent=2))
