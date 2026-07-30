from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from quant_harness.v83_independent_self_research.engine import run


ROOT = Path(__file__).resolve().parents[1]


def _artifact_fingerprint() -> str:
    files = [
        ROOT / "src/quant_harness/v83_independent_self_research/engine.py",
        ROOT / "config/v83_independent_self_research.yaml",
        ROOT / "config/v69_dynamic_theme_leadership.yaml",
        ROOT / "config/v79_generic_trend_sleeve.yaml",
        ROOT / "config/v77_corrected_price_allocation.yaml",
        ROOT / "data/toss_v19c_daily/universe.csv",
    ]
    digest = hashlib.sha256()
    for path in files:
        digest.update(str(path.relative_to(ROOT)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


@pytest.fixture(scope="module", autouse=True)
def v83_result() -> dict:
    manifest_path = ROOT / "reports/v83_independent_self_research/v83_artifact_manifest.json"
    decision_path = ROOT / "reports/v83_independent_self_research/v83_decision.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    if not decision_path.exists() or manifest.get("input_fingerprint") != _artifact_fingerprint():
        result = run(ROOT)
        manifest_path.write_text(json.dumps({"schema_version": 1, "input_fingerprint": _artifact_fingerprint()}, indent=2), encoding="utf-8")
        return result
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    return {"quality_gates_passed": bool(decision.get("quality_gates_passed", True)), "artifact_reused": True}


def _read(name: str) -> pd.DataFrame:
    return pd.read_csv(ROOT / "reports/v83_independent_self_research" / name)


def test_v83_decision_and_all_quality_gates_pass(v83_result: dict) -> None:
    assert v83_result["quality_gates_passed"] is True
    gates = _read("v83_quality_gates.csv")
    assert gates["passed"].astype(bool).all()


def test_parent_lineage_is_reproduced() -> None:
    gates = _read("v83_quality_gates.csv").set_index("gate")
    assert bool(gates.loc["PARENT_LINEAGE_REPRODUCED", "passed"])
    metrics = _read("v83_strategy_metrics.csv").set_index("scenario")
    prior = pd.read_csv(ROOT / "reports/v79_generic_trend_sleeve/v79_all_strategy_metrics.csv").set_index("scenario")
    assert abs(metrics.loc["V69_PARENT", "return_pct"] - prior.loc["V69_FIXED80_DAILY_CORRECTED", "return_pct"]) <= 0.50
    assert abs(metrics.loc["V79_PARENT", "return_pct"] - prior.loc["V79_GENERIC_TREND_BASE70_SLEEVE30", "return_pct"]) <= 0.01


def test_each_feedback_family_only_proposes_its_own_candidates() -> None:
    folds = _read("v83_walk_forward_proposals_and_promotions.csv")
    for row in folds.itertuples(index=False):
        assert str(row.active_strategy).startswith(str(row.family))
        assert str(row.proposed_candidate).startswith(str(row.family))
        assert str(row.next_active_strategy).startswith(str(row.family))


def test_promotion_is_applied_one_fold_later_only() -> None:
    folds = _read("v83_walk_forward_proposals_and_promotions.csv")
    for _, family in folds.groupby("family"):
        family = family.sort_values("test_year").reset_index(drop=True)
        for i in range(1, len(family)):
            assert family.loc[i, "active_strategy"] == family.loc[i - 1, "next_active_strategy"]


def test_feedback_evidence_is_purged_and_matured() -> None:
    folds = _read("v83_walk_forward_proposals_and_promotions.csv")
    assert (pd.to_datetime(folds["evidence_cutoff"]) < pd.to_datetime(folds["test_start"])).all()
    issues = _read("v83_self_issue_scores.csv")
    if not issues.empty:
        assert (pd.to_datetime(issues["evidence_cutoff"]) < pd.to_datetime(issues["test_year"].astype(str) + "-01-01")).all()


def test_own_outcome_ledgers_never_cross_families() -> None:
    for family in ("v69", "v79"):
        for path in (ROOT / "reports/v83_independent_self_research").glob(f"v83_own_outcomes_{family}_*.csv"):
            frame = pd.read_csv(path)
            assert frame["family"].eq(family.upper()).all()
            assert frame["scenario"].str.startswith(family.upper()).all()


def test_future_mutation_and_vendor_robustness_gates_pass() -> None:
    gates = _read("v83_quality_gates.csv").set_index("gate")
    required = [
        "FUTURE_MUTATION_DOES_NOT_CHANGE_PAST_TARGETS",
        "PRICE_VOLUME_SCALE_INVARIANT_TARGETS",
        "SMALL_VENDOR_NOISE_TARGET_STABILITY",
        "V69_SMALL_NOISE_RETURN_STABILITY",
        "V79_SMALL_NOISE_RETURN_STABILITY",
    ]
    for gate in required:
        assert bool(gates.loc[gate, "passed"]), gate


def test_all_targets_are_d1_and_sum_to_one() -> None:
    report = ROOT / "reports/v83_independent_self_research"
    for path in report.glob("v83_target_*.csv"):
        frame = pd.read_csv(path)
        assert (frame["target_weight_sum"] - 1.0).abs().max() <= 1e-12
        valid = frame["information_cutoff"].notna()
        assert (pd.to_datetime(frame.loc[valid, "information_cutoff"]) < pd.to_datetime(frame.loc[valid, "date"])).all()


def test_no_live_or_registry_auto_change() -> None:
    decision = json.loads((ROOT / "reports/v83_independent_self_research/v83_decision.json").read_text(encoding="utf-8"))
    assert decision["live_allowed"] is False
    assert decision["automatic_registry_change"] is False
