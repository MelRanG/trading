from pathlib import Path
import sys,json,hashlib,gzip
import pandas as pd
from guard import admit,enforce,bound_feedback
R=Path(__file__).resolve().parents[2];B=R/'runtime/task13_r1_1';S=R/'runtime/task13_r1'
contracts={'Q0':['overnight_intraday','volatility_scaling','MOM20_crosssection_control'],'Q1':['prior_volume_median','shock_indicator','volume_weighted_mean','no_shock_missing','zero_range_missing','return_volatility_crosssection_controls'],'Q2':['volume_change','absolute_return_volatility','return_volatility_crosssection_controls'],'Q3':['overnight_intraday']}
implemented={'Q0':{'overnight_intraday':True,'volatility_scaling':True},'Q1':{'prior_volume_median':True,'shock_indicator':True},'Q2':{'volume_change':True,'absolute_return_volatility':True},'Q3':{'overnight_intraday':True}}
# Diagnostic-only threshold is not retroactive strategy approval; compare all prior pool, not parent alone.
corr=json.loads((S/'candidate_correlations.json').read_text());rows=[];bindings=[]
for q,req in contracts.items():
 node=S/'native/quanta'/q;g=json.loads((node/'generation.json').read_text());m=json.loads((node/'metrics.json').read_text());per={}
 for a in corr:
  if a['scope']=='evaluation':
   for k,v in a['mean_daily_score_rank_correlations'][q].items():
    if k!=q:per[k]=max(abs(v),per.get(k,0))
 result=admit(q,req,implemented[q],per)
 try:enforce(result);result['enforcement']='PASS'
 except ValueError:result['enforcement']='BLOCKED_AS_REQUIRED'
 rows.append(result);bindings.append(bound_feedback(q,node/'factor.py',m,g['tasks'][0]['factor_description']))
 try:bound_feedback('WRONG',node/'factor.py',m,'');raise AssertionError('binding guard failed')
 except ValueError:pass
(B/'guard_replay.json').write_text(json.dumps(rows,indent=2));(B/'feedback_views.json').write_text(json.dumps(bindings,indent=2));(B/'preregistration.json').write_text(json.dumps({'phaseA_LLM':0,'phaseB_LLM':0,'requirements':contracts,'scope':'Existing candidate technical replay, no strategy/factor changes','PhaseC':'NOT_RUN: exact required crosssectional control absent from current formula/native DSL; mandatory old hypotheses still fail; stop condition hypothesis/expression mismatch applies. Do not spend calls on knowingly incomplete representation.'},indent=2));print(rows)
