"""Price-implied conditions under declared funding/margin assumptions, not consensus."""
from pathlib import Path
import json
b=Path(__file__).resolve().parents[2]/'runtime/task8b';hypotheses=json.loads((b/'declared_valuation_hypotheses.json').read_text());latest=json.loads((b/'postseal_price_observation.json').read_text());prices={r['ticker']:r['new_observed_price'] for r in latest['rows']};result={}
for symbol,anchor in [('NVDA',96221*4),('CRWV',13150)]:
 rows=[]
 for spec in hypotheses[symbol]:
  if spec['scenario']!='base' or spec['fcff_margin']<=0:continue
  y=spec['years'];shares=spec['shares_million']*(1+spec['dilution_per_year'])**y
  required_equity=prices[symbol]*shares*(1+spec['discount_rate'])**y
  required_ev=required_equity+spec['debt_million']-spec['cash_million']+spec['other_claims_million']
  revenue=required_ev/(spec['fcff_margin']*spec['exit_multiple'])
  rows.append({'years':y,'reference_price':prices[symbol],'required_horizon_revenue_USD_million':revenue,'revenue_CAGR_from_proxy':(revenue/anchor)**(1/y)-1,'earn_required_return':spec['discount_rate'],'normal_FCFF_margin_assumed':spec['fcff_margin'],'FCFF_exit_multiple_assumed':spec['exit_multiple'],'projected_net_debt_USD_million':spec['debt_million']-spec['cash_million'],'dilution_per_year':spec['dilution_per_year'],'declared_revenue_USD_million':spec['revenue_million'],'proxy_anchor':anchor,'meaning':'Solve a conditional hurdle, NOT observed sell-side consensus or a revealed unique market expectation'})
 result[symbol]=rows
(b/'reverse_conditions.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
