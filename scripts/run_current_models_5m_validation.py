from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quant_harness.current_models_5m_validation import run_current_models_5m_validation


if __name__ == "__main__":
    result = run_current_models_5m_validation(ROOT)
    print(result["technical_judgement"])
