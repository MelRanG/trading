from __future__ import annotations
import argparse
from pathlib import Path
from quant_harness.v85_operational_hardening.engine import run_operating_day

if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--session")
    parser.add_argument("--rebuild",action="store_true")
    args=parser.parse_args()
    print(run_operating_day(Path(__file__).resolve().parents[1],session=args.session,rebuild=args.rebuild))
