"""Resume only disposable restored DBs; no API requests or broker mutations."""
from pathlib import Path
import argparse,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from quant_harness.investment.operations_data import Warehouse
from quant_harness.investment.operations import decision_for_session
from quant_harness.investment.stockpaper import execute
from quant_harness.investment.store import Store
from quant_harness.investment.review import Source,policy
from quant_harness.investment.review_engine import sealed_review
import psycopg
p=argparse.ArgumentParser();p.add_argument('manifest',type=Path);a=p.parse_args();manifest=json.loads(a.manifest.read_text())
urls={}
for original,item in manifest['databases'].items():
 target=item['restore']['database']
 if not target.startswith('quant_task3_recovery_'):raise ValueError('disposable restored DB required')
 urls[original]='postgresql://quant_task3@127.0.0.1:55432/'+target
w=Warehouse(urls['quant_task3_ops'],ROOT);result={'external_api_calls':0,'broker_mutation_calls':0,'markets':{}}
with w.store.lock():
 for market in ('US','KR'):
  url=urls['quant_task3_'+market.lower()];store=Store(url,market+'_STOCKS')
  with psycopg.connect(url) as c:before=c.execute('SELECT count(*) FROM stock_fill').fetchone()[0]
  identity=decision_for_session(url,market,'2026-11-13')
  packet=Source(url).process_packet(ROOT,identity)
  review=Store(urls['quant_task3_review'],'TASK4_REVIEW_ONLY')
  review_id,process=sealed_review(review,packet,policy(ROOT))
  status=execute(store,ROOT,identity,[])['status'] if market=='KR' else 'PENDING_NO_ELIGIBLE_EVENT'
  with psycopg.connect(url) as c:after=c.execute('SELECT count(*) FROM stock_fill').fetchone()[0]
  if before!=after:raise ValueError('restored replay created duplicate fill')
  result['markets'][market]={'decision_id':identity,'status':status,'fills_before':before,'fills_after':after,'blind_review_id':review_id,'snapshot_reused':bool(w.lookup('inputs:'+market+':2026-11-12'))}
print(json.dumps(result,indent=2))
