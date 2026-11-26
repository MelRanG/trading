from pathlib import Path
import argparse,json,sys,os
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from dotenv import load_dotenv
load_dotenv(ROOT/'runtime/task5/service.env',override=False)
from quant_harness.investment.operations_data import Warehouse
from quant_harness.investment.operations_backup import due_backup
p=argparse.ArgumentParser();p.add_argument('--restore-check',action='store_true');a=p.parse_args()
w=Warehouse(os.environ.get('TASK5_DATABASE_URL','postgresql://quant_task3@127.0.0.1:55432/quant_task3_ops'),ROOT)
with w.store.lock():print(json.dumps(due_backup(w,interval=0 if a.restore_check else 24,restore_check=a.restore_check),indent=2))
