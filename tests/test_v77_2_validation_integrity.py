from __future__ import annotations

from pathlib import Path
import json

import numpy as np
import pandas as pd
import yaml

from quant_harness.v77_corrected_price_allocation.engine import _load_config
from quant_harness.v77_2_validation_integrity.engine import (
    SELECTION_COLUMNS,
    run,
    select_candidate_from_isolated_columns,
)

ROOT = Path(__file__).resolve().parents[1]


def _ensure() -> dict:
    path = ROOT / "reports/v77_2_validation_integrity/v77_2_decision.json"
    if not path.exists():
        run(ROOT)
    return json.loads(path.read_text(encoding="utf-8"))


def test_selection_file_contains_only_development_validation_inputs() -> None:
    _ensure()
    frame = pd.read_csv(ROOT / "reports/v77_2_validation_integrity/v77_2_selection_input_only.csv")
    assert set(SELECTION_COLUMNS).issubset(frame.columns)
    forbidden = {"observed_return_pct", "recent_1y_return_pct", "return_pct", "sharpe", "mdd_pct", "order_count"}
    assert not forbidden.intersection(frame.columns)


def test_observed_and_full_diagnostics_cannot_change_selection() -> None:
    _ensure()
    trials = pd.read_csv(ROOT / "reports/v77_2_validation_integrity/v77_2_trials.csv")
    local = yaml.safe_load((ROOT / "config/v77_2_validation_integrity.yaml").read_text(encoding="utf-8"))
    base_cfg = _load_config(ROOT)
    selected, _ = select_candidate_from_isolated_columns(
        trials,
        baseline_name=local["baseline_scenario"],
        selection_weights=local["selection_weights"],
        validation_floor_pp=base_cfg.validation_floor_pp,
        mdd_tolerance_pp=base_cfg.mdd_tolerance_pp,
    )
    mutated = trials.copy()
    for column in mutated.columns:
        if column not in SELECTION_COLUMNS and pd.api.types.is_numeric_dtype(mutated[column]):
            mutated[column] = np.linspace(-1e12, 1e12, len(mutated))
    mutated_selected, _ = select_candidate_from_isolated_columns(
        mutated,
        baseline_name=local["baseline_scenario"],
        selection_weights=local["selection_weights"],
        validation_floor_pp=base_cfg.validation_floor_pp,
        mdd_tolerance_pp=base_cfg.mdd_tolerance_pp,
    )
    assert selected == mutated_selected


def test_validation_only_and_multiple_testing_block_promotion() -> None:
    decision = _ensure()
    assert decision["observed_mutation_isolated"] is True
    assert decision["validation_bootstrap"]["months"] == 23
    assert decision["promotion_passed"] is False
    assert decision["familywise_positive_probability"] <= decision["validation_bootstrap"]["positive_probability"]
    assert decision["live_allowed"] is False
