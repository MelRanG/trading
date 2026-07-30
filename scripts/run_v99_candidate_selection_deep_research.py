from pathlib import Path
from quant_harness.v99_candidate_selection_deep_research.engine import run

if __name__ == "__main__":
    result = run(Path(__file__).resolve().parents[1])
    print(result["promotion"].to_string(index=False))
    print(result["quality"].to_string(index=False))
