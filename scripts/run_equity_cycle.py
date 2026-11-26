"""US-first, individual-stock-only research/Paper entry point."""
from pathlib import Path
import argparse,json,os,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from quant_harness.investment.equities import run_equity_cycle,load_environment


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--market',choices=['US','KR'],default='US')
    p.add_argument('--compare',action='store_true')
    p.add_argument('--no-llm',action='store_true')
    p.add_argument('--resume')
    p.add_argument('--output',type=Path)
    a=p.parse_args();load_environment(ROOT)
    url=os.environ.get('TASK3_'+a.market+'_DATABASE_URL')
    if not url:p.error('set TASK3_'+a.market+'_DATABASE_URL to a dedicated stock research DB')
    directory=a.output or ROOT/'runtime/task3'/a.market.lower()/'forward'
    try:r=run_equity_cycle(ROOT,url,a.market,directory,use_llm=not a.no_llm,compare=a.compare,resume=a.resume)
    except Exception as exc:
        r={'status':'HOLD_ONLY','reason':type(exc).__name__,'broker_mutation_calls':0}
        directory.mkdir(parents=True,exist_ok=True);(directory/'failure.json').write_text(json.dumps(r))
        print(json.dumps(r));return 2
    print(json.dumps(r,default=str,ensure_ascii=False,indent=2));return 0

if __name__=='__main__':raise SystemExit(main())
