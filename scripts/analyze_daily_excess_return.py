"""Read-only accounting attribution of the frozen daily exports, not alpha research.

No model, replay, database, broker or network is executed.  Current price files
must still match the input hash recorded by both original runs.
"""
from __future__ import annotations

import csv
from datetime import datetime
from decimal import Decimal
from hashlib import sha256
import io
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from audit_current_model_evidence import MODELS, audit_run, save_report
from quant_harness.v104_end_to_end_causal_challenger_audit.adapter import _input_hash

ZERO = Decimal("0")
TOL = Decimal("0.00001")


def rows(path: Path) -> list[dict]:
    return list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8-sig"))))


def pinned_rows(path: Path, expected_hash: str) -> list[dict]:
    snapshot = path.read_bytes()
    if sha256(snapshot).hexdigest() != expected_hash:
        raise ValueError("export snapshot hash mismatch")
    return list(csv.DictReader(io.StringIO(snapshot.decode("utf-8-sig"))))


def decimal(value) -> Decimal:
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError("nonfinite accounting input")
    return result


def load_prices(root: Path, symbols: set[str]) -> dict:
    prices = {}
    for symbol in sorted(symbols):
        source = root / "data/toss_v19c_daily" / f"{symbol}_1d.csv"
        panel = {}
        for row in rows(source):
            timestamp = datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00"))
            if timestamp.tzinfo is None:
                raise ValueError(f"ambiguous price timestamp: {symbol}")
            date = timestamp.astimezone(ZoneInfo("Asia/Seoul")).date().isoformat()
            if date in panel:
                raise ValueError(f"duplicate price date: {symbol} {date}")
            panel[date] = {key: decimal(row[key]) for key in ("open", "close")}
            if any(value <= ZERO for value in panel[date].values()):
                raise ValueError(f"invalid price: {symbol} {date}")
        prices[symbol] = panel
    return prices


def attribute(nav: list[dict], trades: list[dict], prices: dict, initial: Decimal) -> dict:
    """Delta NAV = opening-position mark + trade-to-close mark - execution cost - fee.

    reference_price in the export is D-1 sizing close, NOT raw execution open.
    Execution cost is signed_delta * (fill_price - raw_D_open).  It already
    includes spread/impact and must never be deducted a second time.
    """
    dates = [row["as_of"] for row in nav]
    if not dates or dates != sorted(set(dates)):
        raise ValueError("invalid NAV date sequence")
    by_date = {date: [] for date in dates}
    seen = set()
    for fill in trades:
        if not fill.get("paper_fill_id"):
            continue
        if fill["paper_fill_id"] in seen or fill["as_of"] not in by_date:
            raise ValueError("duplicate or out-of-window fill")
        seen.add(fill["paper_fill_id"])
        by_date[fill["as_of"]].append(fill)
    quantities, previous_closes, symbols = {}, {}, {}
    cash, previous_nav = initial, initial
    daily, idle = [], 0
    for row in nav:
        date = row["as_of"]
        mark = trade_mark = execution_cost = fee = ZERO
        for symbol, quantity in quantities.items():
            if quantity:
                close = prices[symbol][date]["close"]
                gain = quantity * (close - previous_closes[symbol])
                mark += gain
                symbols.setdefault(symbol, ZERO)
                symbols[symbol] += gain
        for fill in by_date[date]:
            symbol, side = fill["symbol"], fill["side"]
            if side not in {"BUY", "SELL"}:
                raise ValueError("invalid fill side")
            qty, fill_price, cost = (decimal(fill[key]) for key in ("fill_quantity", "fill_price", "fee"))
            if qty <= ZERO or fill_price <= ZERO or cost < ZERO:
                raise ValueError("invalid fill terms")
            delta = qty if side == "BUY" else -qty
            raw_open, close = (prices[symbol][date][key] for key in ("open", "close"))
            fill_cash = -delta * fill_price - cost
            if abs(fill_cash - decimal(fill["cash_delta"])) > TOL or delta != decimal(fill["quantity_delta"]):
                raise ValueError("fill cash or quantity identity mismatch")
            if abs(qty * abs(fill_price - raw_open) - qty * decimal(fill["slippage"])) > TOL:
                raise ValueError("export slippage does not match raw execution open")
            gain, slip = delta * (close - raw_open), delta * (fill_price - raw_open)
            trade_mark += gain
            execution_cost += slip
            fee += cost
            cash += fill_cash
            quantities[symbol] = quantities.get(symbol, ZERO) + delta
            if quantities[symbol] < ZERO:
                raise ValueError("negative position")
            symbols[symbol] = symbols.get(symbol, ZERO) + gain - slip - cost
        position_value = sum((q * prices[s][date]["close"] for s, q in quantities.items() if q), ZERO)
        equity = decimal(row["nav_krw"])
        if abs(cash - decimal(row["cash_krw"])) > TOL or abs(position_value - decimal(row["positions_value_krw"])) > TOL:
            raise ValueError("cash or independently repriced position mismatch")
        residual = equity - previous_nav - (mark + trade_mark - execution_cost - fee)
        if abs(residual) > TOL or abs(equity - cash - position_value) > TOL:
            raise ValueError("unexplained daily NAV residual")
        daily.append({"date": date, "opening_position_mark_krw": str(mark), "trade_open_to_close_krw": str(trade_mark),
                      "execution_cost_krw": str(execution_cost), "fee_krw": str(fee), "residual_krw": str(residual)})
        idle += int(position_value == ZERO)
        previous_nav = equity
        previous_closes = {s: prices[s][date]["close"] for s, q in quantities.items() if q}
    totals = {key: str(sum((decimal(row[key]) for row in daily), ZERO)) for key in daily[0] if key != "date"}
    return {"initial_nav_krw": str(initial), "final_nav_krw": str(previous_nav), "totals": totals,
            "net_contribution_by_etf_krw": {s: str(v) for s, v in sorted(symbols.items(), key=lambda item: item[1], reverse=True)},
            "zero_position_days": idle, "zero_position_days_definition": "NO_POSITION_AT_SESSION_CLOSE_NOT_INTRADAY_EXPOSURE", "daily": daily,
            "scope": "ACCOUNTING_ATTRIBUTION_NOT_AGENT_OR_SIGNAL_CAUSAL_VALUE"}


def benchmark_attribution(nav: list[dict], prices: dict, benchmark: dict, initial: Decimal) -> dict:
    if benchmark.get("status") != "EXECUTED" or benchmark.get("final_liquidation") is not False:
        raise ValueError("unknown benchmark execution contract")
    shares = decimal(benchmark["shares"])
    cash = decimal(benchmark["residual_cash_krw"])
    first, last = nav[0]["as_of"], nav[-1]["as_of"]
    if benchmark["start_date"] != first or benchmark["end_date"] != last:
        raise ValueError("benchmark period mismatch")
    open_price = prices["069500"][first]["open"]
    execution = shares * (decimal(benchmark["execution_price_d_open"]) - open_price)
    fee = decimal(benchmark["fee_krw"])
    if abs(execution - decimal(benchmark["spread_cost_krw"]) - decimal(benchmark["impact_cost_krw"])) > TOL:
        raise ValueError("benchmark cost mismatch")
    final = cash + shares * prices["069500"][last]["close"]
    gross = shares * (prices["069500"][last]["close"] - open_price)
    residual = final - initial - gross + execution + fee
    if abs(final - decimal(benchmark["final_nav_krw"])) > TOL or abs(residual) > TOL:
        raise ValueError("benchmark NAV mismatch")
    return {"final_nav_krw": str(final), "gross_price_exposure_gain_krw": str(gross),
            "execution_cost_krw": str(execution), "fee_krw": str(fee), "residual_krw": str(residual)}


def main() -> None:
    folder = ROOT / "runtime/contract_aligned_comparison_20261004_run2"
    frozen = json.loads((ROOT / "runtime/current_model_evidence_audit/verified_exports_v3.json").read_text(encoding="utf-8"))
    input_before = _input_hash(ROOT)
    output = {}
    for model in MODELS:
        audited = audit_run(folder / model, model)
        pinned = next(run for run in frozen["runs"] if run["candidate_id"] == model)
        if audited["artifact_sha256"] != pinned["artifact_sha256"] or input_before != audited["recorded_contract"]["data_input_hash"]:
            raise ValueError("frozen export or data input hash mismatch")
        nav = pinned_rows(folder / model / "daily_nav.csv", audited["artifact_sha256"]["daily_nav.csv"])
        trades = pinned_rows(folder / model / "trades.csv", audited["artifact_sha256"]["trades.csv"])
        prices = load_prices(ROOT, {r["symbol"] for r in trades} | {"069500"})
        initial = decimal(audited["recorded_contract"]["initial_capital_krw"])
        result = attribute(nav, trades, prices, initial)
        benchmark = benchmark_attribution(nav, prices, audited["metrics"]["069500_investable_buy_and_hold"], initial)
        total = result["totals"]
        gross_difference = decimal(total["opening_position_mark_krw"]) + decimal(total["trade_open_to_close_krw"]) - decimal(benchmark["gross_price_exposure_gain_krw"])
        execution_difference = decimal(total["execution_cost_krw"]) - decimal(benchmark["execution_cost_krw"])
        fee_difference = decimal(total["fee_krw"]) - decimal(benchmark["fee_krw"])
        delta = decimal(result["final_nav_krw"]) - decimal(benchmark["final_nav_krw"])
        residual = delta - gross_difference + execution_difference + fee_difference
        if abs(residual) > TOL:
            raise ValueError("unexplained excess NAV")
        result["versus_costed_069500"] = {"final_nav_difference_krw": str(delta), "gross_exposure_gain_difference_krw": str(gross_difference),
            "execution_cost_difference_krw": str(execution_difference), "fee_difference_krw": str(fee_difference), "residual_krw": str(residual)}
        result["benchmark"] = benchmark
        result["source_artifact_hashes"] = audited["artifact_sha256"]
        output[model] = result
    if _input_hash(ROOT) != input_before:
        raise ValueError("data changed during analysis")
    report = {"status": "ACCOUNTING_EXCESS_RETURN_EXPLAINED_NOT_ALPHA_VALIDATION", "data_input_hash": input_before,
              "period": {"start": "2021-10-13", "end": "2026-07-31"}, "models": output,
              "source_audit_hash": frozen["evidence_bundle_hash"], "calculation_version": "SIGNED_FILL_PRICE_MARK_ATTRIBUTION_V1",
              "limitations": ["REUSED_HISTORY_NOT_OOS", "PIT_FIRST_BAR_PROXY", "DISTRIBUTIONS_AND_LIVE_ADJUSTED_PRICE_SEMANTICS_NOT_PROVEN",
                              "NO_AGENT_ABLATION_PERFORMANCE_ESTIMATED", "ZERO_CASH_YIELD_AS_ORIGINAL_MODEL", "NO_FINAL_LIQUIDATION_AS_ORIGINAL_MODEL"],
              "database_calls": 0, "broker_mutation_calls": 0}
    report["content_hash"] = sha256(json.dumps(report, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    path = ROOT / "runtime/daily_excess_return_audit/attribution_summary_v2.json"
    save_report(path, report)
    print(json.dumps({"status": report["status"], "content_hash": report["content_hash"],
                      "models": {m: {k: v for k, v in r.items() if k not in {"daily", "source_artifact_hashes"}} for m, r in output.items()}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
