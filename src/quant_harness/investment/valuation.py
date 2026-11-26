"""Deterministic expectations arithmetic, not an investment recommendation.

Selective implementation of the reverse-DCF function reviewed in Task2;
not a claim to replicate the entire upstream equity-research package.
"""
import math


def implied_growth(*, price, shares, debt, cash, revenue, fcf_margin, discount_rate, terminal_growth, years=5):
    values=(price,shares,debt,cash,revenue,fcf_margin,discount_rate,terminal_growth)
    if any(not isinstance(x,(int,float)) or not math.isfinite(x) for x in values):
        raise ValueError('complete finite valuation inputs required')
    if min(price,shares,revenue)<=0 or min(debt,cash)<0 or not 0<fcf_margin<=1 or not 0<=terminal_growth<discount_rate<1 or not isinstance(years,int) or not 1<=years<=20:
        raise ValueError('invalid valuation assumptions')
    enterprise=price*shares+debt-cash
    if enterprise<=0:raise ValueError('positive enterprise value required')
    def pv(growth):
        flows=[revenue*(1+growth)**t*fcf_margin for t in range(1,years+1)]
        return sum(v/(1+discount_rate)**t for t,v in enumerate(flows,1))+flows[-1]*(1+terminal_growth)/(discount_rate-terminal_growth)/(1+discount_rate)**years
    low,high=-0.95,2.0
    if not pv(low)<=enterprise<=pv(high):
        return {'status':'OUTSIDE_REGISTERED_RANGE','range':[low,high]}
    for _ in range(100):
        middle=(low+high)/2
        if pv(middle)<enterprise:low=middle
        else:high=middle
    return {'status':'CALCULATED_MODEL_IMPLIED_NOT_CONSENSUS','growth':(low+high)/2,
            'enterprise_value':enterprise,'assumptions':{'fcf_margin':fcf_margin,'discount_rate':discount_rate,'terminal_growth':terminal_growth,'years':years}}


def scenario_record(metric, horizon_end, unit, currency, scenarios):
    if len(scenarios)!=3 or {s['name'] for s in scenarios}!={'bear','base','bull'}:
        raise ValueError('three named scenarios required')
    if any(not math.isfinite(s['value']) or not math.isfinite(s['probability']) or not 0<=s['probability']<=1 or not s['assumptions'] for s in scenarios):
        raise ValueError('finite scenarios and assumptions required')
    if abs(sum(s['probability'] for s in scenarios)-1)>1e-9:
        raise ValueError('scenario probabilities must sum to one')
    return {'metric':metric,'horizon_end':horizon_end,'unit':unit,'currency':currency,'scenarios':scenarios,
            'point':sum(s['value']*s['probability'] for s in scenarios),'label_status':'PENDING', 'prediction_is_fact':False}
