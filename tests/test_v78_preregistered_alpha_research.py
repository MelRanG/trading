from __future__ import annotations

from pathlib import Path
import json

import pandas as pd
import yaml

from quant_harness.v78_preregistered_alpha_research.engine import run

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports/v78_preregistered_alpha_research"


def _ensure() -> dict:
    path = REPORT / "v78_decision.json"
    if not path.exists():
        run(ROOT)
    return json.loads(path.read_text(encoding="utf-8"))


def test_exactly_three_preregistered_alpha_candidates() -> None:
    decision = _ensure()
    cfg = yaml.safe_load((ROOT / "config/v78_preregistered_alpha_research.yaml").read_text(encoding="utf-8"))
    gates = pd.read_csv(REPORT / "v78_alpha_promotion_gates.csv")
    assert set(gates["candidate"]) == set(cfg["alpha_candidates"])
    assert len(gates) == 3
    assert decision["promoted_alpha_candidates"] == []


def test_all_alpha_decisions_are_strictly_d1() -> None:
    _ensure()
    for name in ["baseline", "residual", "cross_ts_ensemble", "vol_managed"]:
        ledger = pd.read_csv(REPORT / f"v78_selection_{name}.csv", parse_dates=["date", "information_cutoff"])
        used = ledger.dropna(subset=["information_cutoff"])
        assert (used["information_cutoff"] < used["date"]).all()
        assert not ledger["decision_uses_same_day_close"].astype(bool).any()


def test_feedback_signal_is_shifted_to_d1() -> None:
    _ensure()
    gates = pd.read_csv(REPORT / "v78_quality_gates.csv")
    row = gates[gates["gate"].eq("FEEDBACK_SIGNAL_D1_ONLY")].iloc[0]
    assert bool(row["passed"])


def test_active_agent_contract_coverage_and_ablation() -> None:
    _ensure()
    contracts = pd.read_csv(REPORT / "v78_agent_contracts.csv")
    coverage = pd.read_csv(REPORT / "v78_agent_coverage.csv")
    ablation = pd.read_csv(REPORT / "v78_existing_agent_ablation.csv")
    assert contracts["agent"].nunique() == 8
    assert coverage["agent_count"].eq(8).all()
    assert len(ablation) == 5
    assert not ablation["improves_return_sharpe_mdd"].astype(bool).any()


def test_corrected_execution_order_math_for_every_replayed_strategy() -> None:
    _ensure()
    for path in REPORT.glob("v78_orders_*.csv"):
        orders = pd.read_csv(path)
        if orders.empty:
            continue
        expected = orders["quantity"] * orders["reference_open_krw"]
        assert (expected - orders["notional_at_reference_open_krw"]).abs().max() <= 0.01
        valid = orders["adv20_d1_krw"].gt(0)
        participation = expected[valid] / orders.loc[valid, "adv20_d1_krw"]
        assert (participation - orders.loc[valid, "participation_of_d1_adv"]).abs().max() <= 1e-12
        assert orders["participation_of_d1_adv"].dropna().le(0.0100000001).all()


def test_v78_does_not_hide_recent_benchmark_underperformance() -> None:
    _ensure()
    metrics = pd.read_csv(REPORT / "v78_all_strategy_metrics.csv").set_index("scenario")
    for candidate in ["V78_A_RESIDUAL_MOMENTUM", "V78_B_CROSS_TS_ENSEMBLE", "V78_C_VOL_MANAGED"]:
        assert metrics.loc[candidate, "recent_1y_return_pct"] < metrics.loc["SEMICONDUCTOR_ETF_BUY_HOLD", "recent_1y_return_pct"]
