"""Paired process pilot on one frozen evidence set; efficacy remains unmeasured."""
from pathlib import Path
import argparse
import json
import os
import random
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from quant_harness.investment.store import Store
from quant_harness.investment.discovery import company_discover
from quant_harness.investment.research import digest


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--market',choices=['US','KR'],default='US')
    parser.add_argument('--collection-id',required=True)
    parser.add_argument('--cutoff',required=True)
    parser.add_argument('--output',type=Path,default=ROOT/'runtime/task3/skill_ab')
    args=parser.parse_args()
    from quant_harness.investment.equities import load_environment
    load_environment(ROOT)
    store=Store(os.environ['TASK3_'+args.market+'_DATABASE_URL'],args.market+'_STOCKS')
    from quant_harness.investment.discovery import instant,now
    if instant(args.cutoff)>instant(now()):raise ValueError('future cutoff forbidden')
    evidence=store.get(args.collection_id)['records'][:12]
    args.output.mkdir(parents=True,exist_ok=True)
    plan={'collection_id':args.collection_id,'input_hash':digest(evidence),'cutoff':args.cutoff,'model':'gpt-6.1-terra',
          'methods':['baseline','catalyst','earnings','reverse_dcf','postmortem_record'],
          'max_calls_per_arm':1,'timeout_seconds':120,'seed':3013,'hard_token_budget_enforced':False,
          'purpose':'PROCESS_PILOT_NOT_EFFICACY_OR_STRICT_EQUAL_BUDGET_AB','labels':'PENDING'}
    manifest=args.output/'preregistration.json'
    if manifest.exists() and json.loads(manifest.read_text())!=plan:raise ValueError('experiment manifest conflict')
    manifest.write_text(json.dumps(plan,indent=2))
    order=plan['methods'].copy();random.Random(plan['seed']).shuffle(order)
    results={}
    for method in order:
        result_path=args.output/(method+'.json')
        if result_path.exists():
            result=json.loads(result_path.read_text())
        else:
            result=company_discover(evidence,args.cutoff,skills=False if method=='baseline' else method)
            result_path.write_text(json.dumps(result,ensure_ascii=False,indent=2))
        record_id=store.put('skill_ab_analysis',{'plan_hash':digest(plan),'arm':method,'result':result})
        results[method]={'record_id':record_id,'status':result['status'],'candidates':len(result['candidates']),
                         'input_hash':result['input_hash'],'reason':result['reason']}
        print(method,results[method]['status'],flush=True)
    summary={'plan':plan,'order':order,'results':results,'discovery_accuracy':None,'forecast_accuracy':None,'money_cost':None,
             'conclusion':'No winner: sample=1, missing labels/independent scoring/hard token budget.'}
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False))
    store.export(args.output/'task4_records.jsonl')

if __name__=='__main__':main()
