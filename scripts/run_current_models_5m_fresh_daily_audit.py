from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quant_harness.current_models_5m_fresh_daily_audit import run_fresh_daily_audit


if __name__ == "__main__":
    print(json.dumps(run_fresh_daily_audit(ROOT), ensure_ascii=False, sort_keys=True))
