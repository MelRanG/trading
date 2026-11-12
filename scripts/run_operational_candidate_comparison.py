from pathlib import Path
import json

from dotenv import load_dotenv

from quant_harness.operational_candidate_comparison import run_operational_candidate_comparison


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env")
    print(json.dumps(run_operational_candidate_comparison(root), ensure_ascii=False, indent=2, default=str))
