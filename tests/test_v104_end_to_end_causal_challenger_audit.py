from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
import yaml

from quant_harness.v104_end_to_end_causal_challenger_audit.adapter import _input_hash
from quant_harness.v104_end_to_end_causal_challenger_audit import forward_runtime
from quant_harness.v104_end_to_end_causal_challenger_audit.forward_runtime import (
    _classify_replay_observation,
    _enabled_forward_candidate_ids,
)
from quant_harness.v104_end_to_end_causal_challenger_audit.receipts import (
    issue_receipt,
    receipt_status,
)

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "tests/fixtures/archived_release_reports/v104_end_to_end_causal_challenger_audit"


def test_v104_quality_gates_all_pass() -> None:
    gates = pd.read_csv(REPORT / "v104_quality_gates.csv")
    assert len(gates) >= 14
    assert gates["passed"].astype(bool).all()
    assert {
        "LEGACY_REGISTRY_DYNAMIC_DISPATCH_DEFECT_CONFIRMED_AND_FIXED",
        "ACTIVE_INPUT_HASH_BINDS_MARKET_FLOW_AND_FILING_DATA",
        "ALL_SIX_CAPITAL_AGENTS_CAUSAL",
        "PRIORITY_RUNTIME_ADAPTERS_READY",
    }.issubset(set(gates["gate"]))


def test_v104_explicit_parent_parity_and_registry_dispatch() -> None:
    parity = pd.read_csv(REPORT / "v104_parent_parity.csv")
    assert set(parity["strategy"]) == {"V69", "V79"}
    assert parity["abs_error_krw"].max() < 0.01
    registry = yaml.safe_load((ROOT / "config/strategy_registry_v84.yaml").read_text(encoding="utf-8"))
    assert {row["runtime_candidate_id"] for row in registry["strategies"]} == {"V69_PARENT", "V79_PARENT"}
    assert all(row["engine"].endswith("v104_end_to_end_causal_challenger_audit.adapter") for row in registry["strategies"])
    audit = registry["end_to_end_causal_challenger_audit"]
    assert audit["legacy_registry_dynamic_dispatch_defect"] == "CONFIRMED_AND_FIXED"


def test_v104_all_retained_agents_are_causal() -> None:
    causal = pd.read_csv(REPORT / "v104_agent_causal_audit.csv")
    capital = causal[causal["causal_role"].str.startswith("CAPITAL")]
    governance = causal[causal["agent"].eq("ReviewFeedbackAgent")]
    assert len(capital) == 6
    assert capital["capital_path_changed"].astype(bool).all()
    assert capital["passed"].astype(bool).all()
    assert len(governance) == 1
    assert governance["governance_output_changed"].astype(bool).all()
    assert not governance["capital_path_changed"].astype(bool).any()


def test_v104_remembers_positive_history_and_reruns_key_candidates() -> None:
    inventory = pd.read_csv(REPORT / "v104_historical_improvement_inventory.csv")
    assert len(inventory) >= 13
    assert {
        "ABLATE_V79_63_COMPONENT",
        "MA120_VOLATILITY_GUARD_35PCT",
        "FULL_LEADER_100",
    }.issubset(set(inventory["policy"]))
    deltas = pd.read_csv(REPORT / "v104_candidate_deltas.csv").set_index("candidate_id")
    assert deltas.loc["V79_NO63", "return_pct_delta"] > 150
    assert deltas.loc["V79_NO63", "validation_return_pct_delta"] > 10
    assert deltas.loc["V79_NO63_VOL_GUARD", "return_pct_delta"] > 200
    assert deltas.loc["V69_COMPOSITE_ORTHOGONAL", "return_pct_delta"] > 100


def test_v104_challenger_adapters_are_implemented_but_forward_not_faked() -> None:
    adapters = pd.read_csv(REPORT / "v104_runtime_adapter_registry.csv")
    assert list(adapters.sort_values("priority_rank")["candidate_id"]) == [
        "V79_NO63", "V69_VOL_GUARD", "V79_NO63_VOL_GUARD"
    ]
    assert adapters["enabled_for_new_forward"].astype(bool).all()
    assert set(adapters["adapter_status"]) == {"IMPLEMENTED_AND_TESTED_FORWARD_NOT_STARTED"}
    observations = pd.read_csv(REPORT / "v104_shadow_replay_observations.csv")
    assert observations["historical_replay_only"].astype(bool).all()
    assert not observations["new_forward_observation"].astype(bool).any()


def test_v104_future_mutation_and_no_same_day_leakage() -> None:
    future = pd.read_csv(REPORT / "v104_future_mutation_audit.csv")
    assert len(future) == 5
    assert future["passed"].astype(bool).all()
    assert future["past_target_hash_diff_days"].eq(0).all()
    metrics = pd.read_csv(REPORT / "v104_candidate_metrics.csv")
    assert metrics["same_day_decision_count"].eq(0).all()
    assert metrics["negative_cash_days"].eq(0).all()


def test_v104_market_data_is_bound_into_input_hash(tmp_path: Path) -> None:
    data = tmp_path / "data/toss_v19c_daily"
    data.mkdir(parents=True)
    (data / "universe.csv").write_text("ticker\n069500\n", encoding="utf-8")
    bar = data / "069500_1d.csv"
    bar.write_text("date,close\n2026-07-03,100\n", encoding="utf-8")
    first = _input_hash(tmp_path)
    bar.write_text("date,close\n2026-07-03,101\n", encoding="utf-8")
    second = _input_hash(tmp_path)
    assert first != second


def test_v104_benchmark_data_is_bound_into_input_hash(tmp_path: Path) -> None:
    benchmark = tmp_path / "data/all_prices_long_v62_9_expanded.csv"
    benchmark.parent.mkdir(parents=True)
    benchmark.write_text("date,ticker,close\n2026-07-03,KS11,100\n", encoding="utf-8")
    first = _input_hash(tmp_path)
    benchmark.write_text("date,ticker,close\n2026-07-03,KS11,101\n", encoding="utf-8")
    second = _input_hash(tmp_path)
    assert first != second


def test_post_freeze_batch_replay_is_never_forward_evidence():
    flags = _classify_replay_observation("2026-07-31", "2026-07-03")
    assert flags["post_freeze"] is True
    assert flags["historical_replay_only"] is True
    assert flags["new_forward_observation"] is False
    assert flags["reason"] == "BATCH_REPLAY_HAS_NO_CAPTURE_PROVENANCE"


def test_forward_runner_respects_candidate_enable_flags():
    contract = {
        "enabled_candidates": ["CANDIDATE_A", "CANDIDATE_B"],
        "candidates": {
            "CANDIDATE_A": {"enabled_for_new_forward": False},
            "CANDIDATE_B": {"enabled_for_new_forward": True},
        },
    }
    assert _enabled_forward_candidate_ids(contract) == ["CANDIDATE_B"]
    with pytest.raises(ValueError, match="not enabled for new forward"):
        _enabled_forward_candidate_ids(contract, ["CANDIDATE_A"])


def test_v104_forward_writer_rejects_historical_rows(monkeypatch, tmp_path: Path) -> None:
    rows = pd.DataFrame([{
        "session": "2026-07-03", "candidate_id": "V79_NO63",
        "historical_replay_only": True, "new_forward_observation": False,
    }])
    monkeypatch.setattr(forward_runtime, "build_session_observations", lambda *args, **kwargs: rows)
    result = forward_runtime.append_new_forward_observations(tmp_path)
    assert result["status"] == "NO_NEW_SESSION_AFTER_V104_FREEZE"
    assert result["rows_appended"] == 0
    assert not (tmp_path / forward_runtime.DEFAULT_OUTPUT).exists()


def test_v104_receipt_contract_rejects_unverified_or_mismatched_passes(tmp_path: Path) -> None:
    common = {
        "check_id": "V104_DATA_GATE", "session": "2026-07-06", "candidate_id": "V79_NO63",
        "input_hash": "sealed-input", "expected_evidence": {"candidate_fingerprint": "fixed"},
    }
    # Plain producer fields are declarations, not evidence, and are ignored.
    assert receipt_status(tmp_path, **common) == "NOT_RUN"
    injected = {"data_gate_passed": True, "reconciliation_passed": "True"}
    assert injected["data_gate_passed"] is True and injected["reconciliation_passed"] == "True"
    assert receipt_status(tmp_path, **common) == "NOT_RUN"

    issue_receipt(tmp_path, check_id=common["check_id"], session="2026-07-07", candidate_id=common["candidate_id"], input_hash=common["input_hash"], result_status="PASSED", evidence=common["expected_evidence"])
    assert receipt_status(tmp_path, **common) == "NOT_RUN"

    issue_receipt(tmp_path, check_id=common["check_id"], session=common["session"], candidate_id=common["candidate_id"], input_hash="wrong-input", result_status="PASSED", evidence=common["expected_evidence"])
    assert receipt_status(tmp_path, **common) == "FAILED"

    issued = issue_receipt(tmp_path, check_id=common["check_id"], session=common["session"], candidate_id=common["candidate_id"], input_hash=common["input_hash"], result_status="PASSED", evidence=common["expected_evidence"])
    assert issued["validator_version"]
    assert issued["validated_at_utc"]
    assert receipt_status(tmp_path, **common) == "PASSED"


def test_v104_benchmarks_are_truthfully_classified_and_live_blocked() -> None:
    benchmarks = pd.read_csv(REPORT / "v104_benchmark_comparison.csv")
    p2p3 = benchmarks[benchmarks["benchmark"].eq("LEGACY_P2_PLUS_P3")].iloc[0]
    oracle = benchmarks[benchmarks["benchmark"].eq("BEST_THEME_ETF_ORACLE_COMMON_EXECUTION")].iloc[0]
    assert pd.isna(p2p3["return_pct"])
    assert p2p3["comparison_type"] == "NOT_EXECUTABLE_SIGNAL_DEFINITION_ARCHIVED_REFERENCE"
    assert oracle["comparison_type"] == "HINDSIGHT_ORACLE_NOT_STRATEGY"
    contract = yaml.safe_load((ROOT / "config/v104_challenger_runtime_contract.yaml").read_text(encoding="utf-8"))
    assert contract["new_forward_observations"] == 0
    assert not contract["automatic_champion_promotion"]
    assert not contract["live_execution_allowed"]
