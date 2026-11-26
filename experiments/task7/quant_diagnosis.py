"""No model/API calls. Frozen-output attribution and preregistered diagnostics.
Does not edit prior performance files or select a replacement strategy.
"""
from pathlib import Path
import sys,json,hashlib,importlib.util
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'runtime/task7/quant';BASE.mkdir(parents=True,exist_ok=True)
spec=importlib.util.spec_from_file_location('prior',ROOT/'experiments/task6/evaluation.py');prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior);frames=prior.load_frames('US','validation')
# A distinct diagnostic execution version; hypotheses/parameters were fixed in
# contract.json before any sensitivity outcome was read.
source=(ROOT/'experiments/task6_completion/aligned.py').read_text().replace("initial=100000.):","initial=100000.,top=4,cost_multiplier=1.):").replace('index[:4]','index[:top]').replace('nav*.2/prior','nav*(.8/top)/prior').replace('(5+impact)/1e4','cost_multiplier*(5+impact)/1e4').replace('buy*1.0001','buy*(1+.0001*cost_multiplier)').replace('qty*buy*.0001','qty*buy*.0001*cost_multiplier').replace('qty*sell*.0001','qty*sell*.0001*cost_multiplier')
namespace={};exec(compile(source,'<TASK7_DIAGNOSTIC_EXECUTION>','exec'),namespace);evaluate=namespace['evaluate'];(BASE/'diagnostic_execution_source.py').write_text(source)
C=ROOT/'runtime/task6_completion';W=Path('/home/ansy/app/quant-diligence/completion-rd-work');jobs=[]
for i in range(6):jobs.append((f'QUANTA_NODE{i}',C/f'evaluation/validation/US/quanta{i}/factor_values.csv',C/f'aligned/node{i}/nav.csv',C/f'aligned/node{i}/fills.csv',False))
jobs.append(('VIBE',C/'evaluation/validation/US/vibe0/factor_values.csv',C/'vibe_model_evaluation/vibe/nav.csv',C/'vibe_model_evaluation/vibe/fills.csv',False))
for name in ['baseline','factor_augmented']:jobs.append(('RD_'+name,W/(name+'_predictions.csv'),W/(name+'_nav.csv'),W/(name+'_fills.csv'),True))
result={'scope':'REPEATED_2025_DIAGNOSIS_NO_NEW_ALPHA_SELECTION','llm_calls':0,'source_hashes':{},'candidates':{},'limitations':['Current named US38 / KR20 cohort not PIT or delisting-complete','No historical point-in-time sector classification; sector attribution unavailable','2026 not used in new sensitivity selection','Full native search frameworks and budgets were not equal; no general engine ranking']}
for name,path,navpath,fillpath,is_prediction in jobs:
 values=pd.read_csv(path,parse_dates=['datetime']).set_index(['datetime','instrument']).iloc[:,0].unstack('instrument');nav=pd.read_csv(navpath,parse_dates=['date']);fills=pd.read_csv(fillpath,parse_dates=['date']);fees=float((fills.buy_fee+fills.sell_fee).sum());spread=float((fills.quantity*(fills.entry_open+fills.exit_close)*5/1e4).sum());total=float(nav.cost.sum());impact=total-fees-spread
 assert min(fees,spread,impact)>-1e-5
 # Independent fill-level net cash reconstruction.
 pnl=float((fills.quantity*(fills.sell_price-fills.buy_price)-fills.buy_fee-fills.sell_fee).sum());assert abs(float(nav.nav.iloc[-1])-(100000+pnl))<1e-5
 result['source_hashes'][name]={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [path,navpath,fillpath]}
 quarter={str(k):{'sessions':len(g),'net_return_pct':float(((1+g.net_return).prod()-1)*100),'gross_return_pct':float(((1+g.gross_return).prod()-1)*100),'mean_selection_bps':float(g.selection_effect.mean()*1e4)} for k,g in nav.groupby(nav.date.dt.to_period('Q'))}
 symbols=sorted(s for s in frames if 'BENCHMARK' not in s);close=pd.DataFrame({s:frames[s].close for s in symbols});op=pd.DataFrame({s:frames[s].open for s in symbols});lag=values.reindex(index=close.index,columns=symbols).shift(1);labels=close/op-1;daily=[];rows=[]
 for day in nav.date:
  pair=pd.concat([lag.loc[day],labels.loc[day]],axis=1).dropna();pair.columns=['score','outcome']
  if len(pair)>4 and pair.score.nunique()>1:daily.append((day,float(pair.score.rank().corr(pair.outcome.rank()))))
  if len(pair):rows.append(pair.assign(date=day))
  if not len(pair):continue
 ic=pd.Series(dict(daily)).dropna();prediction=pd.concat(rows) if rows else pd.DataFrame();direction=float((np.sign(prediction.score)==np.sign(prediction.outcome)).mean()) if len(prediction) else None
 # Preserve chronological blocks when estimating IC uncertainty.
 monthly=ic.groupby(ic.index.to_period('M')).mean().to_numpy();rng=np.random.default_rng(7001);interval=np.quantile(rng.choice(monthly,size=(2000,len(monthly)),replace=True).mean(axis=1),[.025,.975]).tolist() if len(monthly) else None
 sensitivities={}
 for top in [4,8]:
  for multiplier in [0,.5,1,2]:
   m,n,f=evaluate(values,frames,top=top,cost_multiplier=multiplier);sensitivities[f'top{top}_cost{multiplier}']=m
 row={'net_return_pct':float((nav.nav.iloc[-1]/100000-1)*100),'gross_compounded_return_pct':float(((1+nav.gross_return).prod()-1)*100),'cost_usd':{'fee':fees,'spread':spread,'impact':impact,'total':total},'turnover':float(nav.turnover.sum()),'mean_exposure':float(nav.exposure.mean()),'selection_mean_bps':float(nav.selection_effect.mean()*1e4),'IC':float(ic.mean()),'IC_month_block95':interval,'positive_IC_session_fraction':float((ic>0).mean()),'direction_accuracy_raw_score_sign':direction,'quarters':quarter,'per_stock_realized_net_pnl':{str(k):float((g.quantity*(g.sell_price-g.buy_price)-g.buy_fee-g.sell_fee).sum()) for k,g in fills.groupby('symbol')},'sensitivity':sensitivities,'interpretation':'Parameters not selected for deployment; grid is a controlled diagnostic, not an optimized strategy.'}
 if is_prediction:row['prediction_mse']=float(np.mean((prediction.score-prediction.outcome)**2))
 result['candidates'][name]=row;print(name,round(row['net_return_pct'],2),round(row['IC'],5),flush=True)
(BASE/'diagnosis.json').write_text(json.dumps(result,indent=2,allow_nan=False));print('DONE',flush=True)
