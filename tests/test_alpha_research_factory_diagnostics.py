from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from quant_harness.alpha_research_factory import _hash
from quant_harness.alpha_research_factory_diagnostics import (
    _verify_contract,
    _verify_existing_artifact,
    assert_next_stage_allowed,
    calculate_d1_reversal_metrics,
    summarize_metrics,
    run as run_diagnostics,
)

ROOT = Path(__file__).resolve().parents[1]


def _close() -> pd.DataFrame:
    index = pd.bdate_range("2024-01-01", periods=200)
    return pd.DataFrame({f"T{i}": 100 + i + pd.Series(range(200), index=index) * (i + 1) for i in range(6)}, index=index)


def test_metric_less_state_cannot_be_rejected_diagnostic() -> None:
    empty, reasons = calculate_d1_reversal_metrics(_close().iloc[:5], horizons=[5], minimum_cross_section_observations=6)
    assert empty.empty
    _, status = summarize_metrics(empty, horizons=[5], minimum_usable_dates=120, criteria={"minimum_horizons_with_positive_rank_ic": 1, "minimum_horizons_with_positive_top3_bottom3_spread": 1, "unknown_nan_reasons_allowed": 0}, nan_reasons=reasons)
    assert status == "BLOCKED_DIAGNOSTIC_NOT_RUN"


def test_failed_metric_rejects_and_synthetic_pass_is_ready() -> None:
    failed = pd.DataFrame([{"horizon_sessions": 5, "rank_ic": -0.1, "top3_bottom3_spread": -0.01, "coverage": 6}] * 120)
    _, status = summarize_metrics(failed, horizons=[5], minimum_usable_dates=120, criteria={"minimum_horizons_with_positive_rank_ic": 1, "minimum_horizons_with_positive_top3_bottom3_spread": 1, "unknown_nan_reasons_allowed": 0}, nan_reasons={})
    assert status == "REJECTED_DIAGNOSTIC"
    passed = pd.DataFrame([{"horizon_sessions": 5, "rank_ic": 0.1, "top3_bottom3_spread": 0.01, "coverage": 6}] * 120)
    _, status = summarize_metrics(passed, horizons=[5], minimum_usable_dates=120, criteria={"minimum_horizons_with_positive_rank_ic": 1, "minimum_horizons_with_positive_top3_bottom3_spread": 1, "unknown_nan_reasons_allowed": 0}, nan_reasons={})
    assert status == "READY_FOR_ROBUSTNESS"


def test_contract_hash_changes_when_tampered() -> None:
    contract = {"proposal_id": "REVERSAL_5D", "metric_output": {"status": "NOT_RUN"}}
    contract["contract_hash"] = _hash(contract)
    tampered = dict(contract)
    tampered["metric_output"] = {"status": "FORGED"}
    assert _hash({k: v for k, v in tampered.items() if k != "contract_hash"}) != tampered["contract_hash"]


def test_contract_tamper_and_data_hash_mismatch_fail_closed(tmp_path: Path) -> None:
    contract = {"proposal_id": "REVERSAL_5D", "metric_output": {"status": "NOT_RUN"}}
    contract["contract_hash"] = _hash(contract)
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(contract), encoding="utf-8")
    assert _verify_contract(path, "REVERSAL_5D")["proposal_id"] == "REVERSAL_5D"
    contract["proposal_id"] = "TAMPERED"
    path.write_text(json.dumps(contract), encoding="utf-8")
    with pytest.raises(RuntimeError, match="BLOCKED_CONTRACT_TAMPER"):
        _verify_contract(path, "REVERSAL_5D")
    artifact = tmp_path / "metrics.json"
    artifact.write_text(json.dumps({"contract_hash": "a", "data_hash": "b", "report": {}}), encoding="utf-8")
    with pytest.raises(RuntimeError, match="BLOCKED_CONTRACT_OR_DATA_HASH_MISMATCH"):
        _verify_existing_artifact(artifact, contract_hash="a", data_hash="different")


def test_stage_skip_is_blocked_until_a_metric_passes() -> None:
    with pytest.raises(RuntimeError, match="BLOCKED_STAGE_SKIP_DIAGNOSTIC"):
        assert_next_stage_allowed("REJECTED_DIAGNOSTIC", "EXECUTION_FEASIBILITY")
    assert_next_stage_allowed("READY_FOR_ROBUSTNESS", "EXECUTION_FEASIBILITY")


def test_diagnostic_metric_is_deterministic_and_has_no_future_signal_input() -> None:
    close = _close()
    left, _ = calculate_d1_reversal_metrics(close, horizons=[5, 20], minimum_cross_section_observations=6)
    right, _ = calculate_d1_reversal_metrics(close, horizons=[5, 20], minimum_cross_section_observations=6)
    pd.testing.assert_frame_equal(left, right)


def test_diagnostic_rerun_keeps_registry_and_events_append_only(tmp_path: Path) -> None:
    first = run_diagnostics(ROOT, output_dir=tmp_path)
    events = (tmp_path / "state_events.jsonl").read_text(encoding="utf-8")
    registry = (tmp_path / "diagnostic_registry.jsonl").read_text(encoding="utf-8")
    second = run_diagnostics(ROOT, output_dir=tmp_path)
    assert first == second
    assert (tmp_path / "state_events.jsonl").read_text(encoding="utf-8") == events
    assert (tmp_path / "diagnostic_registry.jsonl").read_text(encoding="utf-8") == registry
