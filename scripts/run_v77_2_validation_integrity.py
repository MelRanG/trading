#!/usr/bin/env python3
from pathlib import Path
import json
from quant_harness.v77_2_validation_integrity.engine import run

if __name__ == "__main__":
    print(json.dumps(run(Path(__file__).resolve().parents[1]), ensure_ascii=False, indent=2, default=str))
