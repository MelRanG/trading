from pathlib import Path
import json

import numpy as np
import pandas as pd

from quant_harness.v94_universe_agent.policy import build_universe_gate

ROOT = Path(__file__).resolve().parents[1]


def test_actual_bars_and_d1_freshness_are_required() -> None:
    idx = pd.bdate_range("2024-01-01", periods=80)
    close = pd.DataFrame({"A": np.arange(80, dtype=float) + 100.0, "B": np.nan}, index=idx)
    value = pd.DataFrame({"A": 200_000_000.0, "B": np.nan}, index=idx)
    close.loc[idx[10]:, "B"] = np.arange(70, dtype=float) + 50.0
    value.loc[idx[10]:, "B"] = 200_000_000.0
    close.loc[idx[65], "B"] = np.nan
    value.loc[idx[65], "B"] = np.nan
    gate = build_universe_gate(
        close, value, ["A", "B"],
        minimum_history_days=20,
        minimum_median_value_20d_krw=100_000_000.0,
    )
    assert not gate["gate"].loc[idx[20], "B"]  # only 10 real bars by D-1
    assert gate["gate"].loc[idx[70], "B"]
    assert not gate["gate"].loc[idx[66], "B"]  # missing D-1 observation
    assert int(gate["actual_history_d1"].loc[idx[66], "B"]) == 55


def test_future_mutation_cannot_change_past_gate() -> None:
    idx = pd.bdate_range("2023-01-02", periods=100)
    close = pd.DataFrame({"A": np.linspace(100, 150, 100)}, index=idx)
    value = pd.DataFrame({"A": 200_000_000.0}, index=idx)
    base = build_universe_gate(close, value, ["A"], minimum_history_days=20, minimum_median_value_20d_krw=100_000_000.0)["gate"]
    mutated_close = close.copy(); mutated_value = value.copy()
    mutated_close.loc[idx[70]:, "A"] *= 10
    mutated_value.loc[idx[70]:, "A"] *= 0.1
    changed = build_universe_gate(mutated_close, mutated_value, ["A"], minimum_history_days=20, minimum_median_value_20d_krw=100_000_000.0)["gate"]
    pd.testing.assert_frame_equal(base.loc[:idx[69]], changed.loc[:idx[69]])


def test_v94_backtest_promotes_correctness_only() -> None:
    summary = json.loads((ROOT / "reports/v94_universe_agent/v94_summary.json").read_text(encoding="utf-8"))
    assert summary["active_policy"] == "STRICT_PIT_CORRECTNESS"
    assert summary["strict_correctness_promoted"] is True
    assert summary["stable_liquidity_promoted"] is False
    assert summary["strict_nav_abs_error_krw"] == {"V69": 0.0, "V79": 0.0}
    assert summary["strict_signal_diff_days"] == {"V69": 0, "V79": 0}
    assert summary["live_execution_allowed"] is False


def test_v94_outputs_are_complete_and_fail_closed() -> None:
    out = ROOT / "reports/v94_universe_agent"
    required = [
        "v94_point_in_time_universe.csv", "v94_strategy_metrics.csv",
        "v94_parent_comparison.csv", "v94_annual_returns.csv",
        "v94_2026_monthly_returns.csv", "v94_quality_gates.csv", "v94_summary.json",
    ]
    assert all((out / name).exists() for name in required)
    gates = pd.read_csv(out / "v94_quality_gates.csv")
    assert gates.loc[gates["gate"].ne("STABLE_LIQUIDITY_SHARED_PROMOTION"), "passed"].astype(bool).all()
    stable = gates.loc[gates["gate"].eq("STABLE_LIQUIDITY_SHARED_PROMOTION"), "passed"].iloc[0]
    assert not bool(stable)
    state = json.loads((out / "v94_summary.json").read_text(encoding="utf-8"))
    assert state["active_policy"] == "STRICT_PIT_CORRECTNESS"
