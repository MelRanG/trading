from __future__ import annotations

from decimal import Decimal

from quant_harness.paper_execution_runtime import (
    _adv_participation_cap_quantity,
    _partition_executable_intents,
    _require_paper_intent_authority,
)
from quant_harness.daily_paper_runtime import _paper_nav_components, _require_isolated_test_database, validate_market_freshness
from quant_harness.daily_paper_runtime import _run_toss_market_update


def test_only_preview_authorized_intents_enter_paper_execution() -> None:
    executable, blocked = _partition_executable_intents(
        [
            {"intent_id": "ok", "authority_status": "PREVIEW_ONLY"},
            {"intent_id": "hold", "authority_status": "HOLD_ONLY"},
            {"intent_id": "missing"},
        ]
    )

    assert [row["intent_id"] for row in executable] == ["ok"]
    assert {row["intent_id"] for row in blocked} == {"hold", "missing"}


def test_low_level_paper_order_requires_explicit_preview_authority() -> None:
    _require_paper_intent_authority({"authority_status": "PREVIEW_ONLY"})
    for status in (None, "HOLD_ONLY", "BLOCKED"):
        try:
            _require_paper_intent_authority({"authority_status": status})
        except Exception as exc:
            assert "authority is not PREVIEW_ONLY" in str(exc)
        else:
            raise AssertionError("low-level execution must fail closed without preview authority")


def test_adv_participation_cap_uses_floor_of_adv_notional_capacity() -> None:
    assert _adv_participation_cap_quantity(
        adv_krw=Decimal("1000000"), reference_price=Decimal("3000"), participation=Decimal("0.01")
    ) == 3


def test_adv_participation_cap_fails_closed_for_invalid_inputs() -> None:
    assert _adv_participation_cap_quantity(
        adv_krw=Decimal("0"), reference_price=Decimal("100"), participation=Decimal("0.01")
    ) == 0


def test_missing_or_invalid_nav_mark_fails_closed() -> None:
    try:
        _paper_nav_components(
            cash=Decimal("500"),
            positions={"069500": Decimal("2")},
            marks={"069500": Decimal("0")},
        )
    except ValueError as exc:
        assert "missing or invalid valuation marks" in str(exc)
    else:
        raise AssertionError("missing NAV marks must not silently value positions at zero")


def test_operational_freshness_requires_official_market_calendar_cutoff(tmp_path) -> None:
    result = validate_market_freshness(tmp_path)
    assert result.status == "FAILED"
    assert result.failures == ("OFFICIAL_MARKET_CALENDAR_CUTOFF_REQUIRED",)
    assert result.temporal_freshness == "UNKNOWN"


def test_daily_market_update_uses_toss_get_adapters_not_staged_provider(monkeypatch) -> None:
    from types import SimpleNamespace

    calls: list[str] = []
    monkeypatch.setattr(
        "quant_harness.daily_paper_runtime._latest_completed_toss_trading_day",
        lambda client: "2026-10-02",
    )
    monkeypatch.setattr(
        "quant_harness.daily_paper_runtime.run_toss_incremental_update",
        lambda root, write_output, as_of: (calls.append(f"etf:{as_of}") or SimpleNamespace(
            cutoff="2026-10-02", symbols=26, succeeded=26, failed=(), rows_added=10,
            backup_dir="backup", provider="toss_openapi_adjusted", endpoint="GET /api/v1/candles"
        )),
    )
    monkeypatch.setattr(
        "quant_harness.daily_paper_runtime.run_toss_market_indicator_ks11_update",
        lambda root, write_output, as_of: (calls.append(f"ks11:{as_of}") or SimpleNamespace(
            cutoff="2026-10-01", symbols=1, succeeded=1, failed=(), rows_added=1,
            backup_dir="", provider="toss_market_indicator", endpoint="GET /api/v1/market-indicators/{symbol}/candles"
        )),
    )

    result = _run_toss_market_update("workspace")

    assert calls == ["etf:2026-10-02", "ks11:2026-10-02"]
    assert result["cutoff"] == "2026-10-01"
    assert result["provider"] == "toss_openapi_adjusted+toss_market_indicator"
    assert result["rows_added"] == 11
    assert result["latest_completed_date"] == "2026-10-02"
    assert result["failed"] == ()


def test_forward_paper_database_requires_distinct_test_database() -> None:
    assert _require_isolated_test_database(
        "postgresql://test/db", test_database_url="postgresql://test/db", operational_database_url="postgresql://prod/db"
    ) == "postgresql://test/db"
    for test_url, production_url in ((None, "postgresql://prod/db"), ("postgresql://prod/db", "postgresql://prod/db")):
        try:
            _require_isolated_test_database(
                test_url, test_database_url=test_url, operational_database_url=production_url
            )
        except RuntimeError as exc:
            assert "TEST_DATABASE_URL" in str(exc)
        else:
            raise AssertionError("Forward Paper must never fall back to the operational database")
    assert _adv_participation_cap_quantity(
        adv_krw=Decimal("1000000"), reference_price=Decimal("0"), participation=Decimal("0.01")
    ) == 0


def test_preview_cache_key_changes_when_market_input_changes(tmp_path, monkeypatch) -> None:
    from quant_harness.paper_decision_runtime import BUILD_FILES, CONFIG_FILES, build_strategy_preview

    data_dir = tmp_path / "data/toss_v19c_daily"
    data_dir.mkdir(parents=True)
    price_path = data_dir / "069500_1d.csv"
    price_path.write_text("date,close\n2026-10-01,100\n", encoding="utf-8")
    benchmark_path = tmp_path / "data/all_prices_long_v62_9_expanded.csv"
    benchmark_path.parent.mkdir(parents=True, exist_ok=True)
    benchmark_path.write_text("date,ticker,close\n2026-10-01,KS11,100\n", encoding="utf-8")
    manifest = tmp_path / "data/canonical/v84_market_manifest.csv"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text("ticker,start,end\n069500,2026-10-01,2026-10-01\n", encoding="utf-8")
    for relative in (*CONFIG_FILES, *BUILD_FILES):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture", encoding="utf-8")

    seen_fingerprints: list[str] = []
    monkeypatch.setattr(
        "quant_harness.paper_decision_runtime._build_strategy_preview_cached",
        lambda root_text, as_of_text, candidate_id, input_fingerprint: (
            seen_fingerprints.append(input_fingerprint) or input_fingerprint
        ),
    )
    first = build_strategy_preview(tmp_path, as_of="2026-10-01")
    price_path.write_text("date,close\n2026-10-01,101\n", encoding="utf-8")
    second = build_strategy_preview(tmp_path, as_of="2026-10-01")

    assert first != second
    assert len(set(seen_fingerprints)) == 2
