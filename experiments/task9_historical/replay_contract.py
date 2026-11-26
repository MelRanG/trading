"""Historical gates/forecast scoring; never converts missing-data cash to returns."""
from datetime import datetime,timezone,timedelta
from pathlib import Path
import json,math,hashlib

def stamp(x):
 t=datetime.fromisoformat(x.replace('Z','+00:00'))
 if t.tzinfo is None:raise ValueError('timezone required')
 return t

def source_eligible(source,cutoff):
 if source.get('original_version') is not True:return False
 # Date-only releases delayed to the end of that local date; exact timestamp
 # input must already carry the documented timezone, never inferred from period.
 if source.get('published_at'):available=stamp(source['published_at'])
 elif source.get('publication_date') and source.get('publication_timezone_offset'):
  available=stamp(source['publication_date']+'T00:00:00'+source['publication_timezone_offset'])+timedelta(days=1)
 else:return False
 return bool(source.get('sha256')) and available<=stamp(cutoff)

def replay_gate(packet):
 reasons=[]
 for field in ('historical_universe','listing_and_identifiers','official_sessions','eligible_execution_prices','actions_dividends_delistings','original_information_versions'):
  if packet.get('coverage',{}).get(field)!='VERIFIED':reasons.append('MISSING_OR_PARTIAL:'+field)
 if not packet.get('sources') or not all(source_eligible(s,packet['information_cutoff']) for s in packet['sources']):reasons.append('INELIGIBLE_INFORMATION')
 if not packet.get('next_session_open') or stamp(packet['next_session_open'])<=stamp(packet['information_cutoff']):reasons.append('NO_NEXT_ELIGIBLE_SESSION')
 if packet.get('weights') is None:reasons.append('NO_SEALED_DECISION')
 return {'status':'ELIGIBLE_HISTORICAL_REPLAY' if not reasons else 'BLOCKED_DATA_QUALITY','reasons':reasons,'forward_evidence':False,'research_scope':'RECONSTRUCTED_HISTORICAL_LLM_MEMORY_UNCONTROLLED'}

def guarded_replay(packet,executor):
 gate=replay_gate(packet)
 if gate['status']!='ELIGIBLE_HISTORICAL_REPLAY':return {**gate,'portfolio_return':None,'fills':None,'cash_strategy_performance':None}
 return {'gate':gate,'result':executor(packet),'forward_evidence':False}

def score_forecast(forecast,actual,cutoff,evaluated_at):
 if stamp(actual['published_at'])>stamp(evaluated_at):return {'status':'PENDING','reason':'ACTUAL_NOT_YET_PUBLIC'}
 if stamp(actual['published_at'])<=stamp(cutoff):raise ValueError('outcome already known at forecast cutoff')
 if not actual.get('original_version') or not actual.get('source_hash'):raise ValueError('original outcome evidence required')
 for field in ('company_id','metric','period_start','fiscal_end','unit'):
  if forecast.get(field)!=actual.get(field):raise ValueError('forecast/outcome contract mismatch:'+field)
 values=[forecast.get(k) for k in ('bear','base','bull')]+[actual.get('value')]
 if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in values):raise ValueError('finite forecast and outcome required')
 bear,base,bull,value=values
 if not bear<=base<=bull:raise ValueError('scenario ordering')
 return {'status':'HISTORICAL_SCENARIO_SCORED','independent_forecast':forecast.get('forecast_origin')=='INDEPENDENT_SCENARIO','signed_error':base-value,'absolute_error':abs(base-value),'relative_absolute_error':abs(base-value)/abs(value) if value else None,'within_scenario_range':bear<=value<=bull,'price_prediction_accuracy':None,'llm_memory_confounded':True}

def seal(path,payload):
 raw=json.dumps(payload,ensure_ascii=False,sort_keys=True,allow_nan=False);path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 if path.exists() and path.read_text()!=raw:raise ValueError('immutable historical seal conflict')
 if not path.exists():path.write_text(raw)
 return hashlib.sha256(raw.encode()).hexdigest()


def run_existing_replay(packet,market,dates,ledger,initial,execution_spec):
    """Reuse QH replay arithmetic ONLY in an action-free verified interval.

    Existing replay_targets has no dividend/split/delisting event processor.
    Merely possessing corporate-action data does not implement that processor.
    """
    gate=replay_gate(packet)
    if gate['status']!='ELIGIBLE_HISTORICAL_REPLAY':return guarded_replay(packet,None)
    if packet.get('verified_action_free_interval') is not True or packet.get('corporate_action_events'):
        return {'status':'BLOCKED_EXECUTION_ACTION_ADAPTER','portfolio_return':None,'fills':None,'forward_evidence':False}
    from quant_harness.investment.research import replay_targets
    return guarded_replay(packet,lambda p:replay_targets(market,dates,ledger,initial,execution_spec))
