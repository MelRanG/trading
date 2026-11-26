"""Exercise the unchanged reservation cap and only the isolated economic route."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

import pytest

from quant_harness.alpha_research_factory import (
    execute_review_economics, record_review_experiment, register_review_proposal,
)


@pytest.fixture
def offline(tmp_path):
    root = tmp_path
    cfg_dir = root / "config"
    cfg_dir.mkdir()
    original = Path(__file__).resolve().parents[1] / "config/task4_review_contract.json"
    config = json.loads(original.read_text())
    worker = root / "fixture_worker.py"
    worker.write_text(
        "import json, sys\nfrom pathlib import Path\nassert sys.argv[1:] == ['evaluate']\n"
        "Path('worker_result.json').write_text(json.dumps("
        "{'status':'EXPLORATORY_ECONOMICS_COMPLETED','cases':2,'net_fixture':-0.02}))\n"
    )
    proposal = {
        "approval_id": "TEST_FIXTURE", "target": "strategy", "champion": "fixed", "challenger": "fixture",
        "problem_evidence": {"source": "synthetic"}, "expected_effect": "net comparison",
        "falsification": "negative", "input_hash": "fixture", "budget": {"experiments": 1, "parameter_search": 0},
        "stop_conditions": ["fixture ends"], "evaluation_metric": "return", "minimum_cases": 12,
        "split": "EXPLORATORY_ECONOMICS", "worker_hash": sha256(worker.read_bytes()).hexdigest(),
    }
    config["exploratory_economics"] = {"TEST_FIXTURE": {"worker": worker.name, "proposal": proposal,
                                                        "artifacts": "runtime/synthetic_only"}}
    (cfg_dir / original.name).write_text(json.dumps(config))
    return root, proposal


def test_refuses_unapproved_or_isolated_ledger(offline):
    root, proposal = offline
    with pytest.raises(ValueError, match="documented user scope"):
        register_review_proposal(root, {**proposal, "input_hash": "different"})
    with pytest.raises(ValueError, match="official"):
        register_review_proposal(root, proposal, directory=root / "side_ledger")


def test_prior_isolated_reservation_is_counted(offline):
    root, proposal = offline
    old = root / "runtime/task16_cycle_fixture/isolated_factory"
    old.mkdir(parents=True)
    (old / "experiment_reservations.jsonl").write_text(json.dumps({
        "attempt_id": "prior", "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }) + "\n")
    attempt = register_review_proposal(root, proposal)
    with pytest.raises(ValueError, match="before execution"):
        execute_review_economics(root, attempt)
    assert not (root / "runtime/synthetic_only").exists()


def test_worker_runs_once_and_negative_result_is_preserved(offline):
    root, proposal = offline
    attempt = register_review_proposal(root, proposal)
    result = execute_review_economics(root, attempt)
    assert attempt["status"] == "READY_FOR_EXPLORATORY_ECONOMICS"
    assert result["result"]["net_fixture"] == -0.02
    assert result["promotion_status"] == "NOT_ELIGIBLE"
    assert result["result"]["evidence_grade"] == "EXPOSED_CONDITIONAL_ONLY"
    with pytest.raises(FileExistsError):
        execute_review_economics(root, attempt)
    with pytest.raises(ValueError, match="differs from worker evidence"):
        record_review_experiment(root, attempt, {**result["result"], "net_fixture": 0.4})
