from pathlib import Path
import json
import sys

from quant_harness.v104_end_to_end_causal_challenger_audit.adapter import load_candidate_specs, future_mutation_invariant

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: run_v104_future_mutation_check.py CANDIDATE_ID")
    root = Path(__file__).resolve().parents[1]
    candidate_id = sys.argv[1]
    spec = load_candidate_specs(root)[candidate_id]
    passed, diffs = future_mutation_invariant(root, spec)
    print(json.dumps({"candidate_id": candidate_id, "passed": passed, "past_target_hash_diff_days": diffs}))
