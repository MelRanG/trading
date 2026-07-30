from pathlib import Path
from quant_harness.v83_independent_self_research.engine import run

if __name__ == "__main__":
    print(run(Path(__file__).resolve().parents[1]))
