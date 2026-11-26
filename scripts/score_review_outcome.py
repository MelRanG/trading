"""Wake a pending evaluator with explicit session labels; cannot change process review."""
from pathlib import Path
import argparse,json,os,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from quant_harness.investment.store import Store
from quant_harness.investment.review import policy,score_mature_outcome
from quant_harness.investment.review_jobs import Queue
from quant_harness.investment.research import digest


def main():
    p=argparse.ArgumentParser();p.add_argument('--process-id',required=True);p.add_argument('--labels',type=Path,required=True);a=p.parse_args()
    store=Store(os.environ['TASK4_REVIEW_DATABASE_URL'],'TASK4_REVIEW_ONLY');process=store.get(a.process_id)
    with __import__('psycopg').connect(store.url) as conn:
        row=conn.execute("SELECT record_id FROM investment_record WHERE kind='review_process_input' AND payload_hash=%s",(process['packet_hash'],)).fetchone()
    packet=store.get(row[0]);labels=json.loads(a.labels.read_text())
    if labels['decision_id']!=process['decision_id']:raise ValueError('label decision identity mismatch')
    frozen=store.get(process['policy_hash'])
    if digest(frozen)!=process['policy_hash']:raise ValueError('original review policy required')
    result=score_mature_outcome(process,packet,frozen,labels)
    identity=store.put('review_outcome_update',{'process_id':a.process_id,'labels_hash':digest(labels),'result':result})
    job=Queue(store).observe(a.process_id,digest(labels))
    print(json.dumps({'record_id':identity,'status':result['status'],'followup_job':job},indent=2))

if __name__=='__main__':main()
