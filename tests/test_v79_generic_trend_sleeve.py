from __future__ import annotations

from pathlib import Path
import inspect
import json

import numpy as np
import pandas as pd
import yaml

from quant_harness.v79_generic_trend_sleeve.engine import (
    build_generic_trend_features,
    run,
    select_persistent_trend_leader,
)

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports/v79_generic_trend_sleeve"


def _ensure() -> dict:
    path = REPORT / "v79_decision.json"
    if not path.exists():
        run(ROOT)
    return json.loads(path.read_text(encoding="utf-8"))


def test_strategy_logic_has_no_specific_theme_or_ticker_literal() -> None:
    _ensure()
    source = inspect.getsource(build_generic_trend_features) + inspect.getsource(select_persistent_trend_leader)
    forbidden = ["091160", "semiconductor", "battery", "bio", "robot", "energy", "financial"]
    assert not [token for token in forbidden if token.lower() in source.lower()]


def test_exactly_two_preregistered_blends() -> None:
    _ensure()
    cfg = yaml.safe_load((ROOT / "config/v79_generic_trend_sleeve.yaml").read_text(encoding="utf-8"))
    gates = pd.read_csv(REPORT / "v79_candidate_gates.csv")
    assert cfg["strategy_design"]["candidate_base_shares"] == [0.70, 0.80]
    assert len(gates) == 2


def test_all_sleeve_decisions_are_strictly_d1() -> None:
    _ensure()
    ledger = pd.read_csv(REPORT / "v79_generic_trend_selection.csv", parse_dates=["date", "information_cutoff"])
    used = ledger.dropna(subset=["information_cutoff"])
    assert (used["information_cutoff"] < used["date"]).all()
    assert not ledger["decision_uses_same_day_close"].astype(bool).any()


def test_persistence_rules_and_multisector_behaviour() -> None:
    decision = _ensure()
    cfg = yaml.safe_load((ROOT / "config/v79_generic_trend_sleeve.yaml").read_text(encoding="utf-8"))
    assert cfg["trend_sleeve"]["minimum_hold_sessions"] == 20
    assert cfg["trend_sleeve"]["challenger_score_margin"] == 0.10
    assert cfg["trend_sleeve"]["challenger_confirmation_reviews"] == 2
    assert decision["distinct_selected_sectors"] >= 4


def test_target_weights_sum_to_one() -> None:
    _ensure()
    for path in REPORT.glob("v79_targets_*.csv"):
        targets = pd.read_csv(path)
        assert np.allclose(targets["target_weight_sum"], 1.0, atol=1e-12)


def test_multi_asset_order_math_and_participation() -> None:
    _ensure()
    for path in REPORT.glob("v79_orders_v79_generic_*.csv"):
        if "stress" in path.name:
            continue
        orders = pd.read_csv(path)
        if orders.empty:
            continue
        expected = orders["quantity"] * orders["reference_open_krw"]
        assert (expected - orders["notional_at_reference_open_krw"]).abs().max() <= 0.01
        valid = orders["adv20_d1_krw"].gt(0)
        participation = expected[valid] / orders.loc[valid, "adv20_d1_krw"]
        assert (participation - orders.loc[valid, "participation_of_d1_adv"]).abs().max() <= 1e-12
        assert orders["participation_of_d1_adv"].dropna().le(0.0100000001).all()


def test_observed_period_is_diagnostic_and_live_remains_blocked() -> None:
    decision = _ensure()
    gates = pd.read_csv(REPORT / "v79_quality_gates.csv").set_index("gate")
    assert bool(gates.loc["OBSERVED_PERIOD_EXCLUDED_FROM_RESEARCH_SELECTION", "passed"])
    assert decision["live_allowed"] is False
    assert decision["paper_auto_promotion_allowed"] is False
    assert decision["minimum_new_unseen_forward_sessions"] == 60
