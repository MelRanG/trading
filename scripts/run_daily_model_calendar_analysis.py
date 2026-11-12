from pathlib import Path
import argparse
import json

from dotenv import load_dotenv

from quant_harness.daily_model_calendar_analysis import run


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reuse-completed", action="store_true", help="reuse only a completed fresh replay for post-processing recovery")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env")
    print(json.dumps(run(root, reuse_completed=args.reuse_completed), ensure_ascii=False, indent=2, default=str))
