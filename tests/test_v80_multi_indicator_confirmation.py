from __future__ import annotations

from pathlib import Path
import inspect
import json

import numpy as np
import pandas as pd
import yaml

from quant_harness.v80_multi_indicator_confirmation.engine import (
    build_indicator_library,
    preregistered_exposures,
    run,
)

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports/v80_multi_indicator_confirmation"


def _ensure() -> dict:
    path = REPORT / "v80_decision.json"
    if not path.exists():
        run(ROOT)
    return json.loads(path.read_text(encoding="utf-8"))


def test_no_specific_theme_or_ticker_rule() -> None:
    _ensure()
    source = inspect.getsource(build_indicator_library) + inspect.getsource(preregistered_exposures)
    forbidden = ["091160", "semiconductor", "battery", "bio", "robot", "energy", "financial"]
    assert not [token for token in forbidden if token.lower() in source.lower()]


def test_exactly_five_preregistered_candidates() -> None:
    _ensure()
    cfg = yaml.safe_load((ROOT / "config/v80_multi_indicator_confirmation.yaml").read_text(encoding="utf-8"))
    comparison = pd.read_csv(REPORT / "v80_candidate_comparison.csv")
    assert set(comparison["candidate"]) == set(cfg["candidate_order"])
    assert len(comparison) == 5


def test_indicator_panel_is_strict_d1_and_has_all_families() -> None:
    _ensure()
    panel = pd.read_csv(REPORT / "v80_selected_indicator_panel.csv", parse_dates=["date", "information_cutoff"])
    used = panel.dropna(subset=["information_cutoff"])
    assert (used["information_cutoff"] < used["date"]).all()
    required = {
        "ma_positive", "macd_positive", "dmi_positive",
        "rsi_positive", "cci_positive", "stochastic_positive",
        "obv_positive", "ad_positive", "volume_osc_positive",
        "atr_extreme", "bollinger_extreme", "seasonality_positive",
    }
    assert required.issubset(panel.columns)


def test_all_target_weights_sum_to_one_and_exposure_is_bounded() -> None:
    _ensure()
    for path in REPORT.glob("v80_targets_*.csv"):
        targets = pd.read_csv(path)
        assert np.allclose(targets["target_weight_sum"], 1.0, atol=1e-12)
        assert targets["indicator_sleeve_exposure"].between(0.0, 0.30).all()


def test_order_math_and_participation_reconstruct() -> None:
    _ensure()
    for path in REPORT.glob("v80_orders_*.csv"):
        if "stress" in path.name:
            continue
        orders = pd.read_csv(path)
        if orders.empty:
            continue
        expected = orders["quantity"] * orders["reference_open_krw"]
        assert (expected - orders["notional_at_reference_open_krw"]).abs().max() <= 0.01
        valid = orders["adv20_d1_krw"].gt(0)
        reconstructed = expected[valid] / orders.loc[valid, "adv20_d1_krw"]
        assert (reconstructed - orders.loc[valid, "participation_of_d1_adv"]).abs().max() <= 1e-12
        assert orders["participation_of_d1_adv"].dropna().le(0.0100000001).all()


def test_live_and_registry_mutation_remain_blocked() -> None:
    decision = _ensure()
    gates = pd.read_csv(REPORT / "v80_quality_gates.csv").set_index("gate")
    assert decision["live_allowed"] is False
    assert decision["automatic_registry_change"] is False
    assert bool(gates.loc["NO_AUTOMATIC_CHAMPION_MUTATION", "passed"])
    assert bool(gates.loc["LIVE_EXECUTION_BLOCKED", "passed"])
