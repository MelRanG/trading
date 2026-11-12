from pathlib import Path
import json

from quant_harness.base_operational_replay_validation import run_base_operational_replay_validation


if __name__ == "__main__":
    print(json.dumps(run_base_operational_replay_validation(Path(__file__).resolve().parents[1]), indent=2, default=str))
