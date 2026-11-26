"""Historical ETF diagnostic only; cannot place any Paper or Live orders."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from quant_harness.investment.research import run_comparison
if __name__=='__main__':
    result=run_comparison(ROOT,ROOT/'runtime/task3/legacy_etf_diagnostic')
    print({'status':'HISTORICAL_ETF_DIAGNOSTIC_ONLY','selection':result['selection']})
