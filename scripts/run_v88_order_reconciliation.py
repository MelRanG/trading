from pathlib import Path
from quant_harness.v88_order_reconciliation.engine import run

if __name__ == "__main__":
    print(run(Path(".")))
