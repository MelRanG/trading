"""Conditional opportunity valuation and research-only probe contracts.

Declared sensitivities are NOT calibrated expectations or Paper approvals.
"""
import math
from .research import digest

STATUSES={'RESEARCH_INCOMPLETE','RESEARCH_SHADOW','PAPER_ELIGIBLE','REJECTED'}

def number(v):return not isinstance(v,bool) and isinstance(v,(int,float)) and math.isfinite(v)


def value_scenario(spec,price):
    if not number(price) or price<=0:raise ValueError('positive observed reference price required')
    years=spec['years'];method=spec['method'];rate=spec['discount_rate']
    if years not in (1,2,3) or not number(rate) or not 0<rate<1 or not spec.get('assumptions'):raise ValueError('explicit horizon/discount/assumptions required')
    ev=equity=shares=None
    if method=='EPS_PE':
        eps,multiple=spec.get('future_diluted_eps'),spec.get('exit_multiple')
        if not all(number(x) for x in [eps,multiple]) or eps<=0 or multiple<=0:raise ValueError('positive diluted EPS and PE assumptions required')
        future=eps*multiple
    elif method=='BOOK_PBR':
        bv,multiple=spec.get('future_bvps'),spec.get('exit_multiple')
        if not all(number(x) for x in [bv,multiple]) or bv<=0 or multiple<=0:raise ValueError('positive common BVPS and PB assumptions required')
        future=bv*multiple
    elif method=='FCFF_MULTIPLE':
        revenue,margin,multiple=spec.get('revenue_million'),spec.get('fcff_margin'),spec.get('exit_multiple')
        debt,cash,claims,base,dilution=[spec.get(k) for k in ['debt_million','cash_million','other_claims_million','shares_million','dilution_per_year']]
        if not all(number(x) for x in [revenue,margin,multiple,debt,cash,claims,base,dilution]) or min(revenue,multiple,base)<=0 or min(debt,cash,claims)<0 or not -1<margin<1 or not -.1<=dilution<1:raise ValueError('complete finite projected EV/equity bridge required')
        if margin<=0:return {'status':'NOT_VALUABLE_WITH_POSITIVE_FCFF_MULTIPLE','reason':'Nonpositive FCFF requires a different explicit valuation method; missing fair value is not zero'}
        ev=revenue*margin*multiple;equity=ev-debt+cash-claims;shares=base*(1+dilution)**years
        future=max(0,equity)/shares
    else:raise ValueError('unsupported conditional valuation method')
    return {'status':'CONDITIONAL_WHAT_IF_NOT_APPROVED_TARGET','method':method,'years':years,'scenario':spec['scenario'],'enterprise_value_million':ev,'equity_value_million':equity,'projected_diluted_shares_million':shares,'future_price':future,'discounted_fair_price':future/(1+rate)**years,'total_return':future/price-1,'annualized_return':(future/price)**(1/years)-1,'probability':None,'assumptions_hash':digest(spec),'equity_impaired':equity is not None and equity<=0}


def implied_eps(price,multiple):
    if not all(number(x) and x>0 for x in [price,multiple]):raise ValueError('positive price and PE required')
    return price/multiple


def probe_plan(case,policy):
    if case['status'] not in STATUSES:raise ValueError('unrecognized opportunity state')
    if case['status']=='PAPER_ELIGIBLE':raise ValueError('model cannot grant official Paper eligibility')
    reasons=[]
    if case['status']!='RESEARCH_SHADOW':reasons.append(case['status'])
    if not case.get('listing_verified'):reasons.append('CURRENT_COMMON_LISTING_UNVERIFIED')
    if not case.get('source_hashes') or not case.get('falsification'):reasons.append('SOURCE_OR_FALSIFICATION_MISSING')
    if not case.get('bull_thesis') or not case.get('bear_thesis'):reasons.append('TWO_SIDED_THESIS_MISSING')
    rule=case.get('entry_rule',{});trigger=rule.get('trigger')
    if trigger!='NEXT_REGULAR_QUOTE':reasons.append('WAIT_REGISTERED_ENTRY_CONDITION:'+str(trigger))
    if case.get('current_price',0)<=0:reasons.append('CURRENT_PRICE_MISSING')
    return {'ticker':case['ticker'],'market':case['market'],'sector':case['sector'],'classification':case['status'],'eligible_for_probe':not reasons,'reasons':reasons,'weight':policy['initial_probe_weight'] if not reasons else 0,'holding_checkpoints_sessions':policy['holding_checkpoints_sessions'],'entry_rule':rule,'exit_rule':policy['exit_rule'],'benchmark':policy['benchmarks'][case['market']],'official_paper_authority':False,'live_execution_allowed':False}
