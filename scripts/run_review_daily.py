"""One bounded daily review invocation; no scheduler/Gateway or trade authority."""
from pathlib import Path
import argparse,json,os,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from quant_harness.investment.review import Source
from quant_harness.investment.review_engine import run_cycle
from quant_harness.investment.store import Store


def main():
    p=argparse.ArgumentParser();p.add_argument('--limit',type=int,default=20);a=p.parse_args()
    if not 1<=a.limit<=100:p.error('limit must be 1..100')
    review=os.environ['TASK4_REVIEW_DATABASE_URL'];results=[]
    for market in ('US','KR'):
        source=Source(os.environ['TASK4_SOURCE_'+market+'_URL'])
        for identity in source.decisions()[-a.limit:]:
            try:
                r=run_cycle(ROOT,source.url,review,identity)
                results.append({'market':market,'decision_id':identity,'status':r['proposal_status'],'outcome':r['outcome_status']})
            except Exception as exc:
                # Redacted error receipt is retained; budget/data blocks are not passes.
                failure={'market':market,'decision_id':identity,'status':'FAILED_OR_BLOCKED','reason':type(exc).__name__}
                Store(review,'TASK4_REVIEW_ONLY').put('review_daily_failure',failure)
                results.append(failure)
    out=ROOT/'runtime/task4/daily';out.mkdir(parents=True,exist_ok=True)
    Store(review,'TASK4_REVIEW_ONLY').export(out/'review_records.jsonl')
    (out/'result.json').write_text(json.dumps(results,indent=2))
    print(json.dumps(results,indent=2))

if __name__=='__main__':main()
