from __future__ import annotations

import json
from pathlib import Path

from quant_harness.alpha_research_factory_diagnostics import run

ROOT = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    print(json.dumps(run(ROOT), ensure_ascii=False, sort_keys=True))
