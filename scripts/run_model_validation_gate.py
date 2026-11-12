from __future__ import annotations

import json
from pathlib import Path

from quant_harness.model_validation_gate import run_model_validation_gate


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    result = run_model_validation_gate(root)
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
