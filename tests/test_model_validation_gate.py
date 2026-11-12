from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pandas as pd

from quant_harness.model_validation_gate import _cost_terms, _period_metrics, _regime
from quant_harness.v77_corrected_price_allocation import engine as v77


ROOT = Path(__file__).resolve().parents[1]


def test_regime_comparison_uses_the_frozen_v95_policy_not_legacy_v90_labels() -> None:
    previews = {"2018-01-02": {"regime": "DATA_NOT_READY", "selected_candidates": []}}
    trades = pd.DataFrame(columns=["replay_date", "status"])
    frame, summary = _regime(ROOT, [pd.Timestamp("2018-01-02").date()], previews, trades)
    assert frame.iloc[0]["runtime_regime"] == "DATA_NOT_READY"
    assert bool(frame.iloc[0]["normalized_match"]) is True
    assert summary["mapping"] == {}
    assert summary["baseline"].endswith("v95_regime_ledger_d1_ma120_explicit.csv")


def test_calmar_uses_cagr_not_total_return() -> None:
    nav = pd.DataFrame({"as_of": [pd.Timestamp("2020-01-01").date(), pd.Timestamp("2020-07-01").date(), pd.Timestamp("2022-01-01").date()], "nav_krw": [Decimal("100"), Decimal("80"), Decimal("140")]})
    benchmark = pd.Series([100.0, 95.0, 105.0], index=pd.to_datetime(["2020-01-01", "2020-07-01", "2022-01-01"]))
    from quant_harness.model_validation_gate import _risk_details
    result = _risk_details(nav, benchmark)
    assert 0 < result["strategy_calmar"] < 2


def test_cost_terms_stress_doubles_only_cost_parameters() -> None:
    spec = v77._load_config(ROOT).base_execution
    base = _cost_terms(Decimal("100"), Decimal("10000"), Decimal("100000000"), spec, "BUY")
    stress = _cost_terms(Decimal("100"), Decimal("10000"), Decimal("100000000"), spec, "BUY", Decimal("2"))
    assert stress[1] > base[1]
    assert stress[2] > base[2]


def test_period_metrics_are_read_only_calculation() -> None:
    nav = pd.DataFrame({"as_of": [pd.Timestamp("2020-01-01").date(), pd.Timestamp("2020-01-02").date()], "nav_krw": [Decimal("100"), Decimal("110")]})
    benchmark = pd.Series([100.0, 105.0], index=pd.to_datetime(["2020-01-01", "2020-01-02"]))
    result = _period_metrics(nav, benchmark)
    assert abs(result["return"] - 0.1) < 1e-12
    assert abs(result["benchmark_return"] - 0.05) < 1e-12
