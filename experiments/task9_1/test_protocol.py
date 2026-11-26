from pathlib import Path
import json,sys,importlib.util
import numpy as np,pandas as pd,pytest
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from common import B,R,digest
spec=importlib.util.spec_from_file_location('task91_eval',HERE/'evaluate.py');ev=importlib.util.module_from_spec(spec);spec.loader.exec_module(ev)

def test_equal_exposure_and_cost_accounting():
 dates=pd.date_range('2024-12-02',periods=3);stock=pd.Series([1,1.05,1.1],index=dates);idx=pd.Series([1,1.03,1.05],index=dates)
 a,_=ev.mix({'S':stock},{'S':1},idx,6,6);b,_=ev.mix({'S':stock},{'S':.6},idx,6,6)
 assert abs(a['gross_price_return']-.1)<1e-12;assert abs(b['gross_price_return']-.06)<1e-12
 assert abs(b['selection_gross_residual']-.03)<1e-12;assert b['net_price_return']<.06
 assert a['cash_target']==0 and b['cash_target']==.4

def test_missing_selected_outcome_never_renormalized():
 dates=pd.date_range('2024-12-02',periods=2);p=pd.Series([1,1.2],index=dates)
 with pytest.raises(ValueError,match='MISSING_SELECTED_OUTCOME'):ev.mix({'A':p},{'A':.5,'B':.5},p,6,6)

def test_next_eligible_open_horizon():
 sessions=pd.DatetimeIndex(['2024-11-29','2024-12-02','2025-03-03','2025-06-02'])
 a,z=ev.window(sessions,'2024-11-29',3);assert str(a.date())=='2024-12-02';assert str(z.date())=='2025-03-03'

def test_no_future_price_or_amended_share_pass():
 for date in ['2024-11-29','2025-06-30']:
  for m in ['US','KR']:
   screen=json.loads((B/'screens'/date/(m+'.json')).read_text())
   assert 20<=len(screen['screened'])<=50
   for x in screen['deep']:
    f=pd.read_csv(B/'inputs'/date/x['symbol']/'bars.csv');assert f.date.max()<=date
    if m=='KR':
     assert x['cap_proxy']>=500e9
     if 'dated_share_accessions' in x and x.get('share_basis')!='MANUALLY_VERIFIED_ORIGINAL_COMMON_SHARE_TABLE':assert all(z[:8]<=date.replace('-','') for z in x['dated_share_accessions'])

def test_blinded_review_rejects_future_pnl():
 from quant_harness.investment.review import process_review,policy
 sample=json.loads((B/'blinded_process_reviews.json').read_text())[0]['packet'];sample['analysis']['pnl']=1
 with pytest.raises(ValueError,match='outcome fields forbidden'):process_review(sample,policy(R))

def test_budget_truth_and_no_tool_use():
 seals=json.loads((B/'decision_seals.json').read_text());assert len(seals)==4
 assert sum(x['transport']['measured_tokens'] for x in seals)<=360000
 for x in seals:
  assert x['transport']['status']=='SUCCEEDED';assert x['transport']['model']=='gpt-6.1-terra'
  p=B/'model_calls/research'/(x['transport']['request_hash']+'.trace.jsonl')
  for row in p.read_text().splitlines():
   event=json.loads(row);assert event.get('item',{}).get('type') not in ['command_execution','web_search','mcp_tool_call']

def test_missing_required_daily_mark_blocks_replay(tmp_path,monkeypatch):
 monkeypatch.setattr(ev,'B',tmp_path);f=tmp_path/'evaluator_only/2024-11-29/A';f.mkdir(parents=True)
 (f/'receipt.json').write_text(json.dumps({'status':'SAVED'}))
 frame=pd.DataFrame([{'date':'2024-12-02','open':10,'high':11,'low':9,'close':10,'volume':1},{'date':'2024-12-04','open':11,'high':12,'low':10,'close':11,'volume':1}]);frame.to_csv(f/'bars.csv',index=False);frame.to_csv(f/'yahoo_bars.csv',index=False)
 with pytest.raises(AssertionError,match='MISSING_REQUIRED_PRICE_MARKS'):ev.path_for('2024-11-29','A',pd.Timestamp('2024-12-02'),pd.Timestamp('2024-12-04'),pd.date_range('2024-12-02',periods=3))

def test_inclusive_pagination_accepts_equal_overlap_blocks_revision():
 from normalize_outcomes import merge_pages
 a=pd.DataFrame([{'date':'2025-02-20','open':40800.,'high':41000.,'low':39000.,'close':39250.,'volume':100}]);b=a.copy()
 result,overlap=merge_pages([a,b]);assert len(result)==1 and overlap==1
 b.loc[0,'close']=39300.
 with pytest.raises(ValueError,match='CONFLICTING_PAGE_REVISION'):merge_pages([a,b])

def test_corroboration_never_averages_and_blocks_unverified_field():
 spec=importlib.util.spec_from_file_location('verified_eval',HERE/'evaluate_v3.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 ds=pd.DatetimeIndex(['2025-09-19']);n=pd.DataFrame({'open':[39650.],'high':[41850.],'low':[39100.],'close':[40950.]},index=ds);y=n.copy();t=n.copy();t.loc[ds[0],'open']=39250.
 proof=m.corroborated(n,y,t,ds);assert proof[0]['providers']==['YAHOO'];assert n.loc[ds[0],'open']==39650.
 y.loc[ds[0],'open']=39250.
 with pytest.raises(ValueError,match='UNCORROBORATED_RAW_FIELD'):m.corroborated(n,y,t,ds)

def test_isolated_factory_preserves_minimum_cases_and_budget(tmp_path):
 from quant_harness.alpha_research_factory import register_review_proposal,reserve_review_experiment,record_review_experiment
 handoff=json.loads((B/'factory_handoff.json').read_text());proposal=handoff['proposal'];directory=tmp_path/'factory_contract_test'
 attempt=register_review_proposal(R,proposal,directory=directory);assert register_review_proposal(R,proposal,directory=directory)==attempt
 reserve_review_experiment(R,attempt,directory=directory)
 result={'input_hash':proposal['input_hash'],'worker_hash':proposal['worker_hash'],'status':'INSUFFICIENT_EVIDENCE','cases':4,'reason':'Four market-date cases below unchanged minimum12. This is contract isolation test, not operating experiment.'}
 r=record_review_experiment(R,attempt,result,directory=directory);assert r['promotion_status']=='NOT_ELIGIBLE'
 assert record_review_experiment(R,attempt,result,directory=directory)==r
 other={**proposal,'challenger':proposal['challenger']+'_TEST_ONLY'};second=register_review_proposal(R,other,directory=directory)
 with pytest.raises(ValueError,match='budget exhausted'):reserve_review_experiment(R,second,directory=directory)

def test_total_model_budget_including_scope_correction():
 rows=[json.loads(p.read_text()) for p in (B/'model_calls').glob('*/*.reserved.json')]
 assert len(rows)==5;assert all(r['status']=='SUCCEEDED' for r in rows);assert sum(r['measured_tokens'] for r in rows)<=360000

def test_enriched_evidence_spans_are_exact_dated_originals():
 for p in (B/'enriched_packets').glob('*/*.json'):
  x=json.loads(p.read_text());source=R/x['original_text_path'];text=source.read_text()
  from common import sha
  assert sha(source)==x['original_text_sha256']
  meta=json.loads((R/x['source_record']).read_text());assert meta['published'].replace('-','')[:8]<=x['date'].replace('-','')
  for span in x['spans']:assert text[span['start']:span['end']]==span['exact_text']
