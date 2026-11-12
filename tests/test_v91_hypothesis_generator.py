from __future__ import annotations

from pathlib import Path
import pandas as pd
import yaml

from quant_harness.v91_hypothesis_generator.engine import run

ROOT = Path(__file__).resolve().parents[1]


def test_v91_generates_only_repeated_material_self_errors(tmp_path) -> None:
    output = tmp_path / "v91_hypothesis_generator"
    result = run(ROOT, output_dir=output)
    assert result["quality_gates_passed"] is True
    cfg = yaml.safe_load((ROOT / "config/v93_feedback_research.yaml").read_text())
    hypotheses = pd.read_csv(output / "v91_hypotheses.csv")
    proposed = hypotheses[hypotheses["proposal_created"].astype(bool)]
    assert not hypotheses.duplicated(["family", "test_year"]).any()
    assert (proposed["issue_rate"] >= float(cfg["hypothesis"]["minimum_issue_rate"])).all()
    assert (proposed["issue_severity"] >= float(cfg["hypothesis"]["minimum_issue_severity"])).all()
    assert (proposed["effective_events"] >= int(cfg["hypothesis"]["minimum_effective_events"])).all()
    assert proposed["one_component_only"].astype(bool).all()
    for row in hypotheses.itertuples(index=False):
        assert str(row.candidate).startswith(str(row.family))
        assert pd.Timestamp(row.evidence_cutoff) < pd.Timestamp(f"{int(row.test_year)}-01-01")
