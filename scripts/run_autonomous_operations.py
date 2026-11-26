"""Canonical bounded operating invocation; scheduled by one user systemd timer."""
from pathlib import Path
import argparse,json,os,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from dotenv import load_dotenv
load_dotenv(ROOT/'runtime/task5/service.env',override=False)
from quant_harness.investment.operations import tick


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.parse_args()
    sources={m:os.environ.get('TASK5_'+m+'_DATABASE_URL','postgresql://quant_task3@127.0.0.1:55432/quant_task3_'+m.lower()) for m in ('US','KR')}
    result=tick(ROOT,os.environ.get('TASK5_DATABASE_URL','postgresql://quant_task3@127.0.0.1:55432/quant_task3_ops'),sources,
                os.environ.get('TASK4_REVIEW_DATABASE_URL','postgresql://quant_task3@127.0.0.1:55432/quant_task3_review'))
    print(json.dumps(result,indent=2,default=str))
    # Separate research-only DB and failure boundary; existing Paper decision is unchanged.
    if (ROOT/'config/task8_portfolio.json').exists():
        try:
            from quant_harness.investment.company_outcomes import run_tick as observe_company_outcomes
            from quant_harness.investment.shadow_portfolio import observe_shadow_accounts
            print(json.dumps({'task8_shadow_observation':observe_shadow_accounts(ROOT), 'task8_company_observation':observe_company_outcomes(ROOT)},indent=2,default=str))
        except Exception as exc:
            print(json.dumps({'task8_company_observation':{'status':'FAILED_CLOSED','error_type':type(exc).__name__}}))

    if (ROOT/'config/task8b_exploration.json').exists():
        try:
            from quant_harness.investment.exploration import run_tick as observe_exploration
            from quant_harness.investment.exploration_evaluation import observe as evaluate_exploration
            print(json.dumps({'task8b_exploration':observe_exploration(ROOT), 'task8b_evaluation':evaluate_exploration(ROOT)},indent=2,default=str))
        except Exception as exc:
            print(json.dumps({'task8b_exploration':{'status':'FAILED_CLOSED','error_type':type(exc).__name__}}))

    try:
        from quant_harness.investment.research_dispatcher import run_tick as dispatch_research
        print(json.dumps({'task92_research_dispatch':dispatch_research(ROOT)},indent=2,default=str))
    except Exception as exc:
        print(json.dumps({'task92_research_dispatch':{'status':'FAILED_CLOSED','error_type':type(exc).__name__}}))

    # Optional, separately sealed research accounts; no Paper/Champion authority.
    # Shares this timer only. The observer has its own lock and bounded I/O.
    if (ROOT/'runtime/task10_1/forward/contract.json').exists():
        try:
            import subprocess
            observed=subprocess.run(
                [sys.executable,str(ROOT/'experiments/task10_1/forward.py')],
                cwd=ROOT,capture_output=True,text=True,timeout=600,check=True)
            print(json.dumps({'task101_quant_shadow':json.loads(observed.stdout)},indent=2))
            reference=subprocess.run(
                [sys.executable,str(ROOT/'experiments/task10_1/benchmarks.py')],
                cwd=ROOT,capture_output=True,text=True,timeout=90,check=True)
            print(json.dumps({'task101_index_references':json.loads(reference.stdout)},indent=2))
            followups=subprocess.run(
                [sys.executable,str(ROOT/'experiments/task10_1/queue_followups.py')],
                cwd=ROOT,capture_output=True,text=True,timeout=60,check=True)
            print(json.dumps({'task101_research_requests':json.loads(followups.stdout)},indent=2))
        except Exception as exc:
            print(json.dumps({'task101_quant_shadow':{'status':'FAILED_CLOSED','error_type':type(exc).__name__}}))

    try:
        from quant_harness.investment.operations_verification import collect
        collect(ROOT,os.environ.get('TASK5_DATABASE_URL','postgresql://quant_task3@127.0.0.1:55432/quant_task3_ops'),sources,os.environ.get('TASK4_REVIEW_DATABASE_URL','postgresql://quant_task3@127.0.0.1:55432/quant_task3_review'))
    except Exception as exc:
        print(json.dumps({'verification_status':'FAILED','error_type':type(exc).__name__}))

if __name__=='__main__':main()
