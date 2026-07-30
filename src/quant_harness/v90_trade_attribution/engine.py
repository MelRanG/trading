from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from quant_harness.v69_dynamic_theme_leadership import engine as v69
from quant_harness.v77_corrected_price_allocation import engine as v77
from quant_harness.v83_independent_self_research import engine as v83

REPORT = "v90_trade_attribution"


def _cfg(root: Path) -> dict[str, Any]:
    return yaml.safe_load((root / "config/v93_feedback_research.yaml").read_text(encoding="utf-8"))


def _regime_series(market: dict[str, Any], core: str, tickers: list[str]) -> pd.Series:
    close = market["close"]
    core_r63 = close[core].pct_change(63, fill_method=None).shift(1)
    core_vol20 = close[core].pct_change(fill_method=None).rolling(20, min_periods=15).std().shift(1) * np.sqrt(252)
    ma126 = close[tickers].rolling(126, min_periods=80).mean()
    breadth = close[tickers].shift(1).gt(ma126.shift(1)).mean(axis=1)
    result = pd.Series("RANGE_RISK", index=close.index, dtype=object)
    result[(core_r63 < -0.10) | (core_vol20 > 0.35)] = "SHOCK_RISK"
    result[(core_r63 > 0.05) & (breadth >= 0.60)] = "BROAD_BULL"
    result[(core_r63 > 0.00) & (breadth < 0.60) & result.eq("RANGE_RISK")] = "NARROW_BULL"
    return result


def _ranked_two(date: pd.Timestamp, universe: pd.DataFrame, features: dict[str, Any]) -> tuple[str | None, str | None]:
    return v83._ranked_two(date, universe, features)


def _safe_return(market: dict[str, Any], ticker: str | None, start: int, horizon: int) -> float:
    if not ticker or ticker not in market["open"].columns or start + horizon >= len(market["open"]):
        return np.nan
    entry = market["open"].iloc[start].get(ticker, np.nan)
    finish = market["close"].iloc[start + horizon].get(ticker, np.nan)
    if pd.isna(entry) or pd.isna(finish) or float(entry) <= 0:
        return np.nan
    return float(finish / entry - 1.0)


def _path_extremes(market: dict[str, Any], ticker: str | None, start: int, horizon: int) -> tuple[float, float]:
    if not ticker or ticker not in market["close"].columns or start + horizon >= len(market["close"]):
        return np.nan, np.nan
    entry = market["open"].iloc[start].get(ticker, np.nan)
    if pd.isna(entry) or float(entry) <= 0:
        return np.nan, np.nan
    path = market["close"].iloc[start : start + horizon + 1][ticker].dropna()
    if path.empty:
        return np.nan, np.nan
    return float(path.max() / entry - 1.0), float(path.min() / entry - 1.0)


def _event_id(scenario: str, date: pd.Timestamp, old: str | None, new: str | None) -> str:
    raw = f"{scenario}|{date.date()}|{old or 'CASH'}|{new or 'CORE'}"
    return sha256(raw.encode()).hexdigest()[:20]


def _decision_ledger(
    scenario: str,
    selection: pd.DataFrame,
    features: dict[str, Any],
    universe: pd.DataFrame,
    market: dict[str, Any],
    core: str,
    regime: pd.Series,
    horizons: list[int],
) -> pd.DataFrame:
    active_col = "leader_ticker" if "leader_ticker" in selection.columns else "sleeve_ticker"
    score_col = "leader_score_d1" if "leader_score_d1" in selection.columns else "sleeve_score_d1"
    family = "V69" if scenario.startswith("V69") else "V79"
    dates = market["close"].index
    positions = {d: i for i, d in enumerate(dates)}
    prior: str | None = None
    rows: list[dict[str, Any]] = []
    for record in selection.to_dict("records"):
        date = pd.Timestamp(record["date"])
        raw = record.get(active_col)
        current = str(raw) if pd.notna(raw) else None
        if current == prior:
            continue
        event_type = "ENTRY" if prior is None and current else "EXIT" if prior and current is None else "ROTATION"
        runner = _ranked_two(date, universe, features)[1]
        pos = positions[date]
        row: dict[str, Any] = {
            "event_id": _event_id(scenario, date, prior, current),
            "scenario": scenario,
            "family": family,
            "decision_date": date,
            "information_cutoff": record.get("information_cutoff"),
            "event_type": event_type,
            "old_ticker": prior,
            "chosen_ticker": current,
            "runner_up_ticker": runner,
            "core_ticker": core,
            "regime_d1": str(regime.loc[date]),
            "decision_reason": str(record.get("decision_reason", "")),
            "active_score_d1": record.get(score_col, np.nan),
            "snapshot_json": json.dumps({
                k: (None if pd.isna(v) else v)
                for k, v in record.items()
                if k not in {"date"} and isinstance(v, (str, int, float, bool, type(None), np.integer, np.floating))
            }, sort_keys=True, default=str),
        }
        for horizon in horizons:
            row[f"chosen_return_{horizon}d"] = _safe_return(market, current, pos, horizon)
            row[f"old_return_{horizon}d"] = _safe_return(market, prior, pos, horizon)
            row[f"runner_return_{horizon}d"] = _safe_return(market, runner, pos, horizon)
            row[f"core_return_{horizon}d"] = _safe_return(market, core, pos, horizon)
            mfe, mae = _path_extremes(market, current, pos, horizon)
            row[f"chosen_mfe_{horizon}d"] = mfe
            row[f"chosen_mae_{horizon}d"] = mae
            row[f"matured_{horizon}d"] = bool(pos + horizon < len(dates))
        rows.append(row)
        prior = current
    return pd.DataFrame(rows)


def _order_ledger(scenario: str, orders: pd.DataFrame, decisions: pd.DataFrame, regime: pd.Series) -> pd.DataFrame:
    if orders.empty:
        return pd.DataFrame()
    out = orders.copy()
    out["date"] = pd.to_datetime(out["date"])
    event_by_date = decisions.set_index("decision_date")["event_id"].to_dict() if not decisions.empty else {}
    reason_by_date = decisions.set_index("decision_date")["decision_reason"].to_dict() if not decisions.empty else {}
    out["event_id"] = out["date"].map(event_by_date)
    out["trade_type"] = np.where(out["event_id"].notna(), "DECISION_TRADE", "REBALANCE_TRADE")
    out["decision_reason"] = out["date"].map(reason_by_date).fillna("WEIGHT_DRIFT_OR_CASH_REBALANCE")
    out["regime_d1"] = out["date"].map(regime)
    out["family"] = "V69" if scenario.startswith("V69") else "V79"
    notional = out["notional_at_reference_open_krw"].abs().replace(0.0, np.nan)
    slippage = (out["execution_price_krw"] - out["reference_open_krw"]).abs() * out["quantity"]
    out["execution_drag_bps"] = (out["fee_krw"] + slippage).div(notional) * 10000.0
    return out


def run(root: Path | str) -> dict[str, Any]:
    root = Path(root)
    out_dir = root / "reports" / REPORT
    out_dir.mkdir(parents=True, exist_ok=True)
    cfg = _cfg(root)
    cfg77 = v77._load_config(root)
    cfg77 = type(cfg77)(**{**cfg77.__dict__, "end_date": str(cfg["data_end"])})
    market = v77.load_adjusted_market(root, cfg77)
    targets, selections = v83._build_all_targets(root, market, cfg77)
    v69_cfg = v69._load_config(root)
    universe = v69._load_universe(root, type(v69_cfg)(**{**v69_cfg.__dict__, "end_date": str(cfg["data_end"]), "leader_weight": 0.80}))
    tickers = universe["ticker"].astype(str).tolist()
    regime = _regime_series(market, cfg77.core_ticker, tickers)
    horizons = [int(x) for x in cfg["attribution"]["horizons"]]

    decision_frames: list[pd.DataFrame] = []
    order_frames: list[pd.DataFrame] = []
    account_rows: list[dict[str, Any]] = []
    for scenario, info in selections.items():
        decisions = _decision_ledger(scenario, info["selection"], info["features"], universe, market, cfg77.core_ticker, regime, horizons)
        account, orders, audit = v83._execute_target(market, targets[scenario], cfg77, scenario)
        decision_frames.append(decisions)
        order_frames.append(_order_ledger(scenario, orders, decisions, regime))
        account_rows.append({"scenario": scenario, "orders": len(orders), "negative_cash_days": audit["negative_cash_days"], "final_nav_krw": float(account.iloc[-1]["nav_krw"])})

    decisions = pd.concat(decision_frames, ignore_index=True)
    orders = pd.concat(order_frames, ignore_index=True)
    regime_frame = regime.rename("regime_d1").reset_index().rename(columns={"index": "date"})
    quality = pd.DataFrame([
        {"gate": "DECISION_IDS_UNIQUE", "passed": not decisions["event_id"].duplicated().any(), "detail": f"events={len(decisions)}"},
        {"gate": "ALL_INFORMATION_CUTOFFS_D1_OR_EARLIER", "passed": bool((pd.to_datetime(decisions["information_cutoff"]) < pd.to_datetime(decisions["decision_date"])).all()), "detail": "all decision snapshots use prior information"},
        {"gate": "ALL_PARENT_ORDERS_ATTRIBUTED", "passed": len(orders[orders["scenario"].isin(["V69_PARENT", "V79_PARENT"])]) == sum(x["orders"] for x in account_rows if x["scenario"] in {"V69_PARENT", "V79_PARENT"}), "detail": "one row per actual order"},
        {"gate": "MULTI_HORIZON_OUTCOMES_PRESENT", "passed": all(f"chosen_return_{h}d" in decisions for h in horizons), "detail": json.dumps(horizons)},
        {"gate": "NO_NEGATIVE_CASH", "passed": all(x["negative_cash_days"] == 0 for x in account_rows), "detail": f"scenarios={len(account_rows)}"},
    ])
    decisions.to_csv(out_dir / "v90_decision_attribution.csv", index=False)
    orders.to_csv(out_dir / "v90_order_attribution.csv", index=False)
    regime_frame.to_csv(out_dir / "v90_regime_d1.csv", index=False)
    pd.DataFrame(account_rows).to_csv(out_dir / "v90_account_audit.csv", index=False)
    quality.to_csv(out_dir / "v90_quality_gates.csv", index=False)
    summary = {"decision_events": len(decisions), "orders": len(orders), "quality_gates_passed": bool(quality["passed"].all()), "live_allowed": False}
    (out_dir / "v90_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
