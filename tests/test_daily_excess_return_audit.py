from decimal import Decimal
from pathlib import Path
import runpy
from hashlib import sha256

import pytest

A = runpy.run_path(str(Path(__file__).resolve().parents[1] / "scripts/analyze_daily_excess_return.py"))


def test_export_snapshot_hash_is_verified_before_parsing(tmp_path):
    path = tmp_path / "nav.csv"
    path.write_text("as_of,nav_krw\n2026-07-01,1000\n", encoding="utf-8")
    original = sha256(path.read_bytes()).hexdigest()
    assert A["pinned_rows"](path, original)[0]["nav_krw"] == "1000"
    path.write_text("as_of,nav_krw\n2026-07-01,2000\n", encoding="utf-8")
    with pytest.raises(ValueError, match="snapshot hash"):
        A["pinned_rows"](path, original)


def fixture():
    prices = {"ETF": {"2026-07-01": {"open": Decimal(100), "close": Decimal(110)},
                      "2026-07-02": {"open": Decimal(115), "close": Decimal(120)}}}
    trades = [{"paper_fill_id": "buy", "as_of": "2026-07-01", "symbol": "ETF", "side": "BUY",
               "fill_quantity": "5", "fill_price": "101", "fee": "1", "slippage": "1", "cash_delta": "-506", "quantity_delta": "5"},
              {"paper_fill_id": "sell", "as_of": "2026-07-02", "symbol": "ETF", "side": "SELL",
               "fill_quantity": "2", "fill_price": "114", "fee": "1", "slippage": "1", "cash_delta": "227", "quantity_delta": "-2"}]
    nav = [{"as_of": "2026-07-01", "nav_krw": "1044", "cash_krw": "494", "positions_value_krw": "550"},
           {"as_of": "2026-07-02", "nav_krw": "1081", "cash_krw": "721", "positions_value_krw": "360"}]
    return nav, trades, prices


def test_signed_buy_sell_attribution_and_no_cost_double_count():
    nav, trades, prices = fixture()
    result = A["attribute"](nav, trades, prices, Decimal(1000))
    assert result["totals"] == {"opening_position_mark_krw": "50", "trade_open_to_close_krw": "40",
                                "execution_cost_krw": "7", "fee_krw": "2", "residual_krw": "0"}
    assert result["net_contribution_by_etf_krw"] == {"ETF": "81"}
    assert result["scope"] == "ACCOUNTING_ATTRIBUTION_NOT_AGENT_OR_SIGNAL_CAUSAL_VALUE"


@pytest.mark.parametrize("bad", ["missing_price", "position", "cash", "nav", "duplicate", "slippage", "negative_qty", "nonfinite"])
def test_corrupt_or_missing_evidence_fails_closed(bad):
    nav, trades, prices = fixture()
    if bad == "missing_price":
        del prices["ETF"]["2026-07-02"]
    elif bad in {"position", "cash", "nav"}:
        key = {"position": "positions_value_krw", "cash": "cash_krw", "nav": "nav_krw"}[bad]
        nav[1][key] = str(Decimal(nav[1][key]) + 1)
    elif bad == "duplicate":
        trades.append(trades[0].copy())
    elif bad == "slippage":
        trades[0]["slippage"] = "0"
    elif bad == "negative_qty":
        trades[0]["fill_quantity"] = "-5"
    else:
        nav[0]["nav_krw"] = "NaN"
    with pytest.raises((ValueError, KeyError)):
        A["attribute"](nav, trades, prices, Decimal(1000))


def test_d1_reference_is_not_execution_open():
    nav, trades, prices = fixture()
    trades[0]["reference_price"] = "10"  # D-1 sizing reference must not change attributed costs.
    result = A["attribute"](nav, trades, prices, Decimal(1000))
    assert result["totals"]["execution_cost_krw"] == "7"


def test_price_loader_kst_dates_and_duplicate_fail_closed(tmp_path):
    directory = tmp_path / "data/toss_v19c_daily"
    directory.mkdir(parents=True)
    path = directory / "069500_1d.csv"
    path.write_text("timestamp,open,close\n2026-06-30T15:00:00Z,100,110\n", encoding="utf-8")
    assert "2026-07-01" in A["load_prices"](tmp_path, {"069500"})["069500"]
    path.write_text(path.read_text() + "2026-07-01T00:00:00+09:00,100,110\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        A["load_prices"](tmp_path, {"069500"})


def test_costed_benchmark_identity():
    prices = {"069500": {"2026-07-01": {"open": Decimal(100), "close": Decimal(110)},
                         "2026-07-02": {"open": Decimal(115), "close": Decimal(120)}}}
    nav, _, _ = fixture()
    benchmark = {"status": "EXECUTED", "final_liquidation": False, "shares": 5, "residual_cash_krw": "494",
                 "start_date": "2026-07-01", "end_date": "2026-07-02", "execution_price_d_open": "101",
                 "fee_krw": "1", "spread_cost_krw": "4", "impact_cost_krw": "1", "final_nav_krw": "1094"}
    result = A["benchmark_attribution"](nav, prices, benchmark, Decimal(1000))
    assert result["residual_krw"] == "0"
    assert result["gross_price_exposure_gain_krw"] == "100"
    benchmark["spread_cost_krw"] = "5"
    with pytest.raises(ValueError, match="cost mismatch"):
        A["benchmark_attribution"](nav, prices, benchmark, Decimal(1000))
