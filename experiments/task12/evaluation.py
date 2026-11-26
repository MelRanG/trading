"""Thin typed routes to existing labels, native IC, QH execution. No alpha search."""
import pandas as pd,numpy as np
from readiness import labels
from quant_harness.investment.research import replay_targets,metrics

def signal_statistics(scores,target,*,kind='cross_sectional',native_ic=None):
 if not scores.index.equals(target.index) or set(scores.columns)!=set(target.columns):raise ValueError('common dates/universe mask required')
 if kind!='cross_sectional':raise ValueError('event/time-series require their own preregistered primary, not forced IC')
 score=scores.stack(future_stack=True);truth=target.reindex(columns=scores.columns).stack(future_stack=True);score.index.names=truth.index.names=['datetime','instrument']
 if native_ic is None:raise ValueError('pass original qlib.contrib.eva.alpha.calc_ic from isolated Qlib env')
 ic,rank=native_ic(score,truth);spread=[]
 for d in scores.index:
  pair=pd.concat([scores.loc[d].rename('signal'),target.loc[d].rename('target')],axis=1).dropna()
  if len(pair)<8:continue
  ordered=pair.sort_values(pair.columns[0],kind='stable');k=max(1,len(ordered)//5);spread.append({'date':str(d),'spread':float(ordered.iloc[-k:,1].mean()-ordered.iloc[:k,1].mean()),'names':len(pair)})
 return {'IC':ic,'RankIC':rank,'spread':spread,'no_risk_cash_allocation':True,'no_annualization_of_overlapping_IC':True}

def execution_arms(panel,dates,signal_ledger,risk_only_ledger,capital,spec,rebalance_dates,benchmark):
 """Accept candidate-declared horizon/map; reuse the existing deterministic engine.

 This never chooses top4, a holding period, a new risk parameter or a champion.
 Caller must preregister source/event times and mask before evaluation.
 """
 if signal_ledger.date.tolist()!=list(dates) or risk_only_ledger.date.tolist()!=list(dates):raise ValueError('shared session ledger required')
 import json
 risk=panel['close'][benchmark].ge(panel['close'][benchmark].rolling(63,min_periods=63).mean()).shift(1,fill_value=False).reindex(dates)
 def masked(ledger):
  result=ledger.copy();result['target_weights_json']=[x if bool(r) else '{}' for x,r in zip(result.target_weights_json,risk)];return result
 changes={d for i,d in enumerate(dates) if i==0 or risk.iloc[i]!=risk.iloc[i-1]};schedules=set(rebalance_dates)|changes;out={}
 for name,ledger,rs in [('FIXED_EXPOSURE',signal_ledger,set(rebalance_dates)),('SAME_SIGNAL_WITH_EXISTING_RISK',masked(signal_ledger),schedules),('RISK_ONLY_BASELINE',masked(risk_only_ledger),schedules)]:
  nav,fills,intents=replay_targets(panel,dates,ledger,capital,spec,rebalance_dates=rs,allow_unpriced_hold=False)
  out[name]={'metrics':metrics(nav,fills,capital),'account':nav,'fills':fills,'unfilled':intents}
 return out
