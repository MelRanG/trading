"""Review Task3 read-only records using a separate review DB and official Factory."""
from pathlib import Path
import argparse,json,os,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from quant_harness.investment.review_engine import run_cycle
from quant_harness.investment.store import Store


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--decision-id',required=True)
    p.add_argument('--source-market',choices=['KR','US'],default='KR')
    p.add_argument('--compare-id');p.add_argument('--compare-market',choices=['KR','US'],default='US')
    p.add_argument('--output',type=Path,default=ROOT/'runtime/task4')
    a=p.parse_args()
    source=os.environ['TASK4_SOURCE_'+a.source_market+'_URL'];review=os.environ['TASK4_REVIEW_DATABASE_URL']
    others=[(os.environ['TASK4_SOURCE_'+a.compare_market+'_URL'],a.compare_id)] if a.compare_id else []
    result=run_cycle(ROOT,source,review,a.decision_id,comparison_ids=others)
    a.output.mkdir(parents=True,exist_ok=True)
    (a.output/'cycle_result.json').write_text(json.dumps(result,indent=2,default=str))
    Store(review,'TASK4_REVIEW_ONLY').export(a.output/'review_records.jsonl')
    print(json.dumps(result,indent=2,ensure_ascii=False,default=str))

if __name__=='__main__':main()
