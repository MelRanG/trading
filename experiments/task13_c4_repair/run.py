"""Authorized C4-R1 continuation from saved labels and the sealed evaluator."""
import argparse
import inspect
import json
import time
from pathlib import Path

import pandas as pd

from experiments.task13_c4 import preflight
from experiments.task13_c4.evaluate import evaluate

ROOT = preflight.ROOT
ORIGINAL = preflight.OUT
OUT = ROOT / "runtime/task13_c4_repair"
PAIRED_SHA = "60565fbc2fee41c96aba86a177923fe48e80466880e81819e08d06caea48cb8d"


def write(name, data):
    path = OUT / name
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")
    temp.replace(path)


def check():
    read, sha = preflight.read, preflight.sha
    failure = read(ORIGINAL / "failure_audit.json")
    original_execution = read(ORIGINAL / "execution.json")
    assert failure["reservation"] == original_execution
    assert original_execution["status"] == "INVALID_EVALUATION"
    assert original_execution["reserved_attempts"] == 1
    assert failure["valid_statistics"] is False
    assert failure["resolved_signature"] == "(seal, start, wall)"
    assert failure["resolved_evaluator"].endswith("/experiments/task13_c1/evaluate.py")
    assert "unexpected keyword argument 'task14_primary_tests'" in (ORIGINAL / "evaluation.log").read_text()
    assert not (ORIGINAL / "result.json").exists()

    for mapping in (read(ORIGINAL / "seal.json")["hashes"],
                    read(ORIGINAL / "input_hashes.json"),
                    read(ORIGINAL / "artifact_manifest.json")["files"]):
        for name, expected in mapping.items():
            if sha(ROOT / name) != expected:
                raise ValueError(f"Original artifact hash mismatch: {name}")

    evaluator_path = Path(inspect.getfile(evaluate)).resolve()
    beta_path = Path(inspect.getfile(preflight.estimate_beta_sigma)).resolve()
    assert evaluator_path == ROOT / "experiments/task13_c4/evaluate.py"
    assert beta_path == ROOT / "experiments/task13_c1/factor.py"
    signature = inspect.signature(evaluate)
    signature.bind(None, task14_primary_tests=[], c1_primary_p=0.5)

    paired_path = ORIGINAL / "paired.json"
    assert sha(paired_path) == failure["paired_sha256"] == PAIRED_SHA
    paired = read(paired_path)
    rows = read(ORIGINAL / "sample.json")["rows"]
    assert len(paired) == len(rows) == 151
    assert len({row["CIK"] for row in paired}) == 52
    assert [{k: v for k, v in row.items() if k != "outcome"} for row in paired] == rows
    assert all("outcome" in row for row in paired)
    proof = {
        "status": "PASS", "evaluator": str(evaluator_path.relative_to(ROOT)),
        "signature": str(signature), "beta": str(beta_path.relative_to(ROOT)),
        "paired_rows": len(paired), "paired_sha256": PAIRED_SHA,
        "original_seal_sha256": sha(ORIGINAL / "seal.json"),
        "original_contract_sha256": sha(ORIGINAL / "contract.json"),
        "original_inputs_sha256": sha(ORIGINAL / "input_hashes.json"),
        "original_execution_sha256": sha(ORIGINAL / "execution.json"),
        "original_manifest_sha256": sha(ORIGINAL / "artifact_manifest.json"),
        "repair_runner_sha256": sha(Path(__file__)),
    }
    return proof, paired


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify inputs and imports without reserving evaluation")
    args = parser.parse_args()
    proof, paired = check()
    if args.check:
        print(json.dumps(proof))
        return
    if preflight.read(OUT / "import_preflight.json") != proof:
        raise ValueError("Runner or input differs from the verified import smoke test")
    old = preflight.read(ROOT / "runtime/task14/validation.json")["primary_tests"]
    prior = preflight.read(ROOT / "runtime/task13_c1/evaluation.json")["US"]["local_family1_p"]
    rows = pd.DataFrame(paired)
    lease = OUT / "execution.json"
    reservation = {
        "status": "RUNNING", "reserved_attempts": 1, "max_attempts": 1,
        "started": preflight_time(), "authorization": "Task13-C4-R1: explicit import and one statistics-only resume",
        "original_status": "INVALID_EVALUATION", "verified_inputs": proof,
    }
    with lease.open("x") as handle:
        json.dump(reservation, handle, indent=2)
    cpu, wall = time.process_time(), time.monotonic()
    try:
        result = evaluate(rows, task14_primary_tests=old, c1_primary_p=prior)
        write("result.json", result)
    except BaseException as exc:
        write("execution.json", {**reservation, "status": "INVALID_EVALUATION",
                                "finished": preflight_time(), "error": repr(exc)})
        raise
    write("execution.json", {**reservation, "status": "COMPLETED",
          "finished": preflight_time(), "result_sha256": preflight.sha(OUT / "result.json"),
          "cpu_seconds": time.process_time()-cpu, "wall_seconds": time.monotonic()-wall,
          "labels_recalculated": 0, "SEC_HTTP": 0, "price_downloads": 0})


def preflight_time():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    main()
