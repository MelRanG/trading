from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quant_harness.krx_market_flow_pack import run

parser = argparse.ArgumentParser()
mode = parser.add_mutually_exclusive_group()
mode.add_argument("--dry-run", action="store_true")
mode.add_argument("--ingest", action="store_true")
args = parser.parse_args()
print(json.dumps(run(ROOT, dry_run=not args.ingest), ensure_ascii=False, sort_keys=True))

