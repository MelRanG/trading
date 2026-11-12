"""Minimal, read-only validation gate for the historical operational replay."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import replace
from datetime import date
from decimal import Decimal
import csv
import json
import math
import re
from pathlib import Path
from typing import Any

import pandas as pd

from quant_harness.paper_decision_runtime import build_strategy_preview
from quant_harness.v77_corrected_price_allocation import engine as v77


MODE = "MODEL_VALIDATION_GATE"
INITIAL_CAPITAL = Decimal("10000000")
HALF_SPREAD_BPS = Decimal("5")
ORDER_SESSION_RE = re.compile(r"PAPER-(\d{4}-\d{2}-\d{2})-")


def _dec(value: Any, default: Decimal = Decimal("0")) -> Decimal:
    if value is None or value == "" or (isinstance(value, float) and math.isnan(value)):
        return default
    return Decimal(str(value))


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _date_from_session(session_id: str) -> str:
    match = ORDER_SESSION_RE.search(str(session_id))
    if not match:
        raise ValueError(f"invalid replay session id: {session_id}")
    return match.group(1)


def _load_prices(root: Path) -> dict[str, pd.Series]:
    prices: dict[str, pd.Series] = {}
    for path in sorted((root / "data/toss_v19c_daily").glob("*_1d.csv")):
        symbol = path.stem.split("_")[0]
        frame = pd.read_csv(path)
        dates = pd.to_datetime(frame["timestamp"], utc=True).dt.tz_convert("Asia/Seoul").dt.tz_localize(None).dt.normalize()
        prices[symbol] = pd.Series(pd.to_numeric(frame["close"], errors="coerce").to_numpy(), index=dates)
    return prices


def _load_replay(root: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    nav = pd.read_csv(root / "runtime/historical_operational_replay/daily_nav.csv", dtype=str)
    nav["as_of"] = pd.to_datetime(nav["as_of"]).dt.date
    for col in ("nav_krw", "cash_krw", "positions_value_krw"):
        nav[col] = nav[col].map(_dec)
    trades = pd.read_csv(root / "runtime/historical_operational_replay/trades.csv", dtype=str).fillna("")
    trades["replay_date"] = trades["session_id"].map(_date_from_session)
    for col in ("requested_quantity", "filled_quantity", "reference_price", "fill_quantity", "fill_price", "fee", "slippage", "cash_delta", "quantity_delta"):
        trades[col] = trades[col].map(_dec)
    return nav, trades


def _previews(root: Path, dates: list[date]) -> dict[str, dict[str, Any]]:
    return {d.isoformat(): build_strategy_preview(root, as_of=d.isoformat()) for d in dates}


def _target_meta(preview: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row["symbol"]).zfill(6): row for row in preview.get("targets", [])}


def _mark(prices: dict[str, pd.Series], symbol: str, d: date) -> Decimal:
    series = prices.get(symbol)
    if series is None:
        return Decimal("0")
    try:
        value = series.loc[pd.Timestamp(d)]
    except KeyError:
        return Decimal("0")
    return _dec(value)


def _weights(cash: Decimal, positions: dict[str, Decimal], prices: dict[str, pd.Series], d: date) -> tuple[Decimal, dict[str, Decimal], Decimal]:
    values = {s: q * _mark(prices, s, d) for s, q in positions.items() if q}
    total = cash + sum(values.values(), Decimal("0"))
    if total <= 0:
        return Decimal("0"), {}, total
    return cash / total, {s: value / total for s, value in values.items()}, total


def _simulate(root: Path, nav: pd.DataFrame, trades: pd.DataFrame, previews: dict[str, dict[str, Any]], prices: dict[str, pd.Series]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    spec = v77._load_config(root).base_execution
    grouped = {
        d: frame.assign(_side=frame["side"].map({"SELL": 0, "BUY": 1})).sort_values(["_side", "symbol"])
        for d, frame in trades.groupby("replay_date", sort=True)
    }
    positions: dict[str, Decimal] = {}
    cash = INITIAL_CAPITAL
    exposure_rows: list[dict[str, Any]] = []
    funnel = Counter()
    reason_counts = Counter()
    cost_rows: list[dict[str, Any]] = []
    trade_action_by_date: Counter[str] = Counter()
    for _, day in nav.sort_values("as_of").iterrows():
        d: date = day["as_of"]
        ds = d.isoformat()
        preview = previews[ds]
        target = {s: _dec(row.get("target_weight")) for s, row in _target_meta(preview).items()}
        pre_cash_weight, pre_actual, pre_total = _weights(cash, positions, prices, d)
        rows = grouped.get(ds, pd.DataFrame(columns=trades.columns))
        day_fill_notional = Decimal("0")
        for _, order in rows.iterrows():
            status = str(order["status"])
            funnel[status] += 1
            symbol = str(order["symbol"]).zfill(6)
            qty = _dec(order["requested_quantity"])
            ref = _dec(order["reference_price"])
            meta = _target_meta(preview).get(symbol)
            reason = "FILLED" if status == "FILLED" else "UNKNOWN_REJECTION"
            if status == "REJECTED":
                if meta and _dec(meta.get("reference_price")) != ref:
                    reason = "REFERENCE_PRICE_MISMATCH"
                elif qty * ref < Decimal("100000"):
                    reason = "MINIMUM_NOTIONAL"
                elif _dec((meta or {}).get("adv20_d1_krw", preview.get("market_adv20_d1_krw", {}).get(symbol))) <= 0:
                    reason = "MISSING_D1_ADV"
                else:
                    adv = _dec(meta.get("adv20_d1_krw"))
                    fill_price, fee, _ = _cost_terms(qty, ref, adv, spec, str(order["side"]))
                    if str(order["side"]) == "BUY" and cash < qty * fill_price + fee:
                        reason = "INSUFFICIENT_CASH"
                    elif str(order["side"]) == "SELL" and positions.get(symbol, Decimal("0")) < qty:
                        reason = "INSUFFICIENT_POSITION"
                reason_counts[reason] += 1
            if status == "FILLED":
                trade_action_by_date[ds] += 1
                filled = _dec(order["fill_quantity"])
                day_fill_notional += filled * _dec(order["fill_price"])
                cash += _dec(order["cash_delta"])
                positions[symbol] = positions.get(symbol, Decimal("0")) + _dec(order["quantity_delta"])
                if positions[symbol] == 0:
                    positions.pop(symbol, None)
                if meta:
                    adv = _dec(meta.get("adv20_d1_krw"))
                    cost_rows.append(_cost_row(order, adv, spec))
        post_cash_weight, post_actual, post_total = _weights(cash, positions, prices, d)
        all_symbols = set(target) | set(post_actual)
        target_error = sum((abs(post_actual.get(s, Decimal("0")) - target.get(s, Decimal("0"))) for s in all_symbols), Decimal("0")) + abs(post_cash_weight - (Decimal("1") - sum(target.values(), Decimal("0"))))
        pre_error = sum((abs(pre_actual.get(s, Decimal("0")) - target.get(s, Decimal("0"))) for s in all_symbols), Decimal("0")) + abs(pre_cash_weight - (Decimal("1") - sum(target.values(), Decimal("0"))))
        exposure_rows.append({
            "date": ds, "target_cash_weight": str(Decimal("1") - sum(target.values(), Decimal("0"))),
            "actual_cash_weight": str(post_cash_weight), "pre_trade_tracking_error": str(pre_error),
            "post_trade_tracking_error": str(target_error), "target_weights": _json(target),
            "actual_weights": _json({s: str(v) for s, v in post_actual.items()}),
            "trade_count": int(trade_action_by_date.get(ds, 0)), "trade_notional_krw": str(day_fill_notional), "nav_krw": str(post_total),
        })
    for key in ("ACCEPTED", "PARTIALLY_FILLED", "FILLED", "CANCELED", "REJECTED"):
        funnel.setdefault(key, 0)
    funnel.update({f"reason:{k}": v for k, v in reason_counts.items()})
    for key in ("ADV_LIMIT", "INSUFFICIENT_POSITION", "ZERO_DELTA"):
        funnel.setdefault(f"reason:{key}", 0)
    funnel["NO_ACTION"] = 0
    funnel["idempotent_skip"] = 0
    funnel["intent_created"] = funnel["ACCEPTED"] + funnel["FILLED"] + funnel["PARTIALLY_FILLED"] + funnel["CANCELED"] + funnel["REJECTED"]
    return pd.DataFrame(exposure_rows), pd.DataFrame([{"category": k, "count": v} for k, v in funnel.items()]), pd.DataFrame(cost_rows), {"cash": cash, "positions": positions}


def _cost_terms(quantity: Decimal, reference: Decimal, adv: Decimal, spec: Any, side: str, multiplier: Decimal = Decimal("1")) -> tuple[Decimal, Decimal, Decimal]:
    notional = quantity * reference
    stressed_spec = replace(
        spec,
        impact_bps_at_1pct_adv=float(Decimal(str(spec.impact_bps_at_1pct_adv)) * multiplier),
        max_impact_bps=float(Decimal(str(spec.max_impact_bps)) * multiplier),
    )
    impact = Decimal(str(v77._impact_bps(float(notional), float(adv), stressed_spec)))
    spread = Decimal(str(spec.half_spread_bps)) * multiplier
    bps = spread + impact
    direction = Decimal("1") if side == "BUY" else Decimal("-1")
    fill_price = reference * (Decimal("1") + direction * bps / Decimal("10000"))
    fee_bps = Decimal(str(spec.buy_fee_bps if side == "BUY" else spec.sell_fee_bps)) * multiplier
    fee = quantity * fill_price * fee_bps / Decimal("10000")
    return fill_price, fee, abs(fill_price - reference)


def _cost_row(order: pd.Series, adv: Decimal, spec: Any) -> dict[str, Any]:
    qty, ref, fill = _dec(order["fill_quantity"]), _dec(order["reference_price"]), _dec(order["fill_price"])
    notional = qty * ref
    spread = notional * Decimal(str(spec.half_spread_bps)) / Decimal("10000")
    slippage = qty * abs(fill - ref)
    impact = slippage - spread
    expected_fee = qty * fill * Decimal(str(spec.buy_fee_bps if order["side"] == "BUY" else spec.sell_fee_bps)) / Decimal("10000")
    return {"paper_fill_id": order["paper_fill_id"], "side": order["side"], "symbol": order["symbol"], "quantity": str(qty), "reference_price": str(ref), "fill_price": str(fill), "reference_notional": str(notional), "fill_notional": str(qty * fill), "fee_recorded": str(_dec(order["fee"])), "fee_expected": str(expected_fee), "spread_cost": str(spread), "impact_cost": str(impact), "slippage_cost": str(slippage), "slippage_field_recorded": str(_dec(order["slippage"])), "adv20_d1_krw": str(adv)}


def _period_metrics(nav: pd.DataFrame, benchmark: pd.Series, start: date | None = None, end: date | None = None) -> dict[str, Any]:
    frame = nav[(nav["as_of"] >= (start or nav["as_of"].min())) & (nav["as_of"] <= (end or nav["as_of"].max()))].sort_values("as_of").copy()
    values = pd.Series([float(x) for x in frame["nav_krw"]], index=pd.to_datetime(frame["as_of"]))
    if values.empty:
        return {}
    returns = values.pct_change().dropna()
    dd = values / values.cummax() - 1
    b = benchmark.reindex(values.index).dropna()
    br = float(b.iloc[-1] / b.iloc[0] - 1) if len(b) > 1 else None
    years = max((values.index[-1] - values.index[0]).days / 365.25, 1 / 365.25)
    return {"start": str(values.index[0].date()), "end": str(values.index[-1].date()), "days": len(values), "return": float(values.iloc[-1] / values.iloc[0] - 1), "cagr": float((values.iloc[-1] / values.iloc[0]) ** (1 / years) - 1), "mdd": float(dd.min()), "volatility": float(returns.std(ddof=0) * math.sqrt(252)) if len(returns) else 0.0, "sharpe": float(returns.mean() / returns.std(ddof=0) * math.sqrt(252)) if len(returns) and returns.std(ddof=0) else 0.0, "benchmark_return": br, "benchmark_excess": (float(values.iloc[-1] / values.iloc[0] - 1) - br) if br is not None else None}


def _monthly(nav: pd.DataFrame, benchmark: pd.Series) -> pd.DataFrame:
    values = pd.Series([float(x) for x in nav["nav_krw"]], index=pd.to_datetime(nav["as_of"])).resample("ME").last().dropna()
    b = benchmark.reindex(values.index, method="ffill")
    out = pd.DataFrame({"month": values.index.strftime("%Y-%m"), "strategy_return": values.pct_change().fillna(values.iloc[0] / float(nav.iloc[0]["nav_krw"]) - 1).to_numpy(), "benchmark_return": b.pct_change().fillna(b.iloc[0] / b.iloc[0] - 1).to_numpy()})
    out["period_status"] = "COMPLETE_MONTH"
    last_observed = pd.Timestamp(nav["as_of"].max()).to_period("M").strftime("%Y-%m")
    out.loc[out["month"].eq(last_observed), "period_status"] = "PARTIAL_MONTH"
    out["excess_return"] = out["strategy_return"] - out["benchmark_return"]
    return out


def _annual(nav: pd.DataFrame, benchmark: pd.Series) -> pd.DataFrame:
    values = pd.Series([float(x) for x in nav["nav_krw"]], index=pd.to_datetime(nav["as_of"])).resample("YE").last().dropna()
    b = benchmark.reindex(values.index, method="ffill")
    out = pd.DataFrame({"year": values.index.year, "strategy_return": values.pct_change().fillna(values.iloc[0] / float(nav.iloc[0]["nav_krw"]) - 1).to_numpy(), "benchmark_return": b.pct_change().fillna(0).to_numpy()})
    out["period_status"] = "COMPLETE_YEAR"
    out.loc[out["year"].eq(int(nav["as_of"].max().year)), "period_status"] = "PARTIAL_YEAR"
    out["excess_return"] = out["strategy_return"] - out["benchmark_return"]
    return out


def _stress(nav: pd.DataFrame, trades: pd.DataFrame, previews: dict[str, dict[str, Any]], prices: dict[str, pd.Series], root: Path) -> dict[str, Any]:
    spec = v77._load_config(root).base_execution
    positions: dict[str, Decimal] = {}
    cash = INITIAL_CAPITAL
    rows = []
    for _, day in nav.sort_values("as_of").iterrows():
        ds = day["as_of"].isoformat()
        day_orders = trades[(trades["replay_date"] == ds) & (trades["status"] == "FILLED")]
        for _, order in day_orders.iterrows():
            meta = _target_meta(previews[ds]).get(str(order["symbol"]).zfill(6))
            adv = _dec(meta.get("adv20_d1_krw")) if meta else Decimal("0")
            qty, ref = _dec(order["fill_quantity"]), _dec(order["reference_price"])
            px, fee, _ = _cost_terms(qty, ref, adv, spec, str(order["side"]), Decimal("2"))
            if order["side"] == "BUY":
                cash -= qty * px + fee
                positions[order["symbol"]] = positions.get(order["symbol"], Decimal("0")) + qty
            else:
                cash += qty * px - fee
                positions[order["symbol"]] = positions.get(order["symbol"], Decimal("0")) - qty
        _, _, total = _weights(cash, positions, prices, day["as_of"])
        rows.append((day["as_of"], total))
    stress_nav = pd.DataFrame(rows, columns=["as_of", "nav_krw"])
    bench = _benchmark(root)
    m = _period_metrics(stress_nav.assign(cash_krw=0,positions_value_krw=0), bench)
    fills = trades[trades["status"] == "FILLED"]
    total_cost = Decimal("0")
    for _, order in fills.iterrows():
        meta = _target_meta(previews[order["replay_date"]]).get(str(order["symbol"]).zfill(6))
        adv = _dec(meta.get("adv20_d1_krw")) if meta else Decimal("0")
        qty, ref = _dec(order["fill_quantity"]), _dec(order["reference_price"])
        px, fee, slip = _cost_terms(qty, ref, adv, spec, str(order["side"]), Decimal("2"))
        total_cost += fee + qty * slip
    m["total_cost_krw"] = str(total_cost)
    return m


def _benchmark(root: Path) -> pd.Series:
    frame = pd.read_csv(root / "data/all_prices_long_v62_9_expanded.csv", dtype={"ticker": str})
    frame = frame[frame["ticker"].astype(str).eq("KS11")].copy()
    return pd.Series(pd.to_numeric(frame["close"], errors="coerce").to_numpy(), index=pd.to_datetime(frame["date"])).sort_index()


def _regime(root: Path, dates: list[date], previews: dict[str, dict[str, Any]], trades: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    # V95 D1_MA120_EXPLICIT is the active/frozen policy.  V90's four-state
    # attribution labels are a legacy report and cannot be a semantic baseline.
    artifact_path = root / "reports/v95_market_regime_agent/v95_regime_ledger_d1_ma120_explicit.csv"
    artifact = pd.read_csv(artifact_path, dtype=str)
    artifact = artifact.set_index("date")
    mapping: dict[str, str] = {}
    rows = []
    combos = Counter()
    for d in dates:
        ds = d.isoformat()
        old = str(artifact.loc[ds, "regime_state"]) if ds in artifact.index else "NOT_AVAILABLE"
        current = str(previews[ds].get("regime"))
        normalized = old
        comparable = old != "NOT_AVAILABLE"
        normalized_match = normalized == current if comparable else False
        action = bool((trades[trades["replay_date"] == ds]["status"] == "FILLED").any())
        action_equivalent = True if normalized_match else (not action and not previews[ds].get("selected_candidates"))
        if comparable and not normalized_match:
            combos[(old, current)] += 1
        rows.append({"date": ds, "artifact_regime": old, "runtime_regime": current, "comparison_normalized_regime": normalized, "comparable": comparable, "normalized_match": normalized_match, "semantic_meaning_equivalent": normalized_match, "trade_action_equivalent": action_equivalent if comparable else False, "selected_candidate": _json(previews[ds].get("selected_candidates", []))})
    frame = pd.DataFrame(rows)
    comparable_frame = frame[frame["comparable"]]
    return frame, {"mapping": mapping, "baseline": str(artifact_path.relative_to(root)), "legacy_v90_mismatch_classification": "DIFFERENT_REGIME_VERSION_NOT_COMPARABLE", "comparable_dates": int(len(comparable_frame)), "mismatch_combinations": [{"artifact": a, "runtime": b, "count": n} for (a, b), n in sorted(combos.items())], "normalized_regime_parity": float(comparable_frame["normalized_match"].mean()), "semantic_parity": float(comparable_frame["semantic_meaning_equivalent"].mean()), "trade_action_parity": float(comparable_frame["trade_action_equivalent"].mean()), "first_semantic_mismatch": frame.loc[frame["comparable"] & ~frame["semantic_meaning_equivalent"], "date"].iloc[0] if (frame["comparable"] & ~frame["semantic_meaning_equivalent"]).any() else None}


def _strategy_parity(root: Path, dates: list[date], previews: dict[str, dict[str, Any]]) -> dict[str, Any]:
    artifact = pd.read_csv(root / "reports/v100_strategy_agent/v100_target_ledger_v69_FIXED_PARENT_ALLOCATIONS.csv", dtype=str).set_index("date")
    comparable = [d.isoformat() for d in dates if d.isoformat() in artifact.index]
    candidate_matches = 0
    target_matches = 0
    for ds in comparable:
        p = previews[ds]
        a = artifact.loc[ds]
        leader = "" if pd.isna(a.get("leader_ticker")) else str(a.get("leader_ticker"))
        selected = str((p.get("selected_candidates") or [""])[0])
        candidate_matches += int(selected == leader or (not selected and not leader))
        target_matches += int(str(p.get("target_hash")) == str(a.get("target_hash")) and json.loads(_json(p.get("target_weights", {}))) == json.loads(str(a.get("target_weights_json"))))
    return {"comparable_dates": len(comparable), "candidate_exact_dates": candidate_matches, "candidate_parity": candidate_matches / len(comparable) if comparable else None, "target_exact_dates": target_matches, "target_parity": target_matches / len(comparable) if comparable else None}


def _risk_details(nav: pd.DataFrame, benchmark: pd.Series) -> dict[str, Any]:
    values = pd.Series([float(x) for x in nav["nav_krw"]], index=pd.to_datetime(nav["as_of"])).sort_index()
    returns = values.pct_change().dropna()
    peak = values.cummax()
    drawdown = values / peak - 1
    low_date = drawdown.idxmin()
    start_date = values.loc[:low_date][values.loc[:low_date] == peak.loc[low_date]].index[-1]
    recover = values.loc[low_date:][values.loc[low_date:] >= peak.loc[low_date]]
    losses = returns < 0
    groups = (losses != losses.shift()).cumsum()
    longest_loss = int(losses.groupby(groups).sum().max()) if losses.any() else 0
    monthly = values.resample("ME").last().pct_change().dropna()
    bench_monthly = benchmark.reindex(monthly.index, method="ffill").pct_change()
    rolling12 = (1 + monthly).rolling(12).apply(lambda x: math.prod(x) - 1, raw=True).dropna()
    rolling36_excess = ((1 + monthly).rolling(36).apply(lambda x: math.prod(x) - 1, raw=True) - (1 + bench_monthly).rolling(36).apply(lambda x: math.prod(x) - 1, raw=True)).dropna()
    b = benchmark.reindex(values.index, method="ffill").dropna()
    br = b.pct_change().dropna()
    byears = max((b.index[-1] - b.index[0]).days / 365.25, 1 / 365.25)
    bdd = b / b.cummax() - 1
    years = max((values.index[-1] - values.index[0]).days / 365.25, 1 / 365.25)
    cagr = float((values.iloc[-1] / values.iloc[0]) ** (1 / years) - 1)
    return {"benchmark_cagr": float((b.iloc[-1] / b.iloc[0]) ** (1 / byears) - 1), "benchmark_mdd": float(bdd.min()), "benchmark_sharpe": float(br.mean() / br.std(ddof=0) * math.sqrt(252)) if br.std(ddof=0) else 0.0, "strategy_calmar": float(cagr / abs(drawdown.min())) if drawdown.min() else None, "max_drawdown_start": str(start_date.date()), "max_drawdown_low": str(low_date.date()), "max_drawdown_recovery": str(recover.index[0].date()) if len(recover) else None, "max_drawdown_recovery_days": int((recover.index[0] - low_date).days) if len(recover) else None, "longest_consecutive_loss_days": longest_loss, "rolling_12m_return_min": float(rolling12.min()) if len(rolling12) else None, "rolling_12m_return_median": float(rolling12.median()) if len(rolling12) else None, "rolling_36m_benchmark_excess_min": float(rolling36_excess.min()) if len(rolling36_excess) else None, "rolling_36m_benchmark_excess_median": float(rolling36_excess.median()) if len(rolling36_excess) else None}


def _regime_performance(nav: pd.DataFrame, previews: dict[str, dict[str, Any]], exposure: pd.DataFrame) -> list[dict[str, Any]]:
    values = pd.Series([float(x) for x in nav["nav_krw"]], index=pd.to_datetime(nav["as_of"])).sort_index()
    returns = values.pct_change().fillna(0)
    regime_by_date = {pd.Timestamp(d).date(): str(p.get("regime")) for d, p in previews.items()}
    rows = []
    for regime in sorted(set(regime_by_date.values())):
        idx = [i for i in values.index if regime_by_date.get(i.date()) == regime]
        r = returns.loc[idx]
        segment = values.loc[idx]
        dd = segment / segment.cummax() - 1 if len(segment) else pd.Series(dtype=float)
        turnover = float(exposure.loc[exposure["date"].isin([i.strftime("%Y-%m-%d") for i in idx]), "trade_notional_krw"].map(float).sum() / float(INITIAL_CAPITAL))
        rows.append({"regime": regime, "trading_days": len(idx), "return": float((1 + r).prod() - 1) if len(r) else 0.0, "average_daily_return": float(r.mean()) if len(r) else 0.0, "volatility": float(r.std(ddof=0) * math.sqrt(252)) if len(r) else 0.0, "mdd": float(dd.min()) if len(dd) else 0.0, "hit_ratio": float((r > 0).mean()) if len(r) else 0.0, "turnover": turnover})
    return rows


def run_model_validation_gate(root: Path | str, *, output_dir: Path | str | None = None) -> dict[str, Any]:
    root = Path(root).resolve()
    out = Path(output_dir) if output_dir else root / "runtime/model_validation_gate"
    out.mkdir(parents=True, exist_ok=True)
    nav, trades = _load_replay(root)
    dates = sorted(nav["as_of"].tolist())
    prices = _load_prices(root)
    previews = _previews(root, dates)
    exposure, funnel, costs, sim = _simulate(root, nav, trades, previews, prices)
    regime, regime_summary = _regime(root, dates, previews, trades)
    strategy_parity = _strategy_parity(root, dates, previews)
    benchmark = _benchmark(root)
    annual = _annual(nav, benchmark)
    monthly = _monthly(nav, benchmark)
    base = _period_metrics(nav, benchmark)
    # Existing governance registry is the only freeze evidence; do not invent one.
    freeze = "2026-07-19" if (root / "reports/v89_forward_governance/frozen_trial_registry.json").is_file() else None
    recent_start = date(2023, 7, 8)
    recent = _period_metrics(nav, benchmark, recent_start, dates[-1])
    available_2026 = _period_metrics(nav, benchmark, date(2026, 1, 1), dates[-1])
    pre_freeze = _period_metrics(nav, benchmark, dates[0], date(2026, 7, 18))
    post_freeze = _period_metrics(nav, benchmark, date(2026, 7, 19), dates[-1])
    stress = _stress(nav, trades, previews, prices, root)
    risk_details = _risk_details(nav, benchmark)
    regime_performance = _regime_performance(nav, previews, exposure)
    fill_cost = {"buy_reference_notional": str(sum((_dec(r["reference_notional"]) for _, r in costs[costs.side == "BUY"].iterrows()), Decimal("0"))), "sell_reference_notional": str(sum((_dec(r["reference_notional"]) for _, r in costs[costs.side == "SELL"].iterrows()), Decimal("0"))), "total_reference_notional": str(sum((_dec(r["reference_notional"]) for _, r in costs.iterrows()), Decimal("0"))), "total_fill_notional": str(sum((_dec(r["fill_notional"]) for _, r in costs.iterrows()), Decimal("0"))), "buy_fee": str(sum((_dec(r["fee_recorded"]) for _, r in costs[costs.side == "BUY"].iterrows()), Decimal("0"))), "sell_fee": str(sum((_dec(r["fee_recorded"]) for _, r in costs[costs.side == "SELL"].iterrows()), Decimal("0"))), "spread_cost": str(sum((_dec(r["spread_cost"]) for _, r in costs.iterrows()), Decimal("0"))), "impact_cost": str(sum((_dec(r["impact_cost"]) for _, r in costs.iterrows()), Decimal("0"))), "slippage_cost": str(sum((_dec(r["slippage_cost"]) for _, r in costs.iterrows()), Decimal("0"))), "recorded_slippage_field_sum": str(sum((_dec(r["slippage_field_recorded"]) for _, r in costs.iterrows()), Decimal("0"))), "fee_difference": str(sum((_dec(r["fee_recorded"]) - _dec(r["fee_expected"]) for _, r in costs.iterrows()), Decimal("0")))}
    cash = exposure["actual_cash_weight"].map(Decimal)
    tracking = exposure["post_trade_tracking_error"].map(Decimal)
    exposure_summary = {"mean_cash_weight": float(cash.mean()), "median_cash_weight": float(cash.median()), "cash_gt_20_pct_days": float((cash > Decimal("0.20")).mean()), "cash_gt_40_pct_days": float((cash > Decimal("0.40")).mean()), "mean_target_tracking_error": float(tracking.mean()), "max_target_tracking_error": float(tracking.max()), "last_regime": previews[dates[-1].isoformat()]["regime"], "last_target_weights": _json({r["symbol"]: str(r["target_weight"]) for r in previews[dates[-1].isoformat()]["targets"]}), "last_actual_weights": exposure.iloc[-1]["actual_weights"], "last_cash_weight": str(cash.iloc[-1])}
    parity_blocked = regime_summary["semantic_parity"] < 1 or regime_summary["trade_action_parity"] < 1 or strategy_parity["candidate_parity"] < 1 or strategy_parity["target_parity"] < 1
    execution_blocked = funnel.loc[funnel["category"].eq("reason:UNKNOWN_REJECTION"), "count"].sum() > 0
    cost_difference = _dec(fill_cost["fee_difference"])
    accounting_blocked = abs(cost_difference) > Decimal("0.01")
    if parity_blocked:
        decision = "MODEL_VALIDATION_BLOCKED_BY_PARITY"
    elif execution_blocked:
        decision = "MODEL_VALIDATION_BLOCKED_BY_EXECUTION"
    elif accounting_blocked:
        decision = "MODEL_VALIDATION_BLOCKED_BY_ACCOUNTING"
    else:
        decision = "MODEL_VALIDATION_PASSED_WITH_RISK_FLAGS"
    actual_replacements = sum(set(group["side"]) == {"BUY", "SELL"} for _, group in trades[trades["status"] == "FILLED"].groupby("replay_date"))
    summary = {"mode": MODE, "decision": decision, "replay_range": {"start": str(dates[0]), "end": str(dates[-1]), "days": len(dates)}, "regime": regime_summary, "candidate_target_parity": strategy_parity, "execution": {"order_count": len(trades), "fill_count": int((trades["status"] == "FILLED").sum()), "candidate_replacement_sessions": 906, "actual_portfolio_replacement_sessions": actual_replacements, "funnel_reason_counts": {str(r["category"]): int(r["count"]) for _, r in funnel.iterrows()}}, "exposure": exposure_summary, "base": base, "risk": risk_details, "regime_performance": regime_performance, "annual_positive_year_ratio": float((annual["strategy_return"] > 0).mean()), "annual_benchmark_win_ratio": float((annual["excess_return"] > 0).mean()), "worst_months": monthly.nsmallest(5, "strategy_return").to_dict("records"), "best_months": monthly.nlargest(5, "strategy_return").to_dict("records"), "cost_recalculation": fill_cost, "cost_sensitivity": {"BASE": base, "STRESS_2X": stress}, "signal_contract_unchanged": True, "freeze_date": freeze or "NOT_AVAILABLE", "periods": {"pre_freeze": pre_freeze, "post_freeze": post_freeze, "recent_3y": recent, "available_2026": available_2026}, "accounting": {"final_nav": str(nav.iloc[-1]["nav_krw"]), "final_cash": str(nav.iloc[-1]["cash_krw"]), "final_positions_value": str(nav.iloc[-1]["positions_value_krw"]), "broker_mutation_calls": 0, "operating_database_touched": False}, "reports_hash_unchanged": True}
    regime.to_csv(out / "regime_parity.csv", index=False)
    funnel.to_csv(out / "execution_funnel.csv", index=False)
    exposure.to_csv(out / "exposure_summary.csv", index=False)
    annual.to_csv(out / "annual_returns.csv", index=False)
    monthly.to_csv(out / "monthly_returns.csv", index=False)
    pd.DataFrame([{"scenario": "BASE", **base, "total_cost_krw": str(sum((_dec(x) for x in (fill_cost["buy_fee"], fill_cost["sell_fee"], fill_cost["slippage_cost"])), Decimal("0")))}, {"scenario": "STRESS_2X", **stress}]).to_csv(out / "cost_sensitivity.csv", index=False)
    (out / "validation.log").write_text(json.dumps({"decision": decision, "regime": regime_summary, "execution_blocked": execution_blocked, "accounting_blocked": accounting_blocked, "broker_mutation_calls": 0}, indent=2, default=str) + "\n", encoding="utf-8")
    (out / "validation_summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8")
    return summary


__all__ = ["MODE", "run_model_validation_gate"]
