from pathlib import Path
import os
import sys

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
load_dotenv(ROOT / ".env")

from quant_harness.open_5m_long_horizon_audit import run


if __name__ == "__main__":
    print(run(ROOT, os.environ["TEST_DATABASE_URL"], ROOT / "runtime/open_5m_long_horizon_validation"))
