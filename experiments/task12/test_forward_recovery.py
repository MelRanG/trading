"""Fault fixtures only; never access operational observations or providers."""
from pathlib import Path
import sys,json
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'task10_1'))
import forward as f

CAL={'result':{'previousBusinessDay':{'regularMarket':{'startTime':'2025-01-02T14:30:00+00:00','endTime':'2025-01-02T21:00:00+00:00'}},'today':{'regularMarket':{'startTime':'2099-01-02T14:30:00+00:00','endTime':'2099-01-02T21:00:00+00:00'}}}}

def test_transient_collection_failure_can_resume_same_attempt(tmp_path,monkeypatch):
 monkeypatch.setattr(f,'F',tmp_path);monkeypatch.setattr(f,'R',tmp_path);monkeypatch.setattr(f,'get',lambda *a:CAL)
 calls=[]
 def interrupted(*a):calls.append(1);raise ConnectionError('SYNTHETIC_NETWORK_INTERRUPTION')
 monkeypatch.setattr(f,'us_catalog',interrupted)
 c={'universe':[]}
 with pytest.raises(ConnectionError):f.market_tick('US',c,None)
 before=(tmp_path/'attempts/US/2025-01-02.json').read_bytes()
 with pytest.raises(ConnectionError):f.market_tick('US',c,None)
 assert len(calls)==2
 assert (tmp_path/'attempts/US/2025-01-02.json').read_bytes()==before

import pandas as pd

def setup_snapshot(root,day='2025-01-03'):
 ds=pd.bdate_range('2024-08-01',day);frames={s:pd.DataFrame({'open':100.,'high':102.,'low':99.,'close':101.,'volume':1000000.},index=ds) for s in ['US001','US_BENCHMARK']}
 c={'arms':{'US':['INITIAL_STATIC']},'capital':{'US':100000},'universe':[{'market':'US','alias':s,'symbol':s} for s in frames]}
 f.save(root/'contract.json',c);folder=root/'observations/US'/day;folder.mkdir(parents=True)
 hashes={}
 for s,df in frames.items():p=folder/(s+'.csv');df.to_csv(p,index_label='date');hashes[s]=f.sha(p)
 sess={'market':'US','day':day,'opening':day+'T14:30:00+00:00','closing':day+'T21:00:00+00:00'}
 f.save(folder/'accepted.json',{'at':f.now(),'session':sess,'data_hashes':hashes})
 p={'market':'US','signal_date':'2025-01-02','sealed_at':'2025-01-02T22:00:00+00:00','next_session':sess,'arms':{'INITIAL_STATIC':{'weights':{'US001':.2},'rebalance':True,'risk_on':True,'scores':{'US001':1.}}}}
 f.save(root/'plans/US/2025-01-02.json',p)
 return c,frames,sess

def test_accepted_snapshot_reused_and_tamper_blocks(tmp_path,monkeypatch):
 monkeypatch.setattr(f,'F',tmp_path);c,frames,sess=setup_snapshot(tmp_path)
 monkeypatch.setattr(f,'get',lambda *args:pytest.fail('accepted snapshot must not fetch again'))
 pd.testing.assert_frame_equal(f._snapshot('US','2025-01-03',sess,c,None)['US001'],frames['US001'],check_names=False,check_freq=False)
 with (tmp_path/'observations/US/2025-01-03/US001.csv').open('a') as fp:fp.write('INVALID\n')
 with pytest.raises(ValueError,match='SNAPSHOT_CHANGED'):f._load_snapshot('US','2025-01-03',c)

def test_compute_crash_resume_keeps_fills_nav_attempt_and_snapshot(tmp_path,monkeypatch):
 monkeypatch.setattr(f,'F',tmp_path);monkeypatch.setattr(f,'R',tmp_path);c,frames,sess=setup_snapshot(tmp_path)
 # Existing execution assumptions are needed, never use the operating account.
 original=Path(__file__).resolve().parents[2]/'config/task3_equity_contract.json';(tmp_path/'config').mkdir();(tmp_path/'config/task3_equity_contract.json').write_bytes(original.read_bytes());(tmp_path/'config/task4_review_contract.json').write_bytes((original.parent/'task4_review_contract.json').read_bytes())
 cal={'result':{'previousBusinessDay':{'regularMarket':{'startTime':sess['opening'],'endTime':sess['closing']}},'today':CAL['result']['today']}}
 monkeypatch.setattr(f,'get',lambda *a:cal);calls=[]
 def computation(*args):
  calls.append(1)
  if len(calls)==1:raise RuntimeError('SYNTHETIC_COMPUTE_EXIT')
  return {'INITIAL_STATIC':pd.DataFrame(1.,index=frames['US001'].index,columns=['US001'])}
 monkeypatch.setattr(f,'compute',computation)
 with pytest.raises(RuntimeError,match='COMPUTE_EXIT'):f.market_tick('US',c,None)
 account=tmp_path/'accounts/US/INITIAL_STATIC/2025-01-03.json';before=account.read_bytes();attempt=(tmp_path/'attempts/US/2025-01-03.json').read_bytes();snapshot=(tmp_path/'observations/US/2025-01-03/accepted.json').read_bytes()
 result=f.market_tick('US',c,None);assert result['status']=='SEALED_PROSPECTIVE_TARGETS'
 assert account.read_bytes()==before and len(json.loads(before)['fills'])==1
 assert (tmp_path/'attempts/US/2025-01-03.json').read_bytes()==attempt
 assert (tmp_path/'observations/US/2025-01-03/accepted.json').read_bytes()==snapshot
 again=f.market_tick('US',c,None);assert again['network_calls']==0 and len(calls)==2

def test_gap_requires_verified_sessions_before_any_receipt(tmp_path,monkeypatch):
 monkeypatch.setattr(f,'F',tmp_path);c,frames,sess=setup_snapshot(tmp_path,'2025-01-07')
 # Jan3/6 bars would be skipped by selecting only the latest Jan7 calendar.
 f.save(tmp_path/'plans/US/earliest.json',{'signal_date':'2025-01-02','sealed_at':'2025-01-02T22:00:00+00:00','next_session':{'day':'2025-01-03','opening':'2025-01-03T14:30:00+00:00','closing':'2025-01-03T21:00:00+00:00'},'arms':{}})
 with pytest.raises(ValueError,match='MISSING_COMPLETED_SESSION'):f._observe_receipts('US','2025-01-07',frames,c,{'2025-01-07':sess})
 assert not list((tmp_path/'session_receipts').rglob('*.json'))
 known={d:{'day':d,'opening':d+'T14:30:00+00:00','closing':d+'T21:00:00+00:00'} for d in ['2025-01-03','2025-01-06','2025-01-07']}
 f._observe_receipts('US','2025-01-07',frames,c,known)
 receipts=sorted((tmp_path/'session_receipts/US').glob('*.json'));assert len(receipts)==3
 assert json.loads(receipts[0].read_text())['late_observation'] is True
 original=receipts[0].read_bytes();f._observe_receipts('US','2025-01-07',frames,c,known);assert receipts[0].read_bytes()==original

def test_technical_patch_does_not_allow_changed_model(monkeypatch):
 c=json.loads((f.F/'contract.json').read_text());actual=f.sources();model=next(k for k in actual if k.endswith('model.pth'));actual[model]='0'*64
 monkeypatch.setattr(f,'sources',lambda:actual)
 with pytest.raises(AssertionError,match='frozen'):f.verify_sources(c)
