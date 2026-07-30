from pathlib import Path
import json
from quant_harness.v102_market_evidence_agent.engine import run

if __name__ == "__main__":
    result = run(Path(__file__).resolve().parents[1])
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
