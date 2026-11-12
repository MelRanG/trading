from __future__ import annotations

from pathlib import Path
import pandas as pd

from quant_harness.v90_trade_attribution.engine import run

ROOT = Path(__file__).resolve().parents[1]


def test_v90_trade_attribution_pipeline(tmp_path) -> None:
    output = tmp_path / "v90_trade_attribution"
    result = run(ROOT, output_dir=output)
    assert result["quality_gates_passed"] is True
    decisions = pd.read_csv(output / "v90_decision_attribution.csv")
    orders = pd.read_csv(output / "v90_order_attribution.csv")
    assert decisions["event_id"].is_unique
    assert (pd.to_datetime(decisions["information_cutoff"]) < pd.to_datetime(decisions["decision_date"])).all()
    for horizon in (1, 3, 5, 10, 20, 60):
        assert f"chosen_return_{horizon}d" in decisions.columns
        assert f"chosen_mfe_{horizon}d" in decisions.columns
        assert f"chosen_mae_{horizon}d" in decisions.columns
    audit = pd.read_csv(output / "v90_account_audit.csv").set_index("scenario")
    expected_parent_orders = int(audit.loc["V69_PARENT", "orders"] + audit.loc["V79_PARENT", "orders"])
    actual_parent_orders = len(orders[orders["scenario"].isin(["V69_PARENT", "V79_PARENT"])])
    assert actual_parent_orders == expected_parent_orders
    assert orders["execution_drag_bps"].notna().all()
