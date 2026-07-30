from pathlib import Path
from quant_harness.v84_dual_paper_parity.engine import run
if __name__ == "__main__":
    print(run(Path(__file__).resolve().parents[1]))
