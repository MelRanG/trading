"""Declare conditional grids before calculating values; no alpha optimization."""
from pathlib import Path
import json,sys,hashlib
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src'))
from quant_harness.investment.opportunity import value_scenario,implied_eps
b=R/'runtime/task8b';packet=json.loads((b/'research_packet_v2.json').read_text());case_map={c['ticker']:c for c in packet['cases']}
# These are explicit analyst WHAT-IF assumptions, never issuer guidance/consensus.
# Reported EPS anchors are annualized proxies, not TTM or established normalized EPS.
anchors={'FPS':(1.37,'FY2027 issuer adjustedEPS guide midpoint; not GAAP recurringEPS'),'HRMY':(.81*4,'Q32026 dilutedEPS×4; one-quarter proxy'),'CFG':(1.41*4,'Q32026 dilutedEPS×4; credit-cycle uncertainty'),'AMKR':(.70*4,'Q42026 issuer guidance EPS midpoint×4; not actual annualEPS'),'062040.KS':(3231*2,'1H2026 dilutedEPS×2, no quarterly-report upgrade observed'),'002990.KS':(932*4/3,'9M2026 dilutedEPS annualized4/3; capital reduction and PF risk'),'068760.KQ':(509*2,'1H2026 OFS dilutedEPS×2, not CFS'),'024110.KS':(1671*2,'1H2026 dilutedEPS×2; bank funding/reserve risk'),'218410.KQ':(592*2,'1H2026 dilutedEPS×2; do not assume Q3 acceleration persists')}
parameters={'FPS':([-.2,.1,.25],[12,18,24],.14),'HRMY':([-.2,.05,.2],[8,12,16],.14),'CFG':([-.2,.05,.12],[8,11,14],.10),'AMKR':([-.2,.15,.3],[9,13,17],.12),'062040.KS':([-.2,.1,.25],[14,20,26],.12),'002990.KS':([-.4,.05,.2],[5,8,11],.18),'068760.KQ':([-.2,.15,.3],[15,25,35],.14),'024110.KS':([-.2,.03,.08],[4,7,9],.10),'218410.KQ':([-.2,.15,.4],[15,22,30],.14)}
assumptions={}
for symbol,(anchor,basis) in anchors.items():
 rows=[];growth,multiples,rate=parameters[symbol]
 for y in [1,2,3]:
  for i,name in enumerate(['bear','base','bull']):rows.append({'years':y,'scenario':name,'method':'EPS_PE','future_diluted_eps':anchor*(1+growth[i])**y,'exit_multiple':multiples[i],'discount_rate':rate,'assumptions':{'basis':basis,'earnings_growth_per_year':growth[i],'multiple_status':'Declared sensitivity, NOT historical percentile or verified peer median','capital_risk':'Future EPS must include interest, royalties, dilution and ordinary claims; not verified forecast'},'source_ids':[s['source_id'] for s in case_map[symbol]['sources'] if s.get('status')!='FAILED']})
 assumptions[symbol]=rows
# Lotte uses parent-attributable book, not consolidated total assets or lease-free equity.
lotte=case_map['023530.KS'];q3=lotte['sources'][-1]['data']['list'];equity=float(next(r['thstrm_amount'] for r in q3 if r['sj_div']=='BS' and r.get('account_id')=='ifrs-full_EquityAttributableToOwnersOfParent'));shares=28270640
assumptions['023530.KS']=[{'years':y,'scenario':n,'method':'BOOK_PBR','future_bvps':equity/shares*(1+g)**y,'exit_multiple':m,'discount_rate':.14,'assumptions':{'basis':'2026Q3 parent-equity / Q2 outstanding-common proxy; share-count drift/unrecognized impairment unresolved','book_growth':g,'valuation_trap':'Low PB is not cheap if ROE/asset realization/lease-adjusted cash returns remain weak','pb_status':'Declared sensitivity, not peer consensus'},'source_ids':['023530.KS_Q3_CURRENT','023530_shares']} for y in [1,2,3] for n,g,m in [('bear',-.15,.10),('base',0,.20),('bull',.03,.35)]]
assumptions['NVDA']=[];assumptions['CRWV']=[]
for y in [1,2,3]:
 for i,n in enumerate(['bear','base','bull']):
  assumptions['NVDA'].append({'years':y,'scenario':n,'method':'FCFF_MULTIPLE','revenue_million':{1:[400000,480000,560000],2:[400000,600000,750000],3:[380000,700000,950000]}[y][i],'fcff_margin':[.30,.36,.42][i],'exit_multiple':[18,24,30][i],'debt_million':35000,'cash_million':[30000,40000,50000][i],'other_claims_million':0,'shares_million':24285,'dilution_per_year':.01,'discount_rate':.12,'assumptions':{'basis':'Q2 issuer table anchors; future sales/FCFF/capital paths are analyst hypotheses','fcff_definition':'After taxes, capex and working capital, before financing interest','claims':'Zero other claims is a sensitivity assumption, not verified absence','leadership':'Economic continuity must be independently observed afterNov12transition','shares':'Q2 diluted weighted-average proxy, not current fully diluted outstanding'},'source_ids':['NVDA_IR','NVDA_IR_0']})
  assumptions['CRWV'].append({'years':y,'scenario':n,'method':'FCFF_MULTIPLE','revenue_million':{1:[18000,20000,23000],2:[20000,30000,45000],3:[25000,45000,70000]}[y][i],'fcff_margin':{1:[-.10,0,.05],2:[-.05,.05,.12],3:[0,.10,.15]}[y][i],'exit_multiple':[15,20,25][i],'debt_million':{1:[65000,60000,55000],2:[90000,85000,80000],3:[110000,100000,90000]}[y][i],'cash_million':[3000,5000,10000][i],'other_claims_million':0,'shares_million':559,'dilution_per_year':[.12,.10,.08][i],'discount_rate':.18,'assumptions':{'basis':'Q3 issuer anchors; future capacity/backlog conversion/funding are hypothetical','fcff_definition':'After all maintenance/growth capex/tax/WC, BEFORE debt-interest financing; do not substitute adjustedEBITDA','funding':'Projected debt and dilution are declared stress paths, no guarantee of available financing','claims':'Zero incremental other claims is an unresolved sensitivity assumption','shares':'Weighted-average Q3 proxy, not verified spot fully diluted shares'},'source_ids':['CRWV_IR']})
path=b/'declared_valuation_hypotheses.json'
if path.exists() and json.loads(path.read_text())!=assumptions:raise ValueError('immutable hypotheses changed')
path.write_text(json.dumps(assumptions,indent=2));results={}
for symbol,rows in assumptions.items():
 price=case_map[symbol]['current_price']['value'];values=[]
 for row in rows:
  try:values.append({'spec':row,'value':value_scenario(row,price)})
  except ValueError as exc:values.append({'spec':row,'value':{'status':'INCOMPLETE','reason':str(exc)}})
 results[symbol]={'observed_price':price,'price_implied_eps_at_scenario_pe':[{ 'pe':m,'required_eps':implied_eps(price,m)} for m in sorted(set(r['exit_multiple'] for r in rows))] if rows[0]['method']=='EPS_PE' else None,'scenarios':values,'meaning':'Analyst conditional sensitivities; no calibrated probabilities, no Paper approval; NOT empirically established expected price'}
(b/'conditional_values.json').write_text(json.dumps(results,indent=2));print(json.dumps({s:[{'horizon':x['spec']['years'],'scenario':x['spec']['scenario'],'future_price':x['value'].get('future_price'),'status':x['value']['status']} for x in v['scenarios'] if x['spec']['years']==3] for s,v in results.items()},indent=2))
