"""Read task-local evidence only. No policy, provider, DB, or queue calls."""
import ast
import csv
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import subprocess

from experiments.research_references import source

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'runtime/task16_a'
FIXTURES = Path(__file__).with_name('fixtures.json')


def load(path):
    return json.loads(path.read_text())


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


def gather():
    refs={}
    def read(p, json_file=True):
        local=source(ROOT,p)
        refs[p]={'path':str(local.relative_to(ROOT)),'sha256':sha(local)}
        return load(local) if json_file else local

    r2='runtime/task13_f1_r2/result.json'
    r3='runtime/task13_f1_r3/A_constraint_days.csv'
    r4='runtime/task13_f1_r4/result.json'
    r5='runtime/task13_f1_r5/result.json'
    r6='runtime/task13_f1_r6/result.json'
    r6_roster='runtime/task13_f1_r6/entry_cohorts.csv'
    t10='runtime/task10/evaluation/summary.json'
    trigger='runtime/task10/first_trigger.json'
    adoption='runtime/task10/experiments/US_2026-07-15/no_retroactive_rewrite.json'
    v2='runtime/task10/review_outcome_v2_audit.json'
    t2='runtime/task9_2/failure_history.json'
    e2='docs/development/13_E2_team2_increment_and_information.md'
    r4_data=read(r4)
    old=read(r2)
    nav=read(r5)
    pit=read(r6)
    summary=read(t10)
    notice=read(t2)
    t10_v2=read(v2)
    retirement='reports/v102_market_evidence_agent/v102_candidate_promotion.csv'
    raw=subprocess.check_output(['git','show',f'HEAD:{retirement}'],cwd=ROOT)
    refs[retirement]={'path':'git:HEAD:'+retirement,'sha256':sha256(raw).hexdigest()}
    candidates=list(csv.DictReader(raw.decode().splitlines()))
    rejected=[row for row in candidates if 'FLOW_ENTRY_BLOCK_PERSISTENT_5D' in str(row)]
    assert rejected and 'REJECT' in str(rejected).upper(), rejected
    assert r4_data['flow5']=='NO_INCREMENTAL_EVIDENCE'
    stops={'FLOW5_50_50':r4,'V102_FLOW_ENTRY_BLOCK_PERSISTENT_5D':retirement}
    with read(r3,False).open() as f:
        day=next(row for row in csv.DictReader(f) if row['date']=='2024-01-22')
    with read('runtime/task13_f1_r2/T1_A_targets.csv',False).open() as f:
        planned=next(row for row in csv.DictReader(f) if row['date']=='2024-01-22')
    assert json.loads(planned['target_weights_json'])==ast.literal_eval(day['target'])
    period=nav['stress']['windows']
    with read('runtime/task13_f1_r5/nav.csv',False).open() as f:
        daily={row['date']:row for row in csv.DictReader(f)}
    held=daily['2026-06-23']
    summer=period['summer']
    lag=sum(summer['first_crash']<d<=summer['full_cash_dates'][0] for d in daily)
    autumn_prior=max(d for d in daily if d<period['autumn']['full_cash_dates'][0])
    period_b='runtime/task13_f1_r5/independent_verification.json'
    rebound=read(period_b)['window_diagnostics']['summer_trough_to_august_close']
    r6_source=read(r6_roster,False)
    with r6_source.open() as f:
        n_a=sum(row['arm']=='A' for row in csv.DictReader(f))
    assert n_a==pit['arms']['A']['pool_count']
    t10_windows={'task10_rows':summary,'trigger':read(trigger),'activation':read(adoption)}
    read(e2,False)
    selected='runtime/task13_f1_r2/T1_B_targets.csv'
    with read(selected,False).open() as f, read('runtime/task13_f1_r2/T1_A_targets.csv',False).open() as g:
        a,b=list(csv.DictReader(g)),list(csv.DictReader(f))
        assert [r['date'] for r in a]==[r['date'] for r in b]
    picked_days=sum(set(json.loads(x['target_weights_json']))!=set(json.loads(y['target_weights_json'])) for x,y in zip(a,b))
    e5=lambda date,offset: date+'T16:00:00'+offset
    audit=datetime.now(timezone.utc).isoformat()
    raw_cases=[
        ('A_R2_EXECUTION', '2024-01-19', 'R2_T1_A', [r3,r4,'runtime/task13_f1_r2/T1_A_targets.csv'],
         {'actual_names':int(day['names']),'max_names':4,'unfilled_exit_count':len(ast.literal_eval(day['exit_to_zero_unfilled'])),
          'new_buy_count':len(ast.literal_eval(day['new_buy'])),'planned_names':len(ast.literal_eval(day['target'])),
          'targets':ast.literal_eval(day['target']),'repaired_max_names':r4_data['arms']['T1_A']['max_names'],
          'repaired':r4_data['execution']=='EXECUTION_REPAIRED'}),
        ('B_FLOW5',old['starts'],'R4_T1_A_VS_T1_B',[r2,r4,selected,retirement],
         {'hypothesis_id':'FLOW5_50_50','same_policy_delta':r4_data['models_net_difference_pp']['T1']/100,
          'changed_target_days':picked_days,'cost_after_base':r4_data['arms']['T1_A']['total_pct']/100,
          'cost_after_candidate':r4_data['arms']['T1_B']['total_pct']/100}),
        ('C_SUMMER','2026-06-22','R5_MOM63',[r5,period_b,'runtime/task13_f1_r5/nav.csv'],
         {'short_loss':period['summer']['return_pct']['MOM63']/100,
          'market_return':period['summer']['return_pct']['KOSPI']/100,
          'matched_net_delta':(period['summer']['return_pct']['MOM63']-period['summer']['return_pct']['MIX_LAGGED_EXPOSURE'])/100,
          'risk_off_lag_sessions':lag,'starting_positions':json.loads(held['start_positions']),
          'first_full_cash':period['summer']['full_cash_dates'][0],
          'reentry_dates':period['summer']['reentry_dates'],'missed_market_rebound':rebound['KOSPI']/100,
          'season_count':1}),
        ('D_AUTUMN',autumn_prior,'R5_MOM63',[r5,period_b],
         {'first_crash':period['autumn']['first_crash'],'cash_start':period['autumn']['full_cash_dates'][0],
          'short_loss':period['autumn']['return_pct']['MOM63']/100,
          'market_return':period['autumn']['return_pct']['KOSPI']/100,
          'missed_market_rebound':read(period_b)['window_diagnostics']['autumn_trough_to_end']['KODEX200']/100}),
        ('E_UNIVERSE','2023-03-31','R6_FROZEN',[r6,r6_roster,r5],
         {'pit_universe':pit['universe'],'data_gate':pit['data_gate'],'eligible_pool':n_a,
          'sample_overlap':pit['arms']['A']['sample_old_overlap'],'valid_runs':pit['portfolio_runs'],
          'historical_return':pit['legacy_comparator_only']['A_R4']/100,'historical_roster_requests':pit['requests']['total']}),
        ('F_TASK10','2026-05-15','TASK10_STATIC_ADAPTIVE_MOM63',[t10,trigger,adoption,v2],t10_windows),
        ('G_TEAM2','2026-05-15','TASK9_2_NUMERIC_PACKET_V2',[t2,e2],
         {'source_unit_error':notice['prototype_v2']['status']=='REJECTED_PRE_LLM_EPS_UNIT_MAPPING',
          'repaired':not notice['prototype_v2']['used_in_LLM'],'team2_matched_outcome':False,
          'bad_units':notice['prototype_v2']['bad_units']}),
        ('H_TASK10_V2','2026-07-15','TASK10_REVIEW_OUTCOME_V1',[v2,adoption],
         {'version_window_error':'incorrectly retainedaccountstart' in t10_v2['reason'],
          'repaired':t10_v2['historical_correction_not_investment_improvement'],
          'review_rows':len(t10_v2['rows'])}),
    ]
    us='-04:00'
    cases=[dict(case_id=id_,decision_as_of=e5(d,us if id_ in ('F_TASK10','H_TASK10_V2') else '+09:00'),
                evaluation_as_of=audit,strategy_version=version,evidence_refs=[refs[s] for s in sources],
                evidence_class='HISTORICAL_POSTHOC',facts=facts)
           for id_,d,version,sources,facts in raw_cases]
    initial='runtime/task10/process/US/initial.json'
    native=read(initial)
    for case in cases:
        if case['case_id']=='F_TASK10':
            case['decision_packet']=native['packet']
            case['decision_as_of']=native['packet']['cutoff']
            case['evidence_refs'].append(refs[initial])
    contract=load(OUT/'contract.json')
    assert sha(FIXTURES)==contract['fixture_sha256']
    fixtures=load(FIXTURES)
    for phase in ('development','evaluation'):
        for item in fixtures[phase]:
            item.update(decision_as_of='2025-01-02T16:00:00+09:00',evaluation_as_of='2025-06-30T21:00:00+09:00',
                        strategy_version='SYNTHETIC_TEST_V1',evidence_refs=[{'path':str(FIXTURES.relative_to(ROOT)),
                        'sha256':sha(FIXTURES)}],evidence_class='INJECTION_'+phase.upper())
    return cases,fixtures,stops,refs
