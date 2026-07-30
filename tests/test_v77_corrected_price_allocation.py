from __future__ import annotations

from pathlib import Path
import json

import pandas as pd

from quant_harness.v77_corrected_price_allocation.engine import (
    _load_config,
    independent_reconstruct,
    load_adjusted_market,
    run,
)

ROOT = Path(__file__).resolve().parents[1]


def _ensure_report() -> Path:
    path = ROOT / "reports/v77_corrected_price_allocation/v77_decision.json"
    if not path.exists():
        run(ROOT)
    return path


def test_80_20_is_leader_and_core_not_magic_constant() -> None:
    decision = json.loads(_ensure_report().read_text(encoding="utf-8"))
    assert decision["meaning_of_80_20"].startswith("80% selected leader ETF")
    assert decision["fixed_80_is_unquestioned_constant"] is False
    assert decision["operational_control"] == "FIXED_80__DAILY_EXACT"


def test_adjusted_ohlc_source_is_single_scale() -> None:
    audit = pd.read_csv(ROOT / "reports/v77_corrected_price_allocation/v77_adjusted_price_source_audit.csv")
    assert set(audit["source"]) == {"toss_openapi_1d_adjusted"}
    assert audit["median_close_open_ratio"].between(0.99, 1.01).all()
    assert audit["p01_close_open_ratio"].gt(0.90).all()
    assert audit["p99_close_open_ratio"].lt(1.10).all()


def test_tradable_open_is_never_filled_from_close() -> None:
    cfg = _load_config(ROOT)
    market = load_adjusted_market(ROOT, cfg)
    core = cfg.core_ticker
    assert not market["open"][core].isna().any()
    assert not market["close"][core].isna().any()
    gates = pd.read_csv(ROOT / "reports/v77_corrected_price_allocation/v77_quality_gates.csv")
    assert bool(gates.loc[gates["gate"].eq("NO_OPEN_TO_CLOSE_FALLBACK"), "passed"].iloc[0])


def test_independent_order_reconstruction_matches_selected_account() -> None:
    _ensure_report()
    account = pd.read_csv(ROOT / "reports/v77_corrected_price_allocation/v77_selected_account.csv", parse_dates=["date"])
    orders = pd.read_csv(ROOT / "reports/v77_corrected_price_allocation/v77_selected_orders.csv", parse_dates=["date"], dtype={"ticker": str})
    orders["ticker"] = orders["ticker"].str.zfill(6)
    cfg = _load_config(ROOT)
    market = load_adjusted_market(ROOT, cfg)
    oracle = independent_reconstruct(cfg.initial_capital_krw, market["close"], orders)
    merged = account.merge(oracle, on="date", how="inner")
    assert (merged["nav_krw"] - merged["oracle_nav_krw"]).abs().max() <= 0.01
    assert (merged["cash_krw"] - merged["oracle_cash_krw"]).abs().max() <= 0.01


def test_information_cutoff_is_strictly_before_decision_date() -> None:
    ledger = pd.read_csv(ROOT / "reports/v77_corrected_price_allocation/v77_leadership_selection_ledger.csv", parse_dates=["date", "information_cutoff"])
    used = ledger.dropna(subset=["information_cutoff"])
    assert (used["information_cutoff"] < used["date"]).all()
    assert not ledger["decision_uses_same_day_close"].astype(bool).any()


def test_participation_cap_and_cash_invariants_hold() -> None:
    orders = pd.read_csv(ROOT / "reports/v77_corrected_price_allocation/v77_selected_orders.csv")
    account = pd.read_csv(ROOT / "reports/v77_corrected_price_allocation/v77_selected_account.csv")
    assert orders["participation_of_d1_adv"].dropna().le(0.010001).all()
    assert account["cash_krw"].ge(-0.01).all()
    assert account["nav_krw"].gt(0).all()


def test_shadow_challenger_does_not_auto_promote() -> None:
    decision = json.loads(_ensure_report().read_text(encoding="utf-8"))
    assert decision["shadow_challenger"] == "FIXED_100__EVENT_ONLY"
    assert decision["allocation_promotion_passed"] is False
    assert decision["bootstrap_vs_fixed80_control"]["positive_probability"] < 0.90
    assert decision["paper_runtime_changed"] is False
    assert decision["live_allowed"] is False


def test_event_rebalance_reduces_orders_vs_daily_at_same_weight() -> None:
    trials = pd.read_csv(ROOT / "reports/v77_corrected_price_allocation/v77_allocation_rebalance_trials.csv").set_index("scenario")
    assert trials.loc["FIXED_80__EVENT_ONLY", "order_count"] < trials.loc["FIXED_80__DAILY_EXACT", "order_count"]
    assert trials.loc["FIXED_100__EVENT_ONLY", "order_count"] <= trials.loc["FIXED_100__DAILY_EXACT", "order_count"] + 10


def test_delisting_is_explicitly_deferred() -> None:
    decision = json.loads(_ensure_report().read_text(encoding="utf-8"))
    assert decision["delisting_universe_repair_deferred_by_user"] is True
