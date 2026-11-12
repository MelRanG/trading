from __future__ import annotations

from pathlib import Path

import pandas as pd

from quant_harness.alpha_research_factory_completion import (
    _provenance_guard,
    _synthetic_execution,
    enforce_transition,
    evaluate_execution,
    operational_replay_adapter,
    run,
)


ROOT = Path(__file__).resolve().parents[1]


def test_real_rejected_attempt_cannot_enter_execution_or_replay(tmp_path: Path) -> None:
    report = run(ROOT, output_dir=tmp_path)
    assert report["phase_1"]["real_attempt"] == "BLOCKED_ROBUSTNESS_NOT_RUN"
    assert report["phase_2"]["real_replay"] == "BLOCKED_STAGE_EXECUTION_NOT_READY"
    assert report["phase_2"]["real_budget"] == {"used": 0, "limit": 1}


def test_execution_provenance_guards() -> None:
    expected = {x: x for x in ("contract_hash", "data_hash", "diagnostic_artifact_hash", "robustness_artifact_hash")}
    assert _provenance_guard({"status": "READY_FOR_EXECUTION_FEASIBILITY", **expected}, expected) is None
    missing = dict(expected); missing["robustness_artifact_hash"] = None
    assert _provenance_guard({"status": "READY_FOR_EXECUTION_FEASIBILITY", **missing}, expected) == "BLOCKED_ROBUSTNESS_NOT_RUN"
    tampered = dict(expected); tampered["data_hash"] = "tampered"
    assert _provenance_guard({"status": "READY_FOR_EXECUTION_FEASIBILITY", **tampered}, expected) == "BLOCKED_EXECUTION_PROVENANCE_MISMATCH"


def test_actual_v101_synthetic_pass_and_fail() -> None:
    passed, pass_status = _synthetic_execution(ROOT, passing=True)
    failed, fail_status = _synthetic_execution(ROOT, passing=False)
    assert passed["v101_calculation_executed"] is True
    assert pass_status == "READY_FOR_OPERATIONAL_REPLAY"
    assert fail_status == "REJECTED_EXECUTION"
    assert failed["adv_liquidity_rejects"] > 0
    assert passed["sell_before_buy"] is True
    assert passed["negative_cash"] == passed["negative_position"] == passed["duplicate_order"] == 0


def test_metricless_execution_decision_is_forbidden() -> None:
    try:
        evaluate_execution({}, {"minimum_fill_ratio": 0.1, "maximum_cost_to_gross_spread_ratio": 1})
    except ValueError as exc:
        assert "actual V101" in str(exc)
    else:
        raise AssertionError("metricless execution decision was accepted")


def test_state_machine_blocks_skips_and_metricless_decisions() -> None:
    enforce_transition("PROPOSED", "PREREGISTERED")
    for current, target, metric in [
        ("PROPOSED", "READY_FOR_EXECUTION_FEASIBILITY", True),
        ("READY_FOR_DIAGNOSTIC", "REJECTED_DIAGNOSTIC", False),
        ("READY_FOR_OPERATIONAL_REPLAY", "PAPER_PRIMARY", True),
    ]:
        try:
            enforce_transition(current, target, metric_executed=metric)
        except RuntimeError:
            pass
        else:
            raise AssertionError(f"invalid transition accepted: {current}->{target}")


def _request(attempt: str = "A") -> dict[str, object]:
    fields = ("contract_hash", "data_hash", "diagnostic_artifact_hash", "robustness_artifact_hash", "execution_artifact_hash")
    hashes = {field: field for field in fields}
    return {"attempt_id": attempt, "status": "READY_FOR_OPERATIONAL_REPLAY", **hashes, "expected_hashes": hashes}


def _safe_replay(*, promoted: bool = True) -> dict[str, object]:
    return {"database_scope": "SYNTHETIC_FIXTURE_ONLY", "broker_mutation_calls": 0, "paper_primary_access": False, "promotion_passed": promoted, "validation": {"negative_cash_days": 0, "negative_position_days": 0, "duplicate_orders": 0, "reconciliation_failures": 0}}


def test_operational_adapter_budget_provenance_and_idempotency(tmp_path: Path) -> None:
    budget = tmp_path / "budget.jsonl"
    first = operational_replay_adapter(_request(), replay_callable=_safe_replay, budget_registry=budget, fixture=False)
    second = operational_replay_adapter(_request(), replay_callable=_safe_replay, budget_registry=budget, fixture=False)
    assert first["status"] == "FORWARD_SHADOW_ONLY"
    assert second["status"] == "BLOCKED_OPERATIONAL_REPLAY_BUDGET_EXHAUSTED"
    tampered = _request("B"); tampered["data_hash"] = "bad"
    assert operational_replay_adapter(tampered, replay_callable=_safe_replay, budget_registry=tmp_path / "other.jsonl")["status"] == "BLOCKED_OPERATIONAL_REPLAY_PROVENANCE_MISMATCH"


def test_operational_adapter_safety_failure_rejected(tmp_path: Path) -> None:
    unsafe = _safe_replay(); unsafe["broker_mutation_calls"] = 1
    result = operational_replay_adapter(_request(), replay_callable=lambda: unsafe, budget_registry=tmp_path / "fixture.jsonl", fixture=True)
    assert result["status"] == "REJECTED_OPERATIONAL_REPLAY"


def test_end_to_end_and_data_block_are_idempotent(tmp_path: Path) -> None:
    first = run(ROOT, output_dir=tmp_path)
    registry_before = (tmp_path / "execution_feasibility_registry.jsonl").read_bytes()
    op_before = (tmp_path / "operational_replay_registry.jsonl").read_bytes()
    second = run(ROOT, output_dir=tmp_path)
    assert first["final_status"] == "ALPHA_FACTORY_END_TO_END_VALID_REAL_RESEARCH_DATA_BLOCKED"
    assert second["final_status"] == first["final_status"]
    assert (tmp_path / "execution_feasibility_registry.jsonl").read_bytes() == registry_before
    assert (tmp_path / "operational_replay_registry.jsonl").read_bytes() == op_before
    audit = pd.read_csv(tmp_path / "data_readiness_audit.csv")
    assert not audit["classification"].eq("READY_PIT").any()
    assert first["safety"]["broker_mutation_calls"] == 0
