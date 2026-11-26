"""Strict adapter for original Vibe earnings component, outside CLI fallback.
The provider remains upstream; this boundary never invents missing equity value.
"""
from datetime import timedelta
import json,math
from .decision import instant
from .research import digest


def parse_response(raw,packet):
    data=json.loads(raw)  # No code-fence repair or fallback success.
    cases=data.get('cases',[]);expected={c['ticker'] for c in packet['cases']}
    if len(cases)!=len(expected) or {c.get('ticker') for c in cases}!=expected:raise ValueError('company response identity mismatch')
    for analysis in cases:
        case=next(c for c in packet['cases'] if c['ticker']==analysis['ticker'])
        sources={s['source_id'] for s in case['sources'] if s['status']=='SAVED'}|{'TOSS_ADJUSTED_DAILY'}
        if not analysis.get('facts'):raise ValueError('CLI abstention/fallback is not numeric research success')
        for fact in analysis['facts']:
            if fact.get('source_id') not in sources or isinstance(fact.get('value'),bool) or not isinstance(fact.get('value'),(int,float)) or not math.isfinite(fact['value']):raise ValueError('uncited/nonfinite company fact')
        scenarios=analysis.get('scenarios',{})
        values=[scenarios.get(k,{}).get('revenue_million') for k in ['bear','base','bull']]
        if any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or x<0 for x in values) or values!=sorted(values):raise ValueError('invalid forecast scenarios')
        probabilities=[scenarios.get(k,{}).get('probability') for k in ['bear','base','bull']]
        if any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or not 0<=x<=1 for x in probabilities) or abs(sum(probabilities)-1)>1e-8:raise ValueError('invalid scenario probabilities')
        if not analysis.get('falsification') or not analysis.get('forecast_target',{}).get('period_end'):raise ValueError('forecast target/falsification missing')
    return cases


def judgment(analysis,case,*,horizon_sessions=63):
    sources=[s for s in case['sources'] if s['status']=='SAVED'];available=max([s['available_at'] for s in sources]+[case['observed_at']])
    return {'ticker':case['ticker'],'market':case['market'],'currency':'USD' if case['market']=='US' else 'KRW','team':'company','engine':'VIBE_EARNINGS_COMPONENT','version':'TASK8_SOURCE_GATE_V1','source_hashes':[s['sha256'] for s in sources],'available_at':available,'valid_until':(instant(available)+timedelta(days=7)).isoformat(),'horizon_sessions':horizon_sessions,'direction':'ABSTAIN','status':'RESEARCH_ONLY','expected_return':None,'downside':None,'round_trip_cost':None,'liquidity_verified':False,'sector':None,'edge_evidence':'UNPROVEN','hypothesis':analysis['hypothesis'],'falsification':analysis['falsification'],'analysis_hash':digest(analysis),'equity_return_status':'UNQUANTIFIED_NO_VALIDATED_EV_EQUITY_BRIDGE_OR_CONSENSUS','missing':['Independent contemporaneous market expectations','Complete EV to equity/share dilution bridge','Investable expected return/downside with validated cost/liquidity'],'revenue_scenarios_are_equity_returns':False,'issuer_guidance_is_consensus':False}
