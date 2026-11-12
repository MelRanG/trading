from __future__ import annotations

import os
from pathlib import Path
import sys

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
load_dotenv(ROOT / ".env")

from quant_harness.open_5m_execution_validation import run  # noqa: E402


if __name__ == "__main__":
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        raise RuntimeError("TEST_DATABASE_URL is required")
    print(run(ROOT, url, ROOT / "runtime/open_5m_execution_validation"))
