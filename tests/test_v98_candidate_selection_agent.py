from pathlib import Path

import pandas as pd
import pytest

from quant_harness.v98_candidate_selection_agent.engine import run
from quant_harness.v98_candidate_selection_agent.policy import (
    ACTIVE_SELECTION_POLICY,
    build_sector_representative_panel,
    effective_rotation_margin,
    prepare_selection_features,
    validate_taxonomy,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def result():
    return run(ROOT)


def test_v98_quality_parent_parity_and_sector_merge(result):
    assert result["quality"]["passed"].all()
    active = result["metrics"][result["metrics"]["policy"].eq(ACTIVE_SELECTION_POLICY)].set_index("strategy")
    assert active.loc["V69", "ending_nav_krw"] == pytest.approx(76_797_465.62, abs=0.02)
    assert active.loc["V79", "ending_nav_krw"] == pytest.approx(85_075_342.01, abs=0.02)
    assert "v97_sector_theme_agent" not in [p.name for p in (ROOT / "src/quant_harness").iterdir()]


def test_v98_candidates_are_not_promoted_and_uncertainty_is_shadow_only(result):
    promotion = result["promotion"].set_index(["policy", "strategy"])
    assert not promotion["promoted"].any()
    assert promotion.loc[("CROSS_HORIZON_CONSENSUS", "V69"), "status"] == "BACKTEST_REJECTED"
    assert promotion.loc[("CROSS_HORIZON_CONSENSUS", "V79"), "validation_delta_pp"] < 0
    assert promotion.loc[("UNCERTAINTY_AWARE_ROTATION", "V69"), "status"] == "FORWARD_SHADOW_ONLY"
    assert promotion.loc[("UNCERTAINTY_AWARE_ROTATION", "V79"), "status"] == "FORWARD_SHADOW_ONLY"


def test_v98_taxonomy_and_sector_dedup_are_candidate_selection_subpolicy():
    universe = pd.DataFrame({"ticker": ["A", "B", "C"], "sector": ["s", "s", "t"]})
    assert validate_taxonomy(universe)["valid"]
    index = pd.to_datetime(["2026-01-02", "2026-01-05"])
    score = pd.DataFrame({"A": [0.1, 0.2], "B": [0.2, 0.1], "C": [0.15, 0.15]}, index=index)
    eligible = pd.DataFrame(True, index=index, columns=["A", "B", "C"])
    liquidity = pd.DataFrame(1.0, index=index, columns=["A", "B", "C"])
    panel = build_sector_representative_panel(index, [index[1]], universe, score, eligible, liquidity)
    day = panel[panel["date"].eq(index[1])]
    assert len(day) == 2
    assert day.loc[day["sector"].eq("s"), "representative_ticker"].iloc[0] == "A"
    assert not day["decision_uses_same_day_close"].any()


def test_v98_uncertainty_margin_and_consensus_are_deterministic():
    ranked = [("A", "s1", 0.8, 1.0), ("B", "s2", 0.75, 1.0), ("C", "s3", 0.4, 1.0), ("D", "s4", 0.2, 1.0)]
    margin = effective_rotation_margin(ranked, base_margin=0.0, policy="UNCERTAINTY_AWARE_ROTATION", iqr_multiplier=0.25)
    assert margin > 0
    features = {
        "score": pd.DataFrame({"A": [0.8], "B": [0.7]}),
        "eligible": pd.DataFrame({"A": [True], "B": [True]}),
        "liquidity": pd.DataFrame({"A": [1.0], "B": [1.0]}),
        "rel_short": pd.DataFrame({"A": [0.2], "B": [0.1]}),
        "rel_medium": pd.DataFrame({"A": [0.3], "B": [0.2]}),
        "rel_long": pd.DataFrame({"A": [0.4], "B": [-0.1]}),
    }
    result = prepare_selection_features(features, family="V69", policy="CROSS_HORIZON_CONSENSUS")
    assert bool(result["selection_eligible"].iloc[0]["A"])
    assert not bool(result["selection_eligible"].iloc[0]["B"])
