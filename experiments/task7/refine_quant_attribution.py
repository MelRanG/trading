from pathlib import Path
import json,sys,importlib.util
import numpy as np,pandas as pd
R=Path(__file__).resolve().parents[2];b=R/'runtime/task7/quant';r=json.loads((b/'diagnosis.json').read_text());spec=importlib.util.spec_from_file_location('old',R/'experiments/task6/evaluation.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);frames=m.load_frames('US','validation');paired={};errors={}
for key in ['baseline','factor_augmented']:
 p=Path('/home/ansy/app/quant-diligence/completion-rd-work')/(key+'_predictions.csv');v=pd.read_csv(p,parse_dates=['datetime']).set_index(['datetime','instrument']).iloc[:,0];observed=[]
 for (day,symbol),pred in v.items():
  f=frames[symbol];i=f.index.get_loc(day)
  if i+1<len(f) and f.index[i+1]<=pd.Timestamp('2025-12-31'):observed.append((day,symbol,pred,float(f.close.iloc[i+1]/f.open.iloc[i+1]-1)))
 f=pd.DataFrame(observed,columns=['date','symbol','pred','label']);f['sqerr']=(f.pred-f.label)**2;f['zero_sqerr']=f.label**2;errors[key]={'mse':float(f.sqerr.mean()),'zero_forecast_mse':float(f.zero_sqerr.mean()),'direction_accuracy':float((np.sign(f.pred)==np.sign(f.label)).mean()),'n':len(f)}
 daily=f.groupby('date').apply(lambda x:x.pred.rank().corr(x.label.rank()),include_groups=False);paired[key]=daily
z=(paired['factor_augmented']-paired['baseline']).dropna();block=z.groupby(z.index.to_period('M')).mean().to_numpy();rng=np.random.default_rng(7002);interval=np.quantile(rng.choice(block,size=(2000,len(block)),replace=True).mean(axis=1),[.025,.975]).tolist()
causes={}
for engine in ['QUANTA','RD','VIBE']:
 rows=[x for n,x in r['candidates'].items() if n.startswith(engine)]
 causes[engine]=[
 {'type':'EXECUTION_COST','status':'CONFIRMED_FOR_TESTED_CONTRACT','evidence':'Fill-level two-sided costs reconcile with NAV. Fixed5bp halfspread is most of cost; not verified broker quote.'},
 {'type':'EVALUATION_MISMATCH','status':'CONFIRMED_V1;V2_ALIGNED','evidence':'V1 intraday target but overnight-carry NAV. V2 trades next open to same close; old results immutable.'},
 {'type':'DATA_LIMITATION','status':'CONFIRMED','evidence':'US38/KR20 current named survivors, historical membership/sector/adjustment certification missing; independent alpha judgment deferred.'},
 {'type':'SEARCH_BUDGET_LIMITATION','status':'LIMIT_CONFIRMED_EFFECT_UNDETERMINED','evidence':'Quanta6 bounded trajectories, RD5epochs fixedsmallGRU, Vibefew hypotheses. No matched larger-budget/full-native control; cannot conclude native engines intrinsically weak.'},
 {'type':'FEEDBACK_ERROR','status':'CONFIRMED_ALIAS;DOWNSTREAM_EFFECT_UNDETERMINED','evidence':'Absolute averages were passed to native excess metric aliases in Task6completion. V2.1 correct exports exist. Counterfactual corrected same-episode LLM rerun not performed; no causal magnitude claim.'},
 {'type':'ENGINE_LIMITATION','status':'NOT_ESTABLISHED_FOR_ENGINE_FAMILY','evidence':'Tested candidate IC/returns and intervals assess these implementations only; full engine generalization unsupported.'},
 {'type':'UNDETERMINED','status':'NO_INDEPENDENT_EFFICACY_EVIDENCE','evidence':'Observed low net returns can reflect multiple interacting mechanisms. No single causal attribution from PnL.'}]
r['rd_prediction_benchmarks']=errors;r['rd_factor_incremental_IC']={'mean':float(z.mean()),'monthly_block95':interval,'independent_holdout':False};r['cause_classification']=causes;r['sensitivity_limits']='Fixed predeclared diagnostic grid, no deployment selection. Gross replay compounding differs from subtracting a dollar cost amount because costs change subsequent capital.'
(b/'diagnosis.json').write_text(json.dumps(r,indent=2,allow_nan=False));print(json.dumps({'rd':errors,'paired_ic':r['rd_factor_incremental_IC']},indent=2))
