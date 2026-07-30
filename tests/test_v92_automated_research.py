from __future__ import annotations

from pathlib import Path
import pandas as pd

from quant_harness.v92_automated_research.engine import run

ROOT = Path(__file__).resolve().parents[1]


def test_v92_requires_all_promotion_gates_and_preserves_parents() -> None:
    result = run(ROOT)
    assert result["quality_gates_passed"] is True
    folds = pd.read_csv(ROOT / "reports/v92_automated_research/v92_fold_results.csv")
    proposed = folds[folds["proposal_created"].astype(bool)]
    gate_cols = ["gate_return", "gate_mdd", "gate_stress", "gate_issue_reduction", "gate_turnover", "gate_regime"]
    for row in proposed.itertuples(index=False):
        expected = all(bool(getattr(row, col)) for col in gate_cols)
        assert bool(row.passed_backtest) == expected
    metrics = pd.read_csv(ROOT / "reports/v92_automated_research/v92_strategy_metrics.csv").set_index("scenario")
    prior = pd.read_csv(ROOT / "reports/v83_independent_self_research/v83_strategy_metrics.csv").set_index("scenario")
    for parent in ("V69_PARENT", "V79_PARENT"):
        assert abs(float(metrics.loc[parent, "return_pct"]) - float(prior.loc[parent, "return_pct"])) <= 1e-12
