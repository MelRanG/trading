"""Upstream risk/allocation calculations on fixed real price snapshots; no alpha claim."""
from pathlib import Path
import json,pandas as pd,numpy as np
from src.quantlib.portfolio import hierarchical_risk_parity,inverse_variance_weights
from src.quantlib.risk import max_drawdown_analysis
from src.portfolio.rebalance import propose_rebalance
w=Path('/work');frames={s:pd.read_csv('/evidence/market/'+s+'.csv').set_index('date').close for s in ['NVDA','CRWV']};returns=pd.DataFrame(frames).pct_change().dropna();cov=returns.cov();corr=returns.corr();weights=hierarchical_risk_parity(cov,corr)
result={'status':'ORIGINAL_ALLOCATION_EXECUTED','rows':len(returns),'native_hrp_weights':{s:float(weights.iloc[i]) for i,s in enumerate(cov.columns)},'inverse_variance_weights':dict(zip(cov.columns,map(float,inverse_variance_weights(cov)))),'correlations':corr.to_dict(),'drawdown':{s:max_drawdown_analysis((1+returns[s]).cumprod()) for s in returns},'limitations':['Backward-looking covariance allocation has no return forecast/alpha validation','No position/name/sector/cost/turnover constraints are enforced by this allocation function','Real source snapshots; no historical company strategy return has been invented']}
snapshot={'complete':True,'snapshot_id':'TASK8_REAL_US_CASH_SHADOW','created_at':json.loads(Path('/evidence/comparison.json').read_text())['at'],'accounts':[],'fx':{'stale':False,'rates':{'USD':1},'as_of':'2026-11-13'},'positions':[],'combined_holdings':[],'valuation':{'cash_usd':100000,'unpriced_or_other_usd':0},'display_currency':'USD'}
result['original_cash_rebalance']=propose_rebalance(snapshot,{'CASH':1})
try:propose_rebalance(snapshot,{'NVDA':.1,'CASH':.9});result['new_stock_gate']='UNEXPECTED_ALLOWED'
except ValueError as e:result['new_stock_gate']={'status':'REJECTED','reason':str(e)}
(w/'native_portfolio.json').write_text(json.dumps(result,indent=2,default=str));print(json.dumps(result,indent=2,default=str))
