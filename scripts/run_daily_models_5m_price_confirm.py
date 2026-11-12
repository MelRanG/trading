from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quant_harness.daily_models_5m_price_confirm import run


if __name__ == "__main__":
    print(json.dumps(run(ROOT), ensure_ascii=False, sort_keys=True))
