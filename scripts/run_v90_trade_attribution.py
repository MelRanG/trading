from pathlib import Path
from quant_harness.v90_trade_attribution.engine import run
if __name__ == "__main__":
    print(run(Path(__file__).resolve().parents[1]))
