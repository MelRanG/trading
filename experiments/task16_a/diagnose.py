"""Retrospective research overlay on the existing decision-time Review."""
from datetime import date, timedelta
from math import isclose

from quant_harness.investment.discovery import instant
from quant_harness.investment.research import digest
from quant_harness.investment.review import process_review, score_mature_outcome


def native(case, cfg):
    facts=case['facts']
    # Only decision-time fields can cross the original Review boundary.
    # An absent authentic packet stays absent. No forensic evidence is fabricated.
    packet=case.get('decision_packet')
    if case['evidence_class'].startswith('INJECTION'):
        strategy='TASK16_INJECTION'
        cfg={**cfg,'strategy_horizons':{**cfg['strategy_horizons'],strategy:facts.get('horizons',[5])}}
        packet={'source_decision_id':case['case_id'],
                'cutoff':case['decision_as_of'],'market':'KR','strategy_id':strategy,
                'registered_policy':{'gross_cap':.8,'single_name_cap':.2},
                'weights':{},'eligible':True,'intents':[],'analysis':{'missing':[]},
                'source_receipts':[],'evidence':[],'company_candidates':[]}
        for key in cfg['required_trace_fields']:
            packet[key]=digest({'synthetic':True,'key':key,'identity':case['case_id']})
    if packet is None:
        return {'process_status':'EVIDENCE_MISSING','outcome_status':'UNAVAILABLE_FOR_NATIVE_REVIEW',
                'reason':'Case-dependent historical inputs are not an authentic serialized process/outcome packet.'}
    process=process_review(packet,cfg)
    labels=case.get('labels')
    if case['evidence_class'].startswith('INJECTION') and 'elapsed_sessions' in facts:
        entry=date(2025,1,3)
        days=[(entry+timedelta(days=i)).isoformat() for i in range(5+facts['elapsed_sessions'])
              if (entry+timedelta(days=i)).weekday()<5][:facts['elapsed_sessions']+1]
        nav=dict.fromkeys(days,100.0)
        nav[days[-1]]=100*(1+facts.get('short_loss',0.0))
        labels={'decision_id':case['case_id'],'calendar_verified':True,'available_at':case['evaluation_as_of'],
                'source_hash':digest(nav),'sessions':days,'entry_session':days[0],'nav':nav,
                'observed_at_by_session':{d:d+'T16:00:00+09:00' for d in days},'evidence_class':'SYNTHETIC_ONLY'}
    outcome=score_mature_outcome(process,packet,cfg,labels)
    return {'process_status':process['classification'],'findings':process['findings'],
            'outcome_status':outcome['status'],'outcome':outcome}


def baseline(case, review):
    findings={f['issue'] for f in review.get('findings',[])}
    if findings & {'RISK_POLICY_VIOLATION','INELIGIBLE_INTENT','REQUIRED_INPUT_MISSING'}:
        return decision('DATA_ERROR','REPAIR_DATA_OR_EXECUTION',1.0)
    if review['process_status']=='EVIDENCE_MISSING':
        return decision('UNDETERMINED','INSUFFICIENT_EVIDENCE',0)
    if 'horizons' in case['facts'] and review['outcome_status']=='PENDING':
        return decision('UNDETERMINED','INSUFFICIENT_EVIDENCE',0)
    if review['outcome_status']=='MATURED':
        return decision('UNDETERMINED','MONITOR',0)
    return decision('UNDETERMINED','MAINTAIN',0)


def decision(cause, action, confidence, unresolved=None, secondary=None,
             counterfactual='UNAVAILABLE', scope=None, falsification=None, evidence=None):
    return dict(primary_cause=cause,secondary_causes=secondary or [],confidence=confidence,
                unresolved_questions=unresolved or [],counterfactual_status=counterfactual,
                recommended_action=action,falsification_condition=falsification,
                research_required=action=='PROPOSE_RESEARCH',research_scope=scope,
                approval_required=action in ('PROPOSE_RESEARCH','REPAIR_DATA_OR_EXECUTION'),
                diagnosis_evidence=evidence or [])


def drafted(cause, phenomenon, facts):
    cost=cause=='EXECUTION_COST'
    return decision(cause,'PROPOSE_RESEARCH',.85,
        unresolved=['독립 비용 후 우위 미확인'],counterfactual='MATCHED_HISTORICAL_OR_SYNTHETIC_ONLY',
        scope={'problem':phenomenon,'hypothesis_family':'EXECUTION_CAPACITY' if cost else 'MATURE_SIGNAL_MONITOR',
               'dedup':'Exact known rejected IDs checked. Semantic Factory dedup is required before any authorization.',
               'one_decision_change':'rebalance execution timing' if cost else 'frozen signal inclusion',
               'data':'Separate dated sessions, cost and exposure matched; cutoffs and maturity fixed',
               'budget':'One pre-registered existing-tool comparison. Zero approval, reservations, or executions in Task16-A.',
               'independent_validation':facts['independent_validation_available']},
        falsification='No net improvement at the same exposure and operational constraints on independently timed windows.',
        evidence=['paired scope and repeated mature windows'])


def diagnose(case, review, stopped):
    f=case['facts']
    cutoff=instant(case['decision_as_of'])
    evaluated=instant(case['evaluation_as_of'])
    if evaluated<cutoff:
        raise ValueError('evaluation before decision cutoff')
    times=f.get('input_times',[])
    used=[instant(x['available_at']) for x in times if x['used']]
    if any(t>evaluated for t in used):
        return decision('UNDETERMINED','INSUFFICIENT_EVIDENCE',0,['결과 기준시각 뒤 근거 격리'])
    bad=[]
    if any(t>cutoff for t in used):
        bad.append('post-cutoff input used by original decision')
    if 'provider_amount' in f and not isclose(f['normalized_amount'],f['provider_amount']*f['certified_unit_factor']):
        bad.append('certified unit mismatch')
    if f.get('sell_ordered',0)>0 and f.get('sell_filled')==0 and (
            f['holdings_before']!=f['holdings_after'] or f['cash_before']!=f['cash_after']):
        bad.append('zero fill but cash or holdings mutated')
    breach=f.get('actual_names',0)>f.get('max_names',float('inf')) and f.get('unfilled_exit_count',0)>0 and f.get('new_buy_count',0)>0
    if breach:
        bad.append('held names exceed limit after unmatched sells and new buys')
    if f.get('source_unit_error') or f.get('version_window_error'):
        bad.append('recorded unit or version-boundary defect')
    if bad:
        return decision('DATA_ERROR','MAINTAIN' if f.get('repaired') else 'REPAIR_DATA_OR_EXECUTION',1.0,
                        ['기존 수정 회귀·증거 유지'] if f.get('repaired') else ['별도 회귀로 원래 상태 대사'],
                        ['EXECUTION_COST'] if breach else None,counterfactual='TECHNICAL_ACCOUNTING_ONLY',
                        falsification='Reconcile independently against source units, decision cutoff and actual fills.',
                        evidence=bad)
    if f.get('hypothesis_id') in stopped:
        return decision('SELECTION_SIZING','REJECT_HYPOTHESIS',.9,
                        ['동일 사양의 관측 결과만 유지'],counterfactual='EXISTING_FIXED_COMPARISON',
                        falsification='Different predeclared mechanism plus independent evidence is needed to reconsider.',
                        evidence=[stopped[f['hypothesis_id']]])
    if f.get('data_gate')=='DATA_INSUFFICIENT' and f.get('valid_runs')==0:
        return decision('DATA_ERROR','INSUFFICIENT_EVIDENCE',1.0,
                        ['PIT 편입·상폐 가격 및 정산·공통 마스크 결손. 편향의 수익률 크기 미확인'],
                        falsification='Restore the existing frozen cohort to the price, identity and settlement gates.',
                        evidence=['frozen cohort data gate blocked before portfolio evaluation'])
    if 'season_count' in f and f.get('risk_off_lag_sessions',0)>0:
        return decision('UNDETERMINED','MONITOR',.55,
                        ['동일 조건에서 종목 선정과 위험 게이트 효과를 분리한 반사실 없음'],
                        ['REGIME_MISMATCH','SELECTION_SIZING'],counterfactual='EXPOSURE_MATCHED_DIAGNOSTIC_ONLY',
                        falsification='Test one predeclared decision-time risk rule across other periods, including false exits and re-entry costs.',
                        evidence=['observed exit lag, adverse exposure-matched path and missed rebound'])
    if 'cash_start' in f and f['cash_start']<f['first_crash']:
        return decision('UNDETERMINED','MAINTAIN',.65,['현금화의 독립 효과·반등 기회비용의 재현성'],
                        ['REGIME_MISMATCH'],counterfactual='EXPOSURE_MATCHED_DIAGNOSTIC_ONLY',
                        falsification='Compare both draws and rebounds on an independent fixed policy window.',
                        evidence=['observed cash before first shock and subsequent missed rebound'])
    if 'task10_rows' in f:
        return decision('UNDETERMINED','MONITOR',.6,
                        ['미국 STATIC 대비 개선과 시장 초과의 구분. 한국 현금 비중과 종목 선택 기여 미분리'],
                        counterfactual='MATCHED_DIAGNOSTICS_DIFFERENT_MARKETS',
                        falsification='Reproduce net relative gain after matching exposure and costs on new data.',
                        evidence=['paired arm comparisons within each market only'])
    if 'horizons' in f and review['outcome_status']=='PENDING':
        return decision('UNDETERMINED','INSUFFICIENT_EVIDENCE',0,['계약된 라벨 미성숙'])
    ready=f.get('independent_validation_available') and f.get('equal_policy_and_exposure') and f.get('mature_windows',0)>=2
    if ready and f.get('cost_repeats',0)>=2 and isclose(f['gross_before'],f['gross_after']) and (
            f['cost_after']>f['cost_before'] and f['net_after']<f['net_before']):
        return drafted('EXECUTION_COST','Matched gross stable while execution charges eroded net.',f)
    if ready and f.get('ic_before',0)>f.get('benchmark_ic',0)>f.get('ic_after',0):
        return drafted('ALPHA_DECAY','Repeated deterioration of mature IC under matched scope.',f)
    if f.get('model_frozen') and f.get('model_error_after',0)>f.get('model_error_before',0):
        return decision('UNDETERMINED','MONITOR',.55,['입력 분포와 기준 모형 대비 drift 및 비용 후 증분 미확인'],
                        ['MODEL_DRIFT'],evidence=['paired error changed without net improvement'])
    if f.get('mature_windows',0)>=2 and f.get('within_risk_contract'):
        return decision('NORMAL_VARIANCE','MAINTAIN',.6,['정상 변동과 구별할 증거 미확인'])
    return decision('UNDETERMINED','MONITOR',0,['원인 확정에 필요한 성숙·반사실 증거 부족'])
