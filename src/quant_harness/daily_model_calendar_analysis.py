"""Calendar and risk analysis for the two frozen Daily operational models.

This is an analysis-only runner.  It reuses the Paper operational replay in
isolated TEST_DATABASE_URL schemas and never invokes the broker.
"""
from __future__ import annotations

from dataclasses import asdict
from decimal import Decimal
import json
import math
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import psycopg
import yaml

from quant_harness.historical_operational_replay import INITIAL_CAPITAL, run_historical_operational_replay
from quant_harness.operational_candidate_comparison import _ensure_schema, _schema_url
from quant_harness.paper_runtime_store import PAPER_ACCOUNT_ID
from quant_harness.v101_risk_execution_agent import engine as v101
from quant_harness.v104_end_to_end_causal_challenger_audit.adapter import build_candidate_ledgers, load_candidate_specs


START = "2021-10-13"
END = "2026-07-31"
DAILY_CANDIDATES = ("V69_PARENT", "V79_NO63_VOL_GUARD")
MODEL_LABELS = {
    "V69_PARENT": "V69_PARENT Daily",
    "V79_NO63_VOL_GUARD": "V79_NO63_VOL_GUARD Daily",
    "KS11": "KS11",
    "069500": "069500 buy-and-hold",
}


def _json_default(value: Any) -> str:
    if isinstance(value, (pd.Timestamp, Decimal)):
        return str(value)
    raise TypeError(type(value).__name__)


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, default=_json_default) + "\n", encoding="utf-8")


def _price_series(root: Path, symbol: str) -> pd.Series:
    if symbol == "KS11":
        frame = pd.read_csv(root / "data/all_prices_long_v62_9_expanded.csv", dtype={"ticker": str})
        frame = frame[frame["ticker"].astype(str).eq("KS11")].copy()
        frame["date"] = pd.to_datetime(frame["date"])
        return pd.to_numeric(frame.set_index("date")["close"], errors="coerce").sort_index()
    frame = pd.read_csv(root / "data/toss_v19c_daily" / f"{symbol}_1d.csv", dtype={"ticker": str})
    frame["date"] = pd.to_datetime(frame["timestamp"], utc=True).dt.tz_convert("Asia/Seoul").dt.tz_localize(None).dt.normalize()
    return pd.to_numeric(frame.set_index("date")["close"], errors="coerce").sort_index()


def _daily_cutoff(root: Path) -> dict[str, Any]:
    symbols: list[str] = []
    dates: dict[str, str | None] = {}
    for path in sorted((root / "data/toss_v19c_daily").glob("*_1d.csv")):
        symbol = path.stem.removesuffix("_1d")
        frame = pd.read_csv(path, usecols=["timestamp"])
        maximum = pd.to_datetime(frame["timestamp"], errors="coerce", utc=True).max()
        symbols.append(symbol)
        dates[symbol] = maximum.tz_convert("Asia/Seoul").date().isoformat() if pd.notna(maximum) else None
    ks11 = _price_series(root, "KS11")
    dates["KS11"] = ks11.index.max().date().isoformat() if not ks11.empty else None
    required = tuple(symbols) + ("KS11",)
    current = all(dates.get(symbol) == END for symbol in required)
    return {
        "target_cutoff": END,
        "etf_symbols": len(symbols),
        "per_symbol_last_date": dates,
        "already_current": current,
        "updater_called": False,
        "network_calls": 0,
    }


def _read_replay_tables(database_url: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    with psycopg.connect(database_url) as conn:
        nav = pd.read_sql(
            "SELECT as_of,nav_krw,cash_krw,positions_value_krw FROM paper_daily_nav "
            "WHERE paper_account_id=%s ORDER BY as_of",
            conn,
            params=(PAPER_ACCOUNT_ID,),
        )
        trades = pd.read_sql(
            "SELECT s.as_of,o.paper_order_id,o.symbol,o.side,o.filled_quantity,o.reference_price,o.status,"
            "f.paper_fill_id,f.quantity AS fill_quantity,f.fill_price,f.fee,f.slippage,"
            "l.cash_delta,l.quantity_delta "
            "FROM paper_order o JOIN paper_session s USING(session_id) "
            "LEFT JOIN paper_fill f ON f.paper_order_id=o.paper_order_id "
            "LEFT JOIN paper_ledger_event l ON l.paper_fill_id=f.paper_fill_id "
            "ORDER BY s.as_of,o.created_at,f.filled_at",
            conn,
        )
    nav["date"] = pd.to_datetime(nav["as_of"])
    for column in ("nav_krw", "cash_krw", "positions_value_krw"):
        nav[column] = pd.to_numeric(nav[column], errors="coerce")
    if not trades.empty:
        trades["date"] = pd.to_datetime(trades["as_of"])
        for column in ("filled_quantity", "reference_price", "fill_quantity", "fill_price", "fee", "slippage", "cash_delta", "quantity_delta"):
            trades[column] = pd.to_numeric(trades[column], errors="coerce")
    return nav, trades


def _fresh_replay(root: Path, base_url: str, candidate_id: str, output: Path, *, reuse_completed: bool = False) -> dict[str, Any]:
    schema = f"daily_calendar_{candidate_id.lower()}_20260731".replace("-", "_")
    _ensure_schema(base_url, schema)
    schema_url = _schema_url(base_url, schema)
    replay_path = output / "replays" / candidate_id / "replay_summary.json"
    replay: dict[str, Any] | None = None
    if reuse_completed and replay_path.is_file():
        saved = json.loads(replay_path.read_text(encoding="utf-8"))
        if saved.get("common_start") == START and saved.get("common_end") == END and int(saved.get("processed_dates", 0)) > 0:
            replay = saved
    if replay is None:
        replay = run_historical_operational_replay(
            root,
            schema_url,
            reset=True,
            candidate_id=candidate_id,
            start_date=START,
            end_date=END,
            output_dir=output / "replays" / candidate_id,
        )
    nav, trades = _read_replay_tables(schema_url)
    return {"schema": schema, "replay": replay, "nav": nav, "trades": trades}


def _buy_and_hold_069500(root: Path, common_dates: pd.DatetimeIndex) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    specs = load_candidate_specs(root)
    built = build_candidate_ledgers(root, specs["V69_PARENT"], use_common_cutoff=True)
    first = pd.Timestamp(common_dates[0])
    market = built["market"]
    spec = built["cfg77"].base_execution
    policy = v101._policy(root, specs["V69_PARENT"].execution_policy)
    state = v101.AgentPortfolioState(float(INITIAL_CAPITAL), {})
    price = float(market["open"].loc[first, "069500"])
    adv = float(market["adv20_d1"].loc[first, "069500"])
    state, fills, intents, _ = v101.execute_target_map(
        state,
        targets={"069500": 1.0},
        open_prices={"069500": price},
        adv20_d1={"069500": adv},
        spec=spec,
        policy=policy,
        rebalance_band=1e9,
        buy_priority=policy.v69_buy_priority,
        core_ticker="069500",
    )
    closes = _price_series(root, "069500").reindex(common_dates)
    quantity = int(state.quantities.get("069500", 0))
    nav = pd.DataFrame({
        "date": common_dates,
        "nav_krw": [state.cash + quantity * float(value) for value in closes],
        "cash_krw": state.cash,
        "positions_value_krw": [quantity * float(value) for value in closes],
    })
    trades = pd.DataFrame([
        {
            "date": first,
            "paper_order_id": "REFERENCE-069500-INITIAL",
            "symbol": fill.ticker,
            "side": fill.side,
            "fill_quantity": fill.quantity,
            "fill_price": fill.execution_price_krw,
            "fee": fill.fee_krw,
            "slippage": fill.half_spread_cost_krw + fill.impact_cost_krw,
            "cash_delta": -(fill.quantity * fill.execution_price_krw + fill.fee_krw),
            "quantity_delta": fill.quantity,
        }
        for fill in fills
    ])
    return nav, trades, {"initial_intents": len(intents), "fills": len(fills), "cost_contract": "V101 initial BUY, then hold at adjusted daily close"}


def _price_reference_nav(prices: pd.Series, dates: pd.DatetimeIndex) -> pd.DataFrame:
    sampled = prices.reindex(dates)
    missing = sampled.index[sampled.isna()].strftime("%Y-%m-%d").tolist()
    if missing:
        raise ValueError(f"missing benchmark prices: {','.join(missing[:10])}")
    if sampled.empty or not np.isfinite(sampled.to_numpy(dtype=float)).all() or (sampled <= 0).any():
        raise ValueError("benchmark prices are empty or invalid")
    nav = float(INITIAL_CAPITAL) * sampled / float(sampled.iloc[0])
    return pd.DataFrame({"date": dates, "nav_krw": nav.to_numpy(), "cash_krw": 0.0, "positions_value_krw": nav.to_numpy()})


def _returns(nav: pd.DataFrame) -> pd.Series:
    return nav.set_index("date")["nav_krw"].astype(float).pct_change().dropna()


def _period_metrics(nav: pd.DataFrame, trades: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> dict[str, Any]:
    frame = nav[(nav["date"] >= start) & (nav["date"] <= end)].copy()
    if frame.empty:
        return {}
    values = frame["nav_krw"].astype(float)
    returns = values.pct_change().dropna()
    running = values.cummax()
    drawdown = values.div(running).sub(1.0)
    mdd = float(drawdown.min()) if len(drawdown) else 0.0
    annual_vol = float(returns.std(ddof=0) * math.sqrt(252)) if len(returns) else 0.0
    sharpe = float(returns.mean() / returns.std(ddof=0) * math.sqrt(252)) if len(returns) and returns.std(ddof=0) else None
    downside = returns[returns < 0]
    sortino = float(returns.mean() / downside.std(ddof=0) * math.sqrt(252)) if len(downside) and downside.std(ddof=0) else None
    total_return = float(values.iloc[-1] / values.iloc[0] - 1.0)
    five = values.pct_change(5).dropna()
    subset = trades[(trades["date"] >= start) & (trades["date"] <= end)].copy() if not trades.empty else trades
    fills = subset[subset.get("fill_quantity", pd.Series(dtype=float)).notna()].copy() if not subset.empty else subset
    turnover = float((fills["fill_quantity"].abs() * fills["fill_price"]).sum() / float(INITIAL_CAPITAL)) if not fills.empty else 0.0
    return {
        "start_nav_krw": float(values.iloc[0]),
        "end_nav_krw": float(values.iloc[-1]),
        "return": total_return,
        "mdd": mdd,
        "annualized_volatility": annual_vol,
        "sharpe": sharpe,
        "sortino": sortino,
        "calmar": (total_return / abs(mdd)) if mdd < 0 else None,
        "worst_1d_return": float(returns.min()) if len(returns) else None,
        "worst_5d_return": float(five.min()) if len(five) else None,
        "order_count": int(subset["paper_order_id"].nunique()) if not subset.empty and "paper_order_id" in subset else 0,
        "fill_count": int(fills["paper_fill_id"].nunique()) if not fills.empty and "paper_fill_id" in fills else int(len(fills)),
        "turnover": turnover,
        "mean_cash_weight": float((frame["cash_krw"].astype(float) / frame["nav_krw"].astype(float)).mean()),
    }


def _holdings_at_dates(nav: pd.DataFrame, trades: pd.DataFrame, root: Path, dates: list[pd.Timestamp]) -> dict[str, dict[str, float]]:
    fills = trades[trades.get("fill_quantity", pd.Series(dtype=float)).notna()].copy() if not trades.empty else pd.DataFrame()
    if fills.empty:
        return {d.date().isoformat(): {} for d in dates}
    inferred_delta = pd.Series(
        np.where(fills["side"].eq("BUY"), fills["fill_quantity"], -fills["fill_quantity"]),
        index=fills.index,
    )
    fills["quantity_delta"] = fills["quantity_delta"].where(fills["quantity_delta"].notna(), inferred_delta)
    symbols = sorted(fills["symbol"].astype(str).unique())
    price_map = {symbol: _price_series(root, symbol) for symbol in symbols}
    positions: dict[str, float] = {symbol: 0.0 for symbol in symbols}
    out: dict[str, dict[str, float]] = {}
    ordered = fills.sort_values(["date", "paper_order_id"])
    event_rows = list(ordered.itertuples(index=False))
    event_index = 0
    for when in sorted(dates):
        while event_index < len(event_rows) and pd.Timestamp(event_rows[event_index].date) <= when:
            row = event_rows[event_index]
            positions[str(row.symbol)] = positions.get(str(row.symbol), 0.0) + float(row.quantity_delta)
            event_index += 1
        nav_value = float(nav.loc[nav["date"].eq(when), "nav_krw"].iloc[-1])
        weights: dict[str, float] = {}
        for symbol, quantity in positions.items():
            if quantity <= 0:
                continue
            value = price_map[symbol].reindex([when]).iloc[0]
            if pd.notna(value):
                weights[symbol] = quantity * float(value) / nav_value
        out[when.date().isoformat()] = weights
    return out


def _drawdown_metrics(nav: pd.DataFrame) -> dict[str, Any]:
    values = nav.set_index("date")["nav_krw"].astype(float)
    running = values.cummax()
    dd = values.div(running).sub(1.0)
    trough = dd.idxmin()
    peak = values.loc[:trough].idxmax()
    recovery_candidates = values.loc[trough:][values.loc[trough:] >= values.loc[peak]]
    recovery = recovery_candidates.index[0] if not recovery_candidates.empty else None
    underwater = values < running
    lengths: list[int] = []
    current = 0
    for flag in underwater:
        if bool(flag):
            current += 1
        elif current:
            lengths.append(current)
            current = 0
    if current:
        lengths.append(current)
    return {
        "mdd": float(dd.min()), "peak_date": peak.date().isoformat(), "trough_date": trough.date().isoformat(),
        "recovery_date": recovery.date().isoformat() if recovery is not None else None,
        "max_recovery_trading_days": int((values.loc[peak:recovery].shape[0] - 1) if recovery is not None else len(values.loc[peak:])),
        "average_recovery_trading_days": float(np.mean(lengths)) if lengths else 0.0,
        "underwater_day_ratio": float(underwater.mean()),
    }


def _tail_metrics(nav: pd.DataFrame) -> dict[str, Any]:
    returns = _returns(nav)
    out: dict[str, Any] = {}
    for level in (0.95, 0.99):
        threshold = float(returns.quantile(1.0 - level))
        tail = returns[returns <= threshold]
        out[f"var_{int(level * 100)}"] = max(0.0, -threshold)
        out[f"expected_shortfall_{int(level * 100)}"] = max(0.0, -float(tail.mean())) if len(tail) else None
    return out


def _contribution(root: Path, nav: pd.DataFrame, trades: pd.DataFrame, model: str) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame(columns=["model", "symbol", "pnl_krw", "net_profit_share", "holding_days"])
    fills = trades[trades.get("fill_quantity", pd.Series(dtype=float)).notna()].copy()
    if fills.empty:
        return pd.DataFrame(columns=["model", "symbol", "pnl_krw", "net_profit_share", "holding_days"])
    fills = fills.drop_duplicates("paper_fill_id") if "paper_fill_id" in fills.columns else fills
    inferred_delta = pd.Series(
        np.where(fills["side"].eq("BUY"), fills["fill_quantity"], -fills["fill_quantity"]),
        index=fills.index,
    )
    fills["quantity_delta"] = fills["quantity_delta"].where(fills["quantity_delta"].notna(), inferred_delta)
    final_date = pd.Timestamp(nav["date"].max())
    net_profit = float(nav["nav_krw"].iloc[-1]) - float(INITIAL_CAPITAL)
    rows: list[dict[str, Any]] = []
    for symbol, group in fills.groupby("symbol"):
        symbol = str(symbol)
        quantity = float(group["quantity_delta"].sum())
        close = _price_series(root, symbol).reindex([final_date]).iloc[0]
        cash = float(group["cash_delta"].fillna(0.0).sum())
        pnl = cash + (quantity * float(close) if pd.notna(close) else 0.0)
        running = 0.0
        held = 0
        grouped = group.groupby("date")["quantity_delta"].sum()
        for date in pd.to_datetime(nav["date"]):
            running += float(grouped.get(date, 0.0))
            held += int(running > 0)
        rows.append({"model": model, "symbol": symbol, "pnl_krw": pnl, "net_profit_share": (pnl / net_profit) if net_profit else None, "holding_days": held})
    return pd.DataFrame(rows).sort_values("pnl_krw", ascending=False)


def _annual_rows(root: Path, models: dict[str, dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for model, item in models.items():
        nav = item["nav"].copy()
        nav["year"] = nav["date"].dt.year
        endpoint_dates = [group.iloc[-1]["date"] for _, group in nav.groupby("year")]
        holdings = _holdings_at_dates(nav, item["trades"], root, endpoint_dates)
        for year, group in nav.groupby("year"):
            metrics = _period_metrics(nav, item["trades"], group.iloc[0]["date"], group.iloc[-1]["date"])
            ks = _period_metrics(models["KS11"]["nav"], models["KS11"]["trades"], group.iloc[0]["date"], group.iloc[-1]["date"])
            core = _period_metrics(models["069500"]["nav"], models["069500"]["trades"], group.iloc[0]["date"], group.iloc[-1]["date"])
            rows.append({
                "model": MODEL_LABELS[model], "model_id": model, "year": int(year),
                "period_type": "PARTIAL" if year in (2021, 2026) else "FULL_YEAR",
                "start_date": group.iloc[0]["date"].date().isoformat(), "end_date": group.iloc[-1]["date"].date().isoformat(),
                **metrics,
                "ks11_return": ks.get("return"), "excess_vs_ks11": (metrics.get("return") - ks.get("return")) if metrics and ks else None,
                "069500_return": core.get("return"), "excess_vs_069500": (metrics.get("return") - core.get("return")) if metrics and core else None,
                "ending_holdings_weights_json": json.dumps(holdings[group.iloc[-1]["date"].date().isoformat()], sort_keys=True),
            })
    return pd.DataFrame(rows)


def _monthly_2026(root: Path, models: dict[str, dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for model, item in models.items():
        nav = item["nav"].copy()
        nav = nav[(nav["date"] >= pd.Timestamp("2026-01-01")) & (nav["date"] <= pd.Timestamp(END))]
        nav["month"] = nav["date"].dt.to_period("M")
        endpoints = [group.iloc[-1]["date"] for _, group in nav.groupby("month")]
        holdings = _holdings_at_dates(nav, item["trades"], root, endpoints)
        for month, group in nav.groupby("month"):
            metrics = _period_metrics(nav, item["trades"], group.iloc[0]["date"], group.iloc[-1]["date"])
            ks = _period_metrics(models["KS11"]["nav"], models["KS11"]["trades"], group.iloc[0]["date"], group.iloc[-1]["date"])
            core = _period_metrics(models["069500"]["nav"], models["069500"]["trades"], group.iloc[0]["date"], group.iloc[-1]["date"])
            rows.append({
                "model": MODEL_LABELS[model], "model_id": model, "month": str(month), "start_date": group.iloc[0]["date"].date().isoformat(), "end_date": group.iloc[-1]["date"].date().isoformat(),
                "return": metrics.get("return"), "ks11_return": ks.get("return"), "069500_return": core.get("return"),
                "excess_vs_ks11": metrics.get("return") - ks.get("return"), "excess_vs_069500": metrics.get("return") - core.get("return"),
                "mdd": metrics.get("mdd"), "worst_1d_return": metrics.get("worst_1d_return"), "order_count": metrics.get("order_count"), "fill_count": metrics.get("fill_count"),
                "ending_holdings_weights_json": json.dumps(holdings[group.iloc[-1]["date"].date().isoformat()], sort_keys=True),
            })
    return pd.DataFrame(rows)


def _regime_rows(models: dict[str, dict[str, Any]]) -> pd.DataFrame:
    ks_returns = _returns(models["KS11"]["nav"])
    ks_monthly = models["KS11"]["nav"].set_index("date")["nav_krw"].resample("ME").last().pct_change().dropna()
    rows: list[dict[str, Any]] = []
    for model, item in models.items():
        daily = _returns(item["nav"]).reindex(ks_returns.index).dropna()
        bench_daily = ks_returns.reindex(daily.index)
        monthly = item["nav"].set_index("date")["nav_krw"].resample("ME").last().pct_change().dropna().reindex(ks_monthly.index)
        rising = monthly[ks_monthly > 0]
        falling = monthly[ks_monthly < 0]
        crash_month = monthly[ks_monthly <= -0.05]
        crash_day = daily[bench_daily <= -0.02]
        beta = float(daily.cov(bench_daily) / bench_daily.var()) if len(daily) and bench_daily.var() else None
        correlation = float(daily.corr(bench_daily)) if len(daily) else None
        rows.append({
            "model": MODEL_LABELS[model], "model_id": model,
            "ks11_up_month_avg_return": float(rising.mean()) if len(rising) else None,
            "ks11_down_month_avg_return": float(falling.mean()) if len(falling) else None,
            "ks11_month_le_minus_5_model_avg_return": float(crash_month.mean()) if len(crash_month) else None,
            "ks11_day_le_minus_2_model_avg_return": float(crash_day.mean()) if len(crash_day) else None,
            "upside_capture": float(rising.mean() / ks_monthly[ks_monthly > 0].mean()) if len(rising) and ks_monthly[ks_monthly > 0].mean() else None,
            "downside_capture": float(falling.mean() / ks_monthly[ks_monthly < 0].mean()) if len(falling) and ks_monthly[ks_monthly < 0].mean() else None,
            "beta": beta, "correlation": correlation,
            **_drawdown_metrics(item["nav"]), **_tail_metrics(item["nav"]),
        })
    return pd.DataFrame(rows)


def _calendar_month_pnl(nav: pd.DataFrame) -> pd.DataFrame:
    """Return calendar-month NAV P&L without treating partial months as full years."""
    rows: list[dict[str, Any]] = []
    frame = nav.copy()
    frame["month"] = frame["date"].dt.to_period("M")
    for month, group in frame.groupby("month"):
        start = float(group.iloc[0]["nav_krw"])
        end = float(group.iloc[-1]["nav_krw"])
        rows.append({"month": str(month), "pnl_krw": end - start, "return": end / start - 1.0})
    return pd.DataFrame(rows)


def _decision_summary(annual: pd.DataFrame, monthly: pd.DataFrame, regime: pd.DataFrame, contribution: pd.DataFrame, replays: dict[str, Any], models: dict[str, dict[str, Any]], cutoff: dict[str, Any], asof_reference: list[dict[str, Any]]) -> dict[str, Any]:
    decisions: dict[str, Any] = {}
    for model in DAILY_CANDIDATES:
        name = MODEL_LABELS[model]
        a = annual[annual["model_id"].eq(model)]
        m = monthly[monthly["model_id"].eq(model)]
        r = regime[regime["model_id"].eq(model)].iloc[0]
        c = contribution[contribution["model"].eq(name)]
        positive_years = int((a["return"] > 0).sum())
        excess_years = int((a["excess_vs_ks11"] > 0).sum())
        net_profit = float(models[model]["nav"].iloc[-1]["nav_krw"] - float(INITIAL_CAPITAL))
        annual_pnl = (a["end_nav_krw"] - a["start_nav_krw"]).astype(float)
        all_months = _calendar_month_pnl(models[model]["nav"])
        top_year_share = float(annual_pnl.clip(lower=0.0).max() / net_profit) if net_profit > 0 and len(annual_pnl) else None
        top_three_month_share = float(all_months["pnl_krw"].clip(lower=0.0).nlargest(3).sum() / net_profit) if net_profit > 0 else None
        most_held = c.sort_values(["holding_days", "symbol"], ascending=[False, True]).iloc[0] if not c.empty else None
        v69_holdout = _period_metrics(models[model]["nav"], models[model]["trades"], pd.Timestamp("2026-07-20"), pd.Timestamp("2026-07-31")) if model == "V69_PARENT" else None
        if v69_holdout:
            ks_holdout = _period_metrics(models["KS11"]["nav"], models["KS11"]["trades"], pd.Timestamp("2026-07-20"), pd.Timestamp("2026-07-31"))
            core_holdout = _period_metrics(models["069500"]["nav"], models["069500"]["trades"], pd.Timestamp("2026-07-20"), pd.Timestamp("2026-07-31"))
            v69_holdout["excess_vs_ks11"] = v69_holdout["return"] - ks_holdout["return"]
            v69_holdout["excess_vs_069500"] = v69_holdout["return"] - core_holdout["return"]
        decisions[model] = {
            "return_consistency": {"positive_years": positive_years, "observed_years": len(a), "ks11_excess_years": excess_years, "positive_month_ratio": float((all_months["return"] > 0).mean()) if len(all_months) else None, "positive_month_ratio_2026": float((m["return"] > 0).mean()) if len(m) else None},
            "downside_protection": {"downside_capture": r["downside_capture"], "maximum_drawdown": r["mdd"], "var_95": r["var_95"], "expected_shortfall_95": r["expected_shortfall_95"]},
            "concentration_risk": {
                "net_profit_krw": net_profit,
                "best_year_profit_share_of_total_net_profit": top_year_share,
                "top_3_month_profit_share_of_total_net_profit": top_three_month_share,
                "top_etf": c.iloc[0]["symbol"] if not c.empty else None,
                "top_etf_pnl_krw": float(c.iloc[0]["pnl_krw"]) if not c.empty else None,
                "most_held_etf": str(most_held["symbol"]) if most_held is not None else None,
                "most_held_trading_days": int(most_held["holding_days"]) if most_held is not None else 0,
            },
            "turnover_efficiency": {"total_turnover": float(a["turnover"].sum()), "total_orders": int(a["order_count"].sum()), "total_fills": int(a["fill_count"].sum())},
            "suitability_for_full_allocation": "NOT_APPROVED_HISTORICAL_REPLAY_ONLY",
            "suitability_for_limited_risk_allocation": "NOT_APPROVED_PENDING_FORWARD_PAPER",
            "forward_paper_priority": "REQUIRES_SEPARATE_FORWARD_PAPER_EVIDENCE",
            "replay_validation": replays[model]["replay"]["validation"],
            "genuine_holdout": v69_holdout if model == "V69_PARENT" else "NOT_AVAILABLE_CANDIDATE_SPECIFIC_FREEZE_EVIDENCE_MISSING",
        }
    return {
        "analysis_kind": "HISTORICAL_OPERATIONAL_REPLAY_NOT_OUT_OF_SAMPLE",
        "period": {"start": START, "end": END, "partial_years": [2021, 2026]},
        "data_cutoff": cutoff, "cost_contract": "V101 Paper execution for V69/V79; 069500 uses one V101 initial BUY; KS11 is a non-tradable price index reference.",
        "v69_genuine_holdout": {"start": "2026-07-20", "end": "2026-07-31", "status": "DISPLAYED_SEPARATELY", "metrics": decisions["V69_PARENT"]["genuine_holdout"]},
        "v79_genuine_holdout": "NOT_AVAILABLE_CANDIDATE_SPECIFIC_FREEZE_EVIDENCE_MISSING",
        "asof_5m_reference_only": asof_reference,
        "models": decisions,
        "broker_mutation_calls": 0, "operating_database_touched": False, "reports_touched": False,
    }


def _report(summary: dict[str, Any], annual: pd.DataFrame, monthly: pd.DataFrame, regime: pd.DataFrame) -> str:
    lines = [
        "# Daily Model Calendar Analysis",
        "",
        f"- Period: {START} to {END}; 2021 and 2026 are partial years.",
        "- Daily models were fresh-replayed through isolated TEST_DATABASE_URL schemas.",
        "- V69/V79 use the existing V101 Paper fee, spread, impact, cash, minimum-order, D-1 ADV, and SELL-before-BUY contracts.",
        "- KS11 is a non-tradable price-index reference. 069500 buy-and-hold uses one initial V101 BUY then adjusted-close marking.",
        "- Annual/monthly return = last valid NAV / first valid NAV - 1 for that period. Volatility and Sharpe use daily returns and 252 trading days; Sortino uses negative daily-return deviation; Calmar = period return / abs(period MDD).",
        "- VaR/Expected Shortfall are historical daily-return loss measures. Upside/downside capture are conditional average monthly model returns divided by conditional average KS11 monthly returns.",
        "",
        "## Decision boundary",
        "",
        "This is historical operational replay, not out-of-sample proof. V69 only has a separately labelled 2026-07-20..2026-07-31 genuine-holdout slice; V79 has no candidate-specific freeze evidence.",
        f"- V69 genuine holdout: {json.dumps(summary['v69_genuine_holdout']['metrics'], ensure_ascii=False, sort_keys=True)}",
        "",
        "## Annual returns",
        "",
        annual[["model", "year", "period_type", "return", "excess_vs_ks11", "mdd", "sharpe", "order_count", "turnover"]].to_markdown(index=False),
        "",
        "## 2026 monthly returns",
        "",
        monthly[["model", "month", "return", "excess_vs_ks11", "mdd", "order_count"]].to_markdown(index=False),
        "",
        "## Regime and tail risk",
        "",
        regime[["model", "upside_capture", "downside_capture", "beta", "correlation", "mdd", "var_95", "expected_shortfall_95"]].to_markdown(index=False),
        "",
        "## Allocation decision",
        "",
    ]
    for model, decision in summary["models"].items():
        lines.extend([f"### {model}", "", f"- Full allocation: {decision['suitability_for_full_allocation']}", f"- Limited-risk allocation: {decision['suitability_for_limited_risk_allocation']}", f"- Forward Paper priority: {decision['forward_paper_priority']}", f"- Concentration: {json.dumps(decision['concentration_risk'], ensure_ascii=False, sort_keys=True)}", ""])
    lines.extend(["## Existing AS-OF 5M reference only", "", "AS-OF results below are pre-existing reference artifacts and were not executed by this analysis.", "", pd.DataFrame(summary["asof_5m_reference_only"]).to_markdown(index=False) if summary["asof_5m_reference_only"] else "NOT_AVAILABLE", ""])
    return "\n".join(lines)


def run(root: Path | str, *, output_dir: Path | str | None = None, reuse_completed: bool = False) -> dict[str, Any]:
    root = Path(root).resolve()
    out = Path(output_dir) if output_dir else root / "runtime/daily_model_calendar_analysis"
    out.mkdir(parents=True, exist_ok=True)
    cutoff = _daily_cutoff(root)
    if not cutoff["already_current"]:
        raise RuntimeError("daily cutoff is incomplete; run the existing incremental updater before analysis")
    base_url = os.environ.get("TEST_DATABASE_URL")
    if not base_url:
        raise RuntimeError("TEST_DATABASE_URL is required")
    replays = {candidate: _fresh_replay(root, base_url, candidate, out, reuse_completed=reuse_completed) for candidate in DAILY_CANDIDATES}
    common_dates = pd.DatetimeIndex(replays["V69_PARENT"]["nav"]["date"])
    if common_dates.min().date().isoformat() != START or common_dates.max().date().isoformat() != END:
        raise RuntimeError("fresh replay did not cover the requested common period")
    ks11_nav = _price_reference_nav(_price_series(root, "KS11"), common_dates)
    core_nav, core_trades, core_meta = _buy_and_hold_069500(root, common_dates)
    models: dict[str, dict[str, Any]] = {
        "V69_PARENT": {"nav": replays["V69_PARENT"]["nav"], "trades": replays["V69_PARENT"]["trades"]},
        "V79_NO63_VOL_GUARD": {"nav": replays["V79_NO63_VOL_GUARD"]["nav"], "trades": replays["V79_NO63_VOL_GUARD"]["trades"]},
        "KS11": {"nav": ks11_nav, "trades": pd.DataFrame()},
        "069500": {"nav": core_nav, "trades": core_trades},
    }
    annual = _annual_rows(root, models)
    monthly = _monthly_2026(root, models)
    regime = _regime_rows(models)
    drawdown = regime[["model", "model_id", "mdd", "peak_date", "trough_date", "recovery_date", "max_recovery_trading_days", "average_recovery_trading_days", "underwater_day_ratio"]]
    tail = regime[["model", "model_id", "var_95", "expected_shortfall_95", "var_99", "expected_shortfall_99"]]
    contribution = pd.concat([_contribution(root, models[key]["nav"], models[key]["trades"], MODEL_LABELS[key]) for key in ("V69_PARENT", "V79_NO63_VOL_GUARD", "069500")], ignore_index=True)
    asof_path = root / "runtime/asof_5m_models_validation/asof_comparison.csv"
    asof_reference = pd.read_csv(asof_path).to_dict("records") if asof_path.is_file() else []
    summary = _decision_summary(annual, monthly, regime, contribution, replays, models, cutoff, asof_reference)
    summary["reference_069500"] = core_meta
    annual.to_csv(out / "annual_returns.csv", index=False)
    monthly.to_csv(out / "monthly_returns_2026.csv", index=False)
    regime.to_csv(out / "regime_capture.csv", index=False)
    drawdown.to_csv(out / "drawdown_recovery.csv", index=False)
    tail.to_csv(out / "tail_risk.csv", index=False)
    contribution.to_csv(out / "contribution_by_etf.csv", index=False)
    _write_json(out / "model_decision_summary.json", summary)
    (out / "model_decision_report.md").write_text(_report(summary, annual, monthly, regime) + "\n", encoding="utf-8")
    return summary


__all__ = ["END", "START", "_period_metrics", "_tail_metrics", "run"]
