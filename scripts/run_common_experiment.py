"""One preregistered historical paired replay, using archived responses only."""
from pathlib import Path
import json,sys,os
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from dotenv import load_dotenv
load_dotenv(ROOT/'runtime/task5/service.env',override=False)
from quant_harness.investment.operations_data import Warehouse
from quant_harness.investment.operations_experiment import import_us_snapshot,execute_common,worker_hash
from quant_harness.investment.research import digest
snapshot=import_us_snapshot(ROOT)
contract={'team':'quant','adapter':'STOCK_DAILY_FROZEN_V1','snapshot_hash':digest(snapshot),
 'baseline':'EQUAL_WEIGHT_STOCKS','challenger':'MOM63_STOCKS','model_version':'DETERMINISTIC_NO_LLM','prompt_version':'NONE',
 'strategy_version':digest(json.loads((ROOT/'config/task3_equity_contract.json').read_text())),
 'period':'FROZEN_TASK3_ARCHIVE_THROUGH_2026-11-11','metrics':['net return','Sharpe','MDD','turnover','transaction costs'],
 'budget':{'experiments':1,'parameter_search':0},'stop_conditions':['input hash mismatch','code fingerprint change','missing prices','Factory budget'],
 'promotion_conditions':['independent Forward','human approval']}
w=Warehouse(os.environ.get('TASK5_DATABASE_URL','postgresql://quant_task3@127.0.0.1:55432/quant_task3_ops'),ROOT)
w.point('experiment:pending','ops_experiment_request',{'snapshot':snapshot,'contract':contract,'worker_hash':worker_hash(ROOT)})
try:result=execute_common(ROOT,w,snapshot,contract)
except ValueError as exc:
 result={'status':'BLOCKED','reason':str(exc),'input_hash':digest(snapshot),'next_action':'RETRY_SAME_REGISTERED_INPUT_AFTER_FACTORY_BUDGET_RESET'}
w.point('experiment:latest','ops_experiment_status',result)
print(json.dumps(result,indent=2,default=str))
