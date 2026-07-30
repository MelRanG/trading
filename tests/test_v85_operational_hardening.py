from pathlib import Path
import json
import sqlite3

import pandas as pd

from quant_harness.v84_dual_paper_parity.engine import PortfolioState
from quant_harness.v85_operational_hardening.engine import (
    RiskLimits,
    backup_sqlite,
    restore_and_check,
    risk_gate,
)

ROOT = Path(__file__).resolve().parents[1]


def limits(**overrides):
    base = dict(
        kill_switch=False,
        max_single_symbol_weight=0.9,
        max_daily_loss_pct=0.08,
        max_rolling_drawdown_pct=0.25,
        max_open_gap_pct=0.15,
        max_participation_of_d1_adv=0.01,
        minimum_cash_krw=0,
    )
    base.update(overrides)
    return RiskLimits(**base)


def test_v85_reference_validation_summary_is_complete():
    result = json.loads((ROOT / "reports/v85_operational_hardening/summary.json").read_text())
    assert all(result["gates"].values())
    assert result["operating_day"]["status"] == "v85_operational_hardening_complete_live_blocked"
    assert result["artifact_retention"] == "COMPACT_SUMMARY_ONLY_RUNTIME_STATE_REMOVED"


def test_risk_kill_switch_and_gap_fail_closed():
    common = dict(
        targets={"069500": 0.2, "395160": 0.8},
        state=PortfolioState(10_000_000),
        open_prices={"069500": 100, "395160": 130},
        previous_close={"069500": 100, "395160": 100},
        adv20_d1={"069500": 1e9, "395160": 1e9},
    )
    assert not risk_gate(**common, limits=limits(kill_switch=True))["allowed"]
    gap = risk_gate(**common, limits=limits())
    assert not gap["allowed"] and "EXTREME_GAP:395160" in gap["blockers"]


def test_point_in_time_universe_contract():
    pit = pd.read_csv(ROOT / "data/canonical/v85_point_in_time_universe.csv", dtype={"ticker": str})
    assert "069500" in set(pit.ticker.str.zfill(6))
    assert (pd.to_datetime(pit.available_from) <= pd.to_datetime(pit.available_to)).all()
    assert set(pit["listing_source"]) == {"OBSERVED_FIRST_BAR_PROXY"}


def test_sqlite_backup_restore_on_small_fixture(tmp_path: Path):
    source = tmp_path / "paper.db"
    with sqlite3.connect(source) as conn:
        conn.execute("CREATE TABLE accounts(strategy_id TEXT PRIMARY KEY)")
        conn.execute("CREATE TABLE sessions(strategy_id TEXT, session TEXT)")
        conn.executemany("INSERT INTO accounts VALUES(?)", [("v69",), ("v79",)])
        conn.execute("INSERT INTO sessions VALUES(?,?)", ("v69", "2026-07-03"))
    backup = backup_sqlite(source, tmp_path / "backups", "fixture")
    restored = restore_and_check(Path(backup["path"]), tmp_path / "restored.db")
    assert restored["passed"] is True


def test_live_is_blocked_in_config_and_summary():
    result = json.loads((ROOT / "reports/v85_operational_hardening/summary.json").read_text())
    assert not result["operating_day"]["live_execution_allowed"]


def test_risk_concentration_daily_loss_and_drawdown():
    base = dict(
        state=PortfolioState(100),
        open_prices={"069500": 100, "395160": 100},
        previous_close={"069500": 100, "395160": 100},
        adv20_d1={"069500": 1e9, "395160": 1e9},
        limits=limits(),
    )
    concentrated = risk_gate(targets={"069500": 0.04, "395160": 0.96}, **base)
    assert "SINGLE_SYMBOL_CONCENTRATION" in concentrated["blockers"]
    loss = risk_gate(targets={"069500": 1.0}, previous_nav=1000, peak_nav=1000, **base)
    assert "DAILY_LOSS_LIMIT" in loss["blockers"]
    dd = risk_gate(targets={"069500": 1.0}, previous_nav=700, peak_nav=1000, **base)
    assert "DRAWDOWN_LIMIT" in dd["blockers"]
