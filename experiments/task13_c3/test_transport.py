"""Fake transport only: cache/resume/budget/circuit, zero real HTTP."""
import json,hashlib,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as c

def setup(monkeypatch,tmp_path):
 root=tmp_path;b=root/'runtime/task13_c3';b.mkdir(parents=True)
 plan={'HTTP_max':10,'per_response_max_bytes':1000,'total_download_cap_bytes':10000};(b/'plan.json').write_text(json.dumps(plan));(b/'plan.sha256').write_text(c.sha(b/'plan.json'))
 monkeypatch.setattr(c,'R',root);monkeypatch.setattr(c,'B',b);monkeypatch.setattr(c.native,'R',root);monkeypatch.setattr(c.native,'B',b);monkeypatch.setattr(c.native,'P',plan);monkeypatch.setenv('SEC_USER_AGENT','transport-unit-test contact@example.invalid')
 calls=[]
 def fake(url,directory,identity,limit):
  calls.append(url);return b'{"verified":1}',{'source_hash':hashlib.sha256(b'{"verified":1}').hexdigest(),'available_at':'2026-01-01T00:00:00Z'}
 monkeypatch.setattr(c.native,'fetch',fake)
 return b,calls

def test_cache_and_restart_make_one_fake_request(monkeypatch,tmp_path):
 b,calls=setup(monkeypatch,tmp_path);src=c.sources();raw,m=src.get('one','https://unit.invalid/one');assert raw==b'{"verified":1}'
 raw2,m2=c.sources().get('one','https://unit.invalid/one');assert raw2==raw and len(calls)==1
 assert len(list((b/'requests').glob('*.json')))==1

def test_interrupted_reservation_bounded_retry(monkeypatch,tmp_path):
 b,calls=setup(monkeypatch,tmp_path);p=b/'sources/one';p.mkdir(parents=True);(p/'receipt.json').write_text(json.dumps({'status':'RESERVED','url':'https://unit.invalid/one'}));(b/'requests').mkdir();(b/'requests/001.json').write_text(json.dumps({'status':'RESERVED'}))
 raw,m=c.sources().get('one','https://unit.invalid/one');assert raw and len(calls)==1 and (p/'interrupted_receipt.json').exists()
 assert len(list((b/'requests').glob('*.json')))==2
 c.sources().get('one','https://unit.invalid/one');assert len(calls)==1

def test_three_authorization_failures_open_circuit(monkeypatch,tmp_path):
 b,calls=setup(monkeypatch,tmp_path);(b/'requests').mkdir()
 for i in range(3):(b/'requests'/f'{i+1:03}.json').write_text(json.dumps({'status':'FAILED','http_status':403}))
 raw,m=c.sources().get('one','https://unit.invalid/one');assert raw is None and m['status']=='CIRCUIT_OPEN' and not calls

def test_budget_prevents_call(monkeypatch,tmp_path):
 b,calls=setup(monkeypatch,tmp_path);(b/'requests').mkdir()
 for i in range(10):(b/'requests'/f'{i+1:03}.json').write_text(json.dumps({'status':'SAVED'}))
 raw,m=c.sources().get('one','https://unit.invalid/one');assert m['status']=='BUDGET_STOP' and not calls

def test_successful_cache_still_readable_at_budget_exhaustion(monkeypatch,tmp_path):
 b,calls=setup(monkeypatch,tmp_path);raw,m=c.sources().get('one','https://unit.invalid/one')
 for i in range(1,10):(b/'requests'/f'{i+1:03}.json').write_text(json.dumps({'status':'SAVED'}))
 raw2,m2=c.sources().get('one','https://unit.invalid/one');assert raw2==raw and len(calls)==1
