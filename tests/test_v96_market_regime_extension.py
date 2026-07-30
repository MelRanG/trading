from pathlib import Path
import json

import numpy as np
import pandas as pd

from quant_harness.v96_market_regime_extension.policy import build_market_regime_panel

ROOT = Path(__file__).resolve().parents[1]


def _toy() -> tuple[pd.DataFrame, pd.DataFrame]:
    idx = pd.bdate_range("2022-01-03", periods=260)
    bench = np.linspace(100.0, 145.0, len(idx))
    close = pd.DataFrame({"KS11": bench, "A": bench * 0.8, "B": bench * 0.6}, index=idx)
    gate = pd.DataFrame(True, index=idx, columns=["A", "B"])
    return close, gate


def test_continuous_score_is_d1_causal_and_bounded() -> None:
    close, gate = _toy()
    result = build_market_regime_panel(
        close, benchmark_ticker="KS11", theme_tickers=["A", "B"], universe_gate_d1=gate,
        policy="MA120_CONTINUOUS_RISK_SCORE",
    )
    exposure = result["exposure_multiplier"]
    assert exposure.between(0.0, 1.0).all()
    changed = close.copy()
    changed.iloc[-1, changed.columns.get_loc("KS11")] *= 0.1
    changed_result = build_market_regime_panel(
        changed, benchmark_ticker="KS11", theme_tickers=["A", "B"], universe_gate_d1=gate,
        policy="MA120_CONTINUOUS_RISK_SCORE",
    )
    assert float(exposure.iloc[-1]) == float(changed_result["exposure_multiplier"].iloc[-1])


def test_crash_guard_is_temporary_and_does_not_change_parent_selection_gate() -> None:
    close, gate = _toy()
    # Create a sharp five-session fall before the final decision session.
    close.loc[close.index[-7:-1], "KS11"] = [145.0, 143.0, 141.0, 139.0, 137.0, 135.0]
    close.loc[close.index[-7:-1], ["A", "B"]] = close.loc[close.index[-7:-1], ["A", "B"]].mul(
        np.linspace(1.0, 0.75, 6), axis=0
    )
    parent = build_market_regime_panel(
        close, benchmark_ticker="KS11", theme_tickers=["A", "B"], universe_gate_d1=gate,
        policy="D1_MA120_EXPLICIT",
    )
    guard = build_market_regime_panel(
        close, benchmark_ticker="KS11", theme_tickers=["A", "B"], universe_gate_d1=gate,
        policy="MA120_CRASH_GUARD", crash_return_5d_floor=-0.05, crash_volatility_floor=0.10,
    )
    # Selection gate remains the same; only exposure is temporarily reduced.
    assert parent["risk_on"].equals(guard["risk_on"])
    assert int(guard["crash_flag"].sum()) >= 1
    assert (guard["exposure_multiplier"].loc[guard["crash_flag"]] == 0.0).all()
    assert (guard["exposure_multiplier"].loc[~guard["crash_flag"]] == 1.0).all()


def test_v96_backtest_preserves_parent_and_rejects_both_candidates() -> None:
    summary = json.loads((ROOT / "reports/v96_market_regime_extension/v96_summary.json").read_text(encoding="utf-8"))
    assert summary["active_policy"] == "D1_MA120_EXPLICIT"
    assert summary["active_parent_nav_abs_error_krw"] == {"V69": 0.0, "V79": 0.0}
    assert summary["active_parent_exposure_max_error"] == 0.0
    assert summary["promoted_candidates"] == []
    assert summary["forward_shadow_only_candidates"] == []
    assert summary["market_regime_parent_changed"] is False
    assert summary["live_execution_allowed"] is False


def test_v96_candidate_results_and_outputs() -> None:
    out = ROOT / "reports/v96_market_regime_extension"
    required = [
        "v96_strategy_metrics.csv", "v96_candidate_promotion.csv", "v96_regime_diagnostics.csv",
        "v96_annual_returns.csv", "v96_2026_monthly_returns.csv", "v96_quality_gates.csv",
        "v96_market_regime_candidate_registry.json", "v96_summary.json",
    ]
    assert all((out / name).exists() for name in required)
    promotion = pd.read_csv(out / "v96_candidate_promotion.csv").set_index("policy")
    assert not bool(promotion.loc["MA120_CONTINUOUS_RISK_SCORE", "promoted"])
    assert not bool(promotion.loc["MA120_CRASH_GUARD", "promoted"])
    assert float(promotion.loc["MA120_CONTINUOUS_RISK_SCORE", "v69_full_delta_pp"]) < 0
    assert float(promotion.loc["MA120_CONTINUOUS_RISK_SCORE", "v79_full_delta_pp"]) < 0
    assert float(promotion.loc["MA120_CRASH_GUARD", "v69_full_delta_pp"]) < 0
    assert int(promotion.loc["MA120_CRASH_GUARD", "changed_exposure_days_validation"]) == 0
    quality = pd.read_csv(out / "v96_quality_gates.csv")
    required_quality = quality[quality["gate"].ne("OPTIONAL_RESEARCH_PROMOTION")]
    assert required_quality["passed"].astype(bool).all()
