from __future__ import annotations

import argparse
import json
from pathlib import Path

from quant_harness.v104_end_to_end_causal_challenger_audit.forward_runtime import append_new_forward_observations


def main() -> None:
    parser = argparse.ArgumentParser(description="Append a fail-closed V104 parent/challenger paper observation")
    parser.add_argument("--root", default=".")
    parser.add_argument("--as-of", default=None)
    args = parser.parse_args()
    result = append_new_forward_observations(Path(args.root), as_of=args.as_of)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
