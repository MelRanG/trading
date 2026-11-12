from pathlib import Path
import json

from quant_harness.three_model_backtest import run_three_model_backtest


if __name__ == "__main__":
    print(json.dumps(run_three_model_backtest(Path(__file__).resolve().parents[1]), ensure_ascii=False, indent=2, default=str))
