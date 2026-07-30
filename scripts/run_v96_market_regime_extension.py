from pathlib import Path
from quant_harness.v96_market_regime_extension.engine import run

if __name__ == "__main__":
    print(run(Path(__file__).resolve().parents[1]))
