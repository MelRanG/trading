from __future__ import annotations

from decimal import Decimal
import os
from pathlib import Path

import pandas as pd
import pytest

from quant_harness.historical_operational_replay import (
    _costed_buy_hold_069500,
    _intraday_cache_hash,
    _database_url_from_test_env,
    _market_prices_for_session,
    _metrics,
    _parity,
    _slippage_ledger_validation,
    assert_isolated_test_database,
    run_historical_operational_replay,
)
from quant_harness.v104_end_to_end_causal_challenger_audit.adapter import (
    build_candidate_ledgers,
    load_candidate_specs,
)
from quant_harness.paper_decision_runtime import PaperPreviewError, _digest, _execution_targets_hash, _validate_receipt, apply_replay_preopen_sizing
from quant_harness.paper_decision_runtime import _rebalance_trigger
from quant_harness.paper_execution_runtime import _order_intents_by_registered_priority
from quant_harness.v100_strategy_agent.policy import _target_hash


ROOT = Path(__file__).resolve().parents[1]


def test_replay_requires_test_database_only(monkeypatch) -> None:
    monkeypatch.setenv("TEST_DATABASE_URL", "postgresql://test-only")
    assert _database_url_from_test_env("postgresql://test-only") == "postgresql://test-only"
    with pytest.raises(RuntimeError):
        _database_url_from_test_env("postgresql://production")


def test_replay_rejects_test_alias_that_is_operational_database(monkeypatch) -> None:
    url = "postgresql://user:secret@db.local:5432/stocks"
    monkeypatch.setenv("TEST_DATABASE_URL", url)
    monkeypatch.setenv("DATABASE_URL", url)
    with pytest.raises(RuntimeError, match="operational database"):
        assert_isolated_test_database(url)


def test_replay_database_identity_resolves_uri_destination_overrides(monkeypatch) -> None:
    from quant_harness.historical_operational_replay import _database_identity

    monkeypatch.setenv("TEST_DATABASE_URL", "postgresql://user@db.local/stocks_test?dbname=stocks")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user@db.local:5432/stocks")
    with pytest.raises(RuntimeError, match="operational database"):
        assert_isolated_test_database(os.environ["TEST_DATABASE_URL"])
    assert _database_identity("postgresql://user@db.local/stocks") == _database_identity("postgresql://user@db.local:5432/stocks")


def test_replay_accepts_scoped_test_schema_when_database_is_distinct(monkeypatch) -> None:
    base = "postgresql://user:secret@db.local:5432/stocks_test"
    scoped = base + "?options=-c%20search_path%3Dreplay_test"
    monkeypatch.setenv("TEST_DATABASE_URL", base)
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:secret@db.local:5432/stocks")
    assert assert_isolated_test_database(scoped) == scoped


def test_replay_point_in_time_and_d_minus_one_contract() -> None:
    built = build_candidate_ledgers(ROOT, load_candidate_specs(ROOT)["V69_PARENT"], use_common_cutoff=True)
    ledger = built["ledger"]
    dates = pd.to_datetime(ledger["date"])
    cutoff = pd.to_datetime(ledger["information_cutoff"])
    assert not ledger["decision_uses_same_day_close"].fillna(False).any()
    assert bool((cutoff.isna() | (cutoff < dates)).all())
    assert dates.is_unique


def test_replay_metrics_use_nav_and_benchmark_without_rebuilding_strategy() -> None:
    nav = [
        {"as_of": "2026-07-01", "nav_krw": Decimal("100"), "cash_krw": Decimal("100"), "positions_value_krw": Decimal("0")},
        {"as_of": "2026-07-02", "nav_krw": Decimal("101"), "cash_krw": Decimal("101"), "positions_value_krw": Decimal("0")},
    ]
    metrics = _metrics(ROOT, nav, [], Decimal("100"))
    assert metrics["initial_capital_krw"] == "100"
    assert metrics["final_nav_krw"] == "101"
    assert metrics["total_trading_days"] == 2


def test_replay_metrics_include_opening_to_first_nav_return_and_initial_peak() -> None:
    nav = [
        {"as_of": "2026-07-01", "nav_krw": Decimal("90"), "cash_krw": Decimal("90"), "positions_value_krw": Decimal("0")},
        {"as_of": "2026-07-02", "nav_krw": Decimal("100"), "cash_krw": Decimal("100"), "positions_value_krw": Decimal("0")},
        {"as_of": "2026-07-03", "nav_krw": Decimal("80"), "cash_krw": Decimal("80"), "positions_value_krw": Decimal("0")},
    ]
    metrics = _metrics(ROOT, nav, [], Decimal("100"))
    assert metrics["total_return"] == -0.2
    assert metrics["worst_daily_return"] == pytest.approx(-0.2)
    assert metrics["maximum_drawdown"] == pytest.approx(-0.2)
    assert metrics["drawdown_includes_opening_initial_capital"] is True


def test_069500_investable_buy_hold_uses_same_open_cost_adv_and_whole_share_rules() -> None:
    from quant_harness.v77_corrected_price_allocation import engine as v77

    dates = pd.to_datetime(["2026-07-01", "2026-07-02"])
    market = {
        "close": pd.DataFrame({"069500": [100.0, 110.0]}, index=dates),
        "open": pd.DataFrame({"069500": [101.0, 108.0]}, index=dates),
        "adv20_d1": pd.DataFrame({"069500": [100_000_000.0, 100_000_000.0]}, index=dates),
    }
    result = _costed_buy_hold_069500(
        ROOT, market, dates[1:], Decimal("1000000"), v77._load_config(ROOT).base_execution
    )
    assert result["status"] == "EXECUTED"
    assert result["shares"] < 10000
    assert Decimal(result["fee_krw"]) > 0
    assert Decimal(result["spread_cost_krw"]) > 0
    assert result["final_liquidation"] is False


def test_costed_buy_hold_applies_minimum_after_adv_and_cash_clipping() -> None:
    from quant_harness.v77_corrected_price_allocation import engine as v77

    dates = pd.to_datetime(["2026-07-01", "2026-07-02"])
    market = {
        "close": pd.DataFrame({"069500": [100.0, 110.0]}, index=dates),
        "open": pd.DataFrame({"069500": [101.0, 108.0]}, index=dates),
        "adv20_d1": pd.DataFrame({"069500": [100_000_000.0, 1_000_000.0]}, index=dates),
    }
    # D-1 sizing requests 10,000 shares, but the 1% ADV cap permits 92 at
    # the opening price. Post-cap notional is below the minimum, so no fill.
    result = _costed_buy_hold_069500(
        ROOT, market, dates[1:], Decimal("1000000"), v77._load_config(ROOT).base_execution
    )
    assert result["status"] == "NO_FILL"
    assert result["shares"] == 0
    assert result["residual_cash_krw"] == "1000000"


def test_benchmark_endpoint_missing_is_not_silently_replaced_by_earlier_date(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    pd.DataFrame({"date": ["2026-07-01"], "ticker": ["KS11"], "close": [100]}).to_csv(
        data / "all_prices_long_v62_9_expanded.csv", index=False
    )
    nav = [
        {"as_of": "2026-07-01", "nav_krw": Decimal("100"), "cash_krw": Decimal("100"), "positions_value_krw": Decimal("0")},
        {"as_of": "2026-07-02", "nav_krw": Decimal("101"), "cash_krw": Decimal("101"), "positions_value_krw": Decimal("0")},
    ]
    metrics = _metrics(tmp_path, nav, [], Decimal("100"))
    assert metrics["benchmark_total_return"] is None
    assert metrics["benchmark_complete_daily_coverage"] is False
    assert metrics["benchmark_missing_dates"] == ["2026-07-02"]


def test_open5m_warmup_resolver_uses_the_same_adjusted_daily_open_source() -> None:
    from quant_harness.open_5m_full_nav_validation import _resolver
    from quant_harness.v77_corrected_price_allocation import engine as v77

    cfg = v77._load_config(ROOT, use_common_cutoff=True)
    market = v77.load_adjusted_market(ROOT, cfg)
    expected = Decimal(str(market["open"].loc[pd.Timestamp("2021-10-13"), "069500"]))
    actual = _resolver(ROOT)(
        {"as_of": pd.Timestamp("2021-10-13")},
        [{"intent_id": "warmup", "symbol": "069500"}],
    )
    assert actual == {"warmup": expected}


def test_replay_prices_size_from_prior_close_and_execute_at_session_open() -> None:
    index = pd.to_datetime(["2026-07-01", "2026-07-02"])
    market = {
        "close": pd.DataFrame({"069500": [100, 999]}, index=index),
        "open": pd.DataFrame({"069500": [101, 110]}, index=index),
    }
    prior_date, sizing, execution = _market_prices_for_session(market, "2026-07-02", {"069500"})
    assert prior_date == "2026-07-01"
    assert sizing["069500"] == Decimal("100")
    assert execution["069500"] == Decimal("110")


def test_replay_preopen_sizing_changes_execution_receipt_not_strategy_target() -> None:
    evidence = {
        "strategy_build_hash": "build",
        "input_hash": "base-input",
        "candidate_fingerprint": "candidate",
        "decision_uses_same_day_close": False,
        "target_hash": _target_hash({"069500": 0.5, "102110": 0.5}),
    }
    targets = [
        {"symbol": "069500", "target_weight": Decimal("0.5"), "target_notional": Decimal("500"), "reference_price": Decimal("125"), "target_quantity": Decimal("4"), "adv20_d1_krw": Decimal("100000")},
        {"symbol": "102110", "target_weight": Decimal("0.5"), "target_notional": Decimal("500"), "reference_price": Decimal("20"), "target_quantity": Decimal("25"), "adv20_d1_krw": Decimal("100000")},
    ]
    evidence["execution_targets_hash"] = _execution_targets_hash(targets)
    body = {"status": "PASSED", "validator": "test", "evidence": evidence}
    preview = {
        "as_of": "2026-07-02",
        "initial_capital_krw": Decimal("1000"),
        "input_hash": "base-input",
        "session_id": "base-session",
        "decision_id": "base-decision",
        "strategy_build_hash": "build",
        "candidate_fingerprint": "candidate",
        "target_hash": evidence["target_hash"],
        "target_weights": {"069500": 0.5, "102110": 0.5},
        "targets": targets,
        "decision_receipt": {**body, "receipt_hash": _digest(body)},
    }
    result = apply_replay_preopen_sizing(
        preview,
        prior_session="2026-07-01",
        sizing_prices={"069500": Decimal("100"), "102110": Decimal("20")},
        sizing_nav_krw=Decimal("1200"),
        execution_contract_hash="a" * 64,
    )
    _validate_receipt(result)
    assert result["targets"][0]["target_quantity"] == Decimal("6")
    assert result["targets"][0]["target_notional"] == Decimal("600.0")
    assert result["targets"][0]["reference_price"] == Decimal("100")
    assert result["target_hash"] == preview["target_hash"]
    assert result["targets"][0]["target_weight"] == preview["targets"][0]["target_weight"]
    assert result["decision_receipt"]["evidence"]["execution_contract_hash"] == "a" * 64


def test_replay_target_sizing_uses_previous_nav_not_fixed_initial_capital() -> None:
    evidence = {
        "strategy_build_hash": "build", "input_hash": "base-input",
        "candidate_fingerprint": "candidate", "decision_uses_same_day_close": False,
        "target_hash": _target_hash({"069500": 1.0}),
    }
    target = {"symbol": "069500", "target_weight": 1.0, "target_notional": 1000, "reference_price": 100, "target_quantity": 10, "adv20_d1_krw": 100000}
    evidence["execution_targets_hash"] = _execution_targets_hash([target])
    body = {"status": "PASSED", "validator": "test", "evidence": evidence}
    preview = {
        "as_of": "2026-07-02", "initial_capital_krw": Decimal("1000"), "input_hash": "base-input",
        "session_id": "base-session", "decision_id": "base-decision", "strategy_build_hash": "build",
        "candidate_fingerprint": "candidate", "target_hash": evidence["target_hash"],
        "target_weights": {"069500": 1.0}, "targets": [target],
        "decision_receipt": {**body, "receipt_hash": _digest(body)},
    }
    sized = apply_replay_preopen_sizing(
        preview, prior_session="2026-07-01", sizing_prices={"069500": 100},
        sizing_nav_krw=Decimal("1250"), execution_contract_hash="b" * 64,
    )
    assert sized["targets"][0]["target_quantity"] == Decimal("12")
    assert sized["targets"][0]["target_notional"] == Decimal("1250.0")
    assert sized["execution_contract"]["quantity_policy"] == "prior_close_nav_times_target_weight_divided_by_prior_close_floor"


def test_replay_sizing_does_not_repair_an_invalid_original_receipt() -> None:
    weights = {"069500": 1.0}
    target = {"symbol": "069500", "target_weight": 1.0, "target_notional": 1000, "reference_price": 100, "target_quantity": 10, "adv20_d1_krw": 100000}
    evidence = {
        "strategy_build_hash": "build", "input_hash": "base-input",
        "candidate_fingerprint": "candidate", "decision_uses_same_day_close": False,
        "target_hash": _target_hash(weights),
        "execution_targets_hash": _execution_targets_hash([target]),
    }
    body = {"status": "PASSED", "validator": "test", "evidence": evidence}
    preview = {
        "as_of": "2026-07-02", "initial_capital_krw": Decimal("1000"), "input_hash": "base-input",
        "session_id": "base-session", "decision_id": "base-decision", "strategy_build_hash": "build",
        "candidate_fingerprint": "candidate", "target_hash": evidence["target_hash"],
        "target_weights": weights, "targets": [target],
        "decision_receipt": {**body, "receipt_hash": "0" * 64},
    }
    with pytest.raises(PaperPreviewError, match="strategy receipt is invalid"):
        apply_replay_preopen_sizing(
            preview, prior_session="2026-07-01", sizing_prices={"069500": 100},
            sizing_nav_krw=Decimal("1250"), execution_contract_hash="c" * 64,
        )


def test_v101_rebalance_gate_honors_band_pending_and_target_change() -> None:
    assert not _rebalance_trigger(
        target_changed=False, pending=False,
        max_abs_weight_drift=Decimal("0.049"), band=Decimal("0.05"),
    )
    assert _rebalance_trigger(
        target_changed=False, pending=False,
        max_abs_weight_drift=Decimal("0.05"), band=Decimal("0.05"),
    )
    assert _rebalance_trigger(
        target_changed=False, pending=True,
        max_abs_weight_drift=Decimal("0.01"), band=Decimal("0.05"),
    )
    assert _rebalance_trigger(
        target_changed=True, pending=False,
        max_abs_weight_drift=Decimal("0.01"), band=Decimal("0.05"),
    )


def test_v101_registered_buy_priority_is_used_by_paper_execution() -> None:
    specs = load_candidate_specs(ROOT)
    targets = [
        {"symbol": "069500", "target_weight": 0.20, "target_quantity": 20},
        {"symbol": "102110", "target_weight": 0.80, "target_quantity": 80},
    ]
    v69 = _order_intents_by_registered_priority(
        ROOT,
        [
            {"symbol": "102110", "side": "BUY", "current_quantity": 0},
            {"symbol": "069500", "side": "BUY", "current_quantity": 0},
        ],
        targets,
        specs["V69_PARENT"].fingerprint,
    )
    assert [row["symbol"] for row in v69] == ["069500", "102110"]

    v79 = _order_intents_by_registered_priority(
        ROOT,
        [
            {"symbol": "102110", "side": "BUY", "current_quantity": 75},
            {"symbol": "069500", "side": "BUY", "current_quantity": 0},
        ],
        targets,
        specs["V79_NO63_VOL_GUARD"].fingerprint,
    )
    assert [row["symbol"] for row in v79] == ["069500", "102110"]


def test_replay_target_quantity_tampering_invalidates_receipt() -> None:
    evidence = {
        "strategy_build_hash": "build", "input_hash": "base-input",
        "candidate_fingerprint": "candidate", "decision_uses_same_day_close": False,
    }
    weights = {"069500": 1.0}
    target = {"symbol": "069500", "target_weight": 1.0, "target_notional": 1000, "reference_price": 100, "target_quantity": 10, "adv20_d1_krw": 100000}
    evidence["target_hash"] = _target_hash(weights)
    evidence["execution_targets_hash"] = _execution_targets_hash([target])
    body = {"status": "PASSED", "validator": "test", "evidence": evidence}
    preview = {
        "target_hash": evidence["target_hash"], "target_weights": weights, "targets": [target],
        "strategy_build_hash": "build", "input_hash": "base-input", "candidate_fingerprint": "candidate",
        "decision_receipt": {**body, "receipt_hash": _digest(body)},
    }
    _validate_receipt(preview)
    preview["targets"][0]["target_quantity"] = 11
    with pytest.raises(PaperPreviewError, match="executable target payload"):
        _validate_receipt(preview)


def test_replay_intraday_cache_content_is_in_fingerprint(tmp_path: Path) -> None:
    from datetime import date

    cache = tmp_path / "data/toss_intraday_1m/069500"
    cache.mkdir(parents=True)
    path = cache / "2026-07-01.csv"
    path.write_text("timestamp,open\n2026-07-01 09:01,100\n", encoding="utf-8")
    first = _intraday_cache_hash(tmp_path, date(2026, 7, 1), date(2026, 7, 1))
    path.write_text("timestamp,open\n2026-07-01 09:01,101\n", encoding="utf-8")
    second = _intraday_cache_hash(tmp_path, date(2026, 7, 1), date(2026, 7, 1))
    assert first != second


def test_replay_fingerprint_refuses_a_resume_after_input_changes(tmp_path: Path) -> None:
    from quant_harness.historical_operational_replay import _check_or_start_replay_contract

    contract = {"fingerprint": "first"}
    path = tmp_path / "replay_contract.json"
    state = _check_or_start_replay_contract(path, contract, reset=False, existing_dates=set())
    state["status"] = "RUNNING"
    state["completed_dates"] = []
    path.write_text(__import__("json").dumps(state), encoding="utf-8")
    with pytest.raises(RuntimeError, match="fingerprint changed"):
        _check_or_start_replay_contract(path, {"fingerprint": "changed"}, reset=False, existing_dates=set())


def test_replay_refuses_unfingerprinted_existing_nav(tmp_path: Path) -> None:
    from datetime import date
    from quant_harness.historical_operational_replay import _check_or_start_replay_contract

    with pytest.raises(RuntimeError, match="no matching replay contract"):
        _check_or_start_replay_contract(
            tmp_path / "replay_contract.json", {"fingerprint": "first"}, reset=False,
            existing_dates={date(2026, 7, 1)},
        )


def test_replay_does_not_claim_slippage_ledger_reconciliation_without_a_ledger_field() -> None:
    result = _slippage_ledger_validation()
    assert result["slippage_ledger_matches_fills"] is None
    assert result["slippage_ledger_validation"] == "NOT_TRACKED_IN_LEDGER"


def test_replay_entrypoint_does_not_fallback_to_operational_database(monkeypatch) -> None:
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError):
        run_historical_operational_replay(ROOT, "postgresql://anything")


def test_parity_summary_has_fail_closed_shape() -> None:
    result = _parity(ROOT, {})
    assert result["comparable_dates"] == 0
    assert result["exact_dates"] == 0
    assert result["parity_ratio"] is None


def _legacy_reference(root: Path, leader="091180") -> None:
    folder = root / "reports/v100_strategy_agent"
    folder.mkdir(parents=True)
    pd.DataFrame([{"date": "2026-07-01", "leader_ticker": leader,
                   "target_hash": "target", "target_weights_json": '{"069500": 1.0}'}]).to_csv(
        folder / "v100_target_ledger_v69_FIXED_PARENT_ALLOCATIONS.csv", index=False)


def test_challenger_parity_never_uses_parent_reference(tmp_path: Path) -> None:
    _legacy_reference(tmp_path)
    preview = {"2026-07-01": {"candidate_id": "V79_NO63_VOL_GUARD"}}
    result = _parity(tmp_path, preview, candidate_id="V79_NO63_VOL_GUARD")
    assert result["status"] == "NOT_AVAILABLE"
    assert result["parity_ratio"] is None
    assert result["artifact"] is None
    assert result["reason"] == "NO_MODEL_MATCHED_INDEPENDENT_REFERENCE"


@pytest.mark.parametrize("current,reference", [([], "091180"), (["091180"], None)])
def test_legacy_parity_detects_candidate_mismatch_in_both_directions(tmp_path: Path, current, reference) -> None:
    _legacy_reference(tmp_path, reference)
    preview = {"2026-07-01": {"selected_candidates": current, "target_hash": "target",
                             "target_weights": {"069500": 1.0}}}
    result = _parity(tmp_path, preview)
    assert result["mismatch_counts"] == {"candidate": 1}
    assert result["independent_strategy_validation"] is False


def test_legacy_regime_difference_is_not_hidden_by_target_match(tmp_path: Path) -> None:
    _legacy_reference(tmp_path)
    folder = tmp_path / "reports/v90_trade_attribution"
    folder.mkdir()
    pd.DataFrame([{"date": "2026-07-01", "regime_d1": "BROAD_BULL"}]).to_csv(folder / "v90_regime_d1.csv", index=False)
    preview = {"2026-07-01": {"selected_candidates": ["091180"], "target_hash": "target",
                             "target_weights": {"069500": 1.0}, "regime": "RISK_OFF"}}
    result = _parity(tmp_path, preview)
    assert result["mismatch_counts"] == {"regime": 1}
    assert result["target_candidate_parity_ratio"] == 1.0
    assert result["legacy_regime_mismatch_dates"] == ["2026-07-01"]


def test_parity_rejects_mixed_candidate_identity(tmp_path: Path) -> None:
    _legacy_reference(tmp_path)
    with pytest.raises(ValueError, match="candidate identity"):
        _parity(tmp_path, {"2026-07-01": {"candidate_id": "V79_NO63_VOL_GUARD"}})


def test_parity_rejects_duplicate_reference_dates(tmp_path: Path) -> None:
    _legacy_reference(tmp_path)
    path = tmp_path / "reports/v100_strategy_agent/v100_target_ledger_v69_FIXED_PARENT_ALLOCATIONS.csv"
    frame = pd.read_csv(path)
    pd.concat([frame, frame], ignore_index=True).to_csv(path, index=False)
    with pytest.raises(ValueError, match="duplicate"):
        _parity(tmp_path, {})


def test_parity_no_overlap_never_claims_pass(tmp_path: Path) -> None:
    _legacy_reference(tmp_path)
    result = _parity(tmp_path, {"2026-07-02": {}})
    assert result["parity_ratio"] is None
    assert result["uncompared_dates"] == ["2026-07-02"]
    assert result["status"] == "NO_COMPARABLE_DATES"


def test_missing_regime_reference_never_claims_complete_parity(tmp_path: Path) -> None:
    _legacy_reference(tmp_path)
    result = _parity(tmp_path, {"2026-07-01": {"selected_candidates": ["091180"],
                    "target_hash": "target", "target_weights": {"069500": 1.0}}})
    assert result["target_candidate_parity_ratio"] == 1.0
    assert result["parity_ratio"] is None
    assert result["regime_comparable_dates"] == 0
    assert result["regime_uncompared_dates"] == ["2026-07-01"]
