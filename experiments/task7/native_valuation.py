from pathlib import Path
import importlib.util,json,dataclasses
from src.quantlib.valuation.dcf import run_dcf
from src.quantlib.valuation.contracts import MissingInputError
w=Path('/work');packet=json.loads((w/'company_packet.json').read_text());cfg=json.loads(Path('/code/valuation_contract.json').read_text());spec=importlib.util.spec_from_file_location('original_equity_dcf','/skills/equity_dcf.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
# Each historical input is copied verbatim from the preserved issuer table;
# future growth/margins are explicitly scenario assumptions, not facts.
inputs={'NVDA':{'quarter_revenue':96221,'quarter_fcf':21341,'shares_million':24285,'debt':33366,'cash':22443,'source':'NVDA_IR'},'CRWV':{'quarter_revenue':3661,'quarter_fcf':1975-9441,'shares_million':559,'debt':9183+1389+32417+3884,'cash':4122,'source':'CRWV_IR'}}
result={}
for case in packet['cases']:
 s=case['ticker'];v=inputs[s];rows=[]
 for rate in cfg[s]['wacc']:
  rows.append({'wacc':rate,'output':module.reverse_dcf(case['prices']['close'],v['shares_million'],v['debt']-v['cash'],rate,cfg['terminal_growth'],[v['quarter_fcf']*4]*cfg['interim_years'],cfg[s]['steady_fcf_margins'],v['quarter_revenue']*4)})
 try:
  full=run_dcf({'total_debt':v['debt'],'cash_and_equivalents':v['cash'],'diluted_shares':v['shares_million']},capital_structure_basis='target',discounting_convention='year_end',terminal_value_method='perpetuity_growth');native={'status':'UNEXPECTED_COMPLETE'}
 except MissingInputError as e:native={'status':'NOT_RUNNABLE','missing':list(e.missing),'scope':'Original Vibe required-input gate; no fabricated forecast/WACC/terminal assumptions inserted'}
 result[s]={'observed_inputs':v,'price':case['prices'],'assumptions':cfg,'original_equity_reverse_dcf':rows,'original_vibe_dcf':native,'consensus':'NOT_AVAILABLE','investment_action':'NONE','limitations':['Weighted-average share proxy, cash-only bridge; omitted investments/leases may materially change implied growth','Interim constant annualization and terminal FCF margin are assumptions, not expected issuer trajectory','This is conditional model-implied growth, not evidence of mispricing or analyst consensus']}
(w/'native_valuation.json').write_text(json.dumps(result,indent=2,default=str));print(json.dumps(result,indent=2,default=str))
