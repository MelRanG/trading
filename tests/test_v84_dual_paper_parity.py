from pathlib import Path
import json
import pandas as pd
from quant_harness.v84_dual_paper_parity.engine import (
    ExecutionPolicy, PortfolioState, execute_target_map, run,
)
from quant_harness.v77_corrected_price_allocation.engine import _load_config

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/"tests/fixtures/archived_release_reports/v84_dual_paper_parity"

def test_v84_full_run_parity_and_canonical():
    result=json.loads((REPORT/"summary.json").read_text())
    assert all(result["gates"].values())
    parity=pd.read_csv(REPORT/"execution_parity.csv")
    assert parity.abs_error_krw.max() < 0.01
    canonical=pd.read_csv(ROOT/"data/canonical/v84_market_bars.csv",dtype={"ticker":str})
    assert not canonical.duplicated(["date","ticker"]).any()
    assert set(canonical.price_scale)=={"ADJUSTED_OHLC"}

def test_common_execution_is_deterministic_and_affordable():
    policy=ExecutionPolicy.from_v77(_load_config(ROOT).base_execution)
    state=PortfolioState(10_000_000)
    kwargs=dict(targets={"069500":.2,"395160":.8},open_prices={"069500":10000,"395160":50000},adv20_d1={"069500":1e9,"395160":1e9},policy=policy,rebalance_band=0,buy_priority="CORE_THEN_TARGET_DESC",core_ticker="069500")
    a,fills_a,audit_a=execute_target_map(state,**kwargs)
    b,fills_b,audit_b=execute_target_map(PortfolioState(10_000_000),**kwargs)
    assert a==b and fills_a==fills_b and audit_a==audit_b
    assert a.cash >= -0.01
    assert all(x.participation_of_d1_adv <= policy.max_participation_of_d1_adv+1e-12 for x in fills_a)

def test_v84_registry_contains_exactly_two_runtime_candidates():
    import yaml
    reg=yaml.safe_load((ROOT/"config/strategy_registry_v84.yaml").read_text())
    assert {x["strategy_id"] for x in reg["strategies"]}=={"v69_fixed80_daily_control","v79_core70_generic_trend30"}
    assert all(x["runtime_compatible"] for x in reg["strategies"])
    assert not reg["live_execution_allowed"]
