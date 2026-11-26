"""Build one shared anonymous fit prefix per market; never copy the evaluator tail."""
from pathlib import Path
import json,hashlib,datetime,collections
import pandas as pd,numpy as np
from readiness import R,B,C,load,labels,dump,sha
out={}
for m in ['US','KR']:
 fs=load(m);parts=[];days=fs[m+'_BENCHMARK'].index;boundary=pd.Timestamp(C['split']['fit_end'])
 for alias,f in fs.items():
  if 'BENCHMARK' in alias:continue
  z=f.loc[:boundary,['open','high','low','close','volume']].copy();z['return']=z.close.pct_change(fill_method=None);z['instrument']=alias;z.index.name='datetime';parts.append(z.set_index('instrument',append=True))
 frame=pd.concat(parts).sort_index();folder=B/'fit_inputs';folder.mkdir(exist_ok=True);p=folder/(m+'.csv');frame.to_csv(p)
 budgets={}
 for h in [5,20,60]:
  y,end=labels(fs,m,h,C['split']['fit_end']);budgets[str(h)]={str(w):int(y.loc[(np.arange(len(y))>=w)&end.lt(boundary).to_numpy()].notna().sum().sum()) for w in [6,20,39,63,126,252]}
 out[m]={'path':str(p.relative_to(R)),'sha256':sha(p),'price_max_date':str(frame.index.get_level_values(0).max().date()),'rows':len(frame),'columns':list(frame.columns),'label_columns':[],'evaluator_tail_mounted':False,'fit_label_counts_by_declared_warmup':budgets,'feature_observation_authority':'BACKFILL_VIRTUAL_SESSION_DIAGNOSTIC_ONLY'}
meta=json.loads((B/'factor_catalog.json').read_text())['metadata'];forms=collections.defaultdict(list)
for d in meta:forms[d['formula_latex']].append(d['id'])
duplicate=[{'ids':ids,'interpretation':'Exact metadata formula match, not proof of identical executable arrays'} for ids in forms.values() if len(ids)>1]
cap={'quanta':{'native':'planner/evolution/DSL/feedback API, restored old6-node pool separately, no new hypothesis now','input_interface':'Custom Scenario receives typed horizon/kind/sources. Do not execute fixed Task10 5session/GRU-only policy as Task13 defaults','economic_mechanisms':['trend','reversal','volatility','relative_volume_liquidity'],'fullAlphaAgentLoop':'NOT_EXECUTED_TASK12'},'rd':{'native':'model hypothesis/CoSTEER/Qlib fit/predict; existing checkpoint forward only','model_space':['Qlib LinearModel ridge/ols','Qlib LGBModel (import verified)','Qlib GRU/other feasible sequence architecture'],'include_valid_for_training':False,'retraining_performed_now':False,'full_fin_quant':'NOT_EXECUTED_TASK12'},'vibe':{'native':'478metadata, two computed original functions; ResearchLab entrypoint and previous PRE run reused','declared_OHLCV':sum(d['admissible_price_only'] for d in meta),'US_declared_OHLCV':sum(d['admissible_price_only'] and 'equity_us' in d['universe'] for d in meta),'KR_declared_OHLCV':sum(d['admissible_price_only'] and 'equity_kr' in d['universe'] for d in meta),'formula_duplicate_extra':sum(len(v)-1 for v in forms.values() if len(v)>1),'duplicate_groups':duplicate,'all_factor_economics_tested':False}}
dump('task13_inputs.json',{'schema':'TASK13_INPUT_ADMISSIBILITY_V1','status':'READY_FOR_TASK13_S','scope':'OHLCV limited cohort. H5/H20 effective warmup63 train available; H60 warmup63 zero fit, shorter explicit warmup may have small sample, not statistically independent evidence','primary_contract_hash':sha(R/'experiments/task12/contract.json'),'shared_fit_inputs':out,'engine_roles':cap,'role_boundary':'Researcher mounts only shared fit_inputs CSV; no evaluator full tape, labels or future metrics. Evaluator loads source references and maturity mask separately. Generation packets specify primary horizon and architecture space before calls.','generation_packet_required':['campaign_id','candidate_id','engine_native_version','alpha_kind','primary_horizon','economic_mechanism','feature_effective_warmup','source_hash','fit_cutoff','metric_schema','LLM_and_trial_budget','falsification'],'engine_is_not_alpha':True,'B_status':'NOT_READY_MISSING_BREADTH_PIT_MEMBERSHIP_ACTIONS','new_LLM_calls':0})
# One actually source-verifiable accounting fact is an external-data ABI check,
# not a point-in-time feature panel for these58 stocks.
from quant_harness.investment.financial_packet import verify_fact
p=R/'runtime/task9_2/current_numeric_packet_v2.json';packet=json.loads(p.read_text());fact=packet['cases'][0]['verified_facts'][0];source=R/fact['source_path'];verify_fact(fact,source.read_bytes(),packet['asof'])
dump('financial_source_probe.json',{'status':'SOURCE_NUMERIC_PERIOD_UNIT_PROVENANCE_VERIFIED','packet':str(p.relative_to(R)),'packet_hash':sha(p),'symbol':packet['cases'][0]['symbol'],'metric':fact['metric'],'period_start':fact['period_start'],'period_end':fact['period_end'],'published':fact['published'],'source_hash':sha(source),'scope':'Single source chain only. No aligned cross-sectional fundamental/macro vintage panel; not a model feature yet.'})
# These calendar windows were specified by market-history questions, not stock PnL.
windows=[('2018','2018-01-02','2018-12-31'),('2020_crash','2020-02-03','2020-03-31'),('2020_recovery','2020-04-01','2020-08-31'),('2022','2022-02-02','2022-12-30'),('2023_24','2023-01-03','2024-12-31'),('2026_decline','2026-02-27','2026-03-31'),('2026_rebound','2026-03-31','2026-04-08')];results=[]
for file in sorted(B.glob('*_regimes.csv')):
 d=pd.read_csv(file,index_col='date',parse_dates=True)
 for name,start,end in windows:
  v=d.loc[start:end]
  if v.empty:continue
  results.append({'series':file.stem,'window':name,'first_available':str(v.index.min().date()),'last_available':str(v.index.max().date()),'sessions':len(v),'close_price_change_pct':float((v.close.iloc[-1]/v.close.iloc[0]-1)*100),'AS_OF_counts':v.AS_OF_REGIME.value_counts().to_dict(),'EX_POST_counts':v.EX_POST_REGIME.value_counts().to_dict(),'HIGH_VOL_sessions':int(v.AS_OF_HIGH_VOL.sum()),'scope':'Index/proxy context only, not strategy returns. Missing start history is explicit.'})
dump('index_window_checks.json',{'windows_preselected_by_calendar_not_stock_performance':windows,'rows':results,'missing_US_2018_2020':'No suitable existing SP500/SPY source verified; INSUFFICIENT_EVIDENCE, no download necessary for S','stock_primary_panel_before_2025_07':'Not covered by primary nominal tape; extended Task6 adjusted context is separate.'})
print('SHARED_INPUTS_PREPARED', {m:v['rows'] for m,v in out.items()}, 'FINANCIAL_ABI_PASS')
