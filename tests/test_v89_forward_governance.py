from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from quant_harness.v89_forward_governance.engine import ForwardGovernance, ForwardObservation, FrozenContractError, run


def _copy_root(tmp_path: Path) -> Path:
    src = Path(__file__).resolve().parents[1]
    root = tmp_path / "project"
    shutil.copytree(src, root, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "data/runtime/*", "reports/v89_forward_governance/*"))
    cfg_path = root / "config/v89_forward_governance.yaml"
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    cfg["trial"]["minimum_sessions"] = 3
    cfg["trial"]["recommended_sessions"] = 4
    cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    return root


def test_frozen_contract_detects_mutation(tmp_path: Path) -> None:
    root = _copy_root(tmp_path); gov = ForwardGovernance(root); gov.freeze(overwrite=True)
    path = root / gov.cfg["paths"]["strategy_registry"]
    path.write_text(path.read_text(encoding="utf-8") + "\n# mutation\n", encoding="utf-8")
    with pytest.raises(FrozenContractError, match="mutation"): gov.verify_frozen_contract()


def test_observation_is_idempotent_and_conflict_is_blocked(tmp_path: Path) -> None:
    root = _copy_root(tmp_path); gov = ForwardGovernance(root); gov.freeze(start_session="2026-07-20", overwrite=True)
    obs = ForwardObservation("2026-07-20", "v69_fixed80_daily_control", "p", "s", 1.0, 0.1, True, True, 0)
    gov.append_observation(obs); gov.append_observation(obs)
    with pytest.raises(FrozenContractError, match="idempotency"):
        gov.append_observation(ForwardObservation("2026-07-20", "v69_fixed80_daily_control", "p2", "s", 1.0, 0.1, True, True, 0))


def _append_sessions(gov: ForwardGovernance, *, bad_reconcile: bool = False) -> None:
    for day in range(3):
        session = f"2027-01-{day+1:02d}"
        for sid in ["v69_fixed80_daily_control", "v79_core70_generic_trend30"]:
            gov.append_observation(ForwardObservation(session, sid, f"p-{day}-{sid}", f"s-{sid}", 1.0, 0.2, True, not (bad_reconcile and day == 1 and sid.startswith("v79")), 0))


def test_clean_sessions_can_pass_paper_gate_but_live_stays_blocked(tmp_path: Path) -> None:
    root = _copy_root(tmp_path); gov = ForwardGovernance(root); gov.freeze(start_session="2026-07-20", overwrite=True); _append_sessions(gov)
    result = gov.evaluate()
    assert result["canary_eligible"] is True and result["next_stage"] == "CANARY_1_PERCENT"
    assert result["live_execution_allowed"] is False and result["human_approval_required"] is True


def test_bad_reconciliation_blocks_canary(tmp_path: Path) -> None:
    root = _copy_root(tmp_path); gov = ForwardGovernance(root); gov.freeze(start_session="2026-07-20", overwrite=True); _append_sessions(gov, bad_reconcile=True)
    result = gov.evaluate()
    assert result["canary_eligible"] is False
    assert next(x for x in result["strategies"] if x["strategy_id"].startswith("v79"))["reconciliation_failures"] == 1


def test_v89_readiness_harness(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    paths = ForwardGovernance(root).cfg["paths"]
    summaries = [Path(paths[key]) for key in ("v85_summary", "v88_summary")]
    for relative in summaries:
        (root / relative).unlink(missing_ok=True)
    blocked = run(root)
    assert {key for key, ready in blocked["gates"].items() if not ready} == {
        "v85_operational_ready", "v88_reconciliation_ready"
    }
    assert blocked["evaluation"]["live_execution_allowed"] is False

    fixture = Path(__file__).resolve().parent / "fixtures/archived_release_reports"
    for relative in summaries:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(fixture / relative.relative_to("reports"), target)
    result = run(root)
    assert all(result["gates"].values())
    assert result["evaluation"]["live_execution_allowed"] is False
