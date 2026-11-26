from pathlib import Path
import json,math,dataclasses
from src.quantlib.valuation.dcf import equity_bridge
p=Path('/evidence/conditional_values.json');values=json.loads(p.read_text());rows=[]
for ticker,data in values.items():
 for row in data['scenarios']:
  spec,value=row['spec'],row['value']
  if spec['method']!='FCFF_MULTIPLE' or value['status']!='CONDITIONAL_WHAT_IF_NOT_APPROVED_TARGET':continue
  native=equity_bridge(enterprise_value=value['enterprise_value_million'],total_debt=spec['debt_million'],cash_and_equivalents=spec['cash_million'],minority_interest=spec['other_claims_million'],preferred_equity=0,associate_investments=0,diluted_shares=value['projected_diluted_shares_million'])
  assert math.isclose(native.equity_value,value['equity_value_million'],abs_tol=1e-6)
  rows.append({'ticker':ticker,'years':spec['years'],'scenario':spec['scenario'],'native_equity_value':native.equity_value,'native_unfloored_per_share':native.value_per_share,'research_limited_liability_price_floor':value['future_price'],'difference':'Explicit limited liability floor for negative equity, not missing-data substitution' if native.value_per_share<0 else 'PARITY'})
Path('/work/native_value_check.json').write_text(json.dumps({'status':'ORIGINAL_VIBE_EQUITY_BRIDGE_PARITY_PASS','rows':rows},indent=2));print('ORIGINAL_VIBE_EQUITY_BRIDGE_PARITY_PASS',len(rows))
