"""Register an immediate source-access research task from a real Task3 receipt."""
from pathlib import Path
import argparse,json,os,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from quant_harness.investment.review import Source
from quant_harness.investment.store import Store
from quant_harness.investment.review_engine import enqueue_event,run_event_job


def main():
    p=argparse.ArgumentParser();p.add_argument('--decision-id',required=True);p.add_argument('--collection-id',required=True);p.add_argument('--market',choices=['US','KR'],default='US');a=p.parse_args()
    source=Source(os.environ['TASK4_SOURCE_'+a.market+'_URL']);receipt=source.record(a.collection_id,'stock_evidence_collection')
    failures=[r for r in receipt['receipts'] if r.get('status','').startswith(('FAILED','MISSING'))]
    if not failures:raise ValueError('no documented source failure')
    event={'kind':'UNVERIFIED_SOURCE','available_at':receipt['observed_at'],'source_hash':a.collection_id,'record_id':a.collection_id,
           'source_market':a.market,'reason':','.join(r['status'] for r in failures)}
    store=Store(os.environ['TASK4_REVIEW_DATABASE_URL'],'TASK4_REVIEW_ONLY')
    job=enqueue_event(store,a.decision_id,event)
    print(json.dumps(run_event_job(ROOT,store,job),indent=2))

if __name__=='__main__':main()
