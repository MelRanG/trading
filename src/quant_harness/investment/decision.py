"""Versioned source-aware Shadow portfolio decisions. No order authority.

First judgments are independent inputs; no qualitative-to-probability conversion.
Risk caps constrain proposed holdings, and missing eligibility stays cash.
"""
from datetime import datetime,timezone
import math,re
from .research import digest


def instant(s):
    value=datetime.fromisoformat(s.replace('Z','+00:00'))
    if value.tzinfo is None:raise ValueError('aware observation time required')
    return value


def finite(value):
    return not isinstance(value,bool) and isinstance(value,(float,int)) and math.isfinite(value)


def enterprise_to_equity(enterprise_value,debt,cash,other_claims,shares):
    if not all(finite(x) for x in [enterprise_value,debt,cash,other_claims,shares]) or min(debt,cash,other_claims)<0 or shares<=0:raise ValueError('complete finite capital bridge required')
    equity=enterprise_value-debt+cash-other_claims
    return {'enterprise_value':enterprise_value,'equity_value':equity,'equity_value_per_share':equity/shares,'equity_impaired':equity<=0}


def validate_signal(signal,at,policy,market):
    required={'ticker','team','engine','market','currency','source_hashes','available_at','valid_until','horizon_sessions','direction','status','expected_return','downside','round_trip_cost','liquidity_verified','sector','hypothesis','falsification','version','edge_evidence'}
    if not required<=signal.keys():raise ValueError('incomplete independent judgment')
    if signal['team'] not in ('company','quant') or signal['direction'] not in ('LONG','AVOID','ABSTAIN'):raise ValueError('unsupported judgment')
    if signal['market']!=market or signal['currency']!=policy['account_currencies'][market]:raise ValueError('market/currency mixing prohibited')
    if not signal['source_hashes'] or any(not re.fullmatch('[0-9a-f]{64}',h) for h in signal['source_hashes']):raise ValueError('unverified source hashes')
    if not isinstance(signal['horizon_sessions'],int) or isinstance(signal['horizon_sessions'],bool) or signal['horizon_sessions']<=0:raise ValueError('registered horizon required')
    clock=instant(at);seen=instant(signal['available_at'])
    if seen>clock:raise ValueError('future source observation')
    reasons=[]
    if clock>instant(signal['valid_until']) or (clock-seen).total_seconds()>policy['max_evidence_age_hours']*3600:reasons.append('STALE_JUDGMENT')
    if signal['status']!='SHADOW_ELIGIBLE':reasons.append('UNVALIDATED_RESEARCH')
    if signal['direction']!='LONG':reasons.append('NO_LONG_SIGNAL')
    if signal['edge_evidence'] not in ('PREREGISTERED_FORWARD_SHADOW','INDEPENDENT_VALIDATION'):reasons.append('EDGE_NOT_ESTABLISHED')
    if not signal['liquidity_verified']:reasons.append('LIQUIDITY_UNKNOWN')
    if not signal['sector']:reasons.append('SECTOR_UNKNOWN')
    values=[signal['expected_return'],signal['downside'],signal['round_trip_cost']]
    if not all(finite(x) for x in values):reasons.append('RETURN_RISK_COST_UNQUANTIFIED')
    elif signal['downside']<0 or signal['round_trip_cost']<0 or signal['expected_return']<=signal['round_trip_cost']:reasons.append('NO_POSITIVE_NET_EDGE')
    if not signal['hypothesis'] or not signal['falsification']:reasons.append('THESIS_CONTRACT_MISSING')
    return reasons


def decide(signals,policy,market,at,*,mode='integrated',current=None,correlations=None):
    if policy['mode']!='SHADOW_ONLY' or policy['live_execution_allowed'] or policy['automatic_promotion']:raise ValueError('Shadow boundary required')
    if mode not in ('quant','company','integrated'):raise ValueError('unknown comparison arm')
    for k in ['gross_cap','single_name_cap','sector_cap','correlation_cluster_cap','max_turnover','research_name_weight']:
        if not finite(policy[k]) or not 0<=policy[k]<=1:raise ValueError('invalid risk policy')
    current=current or {};correlations=correlations or {};trace=[];eligible={};sector={};groups={}
    if any(not finite(v) or not 0<=v<=1 for v in current.values()) or sum(current.values())>1:raise ValueError('invalid opening allocation')
    for signal in signals:
        reasons=validate_signal(signal,at,policy,market);key=digest(signal)
        included=mode=='integrated' or signal['team']==mode
        if not included:reasons=['ARM_EXCLUDES_TEAM']
        trace.append({'signal_hash':key,'ticker':signal['ticker'],'team':signal['team'],'horizon_sessions':signal['horizon_sessions'],'source_hashes':signal['source_hashes'],'reasons':reasons,'included':included})
        if included:groups.setdefault(signal['ticker'],[]).append((signal,reasons))
    for symbol,rows in groups.items():
        qualified=[s for s,reasons in rows if not reasons]
        # Opposite independent opinions on the SAME horizon trigger research,
        # rather than allowing one team to silently overrule the other.
        conflicts=[(a,b) for a in qualified for b,why in rows if b['direction']=='AVOID' and b['horizon_sessions']==a['horizon_sessions'] and b['team']!=a['team'] and not any(x in why for x in ('STALE_JUDGMENT','UNVALIDATED_RESEARCH','EDGE_NOT_ESTABLISHED'))]
        if conflicts:
            trace.append({'ticker':symbol,'action':'HOLD_NEW_ALLOCATION','reason':'SAME_HORIZON_CONFLICT','signal_pairs':[[digest(a),digest(b)] for a,b in conflicts]});continue
        if qualified:
            sectors={s['sector'] for s in qualified}
            if len(sectors)!=1:raise ValueError('conflicting sector metadata')
            eligible[symbol]=min(policy['research_name_weight'],policy['single_name_cap']);sector[symbol]=next(iter(sectors))
            trace.append({'ticker':symbol,'action':'RESEARCH_ALLOCATION','reason':'NO_WEIGHT_BOOST_FOR_AGREEMENT','independent_sources':len(set(h for s in qualified for h in s['source_hashes'])),'horizons':sorted(set(s['horizon_sessions'] for s in qualified))})
    targets=dict(eligible)
    # Proportional deterministic clipping, never optimize on observed PnL.
    for sect in sorted(set(sector.values())):
        names=[s for s in targets if sector[s]==sect];total=sum(targets[s] for s in names)
        if total>policy['sector_cap']:
            for s in names:targets[s]*=policy['sector_cap']/total
            trace.append({'sector':sect,'reason':'SECTOR_CAP','before':total})
    # Connected high-correlation components; no pairwise double-counting.
    unseen=set(targets)
    while unseen:
        group={min(unseen)};todo=list(group)
        while todo:
            a=todo.pop()
            for b in sorted(unseen-group):
                key='|'.join(sorted([a,b]));value=correlations.get(key)
                if value is None or not finite(value) or not -1<=value<=1:
                    return _result(signals,policy,market,at,mode,current,trace+[{'reason':'CORRELATION_MISSING','pair':key}],'HOLD_ONLY')
                if value>=policy['max_pair_correlation']:group.add(b);todo.append(b)
        unseen-=group;total=sum(targets[s] for s in group)
        if total>policy['correlation_cluster_cap']:
            for s in group:targets[s]*=policy['correlation_cluster_cap']/total
            trace.append({'reason':'CORRELATION_CLUSTER_CAP','names':sorted(group)})
    total=sum(targets.values())
    if total>policy['gross_cap']:
        targets={s:w*policy['gross_cap']/total for s,w in targets.items()};trace.append({'reason':'GROSS_CAP'})
    turnover=sum(abs(targets.get(s,0)-current.get(s,0)) for s in set(current)|set(targets))
    if turnover>policy['max_turnover']+1e-12:return _result(signals,policy,market,at,mode,current,trace+[{'reason':'TURNOVER_BUDGET','turnover':turnover}],'HOLD_ONLY')
    # Missing/rejected evidence cannot silently liquidate an existing position.
    if any(s not in targets and w>0 for s,w in current.items()):return _result(signals,policy,market,at,mode,current,trace+[{'reason':'EXPLICIT_EXIT_POLICY_REQUIRED'}],'HOLD_ONLY')
    return _result(signals,policy,market,at,mode,targets,trace,'TARGETS' if targets else 'ABSTAIN_CASH')


def _result(signals,policy,market,at,mode,weights,trace,status):
    payload={'version':'TASK8_DECISION_V1','policy_hash':digest(policy),'input_hash':digest(signals),'market':market,'currency':policy['account_currencies'][market],'at':at,'mode':mode,'weights':weights,'cash_weight':1-sum(weights.values()),'status':status,'trace':trace,'execution_authority':'SHADOW_ONLY','live_execution_allowed':False}
    payload['decision_hash']=digest(payload);return payload
