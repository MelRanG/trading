from __future__ import annotations

import json
from pathlib import Path

from dotenv import load_dotenv

from quant_harness.v79_high252_operational_replay import run


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env", override=False)
    print(json.dumps(run(root), ensure_ascii=False, sort_keys=True, default=str))
