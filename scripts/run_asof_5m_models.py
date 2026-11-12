from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quant_harness.asof_5m_models import run


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--fresh-replay", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(ROOT, fresh_replay=args.fresh_replay), ensure_ascii=False, sort_keys=True))
