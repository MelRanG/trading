from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from quant_harness.v94_universe_agent.engine import _strict_v79_features
from quant_harness.v98_candidate_selection_agent.policy import prepare_selection_features
from quant_harness.v104_end_to_end_causal_challenger_audit.adapter import load_candidate_specs


ROOT = Path(__file__).resolve().parents[1]


def test_high252_feature_is_lagged_and_does_not_change_v79_eligibility() -> None:
    index = pd.date_range("2020-01-01", periods=270, freq="B")
    close = pd.DataFrame({"111111": np.arange(100.0, 370.0), "222222": np.arange(200.0, 470.0), "KS11": np.arange(300.0, 570.0)}, index=index)
    value = pd.DataFrame(2_000_000_000.0, index=index, columns=close.columns)
    universe = pd.DataFrame({"ticker": ["111111", "222222"]})
    cfg = {"horizons_days": [63, 126, 252], "horizon_weights": [.25, .35, .40], "trend_ma_days": 200, "minimum_history_days": 252, "minimum_median_value_20d_krw": 100_000_000}
    features = _strict_v79_features(close, value, universe, cfg)
    day = index[260]
    expected = close.loc[index[259], "111111"] / close.loc[:index[259], "111111"].tail(252).max() - 1.0
    assert features["high252_proximity"].loc[day, "111111"] == expected
    selected = prepare_selection_features(features, family="V79", policy="V79_HIGH252_PROXIMITY")
    pd.testing.assert_frame_equal(selected["selection_score"], features["high252_proximity"])
    pd.testing.assert_frame_equal(selected["selection_eligible"], features["eligible"])


def test_high252_challenger_changes_only_the_v79_sleeve_score_contract() -> None:
    specs = load_candidate_specs(ROOT)
    base = specs["V79_NO63_VOL_GUARD"]
    challenger = specs["V79_HIGH252_PROXIMITY_VOL_GUARD"]
    assert challenger.strategy == base.strategy == "V79"
    assert challenger.universe_policy == base.universe_policy
    assert challenger.regime_policy == base.regime_policy
    assert challenger.base_selection_policy == base.base_selection_policy
    assert challenger.strategy_policy == base.strategy_policy
    assert challenger.evidence_policy == base.evidence_policy
    assert challenger.execution_policy == base.execution_policy
    assert challenger.sleeve_selection_policy == "V79_HIGH252_PROXIMITY"
