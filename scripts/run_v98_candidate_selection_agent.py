from pathlib import Path
from quant_harness.v98_candidate_selection_agent.engine import run

if __name__ == "__main__":
    result = run(Path(__file__).resolve().parents[1])
    print(result["metrics"].to_string(index=False))
    print(result["promotion"].to_string(index=False))
