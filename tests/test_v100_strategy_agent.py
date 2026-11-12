from pathlib import Path

import pytest

from quant_harness.v84_dual_paper_parity.engine import build_strategy_ledgers
from quant_harness.v100_strategy_agent.engine import run

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def result(tmp_path_factory):
    return run(ROOT, output_dir=tmp_path_factory.mktemp("v100_reports") / "v100_strategy_agent")


def test_v100_quality_and_parent_parity(result):
    assert result["quality"]["passed"].all()
    active = result["metrics"][result["metrics"]["policy"].eq("FIXED_PARENT_ALLOCATIONS")].set_index("strategy")
    assert active.loc["V69", "ending_nav_krw"] == pytest.approx(76_797_465.61576533, abs=0.01)
    assert active.loc["V79", "ending_nav_krw"] == pytest.approx(85_075_342.0114402, abs=0.01)


def test_v100_detects_hidden_component_overlap(result):
    full = result["diagnostics"][(result["diagnostics"]["policy"].eq("FIXED_PARENT_ALLOCATIONS")) & (result["diagnostics"]["period"].eq("FULL"))].set_index("strategy")
    assert full.loc["V79", "same_ticker_overlap_days"] == 203
    assert full.loc["V79", "same_sector_overlap_days"] == 456
    assert full.loc["V79", "max_semantic_sector_weight"] == pytest.approx(0.86)


def test_v100_candidates_are_rejected_without_parent_mutation(result):
    promotion = result["promotion"].set_index(["policy", "strategy"])
    assert promotion.loc[("FULL_LEADER_100", "V69"), "status"] == "BACKTEST_REJECTED"
    assert promotion.loc[("UNCERTAINTY_BUDGET_60_80", "V79"), "status"] == "BACKTEST_REJECTED"
    assert promotion.loc[("V79_SEMANTIC_SECTOR_CAP_70", "V79"), "status"] == "BACKTEST_REJECTED"
    assert not promotion["promoted"].any()
    assert promotion.loc[("FULL_LEADER_100", "V69"), "full_delta_pp"] > 70.0
    assert promotion.loc[("FULL_LEADER_100", "V69"), "recent1y_delta_pp"] < -9.0


def test_v100_sector_cap_is_exact_but_not_profitable(result):
    ledger = result["runs"]["V79_SEMANTIC_SECTOR_CAP_70"]["ledger79"]
    assert ledger["max_semantic_sector_weight"].max() <= 0.7000000001
    assert int(ledger["concentration_cap_applied"].sum()) == 456
    metrics = result["metrics"].set_index(["policy", "strategy"])
    assert metrics.loc[("V79_SEMANTIC_SECTOR_CAP_70", "V79"), "return_pct"] < metrics.loc[("FIXED_PARENT_ALLOCATIONS", "V79"), "return_pct"]


def test_v84_runtime_uses_v100_active_target_contract():
    _market, _universe, ledger69, ledger79, _selection = build_strategy_ledgers(ROOT)
    assert set(ledger69["strategy_policy"]) == {"FIXED_PARENT_ALLOCATIONS"}
    assert set(ledger79["strategy_policy"]) == {"FIXED_PARENT_ALLOCATIONS"}
    assert (ledger69["target_weight_sum"] - 1.0).abs().max() <= 1e-12
    assert (ledger79["target_weight_sum"] - 1.0).abs().max() <= 1e-12
