from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path

import pytest

from quant_harness.v86_control_plane_dashboard.engine import ControlPlane, run as run_v86


def _seed_dual_db(root: Path) -> None:
    path = root / "data/runtime/v85_dual_paper.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE accounts(strategy_id TEXT PRIMARY KEY,cash REAL NOT NULL,quantities_json TEXT NOT NULL,pending INTEGER NOT NULL,prior_signature TEXT);
            CREATE TABLE sessions(strategy_id TEXT NOT NULL,session TEXT NOT NULL,nav REAL NOT NULL,cash REAL NOT NULL,holdings_json TEXT NOT NULL,plan_hash TEXT NOT NULL,PRIMARY KEY(strategy_id,session));
            CREATE TABLE fills(strategy_id TEXT NOT NULL,session TEXT NOT NULL,ticker TEXT NOT NULL,side TEXT NOT NULL,quantity INTEGER NOT NULL,reference_open REAL NOT NULL,execution_price REAL NOT NULL,fee REAL NOT NULL,impact_bps REAL NOT NULL,participation REAL,PRIMARY KEY(strategy_id,session,ticker,side));
            """
        )
        for sid, nav, cash, qty in [
            ("v69_fixed80_daily_control", 11_000_000, 1_000_000, 100),
            ("v79_core70_generic_trend30", 12_000_000, 2_000_000, 120),
        ]:
            holdings = json.dumps({"069500": qty})
            conn.execute("INSERT INTO accounts VALUES(?,?,?,?,?)", (sid, cash, holdings, 0, "sig"))
            conn.execute("INSERT INTO sessions VALUES(?,?,?,?,?,?)", (sid, "2026-07-02", nav - 100_000, cash, holdings, "p1"))
            conn.execute("INSERT INTO sessions VALUES(?,?,?,?,?,?)", (sid, "2026-07-03", nav, cash, holdings, "p2"))
            conn.execute("INSERT INTO fills VALUES(?,?,?,?,?,?,?,?,?,?)", (sid, "2026-07-03", "069500", "BUY", 1, 10000, 10010, 2, 5, 0.001))


@pytest.fixture(scope="module")
def prepared_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    src = Path(__file__).resolve().parents[1]
    root = tmp_path_factory.mktemp("v86") / "project"
    shutil.copytree(src, root, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.rmtree(root / "data/runtime", ignore_errors=True)
    (root / "data/runtime").mkdir(parents=True, exist_ok=True)
    _seed_dual_db(root)
    return root


def test_single_dynamic_ui_and_isolated_accounts(prepared_root: Path) -> None:
    root = prepared_root
    result86 = run_v86(root)
    assert all(result86["gates"].values())
    plane = ControlPlane(root)
    payload = plane.payload()
    assert payload["architecture"]["ui_instances"] == 1
    assert payload["architecture"]["paper_account_model"].startswith("ONE_ISOLATED")
    runtime = [s for s in payload["strategies"] if s["account_available"]]
    assert {x["strategy_id"] for x in runtime} == {"v69_fixed80_daily_control", "v79_core70_generic_trend30"}
    assert plane.strategy_detail("v69_fixed80_daily_control")["account"]["latest_nav_krw"] != plane.strategy_detail("v79_core70_generic_trend30")["account"]["latest_nav_krw"]


def test_feedback_candidate_is_discovered_without_new_ui_code(prepared_root: Path) -> None:
    root = prepared_root
    plane = ControlPlane(root)
    registry_path = plane.ensure_feedback_candidate_registry()
    original = registry_path.read_text(encoding="utf-8")
    try:
        payload = json.loads(original)
        payload["candidates"].append({
            "strategy_id": "feedback_v79_new_alpha_x", "scenario": "V79_NEW_ALPHA_X", "label": "V79 New Alpha X",
            "role": "SHADOW", "status": "RESEARCH_CANDIDATE", "parent_strategy_id": "v79_core70_generic_trend30",
            "created_by": "FeedbackAgent", "managed_by": "external", "source": "test", "runtime_compatible": False,
            "parameters": {"hypothesis": "test-only"},
        })
        registry_path.write_text(json.dumps(payload), encoding="utf-8")
        assert "feedback_v79_new_alpha_x" in {x["strategy_id"] for x in plane.catalog()}
    finally:
        registry_path.write_text(original, encoding="utf-8")
    static = (root / "src/quant_harness/v86_control_plane_dashboard/static/index.html").read_text(encoding="utf-8")
    assert "feedback_v79_new_alpha_x" not in static
    assert "v69_fixed80_daily_control" not in static
    assert "v79_core70_generic_trend30" not in static


def test_research_candidate_has_no_capital_authority(prepared_root: Path) -> None:
    plane = ControlPlane(prepared_root)
    candidate = next(x for x in plane.catalog() if x["created_by"] == "FeedbackAgent")
    detail = plane.strategy_detail(candidate["strategy_id"])
    assert detail["research_only"] is True
    assert detail["account"] is None
    payload = plane.payload(candidate["strategy_id"])
    assert payload["live_execution_allowed"] is False
    assert payload["governance"]["feedback_may_mutate_champion_in_place"] is False
    assert payload["governance"]["automatic_live_promotion"] is False
