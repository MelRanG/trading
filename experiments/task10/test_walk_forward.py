from pathlib import Path
import sys,json,hashlib
import numpy as np,pandas as pd,pytest
sys.path.insert(0,str(Path(__file__).parent))
from shared import B,R,C,rank_ic,frames,target_scores
from replay_factory import open_store,Queue,Clock,clock_at
import quant_harness.alpha_research_factory as factory
from unittest.mock import patch

def test_no_future_labels_in_weekly_signal_quality():
 dates=pd.bdate_range('2026-01-01',periods=60);fs={};scores={}
 for j in range(10):
  o=pd.Series(100+np.arange(60)*(j+1)/50+np.sin(np.arange(60)+j),index=dates);fs['S'+str(j)]=pd.DataFrame({'open':o,'close':o*1.001});scores['S'+str(j)]=pd.Series(np.cos(np.arange(60)+j),index=dates)
 s=pd.DataFrame(scores);cut=dates[40];a=rank_ic(s,fs,cut);changed={k:f.copy() for k,f in fs.items()}
 for f in changed.values():f.loc[f.index>cut,'open']*=1000
 assert a==rank_ic(s,changed,cut);assert max(r['date'] for r in a)<=str(dates[34].date())

def test_label_and_entry_exit_are_exactly_five_open_intervals():
 from shared import labels
 ds=pd.bdate_range('2026-01-01',periods=12);x=pd.DataFrame({'open':np.arange(1.,13.)},index=ds);y=labels({'A':x});assert y.iloc[0,0]==pytest.approx(7/2-1);assert y.iloc[-6:,0].isna().all()

def test_static_adaptive_prefix_not_rewritten_and_rejection_is_unchanged():
 for m in ['US','KR']:
  folder=B/'accounts'/m;a=pd.read_csv(folder/'STATIC_nav.csv');b=pd.read_csv(folder/'ADAPTIVE_nav.csv');fa=pd.read_csv(folder/'STATIC_fills.csv');fb=pd.read_csv(folder/'ADAPTIVE_fills.csv')
  if m=='US':
   a=a[a.date<'2026-07-16'];b=b[b.date<'2026-07-16'];fa=fa[fa.date<'2026-07-16'];fb=fb[fb.date<'2026-07-16']
  pd.testing.assert_frame_equal(a,b);pd.testing.assert_frame_equal(fa,fb)

def test_native_signals_are_not_renamed_MOM_and_no_ETF_trades():
 for m in ['US','KR']:
  x=json.loads((B/'accounts'/m/'summary.json').read_text());assert x['results']['STATIC']['ledger_error']<1e-5;f=pd.read_csv(B/'accounts'/m/'ADAPTIVE_fills.csv');assert not f.ticker.str.contains('BENCHMARK').any();assert (f.quantity>0).all()
 assert (B/'native/quanta/initial/factor.py').exists();assert json.loads((B/'initial_strategy_seal.json').read_text())['initial_equal_static_adaptive']

def test_training_has_real_batches_and_purged_targets_before_outer():
 for p in (B/'models').glob('*/*/training.json'):
  if 'attempt1' in str(p):continue
  x=json.loads(p.read_text());assert x['train_rows']>=x.get('effective_batch_size',256);assert pd.Timestamp(x['train_target_max'])<pd.Timestamp(x['outer_start']);assert pd.Timestamp(x['early_target_max'])<pd.Timestamp(x['outer_start']);assert np.isfinite(x['loss_history']['train']).all();assert np.isfinite(x['loss_history']['valid']).all();assert hashlib.sha256(p.with_name('model.pth').read_bytes()).hexdigest()==x['checkpoint_hash']
 failed=json.loads((B/'models/initial_attempt1/KR/training.json').read_text());assert np.isnan(failed['loss_history']['train']).all()

def test_candidate_source_values_survive_csv_round_trip():
 q=pd.read_csv(B/'signals/US/quanta_candidate.csv',index_col=0,parse_dates=True);rd=pd.read_csv(B/'predictions/US_2026-07-15/US/predictions.csv',parse_dates=['datetime']).set_index(['datetime','instrument']).iloc[:,0].unstack('instrument');expected=target_scores(q,rd);frozen=pd.read_csv(B/'signals/US/candidate.csv',index_col=0,parse_dates=True,float_precision='round_trip');pd.testing.assert_frame_equal(expected,frozen,check_names=False,check_exact=True)

def test_adoption_causality_and_temporal_cross_market_reuse():
 us=json.loads((B/'experiments/US_2026-07-15/event.json').read_text());kr=json.loads((B/'experiments/KR_2026-07-07/event.json').read_text());assert us['effective_session']>'2026-07-15';assert us['official_status']=='FORWARD_REQUIRED' and us['not_official_Champion_or_Paper_promotion'];assert kr['source_quanta']=='initial_full' and kr['local_status']=='MAINTAIN_PARENT';assert json.loads((B/'causality_adoption_probes.json').read_text())['quanta_mutation_at_adoption']=='PREFIX_MATCH'

def test_factory_real_replay_limits_and_immutable_results():
 out=B/'factory';reservations=[json.loads(x) for x in (out/'experiment_reservations.jsonl').read_text().splitlines()];assert len(reservations)==2;assert len({r['timestamp_utc'][:10] for r in reservations})==2
 before=(out/'diagnostic_registry.jsonl').read_bytes();v=json.loads((B/'first_experiment.json').read_text());old=next(json.loads(x) for x in before.decode().splitlines() if json.loads(x)['attempt_id']==v['attempt']['attempt_id']);changed={**old['result'],'cases':999}
 with pytest.raises(ValueError,match='immutable'):factory.record_review_experiment(R,v['attempt'],changed,directory=out)
 assert (out/'diagnostic_registry.jsonl').read_bytes()==before


def test_daily_budget_cannot_be_reset_by_duplicate_reservation(tmp_path):
 v=json.loads((B/'first_experiment.json').read_text());p=dict(v['proposal']);p['champion']='INJECTED_BUDGET_TEST_PARENT';p['challenger']='INJECTED_1';out=tmp_path/'factory';Clock.value=clock_at('2026-06-01','US')
 with patch.object(factory,'datetime',Clock):
  a=factory.register_review_proposal(R,p,directory=out);r=factory.reserve_review_experiment(R,a,directory=out);assert factory.reserve_review_experiment(R,a,directory=out)==r;p2={**p,'challenger':'INJECTED_2'};a2=factory.register_review_proposal(R,p2,directory=out)
  with pytest.raises(ValueError,match='budget'):factory.reserve_review_experiment(R,a2,directory=out)
 Clock.value=clock_at('2026-06-02','US')
 with patch.object(factory,'datetime',Clock):assert factory.reserve_review_experiment(R,a2,directory=out)['timestamp_utc'][:10]=='2026-06-02'


def test_queue_real_postgres_recovers_lease_and_deduplicates():
 import psycopg
 store=open_store();q=Queue(store);payload={'marker':'TASK10_INJECTED_RECOVERY_ONLY','case':'lease_v1'};job=q.enqueue('TASK10_INJECTED_TEST',payload);assert q.enqueue('TASK10_INJECTED_TEST',payload)==job
 with psycopg.connect(store.url) as conn:state=conn.execute('SELECT status FROM review_job WHERE job_id=%s',(job,)).fetchone()[0]
 if state=='DONE':return
 assert q.claim('dead-worker',lease_seconds=-1,identity=job) is not None
 q2=Queue(open_store());assert q2.claim('restarted-worker',identity=job) is not None
 with pytest.raises(ValueError):q2.finish(job,'wrong-owner','impossible')
 rid=store.put('task10_injected_recovery_test',{'simulation_only':True,'not_economic_self_improvement':True});q2.finish(job,'restarted-worker',rid)
 assert q2.claim('duplicate-worker',identity=job) is None

def test_version_outcomes_do_not_score_pre_adoption_marks():
 from version_outcomes_v2 import version_scoped_labels
 packet={'cutoff':'2026-07-15T17:00:00-04:00','source_decision_id':'X'};ds=pd.bdate_range('2026-07-13',periods=8);a=pd.DataFrame({'date':ds,'nav_krw':np.arange(100.,108.)});labels=version_scoped_labels(packet,a,pd.Series(np.arange(100.,108.),index=ds),'2026-07-22');assert labels['entry_session']=='2026-07-16';assert all(d>'2026-07-15' for d in labels['sessions'])
 corrected=json.loads((B/'review_outcomes_v2/US/2026-07-22.json').read_text());assert corrected['entry_session']=='2026-07-16';assert corrected['result']['status']=='PENDING'
 original=json.loads((B/'reviews/US/2026-07-22.json').read_text());assert original['status'] in ['MAINTAIN','MONITOR','RESEARCH','RISK_ACTION','DATA_ISSUE']


def test_factory_snapshot_and_core_worker_hashes_still_match():
 from common import digest,sha
 for p in (B/'experiments').glob('*/reservation.json'):
  x=json.loads(p.read_text());h=digest({f.name:sha(f) for f in Path(__file__).parent.glob('*.py') if f.name in ['shared.py','measure.py','train_worker.py','native_worker.py']});assert x['worker_hash']==h
 for p in (B/'experiments').glob('*/event.json'):
  x=json.loads(p.read_text());assert sha(R/x['candidate_signal_path'])==x['candidate_signal_hash']
