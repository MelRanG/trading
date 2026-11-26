"""Independent LLM note over a previously sealed blind process input only."""
from pathlib import Path
import argparse,json,os,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from quant_harness.investment.store import Store
from quant_harness.investment.review_model import independent_note


def main():
    p=argparse.ArgumentParser();p.add_argument('--process-id',required=True);a=p.parse_args()
    store=Store(os.environ['TASK4_REVIEW_DATABASE_URL'],'TASK4_REVIEW_ONLY')
    process=store.get(a.process_id)
    with __import__('psycopg').connect(store.url) as conn:
        row=conn.execute("SELECT record_id FROM investment_record WHERE kind='review_process_input' AND payload_hash=%s",(process['packet_hash'],)).fetchone()
    if not row:raise ValueError('sealed blind packet missing')
    packet=store.get(row[0]);result=independent_note(packet)
    identity=store.put('independent_review_note',{'process_review_id':a.process_id,'note':result})
    print(json.dumps({'record_id':identity,'status':result['status'],'findings':result.get('commentary',{}).get('findings',[])},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
