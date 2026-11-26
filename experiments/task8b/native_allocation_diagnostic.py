from pathlib import Path
import json,pandas as pd
from src.quantlib.portfolio import hierarchical_risk_parity
packet=json.loads(Path('/evidence/research_packet_v2.json').read_text());result={}
for market in ['US','KR']:
 symbols=[c['ticker'] for c in packet['cases'] if c['market']==market];close=pd.DataFrame({s:pd.read_csv(Path('/evidence/prices')/(s+'.csv')).set_index('date').close for s in symbols});returns=close.pct_change(fill_method=None).dropna();cov=returns.cov();corr=returns.corr();weights=hierarchical_risk_parity(cov,corr)
 result[market]={'native_hrp_weights':{s:float(weights.loc[s]) for s in symbols},'complete_joint_return_rows':len(returns),'exposure':float(weights.sum()),'meaning':'Original covariance-only allocation calculation, no claim this is Vibe full investment judgment; no strategy adopted or historical return optimized'}
Path('/work/native_allocation_diagnostic.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
