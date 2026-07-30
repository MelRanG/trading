from pathlib import Path
import json

import numpy as np
import pandas as pd

from quant_harness.v95_market_regime_agent.policy import build_market_regime_panel

ROOT = Path(__file__).resolve().parents[1]


def _toy() -> tuple[pd.DataFrame, pd.DataFrame]:
    idx = pd.bdate_range("2022-01-03", periods=220)
    bench = np.linspace(100.0, 145.0, len(idx))
    close = pd.DataFrame({"KS11": bench, "A": np.linspace(50, 80, len(idx)), "B": np.linspace(70, 90, len(idx))}, index=idx)
    gate = pd.DataFrame(True, index=idx, columns=["A", "B"])
    return close, gate


def test_market_regime_is_d1_causal() -> None:
    close, gate = _toy()
    base = build_market_regime_panel(close, benchmark_ticker="KS11", theme_tickers=["A", "B"], universe_gate_d1=gate)["risk_on"]
    changed = close.copy()
    changed.iloc[-1, changed.columns.get_loc("KS11")] *= 0.1
    changed_signal = build_market_regime_panel(changed, benchmark_ticker="KS11", theme_tickers=["A", "B"], universe_gate_d1=gate)["risk_on"]
    assert bool(base.iloc[-1]) == bool(changed_signal.iloc[-1])


def test_hysteresis_reduces_threshold_churn() -> None:
    idx = pd.bdate_range("2020-01-01", periods=260)
    trend = np.concatenate([np.linspace(100, 120, 150), 120 + np.sin(np.arange(110)) * 0.8])
    close = pd.DataFrame({"KS11": trend, "A": trend * 0.7}, index=idx)
    gate = pd.DataFrame(True, index=idx, columns=["A"])
    parent = build_market_regime_panel(close, benchmark_ticker="KS11", theme_tickers=["A"], universe_gate_d1=gate, policy="D1_MA120_EXPLICIT")["panel"]
    hyst = build_market_regime_panel(close, benchmark_ticker="KS11", theme_tickers=["A"], universe_gate_d1=gate, policy="MA120_HYSTERESIS_1PCT")["panel"]
    assert int(hyst["regime_switch"].sum()) <= int(parent["regime_switch"].sum())


def test_v95_backtest_keeps_parent_and_blocks_observed_only_promotion() -> None:
    summary = json.loads((ROOT / "reports/v95_market_regime_agent/v95_summary.json").read_text(encoding="utf-8"))
    assert summary["active_policy"] == "D1_MA120_EXPLICIT"
    assert summary["active_parent_nav_abs_error_krw"] == {"V69": 0.0, "V79": 0.0}
    assert summary["active_parent_signal_diff_days"] == {"V69": 0, "V79": 0}
    assert summary["promoted_candidates"] == []
    assert summary["forward_shadow_only_candidates"] == ["MA120_VOLATILITY_GUARD_35PCT"]
    assert summary["market_regime_parent_changed"] is False
    assert summary["live_execution_allowed"] is False


def test_v95_outputs_and_validation_evidence_gate() -> None:
    out = ROOT / "reports/v95_market_regime_agent"
    required = [
        "v95_strategy_metrics.csv", "v95_candidate_promotion.csv", "v95_regime_diagnostics.csv",
        "v95_annual_returns.csv", "v95_2026_monthly_returns.csv", "v95_quality_gates.csv", "v95_summary.json",
    ]
    assert all((out / name).exists() for name in required)
    promotion = pd.read_csv(out / "v95_candidate_promotion.csv")
    vol = promotion[promotion["policy"].eq("MA120_VOLATILITY_GUARD_35PCT")].iloc[0]
    assert not bool(vol["promoted"])
    assert bool(vol["forward_shadow_only"])
    assert int(vol["changed_regime_days_validation"]) == 0
    assert int(vol["changed_regime_days_observed"]) > 0
    summary = json.loads((out / "v95_summary.json").read_text(encoding="utf-8"))
    assert summary["future_mutation_invariant"] is True
