from __future__ import annotations

import os
from pathlib import Path


def load_env_file(path: Path | str, *, override: bool = False) -> dict[str, str]:
    target = Path(path)
    loaded: dict[str, str] = {}
    if not target.exists():
        return loaded
    for raw in target.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if not key:
            continue
        if override or key not in os.environ:
            os.environ[key] = value
        loaded[key] = value
    return loaded
