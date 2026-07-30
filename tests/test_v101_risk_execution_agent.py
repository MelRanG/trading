from pathlib import Path
import json

import pandas as pd
import pytest

from quant_harness.v77_corrected_price_allocation import engine as v77
from quant_harness.v84_dual_paper_parity.engine import execute_target_map as runtime_execute_target_map, PortfolioState, ExecutionPolicy
from quant_harness.v101_risk_execution_agent.engine import (
    ACTIVE_POLICY,
    AgentExecutionPolicy,
    AgentPortfolioState,
    execute_target_map,
)

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports/v101_risk_execution_agent"


def test_v101_parent_parity_and_live_blocked():
    parity = pd.read_csv(REPORT / "v101_parent_parity.csv")
    gates = pd.read_csv(REPORT / "v101_quality_gates.csv")
    assert parity["abs_error_krw"].le(0.01).all()
    assert gates["passed"].all()
    registry = json.loads((REPORT / "v101_risk_execution_registry.json").read_text())
    assert registry["active_policy"] == ACTIVE_POLICY
    assert registry["live_authority"] is False


def test_v101_candidates_do_not_mutate_parent():
    promotion = pd.read_csv(REPORT / "v101_candidate_promotion.csv")
    assert not promotion["promoted"].any()
    band = promotion[(promotion.policy == "V69_REBALANCE_BAND_2PP") & (promotion.strategy == "V69")].iloc[0]
    assert band.order_reduction_ratio > 0.50
    assert band.status == "FORWARD_SHADOW_ONLY_BOOTSTRAP_NOT_CLEARED"
    dynamic = promotion[(promotion.policy == "DYNAMIC_MIN_ORDER_50BPS_NAV") & (promotion.strategy == "V79")].iloc[0]
    assert dynamic.status == "BACKTEST_REJECTED"


def test_execution_fail_closed_on_missing_adv_and_missing_open():
    spec = v77.ExecutionSpec(1.5, 21.5, 5.0, 10.0, 50.0, 0.01, 100000.0)
    policy = AgentExecutionPolicy(ACTIVE_POLICY, 0.0, 0.05, 100000.0, 0.0, "CORE_THEN_TARGET_DESC", "DEFICIT_DESC", True)
    state = AgentPortfolioState(10_000_000.0, {})
    next_state, fills, intents, _ = execute_target_map(
        state, targets={"069500": 1.0}, open_prices={"069500": 10000.0}, adv20_d1={"069500": float("nan")},
        spec=spec, policy=policy, rebalance_band=0.0, buy_priority="CORE_THEN_TARGET_DESC", core_ticker="069500",
    )
    assert not fills
    assert next_state.pending
    assert intents[0]["decision"] == "MISSING_OR_ZERO_D1_ADV"
    with pytest.raises(ValueError):
        execute_target_map(
            state, targets={"069500": 1.0}, open_prices={}, adv20_d1={"069500": 1e9},
            spec=spec, policy=policy, rebalance_band=0.0, buy_priority="CORE_THEN_TARGET_DESC", core_ticker="069500",
        )


def test_dynamic_minimum_order_is_intentional_no_trade_not_blind_backlog():
    spec = v77.ExecutionSpec(1.5, 21.5, 5.0, 10.0, 50.0, 0.01, 100000.0)
    policy = AgentExecutionPolicy("DYNAMIC_MIN_ORDER_50BPS_NAV", 0.0, 0.05, 100000.0, 0.005, "CORE_THEN_TARGET_DESC", "DEFICIT_DESC", False)
    state = AgentPortfolioState(50_000.0, {"069500": 995})
    next_state, fills, intents, _ = execute_target_map(
        state, targets={"069500": 1.0}, open_prices={"069500": 10000.0}, adv20_d1={"069500": 1e12},
        spec=spec, policy=policy, rebalance_band=0.0, buy_priority="CORE_THEN_TARGET_DESC", core_ticker="069500",
    )
    assert not fills
    assert not next_state.pending
    assert intents[0]["decision"] == "BELOW_MIN_ORDER_THRESHOLD"


def test_capacity_and_real_data_contract_are_explicit():
    capacity = pd.read_csv(REPORT / "v101_capacity_diagnostics.csv")
    v69 = capacity[capacity.strategy == "V69"].sort_values("initial_capital_krw")
    assert v69.iloc[-1].participation_limited_intents > v69.iloc[0].participation_limited_intents
    contract = (ROOT / "config/v101_broker_execution_contract.yaml").read_text()
    checklist = (ROOT / "docs/REAL_DATA_EXECUTION_CHECKLIST.md").read_text(encoding="utf-8")
    assert "UNVERIFIED_EXTERNAL" in contract
    assert "v101_execution_observation_template.csv" in checklist


def test_v84_runtime_emits_v101_execution_policy():
    spec = v77.ExecutionSpec(1.5, 21.5, 5.0, 10.0, 50.0, 0.01, 100000.0)
    state, fills, audit = runtime_execute_target_map(
        PortfolioState(10_000_000.0), targets={"069500": 1.0}, open_prices={"069500": 10000.0},
        adv20_d1={"069500": 1e12}, policy=ExecutionPolicy.from_v77(spec), rebalance_band=0.0,
        buy_priority="CORE_THEN_TARGET_DESC", core_ticker="069500",
    )
    assert audit["risk_execution_policy"] == "PARENT_EXECUTION_CONTRACT"
    assert state.cash >= -0.01
