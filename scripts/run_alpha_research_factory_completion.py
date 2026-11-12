from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quant_harness.alpha_research_factory_completion import run

print(json.dumps(run(ROOT), ensure_ascii=False, sort_keys=True))

