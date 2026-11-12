from __future__ import annotations

import json
from pathlib import Path

import pytest

from quant_harness.alpha_research_factory import run


ROOT = Path(__file__).resolve().parents[1]


def test_factory_unrun_diagnostic_is_blocked_not_rejected(tmp_path: Path) -> None:
    result = run(ROOT, output_dir=tmp_path)
    contract = json.loads((tmp_path / "contracts/REVERSAL_5D.json").read_text(encoding="utf-8"))
    assert contract["metric_output"]["status"] == "NOT_RUN"
    assert result["statuses"]["REVERSAL_5D"] == "BLOCKED_DIAGNOSTIC_NOT_RUN"
    events = [json.loads(line) for line in (tmp_path / "state_events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert any(event["to"] == "BLOCKED_DIAGNOSTIC_NOT_RUN" for event in events)
    assert not any(event["to"] == "REJECTED_DIAGNOSTIC" for event in events)


def test_factory_preregisters_and_vetoes_the_three_fixed_proposals(tmp_path: Path) -> None:
    result = run(ROOT, output_dir=tmp_path)
    assert result["status"] == "ALPHA_FACTORY_CONTROL_PLANE_VALID"
    assert result["statuses"] == {
        "HIGH252_EQUIVALENT": "REJECTED_DUPLICATE",
        "REVERSAL_5D": "BLOCKED_DIAGNOSTIC_NOT_RUN",
        "PIT_NEWS_EVENT": "REJECTED_FEASIBILITY",
    }
    assert result["v101_called"] is False
    assert result["operational_replay_called"] is False
    assert result["broker_mutation_calls"] == 0
    attempts = [json.loads(x) for x in (tmp_path / "attempt_registry.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(attempts) == 3
    assert all(x["universe_pit_limitation"] == "OBSERVED_FIRST_BAR_PROXY_NOT_COMPLETE_LISTING_DELISTING_HISTORY" for x in attempts)


def test_factory_contracts_are_immutable_and_second_dry_run_is_append_safe(tmp_path: Path) -> None:
    first = run(ROOT, output_dir=tmp_path)
    saved = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file() and path.name != "dry_run_report.json"}
    second = run(ROOT, output_dir=tmp_path)
    assert first["attempts_written"] == 3
    assert second["attempts_written"] == 0
    assert second["existing_attempts_skipped"] == 3
    contracts = list((tmp_path / "contracts").glob("*.json"))
    assert len(contracts) == 3
    assert all(json.loads(path.read_text(encoding="utf-8"))["contract_hash"] for path in contracts)
    assert all(path.read_bytes() == content for path, content in saved.items())


def test_factory_preserves_recorded_diagnostic_rejection_and_metric_evidence(tmp_path: Path) -> None:
    run(ROOT, output_dir=tmp_path)
    attempt_path = tmp_path / "attempt_registry.jsonl"
    rows = [json.loads(line) for line in attempt_path.read_text(encoding="utf-8").splitlines()]
    # Model a previously recorded measured result; rerunning the control plane
    # must neither reinterpret it nor alter the separate metric evidence.
    for row in rows:
        if row["proposal_id"] == "REVERSAL_5D":
            row["status"] = "REJECTED_DIAGNOSTIC"
            row["veto"] = "DETERMINISTIC_METRICS_VERIFIED"
    attempt_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    metric_path = tmp_path / "diagnostic_registry.jsonl"
    metric_path.write_text(json.dumps({"proposal_id": "REVERSAL_5D", "attempt_status": "REJECTED_DIAGNOSTIC", "metric_output_status": "COMPLETED"}) + "\n", encoding="utf-8")
    saved = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file() and path.name != "dry_run_report.json"}

    result = run(ROOT, output_dir=tmp_path)

    assert result["statuses"]["REVERSAL_5D"] == "REJECTED_DIAGNOSTIC"
    assert result["attempts_written"] == 0
    assert result["existing_attempts_skipped"] == 3
    assert all(path.read_bytes() == content for path, content in saved.items())


def test_factory_rejects_immutable_contract_conflict(tmp_path: Path) -> None:
    run(ROOT, output_dir=tmp_path)
    path = tmp_path / "contracts/REVERSAL_5D.json"
    contract = json.loads(path.read_text(encoding="utf-8"))
    contract["contract_hash"] = "conflicting-contract"
    path.write_text(json.dumps(contract), encoding="utf-8")
    saved = {item: item.read_bytes() for item in tmp_path.rglob("*") if item.is_file()}
    with pytest.raises(RuntimeError, match="immutable preregistration conflict: REVERSAL_5D"):
        run(ROOT, output_dir=tmp_path)
    assert all(item.read_bytes() == content for item, content in saved.items())


def test_factory_trace_separates_llm_proposal_from_metrics_execution_and_replay(tmp_path: Path) -> None:
    run(ROOT, output_dir=tmp_path)
    trace = [json.loads(x) for x in (tmp_path / "agent_invocation_trace.jsonl").read_text(encoding="utf-8").splitlines()]
    risk = [x for x in trace if x["agent"] == "RiskExecutionAgent"]
    review = [x for x in trace if x["agent"] == "ReviewFeedbackAgent"]
    assert len(risk) == 3 and all(x["invocation"] == "NOT_INVOKED" for x in risk)
    assert len(review) == 3 and all(x["capital_mutation"] is False for x in review)
