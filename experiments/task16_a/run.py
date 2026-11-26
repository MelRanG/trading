"""Compare diagnostic decisions using only sealed case records."""
from collections import Counter
from pathlib import Path
import json

from experiments.task16_a.diagnose import baseline, diagnose, native
from experiments.task16_a.evidence import OUT, ROOT, gather, sha
from quant_harness.investment.review import policy


def save(name, obj):
    with (OUT/name).open('x') as f:
        json.dump(obj,f,indent=2,ensure_ascii=False,allow_nan=False)
        f.write('\n')


def evaluate(cases, cfg, stops):
    rows=[]
    for case in cases:
        native_result=native(case,cfg)
        row={k:case[k] for k in ('case_id','decision_as_of','evaluation_as_of','strategy_version','evidence_refs','evidence_class')}
        left=baseline(case,native_result)
        right=diagnose(case,native_result,stops)
        rows.append({**row,'known_facts':case['facts'],'native_review':native_result,
                     'A':left,'B':right,**right})
    return rows


def score(rows, fixtures, arm):
    totals=Counter()
    differences=[]
    for row, f in zip(rows,fixtures,strict=True):
        assert row['case_id']==f['case_id']
        pred=row[arm]
        actual=[pred['primary_cause'],pred['recommended_action']]
        gold=f['gold']
        hit=actual==gold
        totals.update(dict(cases=1,joint_correct=int(hit),cause_correct=int(actual[0]==gold[0]),
                           action_correct=int(actual[1]==gold[1]),
                           technical_defects=int(f.get('defect',False)),
                           technical_misses=int(f.get('defect',False) and actual[0]!='DATA_ERROR'),
                           false_tech_flags=int(not f.get('defect',False) and actual[0]=='DATA_ERROR'),
                           research_proposals=int(pred['research_required']),
                           unnecessary_proposals=int(pred['research_required'] and gold[1]!='PROPOSE_RESEARCH'),
                           missed_proposals=int(not pred['research_required'] and gold[1]=='PROPOSE_RESEARCH'),
                           stopped_reproposal=int(f['case_id'] in ('I09_STOP','I12_RECENT_STOP') and pred['research_required'])))
        if not hit:
            differences.append({'case':row['case_id'],'actual':actual,'expected':gold})
    return {'counts':dict(totals),'differences':differences}


def main():
    cases, fixtures, stops, refs=gather()
    cfg=policy(ROOT)
    development=evaluate(fixtures['development'],cfg,stops)
    injected=evaluate(fixtures['evaluation'],cfg,stops)
    actual=evaluate(cases,cfg,stops)
    save('source_manifest.json',refs)
    save('case_results.json',{'historical':actual,'injected_evaluation':injected,'development':development})
    results={k:score(injected,fixtures['evaluation'],k) for k in ('A','B')}
    mapping={x['case_id']:x['B'] for x in actual}
    guard={
        'repair_reuse':mapping['A_R2_EXECUTION']['primary_cause']=='DATA_ERROR' and mapping['A_R2_EXECUTION']['recommended_action']=='MAINTAIN',
        'reject_known_flow':mapping['B_FLOW5']['recommended_action']=='REJECT_HYPOTHESIS',
        'uncertain_summer':mapping['C_SUMMER']['primary_cause']=='UNDETERMINED' and not mapping['C_SUMMER']['research_required'],
        'maintain_autumn':mapping['D_AUTUMN']['recommended_action']=='MAINTAIN',
        'block_survivor_claim':mapping['E_UNIVERSE']['recommended_action']=='INSUFFICIENT_EVIDENCE',
        'task10_no_auto_followup':not mapping['F_TASK10']['research_required'],
        'team2_error_separated':mapping['G_TEAM2']['primary_cause']=='DATA_ERROR' and not mapping['G_TEAM2']['research_required'],
        'v2_repair_reused':mapping['H_TASK10_V2']['primary_cause']=='DATA_ERROR' and not mapping['H_TASK10_V2']['research_required'],
    }
    assert all(guard.values())
    assert all(row['research_scope'] and row['approval_required'] and row['falsification_condition']
               for row in injected if row['research_required'])
    save('result.json',{'integration':'MINIMAL_EXTENSION_REQUIRED','diagnosis':'DIAGNOSIS_VALIDATED'
                        if results['B']['counts']['joint_correct']==len(injected) else 'DIAGNOSIS_PARTIAL',
                        'research_policy':'RESEARCH_POLICY_VALIDATED'
                        if not any(results['B']['counts'][k] for k in ('unnecessary_proposals','missed_proposals','stopped_reproposal'))
                        else 'INSUFFICIENT_EVIDENCE',
                        'economics':'ECONOMIC_SELF_IMPROVEMENT_NOT_TESTED',
                        'injected':results,'historical_constraints':guard,
                        'historical_economic_cause_accuracy':'NOT_ESTIMABLE',
                        'current_cases_native_packet_available':sum(r['native_review']['process_status']!='EVIDENCE_MISSING' for r in actual),
                        'LLM_calls':0,'market_requests':0,'backtests':0,'official_registrations':0,
                        'fixture_sha256':sha(Path(__file__).with_name('fixtures.json'))})


if __name__=='__main__':
    main()
