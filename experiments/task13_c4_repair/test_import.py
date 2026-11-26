"""Exercise the actual CLI with the C1 search-path collision in place."""
import json
from pathlib import Path
import subprocess
import sys


def test_runner_loads_c4_evaluator_without_reserving():
    root = Path(__file__).resolve().parents[2]
    original = root / "runtime/task13_c4/execution.json"
    repair = root / "runtime/task13_c4_repair/execution.json"
    before = (original.read_bytes(), repair.read_bytes() if repair.exists() else None)
    result = subprocess.run(
        [sys.executable, "-m", "experiments.task13_c4_repair.run", "--check"],
        cwd=root, check=True, capture_output=True, text=True,
    )
    proof = json.loads(result.stdout)
    assert proof["evaluator"] == "experiments/task13_c4/evaluate.py"
    assert "task14_primary_tests" in proof["signature"]
    assert proof["beta"] == "experiments/task13_c1/factor.py"
    assert proof["paired_rows"] == 151
    assert before == (original.read_bytes(), repair.read_bytes() if repair.exists() else None)
