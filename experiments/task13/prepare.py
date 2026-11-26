"""Pre-result sample audit and separate research prefixes. No market requests."""
from pathlib import Path
import sys,json,hashlib,datetime
import pandas as pd,numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'experiments/task12'));from readiness import labels,load
B=R/'runtime/task13';B.mkdir(exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2,default=str,allow_nan=False)+'\n')
if (B/'contract.json').exists():raise SystemExit('Existing preregistration: refuse overwrite')
assets=json.loads((R/'runtime/task10/universe.json').read_text());audit={};longrefs=[]
for market in ['US','KR']:
 fs=load(market);result={}
 for h in [5,20,60]:
  y,end=labels(fs,market,h,'2025-12-31');mask=(np.arange(len(y))>=63)&end.lt(pd.Timestamp('2025-12-31')).to_numpy();z=y.loc[mask];dates=z.index[z.notna().sum(axis=1)>=8];result[str(h)]={'rows':int(z.notna().sum().sum()),'dates':len(dates),'min_names':int(z.notna().sum(axis=1).min()) if len(z) else 0,'max_names':int(z.notna().sum(axis=1).max()) if len(z) else 0,'nonoverlap_blocks_upper_bound':len(dates)//h,'not_effective_independent_sample_size':True}
 long={}
 for a in [a for a in assets if a['market']==market and a['role']=='stock']:
  p=R/'runtime/task6/data/accepted'/(a['symbol']+'.csv');f=pd.read_csv(p,index_col='date',parse_dates=True);receipt=json.loads(p.with_suffix('.receipt.json').read_text());assert sha(p)==receipt['sha256']
  assert not f.index.has_duplicates and f.index.is_monotonic_increasing
  assert ((f[['open','high','low','close']]>0)|f[['open','high','low','close']].isna()).all().all()
  long[a['alias']]=f[['open','high','low','close','volume']];longrefs.append({'alias':a['alias'],'market':market,'path':str(p.relative_to(R)),'sha256':sha(p),'receipt_path':str(p.with_suffix('.receipt.json').relative_to(R)),'adjusted_claim':receipt.get('adjusted_ohlc_provider_claim_not_independent_corporate_action_certification'),'observed_at':receipt['receipts'][0]['available_at']})
 bench='SPY' if market=='US' else '069500.KS';p=R/'runtime/task6/data/accepted'/(bench+'.csv');days=pd.read_csv(p,index_col='date',parse_dates=True).index
 rows=[]
 for alias,f in long.items():
  z=f.reindex(days).loc[:'2025-12-31'].copy();z['instrument']=alias;z.index.name='datetime';rows.append(z.set_index('instrument',append=True))
 panel=pd.concat(rows).sort_index();path=B/'adjusted_inputs'/(market+'.csv');path.parent.mkdir(exist_ok=True);panel.to_csv(path)
 # labels use the same market dates. Never concatenate adjusted and nominal prices.
 extended={}
 tmp={**long,market+'_BENCHMARK':pd.DataFrame(index=days)}
 for h in [5,20,60]:
  y,end=labels(tmp,market,h,'2025-12-31');d=y.index;fit=(d<'2025-01-01')&end.lt(pd.Timestamp('2025-01-01')).to_numpy()&(np.arange(len(y))>=63);val=(d>='2025-02-01')&end.le(pd.Timestamp('2025-12-31')).to_numpy();extended[str(h)]={}
  for name,mask in [('fit',fit),('diagnostic_validation',val)]:
   z=y.loc[mask];ds=z.index[z.notna().sum(axis=1)>=8];extended[str(h)][name]={'rows':int(z.notna().sum().sum()),'dates':len(ds),'nonoverlap_blocks_upper_bound':len(ds)//h,'first':str(ds.min().date()) if len(ds) else None,'last':str(ds.max().date()) if len(ds) else None}
 audit[market]={'nominal_warmup63':result,'adjusted_track':extended,'adjusted_input':str(path.relative_to(R)),'adjusted_sha256':sha(path),'adjusted_date_range':[str(panel.index.get_level_values(0).min().date()),str(panel.index.get_level_values(0).max().date())]}
 # Research native generation sees US fit<=2024; no2025/2026 label, feedback only from training.
 if market=='US':
  train=panel.loc[panel.index.get_level_values(0)<='2024-12-31'].rename(columns=lambda c:'$'+c);train['$return']=train['$close'].groupby(level='instrument').pct_change(fill_method=None);p=B/'generation_input'/'panel.csv';p.parent.mkdir(exist_ok=True);train.to_csv(p)
contract={'schema':'TASK13_NATIVE_RESEARCH_V1','sealed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'campaign_id':'TEAM3_EXPOSED_HISTORY_2026_TASK13','Task12_contract_hash':sha(R/'experiments/task12/contract.json'),'history':'ALL_EXPOSED_DIAGNOSTIC_NOT_HOLDOUT','phase1_candidates':5,'phase2':'At most3 extra Quanta nodes only after first two compute, causality and labels succeed. No parameter search after outer validation.','maximum_candidates':8,'budgets':{'quanta':{'calls':24,'tokens':900000},'rd':{'calls':12,'tokens':500000}},'phase1_call_target':{'quanta':9,'rd':3},'LLM_model':'gpt-6.1-terra','data_requests':0,'CPU_target_hours':24,'tracks':{'nominal_S':'Task12 source/input, frozen fit2025 validation2026, inference factor diagnostic only. Not enough independent fitdates for complex supervised model.','adjusted_RD':'Existing Task6 separate adjusted-provider-claim panel2022-2025 only. fit<=2024-12-31; target end strictly before2025; validation signal>=2025-02-01; purge+>=H embargo; no nominal execution or PnL. Corporate-action/PIT incomplete.'},'vibe':[{'id':'V_ROC20','native_id':'qlib158_roc20','mechanism':'trend','sign':-1,'primary_H':20,'warmup':21,'hypothesis':'Prior20session relative price strength persists over20future sessions; original ratio is negatively oriented.'},{'id':'V_LOWVAR20','native_id':'qlib158_std20','mechanism':'low_variability_return_premium','sign':-1,'primary_H':20,'warmup':20,'hypothesis':'Lower past20session price variability earns a return premium. Return hypothesis, NOT volatility forecast.'}],'quanta':{'node_ids':['Q0','Q1','Q2','Q3','Q4'],'max_nodes':5,'directions':2,'mechanisms':['liquidity-driven reversal','volume-confirmed continuation'],'primary_H':20,'max_effective_warmup':63,'feedback':'Only aligned descriptive fit<=2024 IC/RankIC, zero annualized excess/portfolio alias; no2025/26 diagnostics for evolution selection','fullAlphaAgentLoop':False},'rd':{'id':'RD_SMALL','mechanism':'nonlinear interactions of trend,reversal,volatility and relative volume','primary_H':5,'warmup':61,'features':['ret1','mom20','mom60','vol20','relative_volume20'],'architecture':'Native CoSTEER chooses linear or single hidden layer<=8 units; max100parameters, no sequence network on current sample','epochs':20,'seed':42,'lr':0.001,'baselines':['zero','originalQlibRidge_alpha1','originalQlibLGB_depth3_leaves7_rounds50'],'fit_and_standardization':'<=2024 only; no validation fit/earlystop; fixed20epochs','full_fin_quant':False},'labels':'close t signal, open(t+1) to open(t+H+1), all intermediate market session prices required; same definition in source-adjusted model track (not nominal trade prices)','diagnostics':'Descriptive IC/RankIC, mean spread, distributions, score correlations, MSE/MAE for model. No formal Task14 hypothesis test, no Task15 strategy PnL/cash/risk','Task14_gate':'Valid output, aligned contract, no serious detected leakage and enough stated observations; weak/bias/short data=>INSUFFICIENT_EVIDENCE, no winner forced. PROMISING is provisional only if positive IC and spread both markets; no independent significance claim.','sources':longrefs}
save(B/'sample_audit.json',audit);save(B/'contract.json',contract)
save(B/'preregistration.json',{'contract_sha256':sha(B/'contract.json'),'generation_input_sha256':sha(B/'generation_input/panel.csv'),'selection_before_outer_diagnostics':True,'at':contract['sealed_at']})
print(json.dumps(audit,indent=2))
