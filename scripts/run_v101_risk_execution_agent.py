from pathlib import Path
from quant_harness.v101_risk_execution_agent.engine import run

if __name__ == "__main__":
    result = run(Path(__file__).resolve().parents[1])
    print(result["status"])
