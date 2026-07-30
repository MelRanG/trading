from pathlib import Path
import json
from quant_harness.v94_universe_agent.engine import run

if __name__ == "__main__":
    print(json.dumps(run(Path(__file__).resolve().parents[1]), indent=2))
