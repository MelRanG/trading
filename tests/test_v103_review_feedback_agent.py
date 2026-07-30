from pathlib import Path
import json

import numpy as np
import pandas as pd
import yaml

from quant_harness.v103_review_feedback_agent.engine import (
    _block_bootstrap_positive_probability,
    _forward_lifecycle,
    run,
)
from quant_harness.v103_review_feedback_agent.policy import ACTIVE_REVIEW_FEEDBACK_POLICY

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports/v103_review_feedback_agent"


def test_v103_full_governance_run_and_live_blocked():
    summary = run(ROOT)
    gates = pd.read_csv(REPORT / "v103_quality_gates.csv")
    assert summary["quality_gates_passed"] is True
    assert summary["promoted_candidates"] == 0
    assert summary["parents_changed"] is False
    assert summary["live_allowed"] is False
    assert gates["passed"].all()


def test_v103_reconstructs_trial_memory_and_multiple_testing():
    attempts = pd.read_csv(REPORT / "v103_research_attempt_ledger.csv")
    audit = pd.read_csv(REPORT / "v103_multiple_testing_audit.csv")
    memory = json.loads((REPORT / "v103_research_memory.json").read_text(encoding="utf-8"))
    assert len(attempts) == 39
    assert int(attempts["counts_as_unique_trial"].sum()) == 36
    assert set(audit["strategy"]) == {"V69", "V79"}
    assert (audit["unique_historical_trials"] == 21).all()
    assert (audit["historical_promotion_allowed"] == False).all()  # noqa: E712
    assert memory["cumulative_unique_trials"] == 36
    assert memory["next_cycle_rules"]["same_history_retuning_forbidden"] is True


def test_v103_forward_queue_is_chronological_not_performance_ranked():
    life = pd.read_csv(REPORT / "v103_candidate_lifecycle.csv")
    v69 = life[life.parent_strategy.eq("V69")].sort_values("queue_rank")
    v79 = life[life.parent_strategy.eq("V79")].sort_values("queue_rank")
    assert v69.policy.tolist()[:3] == [
        "MA120_VOLATILITY_GUARD_35PCT",
        "UNCERTAINTY_AWARE_ROTATION",
        "V69_REBALANCE_BAND_2PP",
    ]
    assert v79.policy.tolist() == [
        "MA120_VOLATILITY_GUARD_35PCT",
        "UNCERTAINTY_AWARE_ROTATION",
        "ABLATE_V79_63_COMPONENT",
    ]
    assert (life.groupby("parent_strategy").apply(lambda x: int(x.forward_status.str.contains("RUNTIME_BLOCKED").sum()), include_groups=False) <= 3).all()
    assert not life["promotion_from_historical_allowed"].any()
    assert not life["automatic_promotion_allowed"].any()


def test_v103_does_not_claim_forward_ready_without_runtime_adapter():
    life = pd.read_csv(REPORT / "v103_candidate_lifecycle.csv")
    active = life[life.queue_rank.le(3)]
    assert active.forward_status.eq("FORWARD_CONTRACT_READY_RUNTIME_BLOCKED").all()
    assert active.adapter_status.eq("UNIMPLEMENTED").all()
    assert active.promotion_decision.eq("BLOCKED_RUNTIME_ADAPTER_UNIMPLEMENTED").all()
    assert not active.candidate_runtime_compatible.any()
    registry = json.loads((REPORT / "v103_forward_shadow_registry.json").read_text(encoding="utf-8"))
    assert registry["active_policy"] == ACTIVE_REVIEW_FEEDBACK_POLICY
    assert registry["automatic_parent_mutation"] is False
    assert registry["automatic_capital_authority"] is False


def _synthetic_attempts() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "candidate_fingerprint": "source-a", "strategy": "V69", "policy": "POLICY_A", "agent_scope": "TEST",
            "source_release": "V103", "source_release_number": 103, "source_report": "a.csv", "source_row": 1,
            "status": "FORWARD_SHADOW_ONLY", "raw_bootstrap_probability": 0.95, "counts_as_unique_trial": True,
            "forward_candidate": True,
        },
        {
            "candidate_fingerprint": "source-b", "strategy": "V69", "policy": "POLICY_B", "agent_scope": "TEST",
            "source_release": "V103", "source_release_number": 103, "source_report": "b.csv", "source_row": 2,
            "status": "FORWARD_SHADOW_ONLY", "raw_bootstrap_probability": 0.95, "counts_as_unique_trial": True,
            "forward_candidate": True,
        },
    ])


def test_v103_forward_holm_gate_and_human_only_promotion(tmp_path):
    cfg = yaml.safe_load((ROOT / "config/v103_review_feedback_agent.yaml").read_text(encoding="utf-8"))
    cfg["paths"]["forward_observations"] = "runtime/v103_review_feedback/forward_observations.csv"
    (tmp_path / "config").mkdir()
    (tmp_path / "runtime/v103_review_feedback").mkdir(parents=True)
    candidate_ids = ["feedback_v69_policy_a", "feedback_v69_policy_b"]
    contract = {
        "candidates": {cid: {"adapter_status": "IMPLEMENTED_AND_TESTED"} for cid in candidate_ids}
    }
    (tmp_path / "config/v103_shadow_runtime_contract.yaml").write_text(yaml.safe_dump(contract), encoding="utf-8")

    initial = _forward_lifecycle(_synthetic_attempts(), cfg, tmp_path)
    fingerprints = dict(zip(initial.candidate_id, initial.candidate_fingerprint))
    sessions = pd.bdate_range("2026-07-20", periods=130)
    rows = []
    for j, cid in enumerate(candidate_ids):
        parent_nav = 10_000_000 * np.cumprod(np.full(len(sessions), 1.0001))
        candidate_nav = 10_000_000 * np.cumprod(np.full(len(sessions), 1.0010 + j * 0.0001))
        for i, day in enumerate(sessions):
            rows.append({
                "session": day.date().isoformat(), "candidate_id": cid,
                "candidate_fingerprint": fingerprints[cid], "parent_strategy_id": "V69",
                "parent_fingerprint": "parent", "parent_nav_krw": parent_nav[i], "candidate_nav_krw": candidate_nav[i],
                "parent_daily_return": 0.0001, "candidate_daily_return": 0.0010 + j * 0.0001,
                "parent_execution_cost_krw": 100, "candidate_execution_cost_krw": 100,
                "parent_order_count": 1, "candidate_order_count": 1,
                "changed_decision": i < 12, "matured_20d": i < 10, "matured_60d": i < 10,
                "parent_mdd_pct": -5.0, "candidate_mdd_pct": -4.0,
                "data_gate_passed": True, "reconciliation_passed": True,
                "source_data_hash": "data", "decision_hash": f"d-{cid}-{i}", "observed_at_utc": "2026-07-20T00:00:00Z",
            })
    pd.DataFrame(rows).to_csv(tmp_path / cfg["paths"]["forward_observations"], index=False)
    evaluated = _forward_lifecycle(_synthetic_attempts(), cfg, tmp_path)
    assert evaluated.forward_sessions.eq(130).all()
    assert evaluated.raw_promotion_review_ready.all()
    assert evaluated.holm_passed.all()
    assert evaluated.promotion_decision.eq("HUMAN_PROMOTION_REVIEW_ELIGIBLE").all()
    assert evaluated.capital_authority.eq("NONE").all()
    assert not evaluated.automatic_promotion_allowed.any()


def test_v103_fingerprint_mismatch_fails_closed(tmp_path):
    cfg = yaml.safe_load((ROOT / "config/v103_review_feedback_agent.yaml").read_text(encoding="utf-8"))
    (tmp_path / "config").mkdir()
    (tmp_path / "runtime/v103_review_feedback").mkdir(parents=True)
    (tmp_path / "config/v103_shadow_runtime_contract.yaml").write_text(
        yaml.safe_dump({"candidates": {"feedback_v69_policy_a": {"adapter_status": "IMPLEMENTED_AND_TESTED"}}}),
        encoding="utf-8",
    )
    attempts = _synthetic_attempts().iloc[[0]].copy()
    pd.DataFrame([{
        "session": "2026-07-20", "candidate_id": "feedback_v69_policy_a", "candidate_fingerprint": "WRONG",
        "parent_nav_krw": 10_000_000, "candidate_nav_krw": 10_001_000,
        "parent_daily_return": 0.0, "candidate_daily_return": 0.001,
        "changed_decision": True, "matured_20d": False, "matured_60d": False,
        "parent_mdd_pct": 0.0, "candidate_mdd_pct": 0.0,
        "data_gate_passed": True, "reconciliation_passed": True,
    }]).to_csv(tmp_path / cfg["paths"]["forward_observations"], index=False)
    result = _forward_lifecycle(attempts, cfg, tmp_path).iloc[0]
    assert result.fingerprint_conflicts == 1
    assert result.promotion_decision == "BLOCKED_CANDIDATE_FINGERPRINT_MISMATCH"


def test_block_bootstrap_requires_mature_sample():
    assert _block_bootstrap_positive_probability(pd.Series([0.01] * 19)) == 0.0
    assert _block_bootstrap_positive_probability(pd.Series([0.001] * 120)) == 1.0
