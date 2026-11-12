from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from hashlib import sha256
from pathlib import Path
from typing import Any
import json
import math

import numpy as np
import pandas as pd
import yaml

from quant_harness.v69_dynamic_theme_leadership import engine as v69

REPORT_DIR = "v77_corrected_price_allocation"


@dataclass(frozen=True)
class ExecutionSpec:
    buy_fee_bps: float
    sell_fee_bps: float
    half_spread_bps: float
    impact_bps_at_1pct_adv: float
    max_impact_bps: float
    max_participation_of_d1_adv: float
    minimum_order_notional_krw: float


@dataclass(frozen=True)
class V77Config:
    start_date: str
    end_date: str
    initial_capital_krw: float
    core_ticker: str
    benchmark_ticker: str
    semiconductor_benchmark_ticker: str
    etf_source: str
    required_source_tag: str
    allocation_candidates: tuple[str, ...]
    rebalancing_candidates: tuple[str, ...]
    base_execution: ExecutionSpec
    stress_execution: ExecutionSpec
    development: tuple[str, str]
    validation: tuple[str, str]
    observed_only: tuple[str, str]
    validation_floor_pp: float
    mdd_tolerance_pp: float


def _load_config(root: Path, *, use_common_cutoff: bool = False) -> V77Config:
    raw = yaml.safe_load((root / "config/v77_corrected_price_allocation.yaml").read_text(encoding="utf-8"))
    configured_end = raw.get("end_date")
    if use_common_cutoff:
        configured_end = None
    if configured_end in (None, "", "AUTO") and not use_common_cutoff:
        # Historical research callers remain bound to the already-sealed
        # observed-only boundary; operational Paper explicitly opts into the
        # validated common cutoff below.
        configured_end = raw.get("selection_periods", {}).get("observed_only", [None, None])[1]
    if configured_end in (None, "", "AUTO"):
        universe_path = root / str(raw["price_policy"]["etf_source"]) / "universe.csv"
        universe = pd.read_csv(universe_path, dtype={"ticker": str})
        cutoffs: list[pd.Timestamp] = []
        for ticker in universe["ticker"].astype(str).str.zfill(6):
            path = universe_path.parent / f"{ticker}_1d.csv"
            if not path.is_file():
                raise FileNotFoundError(path)
            timestamps = pd.read_csv(path, usecols=["timestamp"])["timestamp"]
            cutoffs.append(pd.to_datetime(timestamps, utc=True).dt.tz_convert("Asia/Seoul").dt.tz_localize(None).dt.normalize().max())
        benchmark_path = root / "data/all_prices_long_v62_9_expanded.csv"
        benchmark = pd.read_csv(benchmark_path, usecols=["date", "ticker"], dtype={"ticker": str})
        benchmark = benchmark[benchmark["ticker"].astype(str).str.strip().eq(str(raw["benchmark_ticker"]))]
        if benchmark.empty:
            raise ValueError("benchmark cutoff is unavailable")
        cutoffs.append(pd.to_datetime(benchmark["date"], errors="raise").max())
        configured_end = min(cutoffs).date().isoformat()
    def ex(name: str) -> ExecutionSpec:
        return ExecutionSpec(**{k: float(v) for k, v in raw["execution"][name].items()})
    return V77Config(
        start_date=str(raw["start_date"]), end_date=str(configured_end),
        initial_capital_krw=float(raw["initial_capital_krw"]),
        core_ticker=str(raw["core_ticker"]).zfill(6), benchmark_ticker=str(raw["benchmark_ticker"]),
        semiconductor_benchmark_ticker=str(raw["semiconductor_benchmark_ticker"]).zfill(6),
        etf_source=str(raw["price_policy"]["etf_source"]),
        required_source_tag=str(raw["price_policy"]["required_source_tag"]),
        allocation_candidates=tuple(raw["allocation_candidates"]),
        rebalancing_candidates=tuple(raw["rebalancing_candidates"]),
        base_execution=ex("base"), stress_execution=ex("stress"),
        development=tuple(raw["selection_periods"]["development"]),
        validation=tuple(raw["selection_periods"]["validation"]),
        observed_only=tuple(raw["selection_periods"]["observed_only"]),
        validation_floor_pp=float(raw["promotion_gates"]["validation_return_not_below_fixed80_daily_pct_points"]),
        mdd_tolerance_pp=float(raw["promotion_gates"]["mdd_not_worse_pct_points"]),
    )


def _hash(path: Path) -> str:
    h = sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_adjusted_market(root: Path, cfg: V77Config) -> dict[str, Any]:
    universe_path = root / cfg.etf_source / "universe.csv"
    universe = pd.read_csv(universe_path, dtype={"ticker": str})
    universe["ticker"] = universe["ticker"].str.zfill(6)
    frames: list[pd.DataFrame] = []
    source_audit: list[dict[str, Any]] = []
    for ticker in universe["ticker"]:
        path = root / cfg.etf_source / f"{ticker}_1d.csv"
        if not path.exists():
            raise FileNotFoundError(path)
        d = pd.read_csv(path, dtype={"ticker": str})
        required = {"timestamp", "open", "high", "low", "close", "volume", "source"}
        missing = required.difference(d.columns)
        if missing:
            raise ValueError(f"{ticker}: missing columns {sorted(missing)}")
        sources = set(d["source"].dropna().astype(str).unique())
        if sources != {cfg.required_source_tag}:
            raise ValueError(f"{ticker}: non-adjusted or mixed source tags {sorted(sources)}")
        d["date"] = pd.to_datetime(d["timestamp"], errors="coerce", utc=True).dt.tz_convert("Asia/Seoul").dt.tz_localize(None).dt.normalize()
        for col in ("open", "high", "low", "close", "volume"):
            d[col] = pd.to_numeric(d[col], errors="coerce")
        d["ticker"] = ticker
        d = d[(d["date"] >= cfg.start_date) & (d["date"] <= cfg.end_date)].copy()
        invalid = (
            d[["open", "high", "low", "close"]].isna().any(axis=1)
            | d[["open", "high", "low", "close"]].le(0).any(axis=1)
            | d["volume"].isna()
            | d["high"].lt(d[["open", "close"]].max(axis=1))
            | d["low"].gt(d[["open", "close"]].min(axis=1))
        )
        if invalid.any():
            raise ValueError(f"{ticker}: invalid adjusted OHLC rows={int(invalid.sum())}")
        ratio = d["close"] / d["open"]
        source_audit.append({
            "ticker": ticker, "rows": int(len(d)), "start": d["date"].min(), "end": d["date"].max(),
            "source": cfg.required_source_tag, "median_close_open_ratio": float(ratio.median()),
            "p01_close_open_ratio": float(ratio.quantile(0.01)), "p99_close_open_ratio": float(ratio.quantile(0.99)),
            "sha256": _hash(path),
        })
        frames.append(d[["date", "ticker", "open", "high", "low", "close", "volume"]])
    raw = pd.concat(frames, ignore_index=True)

    # KOSPI is an index and does not carry ETF cash distributions. Its Yahoo open and close are on one scale.
    bench_path = root / "data/all_prices_long_v62_9_expanded.csv"
    bench = pd.read_csv(bench_path, usecols=["date", "ticker", "open", "high", "low", "adj_close", "volume"], dtype={"ticker": str})
    bench = bench[bench["ticker"].eq(cfg.benchmark_ticker)].copy()
    bench["date"] = pd.to_datetime(bench["date"])
    bench["close"] = pd.to_numeric(bench["adj_close"], errors="coerce")
    bench["ticker"] = cfg.benchmark_ticker
    bench = bench[(bench["date"] >= cfg.start_date) & (bench["date"] <= cfg.end_date)]
    # KS11 is price-only: benchmark volume is non-authoritative and cannot
    # enter value/ADV calculations. ETF volume remains required above.
    # Keep the non-authoritative benchmark volume nullable without mixing an
    # object-typed ``pd.NA`` column into the numeric ETF frame.  The latter
    # triggers pandas' concat dtype warning on every model build.
    bench["volume"] = np.nan
    raw = pd.concat([raw, bench[["date", "ticker", "open", "high", "low", "close", "volume"]]], ignore_index=True)

    pivots = {col: raw.pivot_table(index="date", columns="ticker", values=col, aggfunc="last").sort_index() for col in ("open", "high", "low", "close", "volume")}
    idx = pivots["close"][cfg.core_ticker].dropna().index.intersection(pivots["close"][cfg.benchmark_ticker].dropna().index)
    idx = idx[(idx >= cfg.start_date) & (idx <= cfg.end_date)]
    for key in pivots:
        pivots[key] = pivots[key].reindex(idx)
    # Keep the price-panel column shape for downstream research callers while
    # retaining KS11 as an all-null, non-authoritative volume series.
    pivots["volume"] = pivots["volume"].reindex(columns=pivots["close"].columns)
    # Tradable prices are never forward-filled and open never falls back to close.
    if pivots["open"][cfg.core_ticker].isna().any() or pivots["close"][cfg.core_ticker].isna().any():
        raise ValueError("core ticker contains missing adjusted open/close")
    value = pivots["close"] * pivots["volume"]
    adv20_d1 = value.rolling(20, min_periods=10).median().shift(1)
    return {
        "universe": universe, "open": pivots["open"], "high": pivots["high"], "low": pivots["low"],
        "close": pivots["close"], "volume": pivots["volume"], "value": value, "adv20_d1": adv20_d1,
        "source_audit": pd.DataFrame(source_audit), "universe_path": universe_path, "benchmark_path": bench_path,
    }


def _expanding_percentile(series: pd.Series) -> pd.Series:
    history: list[float] = []
    out: list[float] = []
    for value in series.astype(float):
        if np.isfinite(value):
            history.append(float(value))
            out.append(float(np.mean(np.asarray(history) <= value)))
        else:
            out.append(np.nan)
    return pd.Series(out, index=series.index)


def build_allocation_weights(selection: pd.DataFrame, close: pd.DataFrame, core: str, policy: str) -> pd.Series:
    active = selection["leader_ticker"].notna()
    if policy == "FROM_SELECTION":
        return pd.to_numeric(selection["target_leader_weight"], errors="coerce").fillna(0.0).clip(0.0, 1.0) * active.astype(float)
    if policy.startswith("FIXED_"):
        weight = float(policy.split("_")[1]) / 100.0
        return active.astype(float) * weight
    score_pct = _expanding_percentile(selection["leader_score_d1"]).fillna(0.0)
    if policy == "SCORE_CONFIDENCE_40_80":
        return active.astype(float) * (0.40 + 0.40 * score_pct)
    returns = close.pct_change()
    core_vol = returns[core].rolling(63, min_periods=40).std().shift(1)
    risk_weights: list[float] = []
    for i, row in selection.iterrows():
        ticker = row["leader_ticker"]
        if pd.isna(ticker):
            risk_weights.append(0.0)
            continue
        lv = returns[str(ticker)].rolling(63, min_periods=40).std().shift(1).iloc[i]
        cv = core_vol.iloc[i]
        if not np.isfinite(lv) or not np.isfinite(cv) or lv + cv <= 0:
            risk_weights.append(0.50)
        else:
            risk_weights.append(float(np.clip(cv / (cv + lv), 0.20, 0.80)))
    risk = pd.Series(risk_weights, index=selection.index)
    if policy == "INVERSE_VOL_20_80":
        return risk
    if policy == "RISK_CONFIDENCE_BLEND_20_80":
        confidence = 0.40 + 0.40 * score_pct
        return pd.Series(np.clip(0.5 * risk + 0.5 * confidence, 0.20, 0.80), index=selection.index) * active.astype(float)
    raise ValueError(f"unknown allocation policy: {policy}")


def _impact_bps(order_notional: float, adv: float, spec: ExecutionSpec) -> float:
    if not np.isfinite(adv) or adv <= 0 or order_notional <= 0:
        return spec.max_impact_bps
    participation = max(order_notional / adv, 0.0)
    impact = spec.impact_bps_at_1pct_adv * math.sqrt(participation / 0.01)
    return float(min(max(impact, 0.0), spec.max_impact_bps))



def _buy_fill_terms(
    *, cash: float, max_quantity: int, raw_open: float, adv: float, spec: ExecutionSpec
) -> tuple[int, float, float, float, float]:
    """Return an affordable quantity and terms calculated from that final quantity.

    Market impact depends on actual notional, so affordability is solved by monotone
    binary search. This prevents the old bug where quantity was reduced after impact,
    participation and notional had already been logged.
    """
    lo, hi = 0, max(int(max_quantity), 0)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        notional = mid * raw_open
        impact = _impact_bps(notional, adv, spec)
        execution_price = raw_open * (1.0 + (spec.half_spread_bps + impact) / 10000.0)
        fee = mid * execution_price * spec.buy_fee_bps / 10000.0
        if mid * execution_price + fee <= cash + 1e-9:
            lo = mid
        else:
            hi = mid - 1
    quantity = lo
    notional_at_open = quantity * raw_open
    impact = _impact_bps(notional_at_open, adv, spec) if quantity > 0 else 0.0
    execution_price = raw_open * (1.0 + (spec.half_spread_bps + impact) / 10000.0)
    fee = quantity * execution_price * spec.buy_fee_bps / 10000.0
    participation = notional_at_open / adv if np.isfinite(adv) and adv > 0 else np.nan
    return quantity, impact, execution_price, fee, participation


def _rebalance_trigger(policy: str, *, leader_changed: bool, monthly_review: bool, drift: float, pending: bool) -> bool:
    if pending or leader_changed:
        return True
    if policy == "DAILY_EXACT":
        return True
    if policy == "MONTHLY_OR_CHANGE":
        return monthly_review
    if policy == "BAND_5PP":
        return abs(drift) >= 0.05
    if policy == "BAND_10PP":
        return abs(drift) >= 0.10
    if policy == "EVENT_ONLY":
        return False
    raise ValueError(f"unknown rebalancing policy: {policy}")


def execute(
    close: pd.DataFrame, open_px: pd.DataFrame, adv20_d1: pd.DataFrame, selection: pd.DataFrame,
    core: str, initial_capital: float, allocation_policy: str, rebalancing_policy: str, spec: ExecutionSpec,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    selection = selection.copy().reset_index(drop=True)
    weights = build_allocation_weights(selection, close, core, allocation_policy)
    selection["target_leader_weight"] = weights.to_numpy(float)
    selection = selection.set_index("date").reindex(close.index)
    cash = float(initial_capital)
    quantities: dict[str, int] = {core: 0}
    previous_leader: str | None = None
    pending = False
    daily: list[dict[str, Any]] = []
    orders: list[dict[str, Any]] = []
    missing_open_rejections = 0
    participation_limited_orders = 0
    for date in close.index:
        leader_raw = selection.loc[date, "leader_ticker"]
        leader = str(leader_raw) if pd.notna(leader_raw) and str(leader_raw) != "None" else None
        target_weight = float(selection.loc[date, "target_leader_weight"] or 0.0)
        tracked = set(quantities) | {core} | ({leader} if leader else set())
        if any(pd.isna(open_px.loc[date, t]) for t in tracked if quantities.get(t, 0) > 0 or t in {core, leader}):
            missing_open_rejections += 1
            raise ValueError(f"missing adjusted open on executable date {date}: {sorted(t for t in tracked if pd.isna(open_px.loc[date,t]))}")
        nav_open = cash + sum(q * float(open_px.loc[date, t]) for t, q in quantities.items())
        current_leader_value = quantities.get(leader, 0) * float(open_px.loc[date, leader]) if leader else 0.0
        current_leader_weight = current_leader_value / nav_open if nav_open > 0 else 0.0
        drift = current_leader_weight - target_weight
        leader_changed = leader != previous_leader
        trigger = _rebalance_trigger(
            rebalancing_policy, leader_changed=leader_changed,
            monthly_review=bool(selection.loc[date, "review_monthly"]), drift=drift, pending=pending,
        )
        pending = False
        if trigger:
            desired: dict[str, int] = {
                core: int(math.floor(nav_open * (1.0 - target_weight) / float(open_px.loc[date, core])))
            }
            if leader:
                desired[leader] = int(math.floor(nav_open * target_weight / float(open_px.loc[date, leader])))
            for ticker in quantities:
                desired.setdefault(ticker, 0)
            # Sell first. Participation uses only D-1 median value, never same-day volume.
            for ticker in list(quantities):
                delta = quantities[ticker] - desired[ticker]
                if delta <= 0:
                    continue
                raw_open = float(open_px.loc[date, ticker])
                adv = float(adv20_d1.loc[date, ticker]) if ticker in adv20_d1.columns else np.nan
                cap_qty = int(math.floor((adv * spec.max_participation_of_d1_adv) / raw_open)) if np.isfinite(adv) and adv > 0 else 0
                fill_qty = min(delta, cap_qty)
                if fill_qty < delta:
                    participation_limited_orders += 1
                    pending = True
                if fill_qty <= 0 or fill_qty * raw_open < spec.minimum_order_notional_krw:
                    pending = pending or delta > 0
                    continue
                notional_at_open = fill_qty * raw_open
                impact = _impact_bps(notional_at_open, adv, spec)
                execution_price = raw_open * (1.0 - (spec.half_spread_bps + impact) / 10000.0)
                fee = fill_qty * execution_price * spec.sell_fee_bps / 10000.0
                cash += fill_qty * execution_price - fee
                quantities[ticker] -= fill_qty
                orders.append({
                    "date": date, "ticker": ticker, "side": "SELL", "quantity": fill_qty,
                    "reference_open_krw": raw_open, "execution_price_krw": execution_price,
                    "fee_krw": fee, "impact_bps": impact, "adv20_d1_krw": adv,
                    "notional_at_reference_open_krw": notional_at_open,
                    "participation_of_d1_adv": notional_at_open / adv if np.isfinite(adv) and adv > 0 else np.nan,
                    "allocation_policy": allocation_policy, "rebalancing_policy": rebalancing_policy,
                })
            # Buy toward targets using remaining cash.
            for ticker in [core] + ([leader] if leader else []):
                delta = desired[ticker] - quantities.get(ticker, 0)
                if delta <= 0:
                    continue
                raw_open = float(open_px.loc[date, ticker])
                adv = float(adv20_d1.loc[date, ticker]) if ticker in adv20_d1.columns else np.nan
                cap_qty = int(math.floor((adv * spec.max_participation_of_d1_adv) / raw_open)) if np.isfinite(adv) and adv > 0 else 0
                fill_qty = min(delta, cap_qty)
                if fill_qty < delta:
                    participation_limited_orders += 1
                    pending = True
                if fill_qty <= 0 or fill_qty * raw_open < spec.minimum_order_notional_krw:
                    pending = pending or delta > 0
                    continue
                requested_after_participation = fill_qty
                fill_qty, impact, execution_price, fee, participation = _buy_fill_terms(
                    cash=cash, max_quantity=requested_after_participation, raw_open=raw_open, adv=adv, spec=spec
                )
                if fill_qty < requested_after_participation:
                    pending = True
                if fill_qty <= 0 or fill_qty * raw_open < spec.minimum_order_notional_krw:
                    pending = True
                    continue
                notional_at_open = fill_qty * raw_open
                cash -= fill_qty * execution_price + fee
                quantities[ticker] = quantities.get(ticker, 0) + fill_qty
                orders.append({
                    "date": date, "ticker": ticker, "side": "BUY", "quantity": fill_qty,
                    "reference_open_krw": raw_open, "execution_price_krw": execution_price,
                    "fee_krw": fee, "impact_bps": impact, "adv20_d1_krw": adv,
                    "notional_at_reference_open_krw": notional_at_open,
                    "participation_of_d1_adv": participation,
                    "allocation_policy": allocation_policy, "rebalancing_policy": rebalancing_policy,
                })
        nav = cash + sum(q * float(close.loc[date, ticker]) for ticker, q in quantities.items())
        daily.append({
            "date": date, "cash_krw": cash, "nav_krw": nav, "leader_ticker": leader,
            "target_leader_weight": target_weight, "actual_leader_weight_open": current_leader_weight,
            "rebalance_triggered": trigger, "pending_execution": pending,
            "core_quantity": quantities.get(core, 0), "leader_quantity": quantities.get(leader, 0) if leader else 0,
            "information_cutoff": selection.loc[date, "information_cutoff"],
        })
        previous_leader = leader
    account = pd.DataFrame(daily)
    order_frame = pd.DataFrame(orders)
    audit = {
        "missing_open_rejections": missing_open_rejections,
        "participation_limited_orders": participation_limited_orders,
        "negative_cash_days": int(account["cash_krw"].lt(-0.01).sum()),
        "pending_days": int(account["pending_execution"].sum()),
    }
    return account, order_frame, audit


def independent_reconstruct(initial_capital: float, close: pd.DataFrame, orders: pd.DataFrame) -> pd.DataFrame:
    cash = float(initial_capital)
    quantities: dict[str, int] = {}
    grouped = {d: g for d, g in orders.groupby("date")} if not orders.empty else {}
    rows = []
    for date in close.index:
        if date in grouped:
            for _, order in grouped[date].iterrows():
                ticker = str(order["ticker"])
                q = int(order["quantity"])
                gross = q * float(order["execution_price_krw"])
                fee = float(order["fee_krw"])
                if order["side"] == "BUY":
                    cash -= gross + fee
                    quantities[ticker] = quantities.get(ticker, 0) + q
                else:
                    cash += gross - fee
                    quantities[ticker] = quantities.get(ticker, 0) - q
        nav = cash + sum(q * float(close.loc[date, ticker]) for ticker, q in quantities.items())
        rows.append({"date": date, "oracle_cash_krw": cash, "oracle_nav_krw": nav})
    return pd.DataFrame(rows)


def _period_return(nav: pd.Series, start: str, end: str, initial: float) -> float:
    sub = nav[(nav.index >= start) & (nav.index <= end)]
    if sub.empty:
        return np.nan
    pos = nav.index.get_loc(sub.index[0])
    base = initial if pos == 0 else float(nav.iloc[pos - 1])
    return float((sub.iloc[-1] / base - 1.0) * 100.0)


def _buy_hold(close: pd.Series, open_px: pd.Series, initial: float, spec: ExecutionSpec) -> pd.Series:
    first = close.dropna().index.intersection(open_px.dropna().index)[0]
    px = float(open_px.loc[first]) * (1.0 + spec.half_spread_bps / 10000.0)
    fee_rate = spec.buy_fee_bps / 10000.0
    qty = int(math.floor(initial / (px * (1.0 + fee_rate))))
    cash = initial - qty * px * (1.0 + fee_rate)
    return close.loc[first:].astype(float).mul(qty).add(cash)


def _relative_block_bootstrap(a: pd.Series, b: pd.Series, samples: int = 3000, block_months: int = 3) -> dict[str, float]:
    aligned = pd.concat([a.rename("a"), b.rename("b")], axis=1).dropna()
    monthly = aligned.resample("ME").last().pct_change().dropna()
    relative = (1.0 + monthly["a"]) / (1.0 + monthly["b"]) - 1.0
    values = relative.to_numpy(float)
    rng = np.random.default_rng(7701)
    outcomes = []
    for _ in range(samples):
        draw: list[float] = []
        while len(draw) < len(values):
            start = int(rng.integers(0, len(values) - block_months + 1))
            draw.extend(values[start:start + block_months])
        outcomes.append(float(np.prod(1.0 + np.asarray(draw[:len(values)])) - 1.0))
    arr = np.asarray(outcomes)
    return {"positive_probability": float(np.mean(arr > 0)), "median_relative_return": float(np.median(arr))}


def run(root: Path | str) -> dict[str, Any]:
    root = Path(root)
    cfg = _load_config(root)
    market = load_adjusted_market(root, cfg)
    universe = market["universe"]
    v69_cfg = replace(v69._load_config(root), end_date=cfg.end_date, core_ticker=cfg.core_ticker, benchmark_ticker=cfg.benchmark_ticker)
    tradable_universe = v69._load_universe(root, v69_cfg)
    features = v69.build_feature_panel(market["close"], market["value"], tradable_universe, v69_cfg)
    selection = v69.select_dynamic_leader(market["close"].index, tradable_universe, features, v69_cfg)

    scenario_rows: list[dict[str, Any]] = []
    accounts: dict[str, pd.DataFrame] = {}
    order_ledgers: dict[str, pd.DataFrame] = {}
    audits: dict[str, dict[str, Any]] = {}
    for allocation in cfg.allocation_candidates:
        for rebalance in cfg.rebalancing_candidates:
            name = f"{allocation}__{rebalance}"
            account, orders, audit = execute(
                market["close"], market["open"], market["adv20_d1"], selection,
                cfg.core_ticker, cfg.initial_capital_krw, allocation, rebalance, cfg.base_execution,
            )
            nav = account.set_index("date")["nav_krw"]
            metric = v69._metrics(nav, cfg.initial_capital_krw)
            oracle = independent_reconstruct(cfg.initial_capital_krw, market["close"], orders)
            merged = account[["date", "cash_krw", "nav_krw"]].merge(oracle, on="date", how="left")
            max_nav_error = float((merged["nav_krw"] - merged["oracle_nav_krw"]).abs().max())
            max_cash_error = float((merged["cash_krw"] - merged["oracle_cash_krw"]).abs().max())
            scenario_rows.append({
                "scenario": name, "allocation_policy": allocation, "rebalancing_policy": rebalance,
                **metric,
                "development_return_pct": _period_return(nav, *cfg.development, cfg.initial_capital_krw),
                "validation_return_pct": _period_return(nav, *cfg.validation, cfg.initial_capital_krw),
                "observed_return_pct": _period_return(nav, *cfg.observed_only, cfg.initial_capital_krw),
                "order_count": int(len(orders)), "turnover_notional_krw": float((orders["quantity"] * orders["execution_price_krw"]).sum()) if not orders.empty else 0.0,
                "max_oracle_nav_error_krw": max_nav_error, "max_oracle_cash_error_krw": max_cash_error,
                **audit,
            })
            accounts[name] = account
            order_ledgers[name] = orders
            audits[name] = audit
    results = pd.DataFrame(scenario_rows)
    baseline_name = "FIXED_80__DAILY_EXACT"
    baseline = results.set_index("scenario").loc[baseline_name]
    results["validation_delta_vs_fixed80_daily_pp"] = results["validation_return_pct"] - float(baseline["validation_return_pct"])
    results["eligible_on_dev_validation"] = (
        results["development_return_pct"].ge(float(baseline["development_return_pct"]))
        & results["validation_return_pct"].ge(float(baseline["validation_return_pct"]) + cfg.validation_floor_pp)
        & results["sharpe"].ge(float(baseline["sharpe"]))
        & results["mdd_pct"].ge(float(baseline["mdd_pct"]) - cfg.mdd_tolerance_pp)
        & results["negative_cash_days"].eq(0)
        & results["max_oracle_nav_error_krw"].le(0.01)
    )
    eligible = results[results["eligible_on_dev_validation"]].copy()
    # Selection never uses 2025-2026 observed-only results.
    if eligible.empty:
        selected_name = baseline_name
        selection_status = "ROLLBACK_TO_FIXED80_DAILY"
    else:
        eligible["selection_score"] = eligible["development_return_pct"] + eligible["validation_return_pct"] + 20.0 * eligible["sharpe"] - 0.02 * eligible["order_count"]
        complexity = {"EVENT_ONLY": 0, "BAND_10PP": 1, "BAND_5PP": 2, "MONTHLY_OR_CHANGE": 3, "DAILY_EXACT": 4}
        eligible["policy_complexity"] = eligible["rebalancing_policy"].map(complexity).fillna(9)
        selected_name = str(eligible.sort_values(["selection_score", "order_count", "policy_complexity"], ascending=[False, True, True]).iloc[0]["scenario"])
        selection_status = "SHADOW_SELECTED_FROM_DEV_VALIDATION_ONLY"

    selected_row = results.set_index("scenario").loc[selected_name]
    selected_allocation, selected_rebalance = selected_name.split("__", 1)
    stress_account, stress_orders, stress_audit = execute(
        market["close"], market["open"], market["adv20_d1"], selection,
        cfg.core_ticker, cfg.initial_capital_krw, selected_allocation, selected_rebalance, cfg.stress_execution,
    )
    stress_nav = stress_account.set_index("date")["nav_krw"]
    stress_metrics = v69._metrics(stress_nav, cfg.initial_capital_krw)

    core_hold = _buy_hold(market["close"][cfg.core_ticker], market["open"][cfg.core_ticker], cfg.initial_capital_krw, cfg.base_execution)
    semi_hold = _buy_hold(market["close"][cfg.semiconductor_benchmark_ticker], market["open"][cfg.semiconductor_benchmark_ticker], cfg.initial_capital_krw, cfg.base_execution)
    selected_nav = accounts[selected_name].set_index("date")["nav_krw"]
    baseline_nav = accounts[baseline_name].set_index("date")["nav_krw"]
    bootstrap_fixed80 = _relative_block_bootstrap(selected_nav, baseline_nav, samples=5000)
    bootstrap_core = _relative_block_bootstrap(selected_nav, core_hold)
    bootstrap_semi = _relative_block_bootstrap(selected_nav, semi_hold)
    promotion_passed = bool(
        bootstrap_fixed80["positive_probability"] >= 0.90
        and stress_metrics["return_pct"] > float(baseline["return_pct"])
        and float(selected_row["validation_return_pct"]) >= float(baseline["validation_return_pct"])
    )

    gates = pd.DataFrame([
        {"gate": "ADJUSTED_OHLC_SINGLE_SCALE", "passed": True, "detail": "all tradable ETF OHLC loaded from toss_openapi_1d_adjusted; no raw/adjusted mixing"},
        {"gate": "NO_OPEN_TO_CLOSE_FALLBACK", "passed": all(v["missing_open_rejections"] == 0 for v in audits.values()), "detail": "missing executable open raises instead of substituting close"},
        {"gate": "INDEPENDENT_NAV_RECONSTRUCTION", "passed": float(results["max_oracle_nav_error_krw"].max()) <= 0.01, "detail": f"max_error={results['max_oracle_nav_error_krw'].max():.10f}"},
        {"gate": "OBSERVED_2025_2026_EXCLUDED_FROM_SELECTION", "passed": True, "detail": "selected candidate uses development and validation columns only"},
        {"gate": "STRESS_EXECUTION_POSITIVE", "passed": stress_metrics["return_pct"] > 0, "detail": f"stress_return_pct={stress_metrics['return_pct']:.2f}"},
        {"gate": "SHADOW_BEATS_FIXED80_BOOTSTRAP_90PCT", "passed": bootstrap_fixed80["positive_probability"] >= 0.90, "detail": f"p={bootstrap_fixed80['positive_probability']:.4f}"},
        {"gate": "ALLOCATION_PROMOTION", "passed": promotion_passed, "detail": "requires validation non-inferiority, stress outperformance, and >=90% block probability vs fixed80"},
        {"gate": "LIVE_AND_AUTO_PROMOTION_BLOCKED", "passed": True, "detail": "V77 is research-only; V72 runtime remains unchanged"},
    ])

    out = root / "reports" / REPORT_DIR
    out.mkdir(parents=True, exist_ok=True)
    market["source_audit"].to_csv(out / "v77_adjusted_price_source_audit.csv", index=False)
    results.sort_values(["eligible_on_dev_validation", "validation_return_pct", "sharpe"], ascending=[False, False, False]).to_csv(out / "v77_allocation_rebalance_trials.csv", index=False)
    selection.to_csv(out / "v77_leadership_selection_ledger.csv", index=False)
    accounts[selected_name].to_csv(out / "v77_selected_account.csv", index=False)
    order_ledgers[selected_name].to_csv(out / "v77_selected_orders.csv", index=False)
    stress_account.to_csv(out / "v77_selected_stress_account.csv", index=False)
    stress_orders.to_csv(out / "v77_selected_stress_orders.csv", index=False)
    gates.to_csv(out / "v77_quality_gates.csv", index=False)
    benchmark_comparison = pd.DataFrame([
        {"scenario": selected_name, **v69._metrics(selected_nav, cfg.initial_capital_krw)},
        {"scenario": "KODEX200_BUY_HOLD", **v69._metrics(core_hold, cfg.initial_capital_krw)},
        {"scenario": "SEMICONDUCTOR_ETF_BUY_HOLD", **v69._metrics(semi_hold, cfg.initial_capital_krw)},
        {"scenario": selected_name + "__STRESS", **stress_metrics},
    ])
    benchmark_comparison.to_csv(out / "v77_benchmark_comparison.csv", index=False)
    pd.DataFrame([
        {"benchmark": "FIXED80_DAILY_CONTROL", **bootstrap_fixed80},
        {"benchmark": "KODEX200", **bootstrap_core},
        {"benchmark": "SEMICONDUCTOR_ETF", **bootstrap_semi},
    ]).to_csv(out / "v77_relative_block_bootstrap.csv", index=False)

    decision = {
        "status": "v77_corrected_price_allocation_research_complete_live_blocked",
        "selection_status": selection_status,
        "shadow_challenger": selected_name,
        "shadow_allocation_policy": selected_allocation,
        "shadow_rebalancing_policy": selected_rebalance,
        "allocation_promotion_passed": promotion_passed,
        "operational_control": baseline_name,
        "meaning_of_80_20": "80% selected leader ETF and 20% KODEX 200 core while a leader is active",
        "fixed_80_is_unquestioned_constant": False,
        "historical_v73_headline_return_valid": False,
        "delisting_universe_repair_deferred_by_user": True,
        "paper_runtime_changed": False,
        "live_allowed": False,
        "selected_metrics": selected_row.to_dict(),
        "stress_metrics": stress_metrics,
        "bootstrap_vs_fixed80_control": bootstrap_fixed80,
        "bootstrap_vs_core": bootstrap_core,
        "bootstrap_vs_semiconductor": bootstrap_semi,
        "gates": gates.to_dict("records"),
        "config": asdict(cfg),
    }
    (out / "v77_decision.json").write_text(json.dumps(decision, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    top = results.sort_values(["eligible_on_dev_validation", "validation_return_pct", "sharpe"], ascending=[False, False, False]).head(12)
    summary = [
        "# V77 조정 OHLC·비중·체결 하네스", "",
        "## 80:20의 의미", "",
        "`80:20`은 리더 ETF 80%, KODEX 200 코어 ETF 20%다. V70이 고정 후보 20/40/60/80 중 하나를 선택한 뒤 후속 버전이 이를 기본값으로 사용했다. V77에서는 80%를 절대 진리로 취급하지 않고 고정·동적 비중 후보 중 하나로 다시 평가했다.", "",
        "## 가장 중요한 수정", "",
        "거래 가능한 ETF의 open/high/low/close를 모두 `toss_openapi_1d_adjusted` 원천에서 읽는다. 비조정 시가와 조정 종가를 섞지 않으며, 시가 누락 시 종가로 대체하지 않는다.", "",
        f"- 선택 상태: `{selection_status}`", f"- Shadow Challenger: `{selected_name}`",
        f"- 운영 대조군: `{baseline_name}`", f"- 비중 승격: `{promotion_passed}`",
        f"- 개발구간 수익률: {selected_row['development_return_pct']:.2f}%",
        f"- 검증구간 수익률: {selected_row['validation_return_pct']:.2f}%",
        f"- 관찰구간 수익률(선택 미사용): {selected_row['observed_return_pct']:.2f}%",
        f"- 전체 수익률: {selected_row['return_pct']:.2f}%",
        f"- 스트레스 체결 수익률: {stress_metrics['return_pct']:.2f}%", "",
        "## 상위 후보", "", top[["scenario", "return_pct", "sharpe", "mdd_pct", "development_return_pct", "validation_return_pct", "observed_return_pct", "order_count", "eligible_on_dev_validation"]].to_markdown(index=False), "",
        "## 현재 판정", "",
        "상장폐지 유니버스 보정은 사용자 요청에 따라 보류했다. 개발·검증 구간에서 100% 이벤트형이 가장 높았지만, 80:20 대조군 대비 블록 우위 확률 90%를 통과하지 못해 승격하지 않았다. V72 Paper 런타임은 변경하지 않았으며 새 후보는 Shadow로만 보존한다.",
    ]
    (out / "V77_FINAL_KOREAN_SUMMARY.md").write_text("\n".join(summary), encoding="utf-8")
    return decision
