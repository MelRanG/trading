from pathlib import Path
import json

from quant_harness.v80_multi_indicator_confirmation.engine import run

if __name__ == "__main__":
    result = run(Path(__file__).resolve().parents[1])
    print(json.dumps(result, ensure_ascii=False, indent=2))
