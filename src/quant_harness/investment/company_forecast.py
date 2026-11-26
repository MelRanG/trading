"""Source-only company research review and immutable forecast scoring boundary.
No orders, NAV mutation, strategy promotion, or synthetic realized labels.
"""
from datetime import datetime,timezone
import math,re

def instant(s):
 d=datetime.fromisoformat(s.replace('Z','+00:00'))
 if d.tzinfo is None:raise ValueError('timezone required')
 return d

def scenarios_of(record):
 s=record.get('scenarios',{});return {k:s[k] for k in ['bull','base','bear'] if isinstance(s,dict) and isinstance(s.get(k),dict)}

def audit_forecast(record):
 cases=scenarios_of(record);issues=[]
 if set(cases)!={'bull','base','bear'}:issues.append('SCENARIOS_INCOMPLETE')
 probabilities=[r.get('probability') for r in cases.values()]
 if len(probabilities)!=3 or any(not isinstance(x,(int,float)) or not math.isfinite(x) or not 0<=x<=1 for x in probabilities):issues.append('PROBABILITIES_MISSING')
 elif abs(sum(probabilities)-1)>1e-8:issues.append('PROBABILITIES_NOT_SUM_ONE')
 values=[cases.get(k,{}).get('revenue_million') for k in ['bear','base','bull']]
 if any(not isinstance(x,(int,float)) or not math.isfinite(x) or x<0 for x in values):issues.append('REVENUE_FORECAST_MISSING')
 elif values!=sorted(values):issues.append('REVENUE_SCENARIO_ORDER')
 for k,v in cases.items():
  margin=v.get('gaap_operating_margin_pct')
  if margin is not None and (not isinstance(margin,(int,float)) or not math.isfinite(margin) or not -100<=margin<=100):issues.append('INVALID_MARGIN:'+k)
  if not v.get('assumptions'):issues.append('ASSUMPTION_MISSING:'+k)
 return {'status':'PROCESS_CHECKS_PASS' if not issues else 'PROCESS_ISSUES','issues':issues,'future_accuracy':'PENDING','hypothesis_error_from_profit_loss':False}

def score_forecast(forecast,label=None,now=None):
 # Period end or scheduled date alone never matures a forecast.
 if label is None:return {'status':'PENDING','reason':'NO_OBSERVED_RELEASE_LABEL'}
 if label.get('source_class')!='OFFICIAL_ISSUER' or label.get('verification_status')!='VERIFIED' or not re.fullmatch(r'[0-9a-f]{64}',label.get('source_sha256','')) or not label.get('source_id'):raise ValueError('verified official source and content hash required')
 current=instant(now or datetime.now(timezone.utc).isoformat());observed=instant(label['observed_at']);released=instant(label['released_at']);sealed=instant(forecast['sealed_at'])
 if observed>current or released>current:return {'status':'PENDING','reason':'RELEASE_NOT_YET_OBSERVED'}
 if released<=sealed:raise ValueError('label predates forecast; not independent Forward')
 if observed<released:raise ValueError('invalid observation chronology')
 if any(forecast[k]!=label[k] for k in ['ticker','metric','period_end','unit']):raise ValueError('forecast/label identity or unit mismatch')
 actual=float(label['actual']);pred=float(forecast['base_value'])
 if not all(math.isfinite(x) for x in [actual,pred]):raise ValueError('nonfinite forecast or actual')
 return {'status':'MATURE','absolute_error':abs(pred-actual),'signed_error':pred-actual,'relative_absolute_error':abs(pred-actual)/abs(actual) if actual else None,'interval_covered':forecast['bear_value']<=actual<=forecast['bull_value'],'source_id':label['source_id']}
