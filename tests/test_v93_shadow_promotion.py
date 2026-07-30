from __future__ import annotations

import json
from pathlib import Path
import pandas as pd

from quant_harness.v93_shadow_promotion.engine import run
from quant_harness.v86_control_plane_dashboard.engine import ControlPlane

ROOT = Path(__file__).resolve().parents[1]


def test_v93_registry_has_no_automatic_capital_authority() -> None:
    result = run(ROOT)
    assert result["quality_gates_passed"] is True
    payload = json.loads((ROOT / "reports/v93_shadow_promotion/v93_feedback_candidate_registry.json").read_text())
    assert payload["policy"]["automatic_capital_authority"] is False
    assert payload["policy"]["automatic_champion_change"] is False
    summary = pd.read_csv(ROOT / "reports/v92_automated_research/v92_candidate_summary.csv")
    eligible = set(summary.loc[summary["shadow_eligible"].astype(bool), "candidate"].astype(str)) if not summary.empty else set()
    for candidate in payload["candidates"]:
        assert candidate["capital_authority"] == "NONE"
        assert (candidate["status"] == "SHADOW_ELIGIBLE") == (candidate["scenario"] in eligible)


def test_control_plane_reads_v93_registry_without_strategy_specific_ui() -> None:
    plane = ControlPlane(ROOT)
    catalog = plane.catalog()
    feedback = [x for x in catalog if x["created_by"] == "FeedbackAgent"]
    assert feedback
    static = (ROOT / "src/quant_harness/v86_control_plane_dashboard/static/index.html").read_text(encoding="utf-8")
    for item in feedback:
        assert item["strategy_id"] not in static
        assert item["account_id"] is None
