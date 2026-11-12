from __future__ import annotations

from datetime import date
from decimal import Decimal
import os
from pathlib import Path

import psycopg
import pytest

from quant_harness.daily_paper_runtime import (
    FreshnessResult,
    _daily_cycle_lock,
    run_daily_paper_cycle,
    validate_freshness_records,
)
from quant_harness.paper_runtime_store import (
    PAPER_ACCOUNT_ID,
    ensure_paper_account,
    initialize_paper_schema,
)


ROOT = Path(__file__).resolve().parents[1]
URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="TEST_DATABASE_URL is required for PostgreSQL acceptance")


@pytest.fixture(autouse=True)
def clean_daily_tables() -> None:
    initialize_paper_schema(URL)
    with psycopg.connect(URL) as conn:
        conn.execute(
            "TRUNCATE paper_daily_nav,paper_reconciliation,paper_ledger_event,paper_fill,paper_order,"
            "paper_audit_event,order_intent_preview,target_allocation,strategy_decision,paper_session,"
            "paper_position,paper_cash,paper_account CASCADE"
        )
    ensure_paper_account(URL, Decimal("10000000"), "config/v85_operations.yaml:initial_capital_krw")


def test_freshness_records_require_all_symbols_and_common_cutoff() -> None:
    records = {symbol: {"last_date": "2026-07-08", "valid": True} for symbol in [f"S{i:02d}" for i in range(26)]}
    result = validate_freshness_records(
        records,
        {"last_date": "2026-07-08", "valid": True},
        run_date=date(2026, 7, 9),
    )
    assert result.status == "FRESH"
    assert result.cutoff == "2026-07-08"
    assert result.structural_completeness == "PASSED"
    assert result.temporal_freshness == "FRESH"

    incomplete = dict(records)
    incomplete.pop("S25")
    assert validate_freshness_records(incomplete, {"last_date": "2026-07-08", "valid": True}).status == "INCOMPLETE"

    stale = validate_freshness_records(
        records,
        {"last_date": "2026-07-08", "valid": True},
        run_date=date(2026, 7, 31),
    )
    assert stale.status == "STALE"
    assert stale.structural_completeness == "PASSED"
    assert stale.temporal_freshness == "STALE"
    assert stale.latest_completed_date == "2026-07-30"


def test_daily_cycle_incomplete_gate_does_not_create_decision_or_orders(monkeypatch) -> None:
    update = {"cutoff": "2026-07-08", "latest_completed_date": "2026-07-08", "failed": (), "rows_added": 0}
    monkeypatch.setattr("quant_harness.daily_paper_runtime._run_toss_market_update", lambda *a, **k: update)
    monkeypatch.setattr("quant_harness.daily_paper_runtime.append_canonical", lambda *a, **k: 0)
    monkeypatch.setattr(
        "quant_harness.daily_paper_runtime.validate_market_freshness",
        lambda root, latest_completed_date=None: FreshnessResult("INCOMPLETE", None, 25, ("401170",), "KS11"),
    )
    called = {"preview": 0, "execute": 0}
    monkeypatch.setattr("quant_harness.daily_paper_runtime.run_paper_decision_preview", lambda *a, **k: called.__setitem__("preview", called["preview"] + 1))
    monkeypatch.setattr("quant_harness.daily_paper_runtime.run_paper_execution_cycle", lambda *a, **k: called.__setitem__("execute", called["execute"] + 1))

    result = run_daily_paper_cycle(URL, ROOT, snapshot_mode="mock")

    assert result["status"] == "HOLD_ONLY"
    assert result["freshness"]["status"] == "INCOMPLETE"
    assert result["orders"] == []
    assert called == {"preview": 0, "execute": 0}
    with psycopg.connect(URL) as conn:
        assert conn.execute("SELECT count(*) FROM paper_session").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM paper_order").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM paper_daily_nav").fetchone()[0] == 1


def test_temporal_stale_keeps_operational_authority_hold_only(monkeypatch) -> None:
    monkeypatch.setattr("quant_harness.daily_paper_runtime._run_toss_market_update", lambda *a, **k: {"cutoff": "2026-07-08", "latest_completed_date": "2026-07-08", "failed": (), "rows_added": 0})
    monkeypatch.setattr("quant_harness.daily_paper_runtime.append_canonical", lambda *a, **k: 0)
    monkeypatch.setattr(
        "quant_harness.daily_paper_runtime.validate_market_freshness",
        lambda root, latest_completed_date=None: FreshnessResult("STALE", "2026-07-08", 26, (), "KS11"),
    )
    called = {"preview": 0}
    monkeypatch.setattr("quant_harness.daily_paper_runtime.run_paper_decision_preview", lambda *a, **k: called.__setitem__("preview", called["preview"] + 1))

    result = run_daily_paper_cycle(URL, ROOT, snapshot_mode="mock")

    assert result["status"] == "HOLD_ONLY"
    assert result["operational_authority"] == "HOLD_ONLY"
    assert result["freshness"]["structural_completeness"] == "PASSED"
    assert result["freshness"]["temporal_freshness"] == "STALE"
    assert result["orders"] == []
    assert called["preview"] == 0


def test_daily_cycle_fresh_path_saves_nav_and_is_idempotent(monkeypatch) -> None:
    update = {"cutoff": "2026-07-08", "latest_completed_date": "2026-07-08", "failed": (), "rows_added": 0}
    freshness = FreshnessResult("FRESH", "2026-07-08", 26, (), "KS11")
    monkeypatch.setattr("quant_harness.daily_paper_runtime._run_toss_market_update", lambda *a, **k: update)
    monkeypatch.setattr("quant_harness.daily_paper_runtime.append_canonical", lambda *a, **k: 0)
    monkeypatch.setattr("quant_harness.daily_paper_runtime.validate_market_freshness", lambda root, latest_completed_date=None: freshness)
    monkeypatch.setattr(
        "quant_harness.daily_paper_runtime.build_strategy_preview",
        lambda root: {"as_of": date(2026, 7, 8), "session_id": "S-DAILY"},
    )
    monkeypatch.setattr(
        "quant_harness.daily_paper_runtime.run_paper_decision_preview",
        lambda *a, **k: {"status": "SAVED", "authority_status": "PREVIEW_ONLY", "decision": {"as_of": date(2026, 7, 8)}, "read_only_snapshot": {"status": "SAVED", "mutation_calls": 0}},
    )
    monkeypatch.setattr(
        "quant_harness.daily_paper_runtime.run_paper_execution_cycle",
        lambda *a, **k: {"status": "COMPLETED", "orders": [{"status": "FILLED"}], "reconciliation": {"status": "PASSED"}, "broker_mutation_calls": 0},
    )

    first = run_daily_paper_cycle(URL, ROOT, snapshot_mode="mock")
    second = run_daily_paper_cycle(URL, ROOT, snapshot_mode="mock")

    assert first["freshness"]["status"] == "FRESH"
    assert first["status"] == second["status"] == "COMPLETED"
    assert first["nav"]["as_of"] == second["nav"]["as_of"] == "2026-07-08"
    with psycopg.connect(URL) as conn:
        assert conn.execute("SELECT count(*) FROM paper_daily_nav").fetchone()[0] == 1


def test_concurrent_daily_cycle_fails_closed_before_database_or_network(monkeypatch, tmp_path: Path) -> None:
    calls = {"schema": 0, "update": 0}
    monkeypatch.setattr(
        "quant_harness.daily_paper_runtime.initialize_paper_schema",
        lambda *args, **kwargs: calls.__setitem__("schema", calls["schema"] + 1),
    )
    monkeypatch.setattr(
        "quant_harness.daily_paper_runtime._run_toss_market_update",
        lambda *args, **kwargs: calls.__setitem__("update", calls["update"] + 1),
    )

    with _daily_cycle_lock(tmp_path) as acquired:
        assert acquired == "ACQUIRED"
        result = run_daily_paper_cycle(URL, tmp_path, snapshot_mode="mock")

    assert result["status"] == "HOLD_ONLY"
    assert result["failure"] == "DAILY_CYCLE_ALREADY_RUNNING"
    assert result["orders"] == []
    assert result["broker_mutation_calls"] == 0
    assert calls == {"schema": 0, "update": 0}
