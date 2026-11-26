from pathlib import Path
from datetime import datetime,timezone,timedelta
from copy import deepcopy
import json
import os
import psycopg
import pytest
from quant_harness.investment.research import digest
from quant_harness.investment.review import policy,process_review,score_mature_outcome,proposal_context,Source
from quant_harness.investment.review_engine import sealed_review,experiment_bundle,propose,run_isolated,enqueue_event,run_event_job
from quant_harness.investment.review_jobs import Queue
from quant_harness.investment.review_access import ProposalView
from quant_harness.investment.review_shadow import packet_for_shadow,compare_shadow_reply
from quant_harness.investment.store import Store
from quant_harness.alpha_research_factory import register_review_proposal,reserve_review_experiment,record_review_experiment,find_review_hypothesis

ROOT=Path(__file__).resolve().parents[1]
URL=os.getenv('TASK4_TEST_DATABASE_URL')


def packet():
    frozen=json.loads((ROOT/'config/task3_equity_contract.json').read_text())
    return {'source_decision_id':'D-FIXTURE','cutoff':'2020-01-02T14:00:00+00:00','market':'US','strategy_id':'MOM63_STOCKS',
        'currency':'USD','contract_hash':digest(frozen),'input_hash':'frozen-input','algorithm_hash':'frozen-code',
        'eligible':True,'weights':{'AAPL':0.19},'prior_marks':{'AAPL':100},'intents':[{'symbol':'AAPL','delta_quantity':'10'}],
        'analysis':{'status':'CANDIDATES','missing':[]},'evidence':[],'company_candidates':[],
        'registered_policy':frozen,'numeric_forecasts':[],'counterfactuals':[]}


def labels(p):
    return {'decision_id':p['source_decision_id'],'calendar_verified':True,'source_hash':'SYNTHETIC_LABEL_FIXTURE','evidence_class':'SYNTHETIC',
        'available_at':'2020-01-07T22:00:00+00:00','entry_session':'2020-01-02','sessions':['2020-01-02','2020-01-03','2020-01-06'],
        'nav':{'2020-01-02':100,'2020-01-03':90,'2020-01-06':95},'benchmark':{'2020-01-02':100,'2020-01-03':92,'2020-01-06':96},
        'observed_at_by_session':{'2020-01-02':'2020-01-02T21:00:00+00:00','2020-01-03':'2020-01-03T21:00:00+00:00','2020-01-06':'2020-01-06T21:00:00+00:00'}}


def test_process_blind_to_future_fields_and_no_pnl_error():
    p=packet();cfg=policy(ROOT);r=process_review(p,cfg)
    assert r['classification']=='NO_CHANGE' and r['loss_classification']=='PENDING_OUTCOME'
    for key in ('nav','holdout_results','actual_return','fill_price'):
        contaminated=deepcopy(p);contaminated[key]=123
        with pytest.raises(ValueError,match='forbidden'):process_review(contaminated,cfg)
    assert 'metrics' not in proposal_context(r)


def test_maturity_pending_and_normal_loss_is_not_causal_error():
    p=packet();cfg=policy(ROOT);r=process_review(p,cfg)
    assert score_mature_outcome(r,p,cfg)['status']=='PENDING'
    evaluated=score_mature_outcome(r,p,cfg,labels(p))
    first=evaluated['horizons']['1']
    assert first['return']==pytest.approx(-0.1)
    assert first['excess_market']==pytest.approx(-0.02)
    assert first['classification']=='STOCHASTIC_LOSS' and first['confidence']<0.5 and not first['causality_proven']
    assert evaluated['horizons']['5']['status']=='PENDING'


def test_profit_does_not_whitewash_process_violation():
    p=packet();p['weights']={'AAPL':1};cfg=policy(ROOT);r=process_review(p,cfg)
    assert any(f['category']=='SIZING' for f in r['findings'])
    l=labels(p);l['nav']['2020-01-03']=120
    assert score_mature_outcome(r,p,cfg,l)['horizons']['1']['classification']=='UNDETERMINED'
    assert r['classification']=='RESEARCH_NEEDED'


@pytest.mark.parametrize('field,value',[('source_hash',''),('calendar_verified',False),('decision_id','OTHER'),('available_at','2099-01-01T00:00:00+00:00')])
def test_unverified_or_future_labels_fail_closed(field,value):
    p=packet();cfg=policy(ROOT);l=labels(p);l[field]=value
    with pytest.raises(ValueError):score_mature_outcome(process_review(p,cfg),p,cfg,l)


def test_policy_and_packet_immutable_and_no_hindsight_best_action():
    p=packet();p['counterfactuals']=[{'id':'PREREGISTERED_CASH'}];cfg=policy(ROOT);r=process_review(p,cfg)
    l=labels(p);l['counterfactuals']={'HINDSIGHT_BEST':{'return':10},'PREREGISTERED_CASH':{'return':0}}
    result=score_mature_outcome(r,p,cfg,l)['horizons']['1']
    assert [s['id'] for s in result['counterfactual_scores']]==['PREREGISTERED_CASH']
    bad=deepcopy(p);bad['weights']={}
    with pytest.raises(ValueError,match='mismatch'):score_mature_outcome(r,bad,cfg,l)


def test_forecast_scoring_registered_only():
    p=packet();p['numeric_forecasts']=[{'forecast_id':'EPS','point':2,'horizon_end':'2020-01-03'},
      {'forecast_id':'EVENT','probability':0.8,'horizon_end':'2020-01-03'}]
    cfg=policy(ROOT);l=labels(p);l['forecast_actuals']={'EPS':1.5,'EVENT':1,'UNREGISTERED':900}
    result=score_mature_outcome(process_review(p,cfg),p,cfg,l)['horizons']['1']['forecast_scores']
    assert result[0]['absolute_error']==0.5 and result[1]['brier']==pytest.approx(0.04)
    assert len(result)==2


@pytest.fixture
def store():
    if not URL:pytest.skip('TASK4_TEST_DATABASE_URL required')
    if not URL.endswith('/quant_task3_review_test'):raise ValueError('dedicated review test DB only')
    s=Store(URL,'TASK4_REVIEW_ONLY');Queue(s)
    with psycopg.connect(URL) as c:c.execute('TRUNCATE review_job,investment_run,investment_record CASCADE')
    return s


def test_seal_restart_dedup_and_holdout_view(store):
    p=packet();cfg=policy(ROOT)
    one,review=sealed_review(store,p,cfg);two,again=sealed_review(Store(URL,'TASK4_REVIEW_ONLY'),p,cfg)
    assert one==two and review==again
    result=store.put('review_outcome',{'holdout_results':{'return':999}})
    view=ProposalView(store)
    assert view.process_context(one)['decision_id']==p['source_decision_id']
    with pytest.raises(PermissionError):view.process_context(result)
    with pytest.raises(PermissionError):view.final_results(result)


def test_queue_crash_lease_reclaim_ownership_and_dedup(store):
    q=Queue(store);identity=q.enqueue('PROCESS_REVIEW',{'packet':'one'})
    assert q.enqueue('PROCESS_REVIEW',{'packet':'one'})==identity
    assert q.claim('first',identity=identity)
    assert q.claim('second',identity=identity) is None
    with psycopg.connect(URL) as c:c.execute("UPDATE review_job SET lease_until=now()-interval '1 second' WHERE job_id=%s",(identity,))
    assert q.claim('second',identity=identity)
    result=store.put('test-result',{'done':True})
    with pytest.raises(ValueError):q.finish(identity,'first',result)
    q.finish(identity,'second',result)
    assert q.claim('third',identity=identity) is None


def test_immediate_events_and_shadow_permissions(store):
    event={'kind':'THESIS_INVALIDATION_EVENT','available_at':'2020-01-02T00:00:00+00:00','source_hash':'SYNTHETIC_EVENT'}
    assert enqueue_event(store,'D',event)==enqueue_event(store,'D',event)
    with pytest.raises(ValueError):enqueue_event(store,'D',{**event,'holdout_results':{'pnl':10}})
    p=packet();r=process_review(p,policy(ROOT));shadow=packet_for_shadow(r)
    assert compare_shadow_reply(shadow,{'input_hash':shadow['input_hash'],'reference_ids':[p['source_decision_id']]})['status']=='SHADOW_ONLY'
    with pytest.raises(ValueError):compare_shadow_reply(shadow,{'input_hash':shadow['input_hash'],'orders':[{}]})
    with pytest.raises(ValueError):compare_shadow_reply(shadow,{'input_hash':shadow['input_hash'],'reference_ids':['FUTURE_VERSION']})


def proposal_fixture():
    p=packet();p['algorithm_hash']=None;cfg=policy(ROOT)
    bundle=experiment_bundle([p,packet()],cfg)
    return propose(process_review(p,cfg),bundle)['proposal'],bundle


def test_official_factory_reserve_metrics_duplicate_and_budget(tmp_path):
    plan,bundle=proposal_fixture();out=tmp_path/'factory'
    attempt=register_review_proposal(ROOT,plan,directory=out)
    assert register_review_proposal(ROOT,plan,directory=out)==attempt
    result=run_isolated(bundle)
    assert result['cases']==2 and result['metrics']['champion_accuracy']==0.5 and result['metrics']['challenger_accuracy']==1
    assert result['status']=='INSUFFICIENT_EVIDENCE'
    with pytest.raises(ValueError,match='reserved'):record_review_experiment(ROOT,attempt,result,directory=out)
    reserve_review_experiment(ROOT,attempt,directory=out)
    first=record_review_experiment(ROOT,attempt,result,directory=out)
    assert record_review_experiment(ROOT,attempt,result,directory=out)==first
    changed=deepcopy(plan);changed['input_hash']='OTHER-DATA'
    with pytest.raises(ValueError,match='family'):register_review_proposal(ROOT,changed,directory=out)
    assert find_review_hypothesis(ROOT,changed,directory=out)['attempt_id']==attempt['attempt_id']
    changed['challenger']='DIFFERENT_HYPOTHESIS'
    other=register_review_proposal(ROOT,changed,directory=out)
    with pytest.raises(ValueError,match='before execution'):reserve_review_experiment(ROOT,other,directory=out)


def test_factory_cannot_weaken_samples_or_approve(tmp_path):
    plan,bundle=proposal_fixture();out=tmp_path/'f'
    bad=deepcopy(plan);bad['minimum_cases']=1
    with pytest.raises(ValueError,match='weakened'):register_review_proposal(ROOT,bad,directory=out)
    a=register_review_proposal(ROOT,plan,directory=out);reserve_review_experiment(ROOT,a,directory=out)
    result=run_isolated(bundle);result['status']='APPROVED'
    with pytest.raises(ValueError):record_review_experiment(ROOT,a,result,directory=out)
    result['status']='FORWARD_REQUIRED'
    with pytest.raises(ValueError,match='sample'):record_review_experiment(ROOT,a,result,directory=out)


def test_actual_task3_read_only_and_blind_packet():
    url=os.getenv('TASK4_SOURCE_KR_URL')
    if not url:pytest.skip('actual Task3 read-only source URL required')
    source=Source(url);identity='4389b05872e93e4097ab69f10896f4e83e8c88bc72495bc639a2de96a4b990ac'
    p=source.process_packet(ROOT,identity)
    assert p['algorithm_hash'] is None and p['source_decision_id']==identity
    assert not {'nav','pnl','stock_fill','stock_nav'} & p.keys()
    assert process_review(p,policy(ROOT))['coverage']['future_returns_seen'] is False
    with source.connect() as c:
        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):c.execute('CREATE TABLE task4_must_never_write_source (id integer)')


def test_future_calendar_is_pending_not_future_outcome():
    p=packet();cfg=policy(ROOT);l=labels(p)
    l['sessions']=['2020-01-02','2099-01-02']
    l['nav']['2099-01-02']=999999
    result=score_mature_outcome(process_review(p,cfg),p,cfg,l)
    assert result['horizons']['1']['status']=='PENDING'


def test_queue_crash_retry_limit_is_terminal(store):
    q=Queue(store);key=q.enqueue('PROCESS_REVIEW',{'fixture':True})
    for n in range(3):
        assert q.claim(str(n),identity=key)
        with psycopg.connect(URL) as c:c.execute("UPDATE review_job SET lease_until=now()-interval '1 second' WHERE job_id=%s",(key,))
    assert q.claim('fourth',identity=key) is None
    with psycopg.connect(URL) as c:assert c.execute('SELECT status FROM review_job WHERE job_id=%s',(key,)).fetchone()[0]=='FAILED'


def test_factory_tamper_and_metric_replay_fail_closed(tmp_path):
    plan,bundle=proposal_fixture();out=tmp_path/'factory';a=register_review_proposal(ROOT,plan,directory=out)
    reserve_review_experiment(ROOT,a,directory=out);result=run_isolated(bundle)
    changed=dict(result,input_hash='CHANGED')
    with pytest.raises(ValueError,match='provenance'):record_review_experiment(ROOT,a,changed,directory=out)
    path=out/'contracts'/(a['proposal_id']+'.json')
    contract=json.loads(path.read_text());contract['proposal']['minimum_cases']=0;path.write_text(json.dumps(contract))
    with pytest.raises(ValueError,match='integrity'):record_review_experiment(ROOT,a,result,directory=out)


def test_source_event_registers_once_without_fake_experiment(store,tmp_path):
    event={'kind':'UNVERIFIED_SOURCE','available_at':'2020-01-02T00:00:00+00:00','source_hash':'SYNTHETIC_EVENT','reason':'fixture source unavailable'}
    key=enqueue_event(store,'FIXTURE',event)
    result=run_event_job(ROOT,store,key,factory_directory=tmp_path/'factory')
    assert result['status']=='PENDING_EVIDENCE' and not result['experiment_executed']
    assert run_event_job(ROOT,store,key,factory_directory=tmp_path/'factory')['status']=='ALREADY_CLAIMED_OR_COMPLETE'
    assert not (tmp_path/'factory'/'diagnostic_registry.jsonl').exists()


def test_registered_result_cache_survives_new_worker(tmp_path,monkeypatch):
    from quant_harness.investment import review_engine as engine
    plan,bundle=proposal_fixture();out=tmp_path/'factory';a=register_review_proposal(ROOT,plan,directory=out)
    original=engine.run_isolated;calls=[]
    def counted(bundle):calls.append(1);return original(bundle)
    monkeypatch.setattr(engine,'run_isolated',counted)
    first=engine.registered_experiment(ROOT,a,bundle,directory=out)
    second=engine.registered_experiment(ROOT,a,bundle,directory=out)
    assert first==second and len(calls)==1


def test_complete_source_db_cannot_be_used_as_review_db():
    from quant_harness.investment.review_engine import run_cycle
    with pytest.raises(ValueError,match='distinct'):
        run_cycle(ROOT,'postgresql://u@localhost:55432/quant_task3_us','postgresql://u@127.0.0.1:55432/quant_task3_us','D')


def test_multiple_causes_remain_separate_from_winning_result():
    p=packet();p['eligible']=False;p['weights']={'AAPL':0.99}
    r=process_review(p,policy(ROOT))
    assert {'SIZING','EXECUTION'}<={f['category'] for f in r['findings']}
    assert all(f['impact_on_return']=='UNDETERMINED' for f in r['findings'])


def test_execution_arithmetic_not_return_causality():
    from quant_harness.investment.review_execution import audit_execution
    class Fixture:
        def current_outcome_availability(self,identity):
            return {'fills':[{'symbol':'AAPL','quantity':'10','price':'101','fee':'2','side':'BUY','event_hash':'fixture','created_at':'2020-01-02T15:00:03+00:00'}]}
        def record(self,identity,kind):
            return {'decision_id':'D','events':[{'symbol':'AAPL','price':'100','event_at':'2020-01-02T15:00:00+00:00'}]}
    r=audit_execution(Fixture(),'D')
    assert r['total_execution_cost']==12 and r['fills'][0]['quote_to_commit_seconds']==3
    assert not r['investment_error_inferred']


def test_crash_rebound_not_hindsight_timing_error():
    p=packet();cfg=policy(ROOT);cfg['strategy_horizons']['MOM63_STOCKS']=[1,2]
    l=labels(p);l['nav']={'2020-01-02':100,'2020-01-03':70,'2020-01-06':95}
    l['benchmark']={'2020-01-02':100,'2020-01-03':72,'2020-01-06':96}
    r=process_review(p,cfg);result=score_mature_outcome(r,p,cfg,l)
    assert result['horizons']['1']['mdd']==pytest.approx(-0.3)
    assert result['horizons']['2']['return']==pytest.approx(-0.05)
    assert result['horizons']['2']['mdd']==pytest.approx(-0.3)
    assert result['horizons']['2']['risk_adjusted_metric']['observations']==2
    assert not any(f['category']=='TIMING' for f in r['findings'])
