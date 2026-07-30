from pathlib import Path
import json

from quant_harness.v104_end_to_end_causal_challenger_audit.engine import run

if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    result = run(root)
    print(json.dumps(result["registry"], indent=2, ensure_ascii=False))
