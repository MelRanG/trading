from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from quant_harness.alpha_research_factory_robustness import calculate_robustness, evaluate_robustness, run


ROOT = Path(__file__).resolve().parents[1]


def _cfg() -> dict[str, object]:
    return {"minimum_bucket_dates": 20, "minimum_rolling_windows": 3, "minimum_rolling_direction_agreement": 0.60, "maximum_single_bucket_concentration": 0.70, "minimum_horizons_with_positive_rank_ic": 1, "minimum_horizons_with_positive_spread": 1, "rolling_window_dates": 20}


def _fixture(*, positive: bool, sparse: bool = False) -> pd.DataFrame:
    dates = pd.bdate_range("2023-01-02", periods=780)
    rows = []
    for i, date in enumerate(dates):
        for ticker, sector, score in [("A", "S1", 1.0), ("B", "S1", 0.5), ("C", "S2", -0.5), ("D", "S2", -1.0)]:
            ret = score * (0.01 if positive else -0.01)
            rows.append({"date": date, "ticker": ticker, "sector": sector, "risk_on": i % 2 == 0, "horizon_sessions": 5, "signal": score, "future_return": ret})
    frame = pd.DataFrame(rows)
    return frame.iloc[:32] if sparse else frame


def test_real_reversal_is_blocked_before_robustness(tmp_path: Path) -> None:
    result = run(ROOT, output_dir=tmp_path)
    assert result["attempt_status"] == "BLOCKED_DIAGNOSTIC_NOT_RUN"
    assert result["diagnostic_artifact_hash"] is None
    assert result["operational_replay_budget"] == {"used": 0, "limit": 1}


def test_synthetic_fail_and_pass_transitions() -> None:
    failed = calculate_robustness(_fixture(positive=False), cfg=_cfg())
    assert evaluate_robustness(failed, cfg=_cfg()) == "REJECTED_ROBUSTNESS"
    passed = calculate_robustness(_fixture(positive=True), cfg=_cfg())
    assert evaluate_robustness(passed, cfg=_cfg()) == "READY_FOR_EXECUTION_FEASIBILITY"


def test_sparse_bucket_fails_closed() -> None:
    result = calculate_robustness(_fixture(positive=True, sparse=True), cfg=_cfg())
    assert evaluate_robustness(result, cfg=_cfg()) == "REJECTED_ROBUSTNESS"
    assert result["nan_reasons"]["INSUFFICIENT_BUCKET_DATES"] > 0


def test_blocked_real_robustness_rerun_is_idempotent_and_events_append_only(tmp_path: Path) -> None:
    first = run(ROOT, output_dir=tmp_path)
    events = (tmp_path / "state_events.jsonl").read_text(encoding="utf-8")
    registry = (tmp_path / "robustness_registry.jsonl").read_text(encoding="utf-8")
    second = run(ROOT, output_dir=tmp_path)
    assert first == second
    assert (tmp_path / "state_events.jsonl").read_text(encoding="utf-8") == events
    assert (tmp_path / "robustness_registry.jsonl").read_text(encoding="utf-8") == registry
