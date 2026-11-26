"""Reconstruct ONE fully disclosed numeric scenario, without changing sealed decisions."""
from common import *
sys.path.insert(0,'/home/ansy/app/quant-diligence/vibe-original/agent')
from src.quantlib.valuation.dcf import equity_bridge
p=B/'decisions/US/2026-05-15.json';c=next(c for c in json.loads(p.read_text())['cases'] if c['symbol']=='SFM');assumptions=c['valuation']['assumptions'];assert all(t in assumptions for t in ['300, 300, 300','400, 440, 480','500 each year','12%','10%','8.5%','2.5%','3%'])
rows=[]
for name,flows,r,g in [('bear',[300,300,300],.12,0),('base',[400,440,480],.10,.025),('bull',[500,500,500],.085,.03)]:
 pv=sum(v/(1+r)**(i+1) for i,v in enumerate(flows))+flows[-1]*(1+g)/(r-g)/(1+r)**3;equity=pv+252.161-99.593
 native=equity_bridge(enterprise_value=equity,total_debt=0,cash_and_equivalents=0,minority_interest=0,preferred_equity=0,associate_investments=0,diluted_shares=95.585);model=c['valuation'][name]
 rows.append({'scenario':name,'cashflow_units':'USD_millions','FCFE':flows,'discount_rate':r,'terminal_growth':g,'model_reported_per_share':model,'annual_period_reconstruction_per_share':native.value_per_share,'relative_difference_to_model':native.value_per_share/model-1,'native_equity_per_share_bridge':True,'opening_net_cash_added_once_as_model_assumed':252.161-99.593,'FCFE_no_additional_EV_debt_subtraction':True})
freeze(B/'valuation_arithmetic_audit.json',{'case':'SFM_initial','decision_hash':sha(p),'declared_assumptions':assumptions,'rows':rows,'status':'REPORTED_VALUES_NOT_REPRODUCED_FROM_EXPLICIT_ASSUMPTIONS','limitation':'Annual end-period illustration only; actual asof stub/enddate convention was not fully specified. Not a corrected approved target. Missing disclosed assumptions or arithmetic error cannot be distinguished.','sealed_inputs_decisions_portfolios_changed':False,'causal_impact_on_return':'UNDETERMINED','additional_LLM_calls':0});print([(r['scenario'],r['model_reported_per_share'],round(r['annual_period_reconstruction_per_share'],2)) for r in rows])
