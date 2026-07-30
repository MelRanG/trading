#!/usr/bin/env python3
from pathlib import Path
import json
from quant_harness.v77_corrected_price_allocation.engine import run

if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    print(json.dumps(run(root), ensure_ascii=False, indent=2, default=str))
