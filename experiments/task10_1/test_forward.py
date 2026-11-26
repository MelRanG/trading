from pathlib import Path
import sys,json,datetime
import pandas as pd,numpy as np,pytest
sys.path.insert(0,str(Path(__file__).parent))
import forward as f

def frames():
 ds=pd.bdate_range('2026-07-01','2026-11-20');out={}
 for s in ['US001','US002','US_BENCHMARK']:
  out[s]=pd.DataFrame({'open':100.,'high':102.,'low':99.,'close':101.,'volume':1000000.},index=ds)
 return out

def test_same_day_future_open_allowed(tmp_path,monkeypatch):
 monkeypatch.setattr(f,'F',tmp_path);fs=frames();c={'sealed_at':'2026-11-16T05:00:00+00:00','capital':{'US':100000},'arms':{'US':['INITIAL_STATIC']}}
 plan={'next_session':{'day':'2026-11-16','opening':'2026-11-16T14:30:00+00:00'},'sealed_at':c['sealed_at'],'arms':{'INITIAL_STATIC':{'weights':{'US001':.2},'rebalance':True}}}
 f.save(tmp_path/'plans/US/2026-11-13.json',plan)
 a=f.settle('US',{s:x.loc[:'2026-11-13'] for s,x in fs.items()},c);assert a['status']=='PENDING_NEXT_COMPLETED_SESSION'
 b=f.settle('US',{s:x.loc[:'2026-11-16'] for s,x in fs.items()},c);assert b['arms']['INITIAL_STATIC']['metrics']['fills']==1
 before=(tmp_path/'accounts/US/INITIAL_STATIC/2026-11-16.json').read_bytes()
 f.settle('US',{s:x.loc[:'2026-11-17'] for s,x in fs.items()},c);assert (tmp_path/'accounts/US/INITIAL_STATIC/2026-11-16.json').read_bytes()==before

def test_after_open_plan_never_backfills(tmp_path,monkeypatch):
 monkeypatch.setattr(f,'F',tmp_path)
 f.save(tmp_path/'plans/US/2026-11-13.json',{'next_session':{'day':'2026-11-16','opening':'2026-11-16T14:30:00+00:00'},'sealed_at':'2026-11-16T15:00:00+00:00','arms':{}})
 assert f.settle('US',frames(),{'sealed_at':'2026-11-16T15:00:00+00:00','arms':{'US':[]}})['status']=='PENDING_FIRST_SEALED_TARGET'

def test_revision_fail_closed():
 fs=frames()['US001'];new=fs.tail(8).copy();new.iloc[-1,new.columns.get_loc('close')]*=2
 with pytest.raises(ValueError,match='REVISION'):f.validate_revisions(fs,new)

def test_no_risk_signal_means_cash():
 fs=frames();fs['US_BENCHMARK'].iloc[-1,fs['US_BENCHMARK'].columns.get_loc('close')]=10
 scores=pd.DataFrame(1.,index=fs['US001'].index,columns=['US001','US002'])
 assert f.choose(scores,fs,'US')==({},False)

def test_immutable_account_conflict(tmp_path):
 p=tmp_path/'a.json';f.save(p,{'v':1})
 with pytest.raises(ValueError,match='immutable'):f.save(p,{'v':2})

def test_frozen_model_mutation_veto(tmp_path,monkeypatch):
 monkeypatch.setattr(f,'F',tmp_path);monkeypatch.setattr(f,'sources',lambda:{'model':'one'})
 a=f.enroll();assert a['US_candidate_status']=='FORWARD_REQUIRED';assert a['KR_retrain_status']=='REJECTED_NOT_USED'
 monkeypatch.setattr(f,'sources',lambda:{'model':'two'})
 with pytest.raises(AssertionError,match='frozen'):f.enroll()

def test_process_review_is_outcome_blind():
 p={'market':'US','signal_date':'2026-11-13','sealed_at':'2026-11-16T05:00:00+00:00','contract_hash':'a'*64,'source_hash':'b'*64,'arms':{'INITIAL_STATIC':{'weights':{'US001':.2}}}}
 r=f.process_seals(p)['INITIAL_STATIC'];assert r['result']['coverage']['future_returns_seen'] is False
 assert 'nav' not in r['packet']

def test_future_review_waits_for_actual_observations(tmp_path,monkeypatch):
 monkeypatch.setattr(f,'F',tmp_path)
 assert f.review('US',frames(),{'arms':{'US':['INITIAL_STATIC']}})['status']=='PENDING_FIRST_FORWARD_SESSION'

def test_weekly_native_horizon_maturity_uses_saved_receipts(tmp_path,monkeypatch):
 monkeypatch.setattr(f,'F',tmp_path);ds=pd.bdate_range('2025-11-03',periods=70)
 fs={s:pd.DataFrame({'open':100.,'high':101.,'low':99.,'close':100.,'volume':1000000.},index=ds) for s in ['US001','US_BENCHMARK']}
 dates=ds[-10:];p={'market':'US','signal_date':str(ds[-11].date()),'sealed_at':'2025-12-01T00:00:00+00:00','contract_hash':'a'*64,'source_hash':'b'*64,'arms':{'INITIAL_STATIC':{'weights':{},'scores':{'US001':1.}}}}
 p['process']=f.process_seals(p);f.save(tmp_path/'plans/US/a.json',p)
 c={'sealed_at':p['sealed_at'],'arms':{'US':['INITIAL_STATIC']}}
 for d in dates[:5]:
  day=str(d.date());f.save(tmp_path/'accounts/US/INITIAL_STATIC'/(day+'.json'),{'day':day,'nav':{'nav_krw':100000,'holdings_json':'{}'}});f.save(tmp_path/'observations/US'/day/'accepted.json',{'at':day+'T23:00:00+00:00'})
 out=f.review('US',fs,c);assert out['arms']['INITIAL_STATIC']['native_outcome_review']['status']=='PENDING'
 for d in dates[5:]:
  day=str(d.date());f.save(tmp_path/'accounts/US/INITIAL_STATIC'/(day+'.json'),{'day':day,'nav':{'nav_krw':100000,'holdings_json':'{}'}});f.save(tmp_path/'observations/US'/day/'accepted.json',{'at':day+'T23:00:00+00:00'})
 out=f.review('US',fs,c);assert out['arms']['INITIAL_STATIC']['native_outcome_review']['horizons']['5']['status']=='MATURED'

def test_followups_separate_engines_and_deduplicate_without_executor(tmp_path,monkeypatch):
 import queue_followups as q
 records={};jobs={}
 class Store:
  def __init__(self,*args):pass
  def lock(self):
   from contextlib import nullcontext
   return nullcontext()
  def get(self,key):
   if key not in records:raise ValueError('missing')
   return records[key]
  def put(self,kind,payload,key):records[key]=payload
 class Queue:
  def __init__(self,store):pass
  def enqueue(self,kind,payload):
   identity=q.digest({'kind':kind,'payload':payload});jobs[identity]=kind;return identity
 monkeypatch.setattr(q,'Store',Store);monkeypatch.setattr(q,'Queue',Queue)
 folder=tmp_path/'runtime/task10_1/forward';f.save(folder/'contract.json',{'schema':'SYNTHETIC_QUEUE_TEST_ONLY'})
 f.save(folder/'reviews/US/2025-01-01.json',{'market':'US','research_requests':[{'arm':'INITIAL_STATIC','target':'QUANTA_ALONE'},{'arm':'INITIAL_STATIC','target':'RD_RETRAIN_ALONE'}]})
 first=q.submit(tmp_path);again=q.submit(tmp_path);assert first==again
 assert len(jobs)==2 and len(records)==2 and first['experiments_executed']==0
 assert set(jobs.values())=={'TASK101_QUANTA_RESEARCH_REQUEST','TASK101_RD_RETRAIN_REQUEST'}

def test_scheduled_poll_uses_sealed_session_without_network(tmp_path,monkeypatch):
 monkeypatch.setattr(f,'F',tmp_path)
 f.save(tmp_path/'plans/US/a.json',{'signal_date':'2026-11-13','next_session':{'day':'2099-01-01','closing':'2099-01-01T21:00:00+00:00'}})
 class Denied:
  def _request(self,*a,**kw):raise AssertionError('must not call network before known close')
 result=f.market_tick('US',{},Denied());assert result['network_calls']==0 and result['status']=='WAIT_NEXT_COMPLETED_SESSION'

def test_index_reference_keeps_frozen_start_beyond_one_month(tmp_path,monkeypatch):
 import benchmarks as b
 monkeypatch.setattr(b,'R',tmp_path);folder=tmp_path/'runtime/task10_1/forward';f.save(folder/'plans/US/first.json',{'next_session':{'day':'2025-01-02'}})
 f.save(folder/'observations/US/2025-03-03/accepted.json',{'at':'2025-03-03T22:00:00+00:00'})
 f.save(folder/'benchmarks/US/2025-01-03/result.json',{'start_session':'2025-01-02','start_open':99.})
 stamp=int(f.datetime.datetime(2025,3,3,15,tzinfo=f.datetime.timezone.utc).timestamp())
 f.save(folder/'benchmarks/US/2025-03-03/response.json',{'chart':{'result':[{'meta':{'symbol':'^GSPC'},'timestamp':[stamp],'indicators':{'quote':[{'open':[120.],'close':[121.]}]}}]}})
 f.save(folder/'benchmarks/US/2025-03-03/receipt.json',{'scope':'SYNTHETIC_TEST_NOT_FORWARD'})
 result=b.observe()['US'];assert result['start_open']==99. and result['start_session']=='2025-01-02'
 assert result['price_return_pct']==pytest.approx((121/99-1)*100)
