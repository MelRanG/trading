from common import *
import math,datetime,sys
sys.path.insert(0,'/home/ansy/app/quant-diligence/vibe-original/agent')
from src.quantlib.valuation.dcf import equity_bridge,FCFFYear

def timed_value(asof,scenario):
 rate=float(scenario['discount_rate']);g=float(scenario['terminal_growth']);assert math.isfinite(rate) and 0<=g<rate
 start=datetime.datetime.fromisoformat(asof).date();cashflows=[];times=[]
 for i,row in enumerate(scenario['cashflows']):
  end=datetime.date.fromisoformat(row['end_date']);t=(end-start).days/365.25;assert t>0 and (not times or t>times[-1])
  bridge=FCFFYear(year=i+1,ebit=row['ebit'],tax_rate=row['tax_rate'],nopat=row['ebit']*(1-row['tax_rate']),depreciation_amortization=row['da'],capex=row['capex'],delta_nwc=row['delta_nwc'],fcff=row['ebit']*(1-row['tax_rate'])+row['da']-row['capex']-row['delta_nwc']);assert row['capex']>=0 and row['da']>=0
  cashflows.append(bridge.fcff);times.append(t)
 assert len(times)==5
 ev=sum(v/(1+rate)**t for v,t in zip(cashflows,times))+cashflows[-1]*(1+g)/(rate-g)/(1+rate)**times[-1]
 native=equity_bridge(enterprise_value=ev,total_debt=scenario['debt'],cash_and_equivalents=scenario['cash'],minority_interest=scenario['other_claims'],preferred_equity=0,associate_investments=0,diluted_shares=scenario['diluted_shares'])
 return {'EV_conditional':ev,'equity_conditional':native.equity_value,'value_per_share_conditional':native.value_per_share,'first_stub_years':times[0],'dates':[r['end_date'] for r in scenario['cashflows']],'cashflows':cashflows,'dilution_plus5pct_value':native.value_per_share/1.05,'native_FCFF_bridge_and_equity_bridge':True,'calendar_fraction_discount_adapter':'ACT365.25 end-of-period','capital_rollforward':'LAST_DISCLOSED_BALANCE_PROXY_NOT_VERIFIED_ASOF_BANK_BALANCE','not_approved_price_target':True}

if __name__=='__main__':
 W=Path('/home/ansy/app/quant-diligence/task9-2-work');W=W if W.exists() else B/'model_outputs';rows=[]
 for stage in ['history_after','history_lg_repair','current_repair']:
  x=json.loads((W/(stage+'.json')).read_text())
  for c in x['cases']:
   for s in c.get('scenarios',[]):
    rate=s['discount_rate'];g=s['terminal_growth'];assert 0<=g<rate;flows=s['fcff'];pv=sum(v/(1+rate)**(i+1) for i,v in enumerate(flows))+flows[-1]*(1+g)/(rate-g)/(1+rate)**len(flows);method=s.get('method','FCFF_DCF');value=pv/s['diluted_shares'] if method=='FCFE_DCF' else equity_bridge(enterprise_value=pv,total_debt=s['debt'],cash_and_equivalents=s['cash'],minority_interest=s['other_claims'],preferred_equity=0,associate_investments=0,diluted_shares=s['diluted_shares']).value_per_share
    rows.append({'stage':stage,'symbol':c['symbol'],'name':s['name'],'method':method,'value_per_share_annual_illustration':value,'status':'ILLUSTRATIVE_TIMING_UNRESOLVED_NOT_ASOF_TARGET','reason':'Full fiscal-year or Sep30-anchored remaining flow not same as research cutoff; do not present as fully validated as-of fair value'})
 dump(B/'valuation_annual_diagnostics.json',rows)
 x=json.loads((W/'current_timing.json').read_text());packet=json.loads((B/'current_numeric_packet_v2.json').read_text());assert x['input_hash']==digest(packet);rows=[]
 for c in x['cases']:
  for s in c['scenarios']:rows.append({'symbol':c['symbol'],'name':s['name'],'asof':x['asof'],'decision_state':c['decision_state'],'missing_fields':c['remaining_data_gaps'],'assumptions':s['assumptions'],'lease_convention':s['lease_convention'],'invalidation':s['invalidation'],**timed_value(x['asof'],s)})
 freeze(B/'current_timed_valuations.json',rows);print('NATIVE_BRIDGES',len(rows));print([(r['symbol'],r['name'],round(r['value_per_share_conditional'],2),round(r['first_stub_years'],3)) for r in rows])
