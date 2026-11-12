from pathlib import Path

import pandas as pd
import pytest

from quant_harness.v98_candidate_selection_agent.policy import (
    ABLATION_POLICIES,
    EXPECTED_VALUE_ROTATION,
    expected_value_rotation_gate,
)
from quant_harness.v99_candidate_selection_deep_research.engine import _ablation_summary, run

ROOT = Path(__file__).resolve().parents[1]


def test_ablation_summary_includes_every_registered_component():
    rows = []
    metrics = [
        {"policy": "TOP_SCORE_SECTOR_DEDUP", "strategy": strategy}
        for strategy in ("V69", "V79")
    ]
    for policy in ABLATION_POLICIES:
        strategy = "V69" if policy.startswith("ABLATE_V69") else "V79"
        metrics.append({"policy": policy, "strategy": strategy})
    for row in metrics:
        rows.append({
            **row,
            "return_pct": 10.0,
            "validation_return_pct": 2.0,
            "development_return_pct": 3.0,
            "purged_validation_return_pct": 1.5,
            "observed_return_pct": 0.5,
            "recent_1y_return_pct": 1.0,
            "stress_return_pct": 8.0,
            "mdd_pct": -10.0,
            "order_count": 4,
        })
    summary = _ablation_summary(pd.DataFrame(rows))
    assert set(ABLATION_POLICIES).issubset(set(summary["policy"]))


@pytest.fixture(scope="module")
def result(tmp_path_factory):
    return run(ROOT, output_dir=tmp_path_factory.mktemp("v99_reports") / "v99_candidate_selection_deep_research")


def test_v99_quality_and_parent_parity(result):
    assert result["quality"]["passed"].all()
    active = result["metrics"][result["metrics"]["policy"].eq("TOP_SCORE_SECTOR_DEDUP")].set_index("strategy")
    assert active.loc["V69", "ending_nav_krw"] == pytest.approx(76_797_465.61576533, abs=0.01)
    assert active.loc["V79", "ending_nav_krw"] == pytest.approx(85_075_342.0114402, abs=0.01)


def test_v99_error_taxonomy_separates_ranking_rotation_and_timing(result):
    summary = result["error_summary"].set_index(["strategy", "error_type"])
    assert summary.loc[("V69", "ROTATION_ERROR_60D"), "error_count"] == 15
    assert summary.loc[("V79", "RANK_ERROR_60D"), "error_count"] == 103
    assert summary.loc[("V79", "DELAYED_ENTRY_20D"), "error_count"] == 35
    assert summary.loc[("V69", "DELAYED_ENTRY_20D"), "error_count"] == 0


def test_v99_ablation_identifies_v79_short_horizon_as_promising_but_not_cleared(result):
    ablation = result["ablation"].set_index("policy")
    assert ablation.loc["ABLATE_V69_SHORT_COMPONENT", "conclusion"] == "VALUE_ADDING_COMPONENT"
    assert ablation.loc["ABLATE_V79_63_COMPONENT", "conclusion"] == "REDUNDANT_OR_HARMFUL_COMPONENT"
    assert ablation.loc["ABLATE_V79_63_COMPONENT", "validation_delta_pp"] > 10.0
    promotion = result["promotion"].set_index(["policy", "strategy"])
    row = promotion.loc[("ABLATE_V79_63_COMPONENT", "V79")]
    assert row["status"] == "FORWARD_SHADOW_ONLY_MULTIPLE_TESTING_NOT_CLEARED"
    assert not bool(row["backtest_passed"])
    assert row["stress_delta_pp"] > 100.0
    assert row["validation_bootstrap_probability"] < 0.90
    assert row["familywise_probability_lower_bound"] == pytest.approx(0.0)


def test_v99_candidates_c_d_e_are_rejected_without_parent_mutation(result):
    promotion = result["promotion"]
    cde = promotion[promotion["policy"].isin([
        "TREND_QUALITY_SCORE", "SECTOR_RESIDUAL_MOMENTUM", "EXPECTED_VALUE_ROTATION"
    ])]
    assert set(cde["status"]) == {"BACKTEST_REJECTED"}
    assert not cde["promoted"].any()
    metrics = result["metrics"].set_index(["policy", "strategy"])
    assert metrics.loc[("TREND_QUALITY_SCORE", "V69"), "return_pct"] < metrics.loc[("TOP_SCORE_SECTOR_DEDUP", "V69"), "return_pct"]
    assert metrics.loc[("SECTOR_RESIDUAL_MOMENTUM", "V79"), "return_pct"] < metrics.loc[("TOP_SCORE_SECTOR_DEDUP", "V79"), "return_pct"]


def test_v99_expected_value_gate_is_strictly_schedule_driven_and_deterministic():
    ranked = [("A", "s1", 0.9, 1.0), ("B", "s2", 0.5, 1.0), ("C", "s3", 0.3, 1.0)]
    date = pd.Timestamp("2026-01-05")
    schedule = {
        "2026-01-05": {
            "sample_count": 40,
            "intercept": 0.0,
            "coef_gap": 0.01,
            "coef_normalized_gap": 0.0,
        }
    }
    allowed, predicted, samples, reason = expected_value_rotation_gate(
        date, ranked, "B", policy=EXPECTED_VALUE_ROTATION,
        schedule=schedule, minimum_samples=30, cost_buffer_return=0.008,
    )
    assert samples == 40
    assert predicted == pytest.approx(0.004)
    assert not allowed
    assert reason == "EXPECTED_VALUE_BELOW_COST"
