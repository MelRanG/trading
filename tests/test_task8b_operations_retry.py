"""Successful official experiment must not block unrelated daily observation hooks."""
from pathlib import Path
import json,psycopg
from quant_harness.investment.operations_data import Warehouse
from quant_harness.investment import operations
from quant_harness.investment import operations_experiment,operations_backup

def test_successful_factory_receipt_can_be_referenced_by_daily_retry(tmp_path,monkeypatch):
 url='postgresql://quant_task3@127.0.0.1:55432/quant_task3_ops_test'
 with psycopg.connect(url) as conn:conn.execute('DROP SCHEMA public CASCADE');conn.execute('CREATE SCHEMA public')
 (tmp_path/'config').mkdir();root=Path(__file__).resolve().parents[1];(tmp_path/'config/task5_operations.json').write_bytes((root/'config/task5_operations.json').read_bytes())
 warehouse=Warehouse(url,tmp_path);warehouse.point('experiment:pending','TEST_REQUEST',{'worker_hash':'fixture','snapshot':{'input':'frozen'},'contract':{'scope':'fixture'}})
 monkeypatch.setattr(operations,'market_tick',lambda w,client,cfg,market,source,review:{'market':market,'status':'FIXTURE_NO_TRADES','reviews':{}})
 monkeypatch.setattr(operations,'bounded_client',lambda *args:None)
 monkeypatch.setattr(operations_experiment,'worker_hash',lambda root:'fixture')
 receipt={'contract_hash':'fixture','result':{'status':'FORWARD_REQUIRED','input_hash':'frozen'},'factory_result':{'promotion_status':'NOT_ELIGIBLE'}}
 calls=[]
 def experiment(root,w,snapshot,contract):
  calls.append(1);w.store.put('ops_common_experiment',receipt);return receipt
 monkeypatch.setattr(operations_experiment,'execute_common',experiment);monkeypatch.setattr(operations_backup,'due_backup',lambda *args:{'status':'NOT_DUE'})
 result=operations.tick(tmp_path,url,{'US':'unused','KR':'unused'},'unused')
 assert result['experiment']==receipt and len(calls)==1
 assert operations.tick(tmp_path,url,{'US':'unused','KR':'unused'},'unused')['experiment'] is None and len(calls)==1
 # Immutable official experiment content retains its original identity and kind.
 assert warehouse.store.get(__import__('quant_harness.investment.research',fromlist=['digest']).digest(receipt))==receipt
