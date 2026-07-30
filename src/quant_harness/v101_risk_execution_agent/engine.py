from __future__ import annotations

import json
import math
import pickle
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd
import yaml

from quant_harness.v69_dynamic_theme_leadership import engine as v69
from quant_harness.v77_corrected_price_allocation import engine as v77
from quant_harness.v77_2_validation_integrity.engine import _relative_bootstrap_period, _slice_metrics
from quant_harness.v84_dual_paper_parity import engine as v84

REPORT = "v101_risk_execution_agent"
ACTIVE_POLICY = "PARENT_EXECUTION_CONTRACT"
CANDIDATES = (
    "V69_REBALANCE_BAND_2PP",
    "DYNAMIC_MIN_ORDER_50BPS_NAV",
    "V69_ALPHA_FIRST_BUY_PRIORITY",
)
ALL_POLICIES = (ACTIVE_POLICY,) + CANDIDATES


@dataclass(frozen=True)
class AgentExecutionPolicy:
    policy_id: str
    v69_rebalance_band: float
    v79_rebalance_band: float
    minimum_order_notional_krw: float
    dynamic_min_order_nav_fraction: float
    v69_buy_priority: str
    v79_buy_priority: str
    deferred_min_order_sets_pending: bool


@dataclass
class AgentPortfolioState:
    cash: float
    quantities: dict[str, int]
    pending: bool = False
    prior_signature: str | None = None


@dataclass(frozen=True)
class ExecutionFill:
    ticker: str
    side: str
    quantity: int
    reference_open_krw: float
    execution_price_krw: float
    fee_krw: float
    half_spread_cost_krw: float
    impact_cost_krw: float
    impact_bps: float
    adv20_d1_krw: float
    participation_of_d1_adv: float
    requested_quantity: int
    participation_cap_quantity: int
    cash_cap_quantity: int | None
    target_delta_notional_krw: float
    minimum_order_threshold_krw: float


def _load_cfg(root: Path) -> dict[str, Any]:
    return yaml.safe_load((root / "config/v101_risk_execution_agent.yaml").read_text(encoding="utf-8"))


def _policy(root: Path, policy_id: str) -> AgentExecutionPolicy:
    cfg = _load_cfg(root)
    key = {
        ACTIVE_POLICY: "parent",
        "V69_REBALANCE_BAND_2PP": "v69_rebalance_band_2pp",
        "DYNAMIC_MIN_ORDER_50BPS_NAV": "dynamic_min_order_50bps_nav",
        "V69_ALPHA_FIRST_BUY_PRIORITY": "v69_alpha_first_buy_priority",
    }[policy_id]
    p = cfg["policy"][key]
    return AgentExecutionPolicy(policy_id=policy_id, **p)


def _signature(weights: Mapping[str, float]) -> str:
    return sha256(json.dumps(dict(sorted(weights.items())), separators=(",", ":")).encode()).hexdigest()


def _normalise_targets(weights: Mapping[str, float]) -> dict[str, float]:
    clean = {str(k).zfill(6): float(v) for k, v in weights.items() if float(v) > 1e-12}
    total = sum(clean.values())
    if not clean or not np.isclose(total, 1.0, atol=1e-9):
        raise ValueError(f"target weights must sum to one; total={total}")
    return clean


def _buy_order(targets: dict[str, float], desired: dict[str, int], quantities: dict[str, int], priority: str, core_ticker: str) -> list[str]:
    if priority == "CORE_THEN_TARGET_DESC":
        return [core_ticker] + [t for t in sorted(targets, key=lambda x: (targets[x], x), reverse=True) if t != core_ticker]
    if priority == "NONCORE_THEN_CORE":
        return [t for t in sorted(targets, key=lambda x: (targets[x], x), reverse=True) if t != core_ticker] + ([core_ticker] if core_ticker in targets else [])
    if priority == "DEFICIT_DESC":
        return sorted(targets, key=lambda t: (desired.get(t, 0) - quantities.get(t, 0), targets[t], t), reverse=True)
    raise ValueError(f"unknown buy priority {priority}")


def execute_target_map(
    state: AgentPortfolioState,
    *,
    targets: Mapping[str, float],
    open_prices: Mapping[str, float],
    adv20_d1: Mapping[str, float],
    spec: v77.ExecutionSpec,
    policy: AgentExecutionPolicy,
    rebalance_band: float,
    buy_priority: str,
    core_ticker: str,
) -> tuple[AgentPortfolioState, list[ExecutionFill], list[dict[str, Any]], dict[str, Any]]:
    targets = _normalise_targets(targets)
    tracked = set(state.quantities) | set(targets)
    missing = sorted(t for t in tracked if t not in open_prices or not np.isfinite(open_prices[t]) or open_prices[t] <= 0)
    if missing:
        raise ValueError(f"missing executable adjusted open: {missing}")
    nav_open = state.cash + sum(q * float(open_prices[t]) for t, q in state.quantities.items())
    actual = {t: state.quantities.get(t, 0) * float(open_prices[t]) / nav_open for t in tracked} if nav_open > 0 else {}
    max_drift = max((abs(actual.get(t, 0.0) - targets.get(t, 0.0)) for t in tracked), default=0.0)
    signature = _signature(targets)
    target_changed = signature != state.prior_signature
    trigger = bool(state.pending or target_changed or max_drift >= rebalance_band)
    quantities = dict(state.quantities)
    cash = float(state.cash)
    pending = False
    fills: list[ExecutionFill] = []
    intents: list[dict[str, Any]] = []
    counts = {
        "participation_limited_orders": 0,
        "cash_limited_orders": 0,
        "minimum_notional_deferred_orders": 0,
        "missing_adv_blocks": 0,
    }
    dynamic_threshold = max(float(policy.minimum_order_notional_krw), nav_open * float(policy.dynamic_min_order_nav_fraction))
    if trigger:
        desired = {t: int(math.floor(nav_open * w / float(open_prices[t]))) for t, w in targets.items()}
        for ticker in quantities:
            desired.setdefault(ticker, 0)
        for ticker in sorted(quantities):
            requested = quantities.get(ticker, 0) - desired.get(ticker, 0)
            if requested <= 0:
                continue
            raw = float(open_prices[ticker]); adv = float(adv20_d1.get(ticker, np.nan))
            cap = int(math.floor(adv * spec.max_participation_of_d1_adv / raw)) if np.isfinite(adv) and adv > 0 else 0
            qty = min(requested, cap)
            reason = "EXECUTED"
            if cap <= 0:
                reason = "MISSING_OR_ZERO_D1_ADV"; pending = True; counts["missing_adv_blocks"] += 1
            elif qty < requested:
                pending = True; counts["participation_limited_orders"] += 1
            delta_notional = requested * raw
            if qty > 0 and qty * raw < dynamic_threshold:
                reason = "BELOW_MIN_ORDER_THRESHOLD"; qty = 0; counts["minimum_notional_deferred_orders"] += 1
                if policy.deferred_min_order_sets_pending:
                    pending = True
            intents.append({
                "ticker": ticker, "side": "SELL", "requested_quantity": requested,
                "participation_cap_quantity": cap, "cash_cap_quantity": None,
                "final_quantity": qty, "decision": reason,
                "target_delta_notional_krw": delta_notional,
                "minimum_order_threshold_krw": dynamic_threshold,
            })
            if qty <= 0:
                continue
            notional = qty * raw
            impact = v77._impact_bps(notional, adv, spec)
            px = raw * (1.0 - (spec.half_spread_bps + impact) / 10000.0)
            fee = qty * px * spec.sell_fee_bps / 10000.0
            spread_cost = qty * raw * spec.half_spread_bps / 10000.0
            impact_cost = qty * raw * impact / 10000.0
            cash += qty * px - fee
            quantities[ticker] = quantities.get(ticker, 0) - qty
            fills.append(ExecutionFill(
                ticker, "SELL", qty, raw, px, fee, spread_cost, impact_cost, impact, adv,
                notional / adv if np.isfinite(adv) and adv > 0 else np.nan,
                requested, cap, None, delta_notional, dynamic_threshold,
            ))
        for ticker in _buy_order(targets, desired, quantities, buy_priority, core_ticker):
            requested = desired.get(ticker, 0) - quantities.get(ticker, 0)
            if requested <= 0:
                continue
            raw = float(open_prices[ticker]); adv = float(adv20_d1.get(ticker, np.nan))
            cap = int(math.floor(adv * spec.max_participation_of_d1_adv / raw)) if np.isfinite(adv) and adv > 0 else 0
            participation_qty = min(requested, cap)
            reason = "EXECUTED"
            if cap <= 0:
                reason = "MISSING_OR_ZERO_D1_ADV"; pending = True; counts["missing_adv_blocks"] += 1
            elif participation_qty < requested:
                pending = True; counts["participation_limited_orders"] += 1
            delta_notional = requested * raw
            if participation_qty > 0 and participation_qty * raw < dynamic_threshold:
                reason = "BELOW_MIN_ORDER_THRESHOLD"; participation_qty = 0; counts["minimum_notional_deferred_orders"] += 1
                if policy.deferred_min_order_sets_pending:
                    pending = True
            cash_cap_qty = 0
            qty = 0
            impact = px = fee = participation = 0.0
            if participation_qty > 0:
                qty, impact, px, fee, participation = v77._buy_fill_terms(
                    cash=cash, max_quantity=participation_qty, raw_open=raw, adv=adv, spec=spec
                )
                cash_cap_qty = qty
                if qty < participation_qty:
                    pending = True; counts["cash_limited_orders"] += 1
                    reason = "CASH_LIMITED" if qty == 0 else "PARTIAL_CASH_LIMITED"
                if qty > 0 and qty * raw < dynamic_threshold:
                    qty = 0
                    pending = True
                    counts["minimum_notional_deferred_orders"] += 1
                    reason = "BELOW_MIN_AFTER_CASH_CAP"
            intents.append({
                "ticker": ticker, "side": "BUY", "requested_quantity": requested,
                "participation_cap_quantity": cap, "cash_cap_quantity": cash_cap_qty,
                "final_quantity": qty, "decision": reason,
                "target_delta_notional_krw": delta_notional,
                "minimum_order_threshold_krw": dynamic_threshold,
            })
            if qty <= 0:
                continue
            spread_cost = qty * raw * spec.half_spread_bps / 10000.0
            impact_cost = qty * raw * impact / 10000.0
            cash -= qty * px + fee
            quantities[ticker] = quantities.get(ticker, 0) + qty
            fills.append(ExecutionFill(
                ticker, "BUY", qty, raw, px, fee, spread_cost, impact_cost, impact, adv, participation,
                requested, cap, cash_cap_qty, delta_notional, dynamic_threshold,
            ))
    next_state = AgentPortfolioState(cash=cash, quantities=quantities, pending=pending, prior_signature=signature)
    audit = {
        "triggered": trigger,
        "target_changed": target_changed,
        "max_abs_weight_drift_open": max_drift,
        "minimum_order_threshold_krw": dynamic_threshold,
        **counts,
    }
    return next_state, fills, intents, audit


def replay(
    close: pd.DataFrame,
    open_px: pd.DataFrame,
    adv20_d1: pd.DataFrame,
    ledger: pd.DataFrame,
    *,
    initial_capital: float,
    spec: v77.ExecutionSpec,
    policy: AgentExecutionPolicy,
    strategy: str,
    core_ticker: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    indexed = ledger.set_index("date").reindex(close.index)
    state = AgentPortfolioState(initial_capital, {})
    band = policy.v69_rebalance_band if strategy == "V69" else policy.v79_rebalance_band
    priority = policy.v69_buy_priority if strategy == "V69" else policy.v79_buy_priority
    daily: list[dict[str, Any]] = []
    orders: list[dict[str, Any]] = []
    intents: list[dict[str, Any]] = []
    for date in close.index:
        raw = indexed.loc[date, "target_weights_json"]
        targets = raw if isinstance(raw, dict) else json.loads(str(raw))
        relevant = set(state.quantities) | set(targets)
        opens = {t: float(open_px.loc[date, t]) for t in relevant}
        adv = {t: float(adv20_d1.loc[date, t]) if t in adv20_d1.columns else np.nan for t in relevant}
        state, fills, day_intents, audit = execute_target_map(
            state, targets=targets, open_prices=opens, adv20_d1=adv, spec=spec,
            policy=policy, rebalance_band=band, buy_priority=priority, core_ticker=core_ticker,
        )
        for f in fills:
            orders.append({"date": date, "strategy": strategy, "policy": policy.policy_id, **asdict(f)})
        for i in day_intents:
            intents.append({"date": date, "strategy": strategy, "policy": policy.policy_id, **i})
        nav = state.cash + sum(q * float(close.loc[date, t]) for t, q in state.quantities.items())
        tracked = set(targets) | set(state.quantities)
        actual_weights = {t: state.quantities.get(t, 0) * float(close.loc[date, t]) / nav for t in tracked} if nav > 0 else {}
        tracking = max((abs(actual_weights.get(t, 0.0) - targets.get(t, 0.0)) for t in tracked), default=0.0)
        daily.append({
            "date": date, "strategy": strategy, "policy": policy.policy_id,
            "cash_krw": state.cash, "nav_krw": nav,
            "holdings_json": json.dumps({k: v for k, v in state.quantities.items() if v}, sort_keys=True),
            "target_weights_json": json.dumps(targets, sort_keys=True),
            "pending_execution": state.pending, "max_abs_tracking_error_close": tracking,
            **audit,
        })
    return pd.DataFrame(daily), pd.DataFrame(orders), pd.DataFrame(intents)


def _metrics(account: pd.DataFrame, orders: pd.DataFrame, intents: pd.DataFrame, initial: float, purged_start: pd.Timestamp) -> dict[str, Any]:
    nav = account.set_index("date")["nav_krw"]
    row: dict[str, Any] = {**v69._metrics(nav, initial)}
    periods = {
        "development": ("2018-01-01", "2022-12-31"),
        "validation": ("2023-01-01", "2024-12-31"),
        "purged_validation": (str(purged_start.date()), "2024-12-31"),
        "observed": ("2025-01-01", "2026-07-03"),
        "recent_1y": ("2025-07-04", "2026-07-03"),
    }
    for name, (start, end) in periods.items():
        m = _slice_metrics(nav, start, end, initial)
        row[f"{name}_return_pct"] = m["return_pct"]
        row[f"{name}_sharpe"] = m["sharpe"]
        row[f"{name}_mdd_pct"] = m["mdd_pct"]
    row["order_count"] = int(len(orders))
    row["turnover_notional_krw"] = float((orders["quantity"] * orders["reference_open_krw"]).sum()) if not orders.empty else 0.0
    for c in ("fee_krw", "half_spread_cost_krw", "impact_cost_krw"):
        row[f"total_{c}"] = float(pd.to_numeric(orders.get(c, pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
    row["total_execution_cost_krw"] = row["total_fee_krw"] + row["total_half_spread_cost_krw"] + row["total_impact_cost_krw"]
    row["pending_days"] = int(account["pending_execution"].sum())
    row["participation_limited_intents"] = int((intents.get("participation_cap_quantity", pd.Series(dtype=float)) < intents.get("requested_quantity", pd.Series(dtype=float))).sum()) if not intents.empty else 0
    row["minimum_notional_deferred_intents"] = int(intents.get("decision", pd.Series(dtype=str)).isin(["BELOW_MIN_ORDER_THRESHOLD", "BELOW_MIN_AFTER_CASH_CAP"]).sum()) if not intents.empty else 0
    row["cash_limited_intents"] = int(intents.get("decision", pd.Series(dtype=str)).isin(["CASH_LIMITED", "PARTIAL_CASH_LIMITED"]).sum()) if not intents.empty else 0
    first_fill = orders["date"].min() if not orders.empty else account["date"].min()
    tracking_window = account[account["date"] >= first_fill]
    row["average_tracking_error_pp"] = float(tracking_window["max_abs_tracking_error_close"].mean() * 100.0)
    row["maximum_tracking_error_pp"] = float(tracking_window["max_abs_tracking_error_close"].max() * 100.0)
    row["negative_cash_days"] = int(account["cash_krw"].lt(-0.01).sum())
    row["maximum_participation"] = float(pd.to_numeric(orders.get("participation_of_d1_adv", pd.Series(dtype=float)), errors="coerce").max()) if not orders.empty else 0.0
    row["maximum_impact_bps"] = float(pd.to_numeric(orders.get("impact_bps", pd.Series(dtype=float)), errors="coerce").max()) if not orders.empty else 0.0
    return row


def _run_policy(root: Path, policy_id: str, initial_capital: float = 10_000_000.0) -> dict[str, Any]:
    cfg77 = v77._load_config(root)
    market, _universe, ledger69, ledger79, _ = v84.build_strategy_ledgers(root)
    p = _policy(root, policy_id)
    out: dict[str, Any] = {"policy": p, "market": market, "ledger69": ledger69, "ledger79": ledger79}
    for label, ledger in (("69", ledger69), ("79", ledger79)):
        strategy = f"V{label}"
        account, orders, intents = replay(
            market["close"], market["open"], market["adv20_d1"], ledger,
            initial_capital=initial_capital, spec=cfg77.base_execution, policy=p,
            strategy=strategy, core_ticker=cfg77.core_ticker,
        )
        stress, stress_orders, stress_intents = replay(
            market["close"], market["open"], market["adv20_d1"], ledger,
            initial_capital=initial_capital, spec=cfg77.stress_execution, policy=p,
            strategy=strategy, core_ticker=cfg77.core_ticker,
        )
        out[f"account{label}"] = account; out[f"orders{label}"] = orders; out[f"intents{label}"] = intents
        out[f"stress{label}"] = stress; out[f"stress_orders{label}"] = stress_orders; out[f"stress_intents{label}"] = stress_intents
    return out


def _metric_table(runs: dict[str, dict[str, Any]], purge_sessions: int) -> pd.DataFrame:
    rows = []
    market_index = runs[ACTIVE_POLICY]["market"]["close"].index
    validation_start = market_index[market_index >= pd.Timestamp("2023-01-01")][0]
    pos = market_index.get_loc(validation_start)
    purged_start = market_index[min(pos + purge_sessions, len(market_index) - 1)]
    for policy_id, run in runs.items():
        for label in ("69", "79"):
            m = _metrics(run[f"account{label}"], run[f"orders{label}"], run[f"intents{label}"], 10_000_000.0, purged_start)
            stress_nav = run[f"stress{label}"].set_index("date")["nav_krw"]
            m.update({
                "policy": policy_id, "strategy": f"V{label}",
                "stress_return_pct": float((stress_nav.iloc[-1] / 10_000_000.0 - 1.0) * 100.0),
                "stress_order_count": int(len(run[f"stress_orders{label}"])),
            })
            rows.append(m)
    return pd.DataFrame(rows)


def _promotion(root: Path, metrics: pd.DataFrame, runs: dict[str, dict[str, Any]]) -> pd.DataFrame:
    cfg = _load_cfg(root); p = cfg["promotion"]
    parent = metrics[metrics.policy.eq(ACTIVE_POLICY)].set_index("strategy")
    rows: list[dict[str, Any]] = []
    for policy_id in CANDIDATES:
        candidate = metrics[metrics.policy.eq(policy_id)].set_index("strategy")
        for strategy in ("V69", "V79"):
            applicable = not (policy_id in {"V69_REBALANCE_BAND_2PP", "V69_ALPHA_FIRST_BUY_PRIORITY"} and strategy == "V79")
            label = "69" if strategy == "V69" else "79"
            nav_c = runs[policy_id][f"account{label}"].set_index("date")["nav_krw"]
            nav_p = runs[ACTIVE_POLICY][f"account{label}"].set_index("date")["nav_krw"]
            boot = _relative_bootstrap_period(nav_c, nav_p, "2023-01-01", "2024-12-31", samples=int(p["bootstrap_samples"]), block_months=3)
            parent_orders = max(int(parent.loc[strategy, "order_count"]), 1)
            order_reduction = 1.0 - float(candidate.loc[strategy, "order_count"]) / parent_orders
            gates = {
                "development_noninferior": candidate.loc[strategy, "development_return_pct"] >= parent.loc[strategy, "development_return_pct"] - float(p["development_tolerance_pp"]),
                "validation_noninferior": candidate.loc[strategy, "validation_return_pct"] >= parent.loc[strategy, "validation_return_pct"] - float(p["validation_tolerance_pp"]),
                "purged_validation_noninferior": candidate.loc[strategy, "purged_validation_return_pct"] >= parent.loc[strategy, "purged_validation_return_pct"] - float(p["purged_validation_tolerance_pp"]),
                "recent1y_noninferior": candidate.loc[strategy, "recent_1y_return_pct"] >= parent.loc[strategy, "recent_1y_return_pct"] - float(p["recent1y_tolerance_pp"]),
                "stress_noninferior": candidate.loc[strategy, "stress_return_pct"] >= parent.loc[strategy, "stress_return_pct"] - float(p["stress_tolerance_pp"]),
                "mdd_noninferior": candidate.loc[strategy, "mdd_pct"] >= parent.loc[strategy, "mdd_pct"] - float(p["mdd_tolerance_pp"]),
                "tracking_average_bounded": candidate.loc[strategy, "average_tracking_error_pp"] <= parent.loc[strategy, "average_tracking_error_pp"] + float(p["average_tracking_error_tolerance_pp"]),
                "tracking_max_bounded": candidate.loc[strategy, "maximum_tracking_error_pp"] <= parent.loc[strategy, "maximum_tracking_error_pp"] + float(p["maximum_tracking_error_tolerance_pp"]),
                "negative_cash_zero": candidate.loc[strategy, "negative_cash_days"] == 0,
                "bootstrap_supported": float(boot["positive_probability"]) >= float(p["validation_bootstrap_probability_min"]),
                "execution_value_added": order_reduction >= float(p["minimum_order_reduction_ratio"]) or candidate.loc[strategy, "total_execution_cost_krw"] < parent.loc[strategy, "total_execution_cost_krw"],
            }
            passed = bool(applicable and all(gates.values()))
            if not applicable:
                status = "NOT_APPLICABLE_PARENT_PARITY"
            elif passed:
                status = "BACKTEST_PASSED_FORWARD_REQUIRED"
            elif all(v for k, v in gates.items() if k != "bootstrap_supported") and not gates["bootstrap_supported"]:
                status = "FORWARD_SHADOW_ONLY_BOOTSTRAP_NOT_CLEARED"
            else:
                status = "BACKTEST_REJECTED"
            rows.append({
                "policy": policy_id, "strategy": strategy, "applicable": applicable,
                "status": status, "backtest_passed": passed, "promoted": False,
                "order_reduction_ratio": order_reduction,
                "validation_bootstrap_probability": float(boot["positive_probability"]),
                "return_delta_pp": float(candidate.loc[strategy, "return_pct"] - parent.loc[strategy, "return_pct"]),
                "validation_delta_pp": float(candidate.loc[strategy, "validation_return_pct"] - parent.loc[strategy, "validation_return_pct"]),
                "purged_validation_delta_pp": float(candidate.loc[strategy, "purged_validation_return_pct"] - parent.loc[strategy, "purged_validation_return_pct"]),
                "recent1y_delta_pp": float(candidate.loc[strategy, "recent_1y_return_pct"] - parent.loc[strategy, "recent_1y_return_pct"]),
                "stress_delta_pp": float(candidate.loc[strategy, "stress_return_pct"] - parent.loc[strategy, "stress_return_pct"]),
                "execution_cost_delta_krw": float(candidate.loc[strategy, "total_execution_cost_krw"] - parent.loc[strategy, "total_execution_cost_krw"]),
                "average_tracking_error_pp": float(candidate.loc[strategy, "average_tracking_error_pp"]),
                "maximum_tracking_error_pp": float(candidate.loc[strategy, "maximum_tracking_error_pp"]),
                "gates_json": json.dumps({k: bool(v) for k, v in gates.items()}, sort_keys=True),
            })
    return pd.DataFrame(rows)


def _parent_parity(root: Path, run: dict[str, Any]) -> pd.DataFrame:
    cfg77 = v77._load_config(root)
    market, _universe, ledger69, ledger79, _ = v84.build_strategy_ledgers(root)
    official69, _ = v84.replay_target_ledger(
        market["close"], market["open"], market["adv20_d1"], ledger69,
        initial_capital=cfg77.initial_capital_krw, policy=v84.ExecutionPolicy.from_v77(cfg77.base_execution),
        rebalance_band=0.0, scenario="V101_PARENT_PARITY_69", buy_priority="CORE_THEN_TARGET_DESC", core_ticker=cfg77.core_ticker,
    )
    official79, _ = v84.replay_target_ledger(
        market["close"], market["open"], market["adv20_d1"], ledger79,
        initial_capital=cfg77.initial_capital_krw, policy=v84.ExecutionPolicy.from_v77(cfg77.base_execution),
        rebalance_band=0.05, scenario="V101_PARENT_PARITY_79",
    )
    return pd.DataFrame([
        {"strategy": "V69", "official_final_nav": float(official69.nav_krw.iloc[-1]), "v101_final_nav": float(run["account69"].nav_krw.iloc[-1]), "abs_error_krw": abs(float(official69.nav_krw.iloc[-1] - run["account69"].nav_krw.iloc[-1]))},
        {"strategy": "V79", "official_final_nav": float(official79.nav_krw.iloc[-1]), "v101_final_nav": float(run["account79"].nav_krw.iloc[-1]), "abs_error_krw": abs(float(official79.nav_krw.iloc[-1] - run["account79"].nav_krw.iloc[-1]))},
    ])


def _load_cached_run(root: Path, policy_id: str, capital: float = 10_000_000.0) -> dict[str, Any]:
    name = f"{policy_id}.pkl" if capital == 10_000_000.0 else f"CAP_{int(capital)}.pkl"
    path = root / ".v101_cache" / name
    if path.exists():
        with path.open("rb") as f:
            return pickle.load(f)
    return _run_policy(root, policy_id, capital)




def _run_job(root_text: str, policy_id: str, capital: float) -> tuple[str, float, dict[str, Any]]:
    root = Path(root_text)
    return policy_id, capital, _run_policy(root, policy_id, capital)


def _load_run_matrix(root: Path) -> tuple[dict[str, dict[str, Any]], dict[float, dict[str, Any]]]:
    policy_runs: dict[str, dict[str, Any]] = {}
    capital_runs: dict[float, dict[str, Any]] = {}
    jobs: list[tuple[str, float]] = [(p, 10_000_000.0) for p in ALL_POLICIES]
    jobs += [(ACTIVE_POLICY, 100_000_000.0), (ACTIVE_POLICY, 1_000_000_000.0)]
    missing: list[tuple[str, float]] = []
    for policy_id, capital in jobs:
        name = f"{policy_id}.pkl" if capital == 10_000_000.0 else f"CAP_{int(capital)}.pkl"
        path = root / ".v101_cache" / name
        if path.exists():
            with path.open("rb") as f:
                result = pickle.load(f)
            if capital == 10_000_000.0:
                policy_runs[policy_id] = result
            else:
                capital_runs[capital] = result
        else:
            missing.append((policy_id, capital))
    if missing:
        workers = min(3, len(missing))
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(_run_job, str(root), policy_id, capital) for policy_id, capital in missing]
            for future in as_completed(futures):
                policy_id, capital, result = future.result()
                if capital == 10_000_000.0:
                    policy_runs[policy_id] = result
                else:
                    capital_runs[capital] = result
    return policy_runs, capital_runs


def _capacity(root: Path, base_run: dict[str, Any] | None = None, capital_runs: dict[float, dict[str, Any]] | None = None) -> pd.DataFrame:
    cfg = _load_cfg(root)
    rows: list[dict[str, Any]] = []
    for capital in cfg["capacity_diagnostics"]["initial_capital_krw"]:
        if float(capital) == 10_000_000.0 and base_run is not None:
            run = base_run
        elif capital_runs is not None and float(capital) in capital_runs:
            run = capital_runs[float(capital)]
        else:
            run = _load_cached_run(root, ACTIVE_POLICY, float(capital))
        for label in ("69", "79"):
            account = run[f"account{label}"]; orders = run[f"orders{label}"]; intents = run[f"intents{label}"]
            rows.append({
                "initial_capital_krw": float(capital), "strategy": f"V{label}",
                "final_nav_krw": float(account.nav_krw.iloc[-1]),
                "return_pct": float((account.nav_krw.iloc[-1] / float(capital) - 1.0) * 100.0),
                "order_count": int(len(orders)),
                "pending_days": int(account.pending_execution.sum()),
                "participation_limited_intents": int((intents.participation_cap_quantity < intents.requested_quantity).sum()) if not intents.empty else 0,
                "max_participation": float(orders.participation_of_d1_adv.max()) if not orders.empty else 0.0,
                "max_tracking_error_pp": float(account.loc[account.date >= orders.date.min(), "max_abs_tracking_error_close"].max() * 100.0) if not orders.empty else 0.0,
                "total_execution_cost_krw": float(orders[["fee_krw", "half_spread_cost_krw", "impact_cost_krw"]].sum().sum()) if not orders.empty else 0.0,
            })
    return pd.DataFrame(rows)


def _operational_gaps() -> pd.DataFrame:
    return pd.DataFrame([
        {"item": "BROKER_TICK_SIZE", "severity": "BLOCK_LIVE", "required_actual_data": "effective-dated tick-size table and order-price rounding behavior", "validation": "planned price is broker-valid for every order"},
        {"item": "PRICE_LIMIT_AND_SESSION", "severity": "BLOCK_LIVE", "required_actual_data": "daily price-limit state, auction/session windows, halt status", "validation": "no order outside valid session or tradable price range"},
        {"item": "FEE_TAX_EFFECTIVE_DATE", "severity": "BLOCK_LIVE", "required_actual_data": "account/product/date-specific fee and tax ledger", "validation": "broker cash movement reconciles within 1 KRW"},
        {"item": "PARTIAL_FILL_LIFECYCLE", "severity": "BLOCK_LIVE", "required_actual_data": "order status history and exchange fill timestamps", "validation": "remaining quantity and average price reconstruct exactly"},
        {"item": "REJECT_CANCEL_REPLACE", "severity": "BLOCK_LIVE", "required_actual_data": "reject code dictionary and cancel/replace semantics", "validation": "rejected or unknown orders force HOLD_ONLY; no blind retry"},
        {"item": "BUYING_POWER_SETTLEMENT", "severity": "BLOCK_LIVE", "required_actual_data": "available cash, settlement, reserved cash, unsettled proceeds", "validation": "no negative or broker-rejected buying power"},
        {"item": "IDEMPOTENCY", "severity": "BLOCK_LIVE", "required_actual_data": "client order id support or deterministic lookup key", "validation": "timeout-after-accept cannot create duplicate order"},
        {"item": "QUOTE_AND_ACCOUNT_FRESHNESS", "severity": "BLOCK_LIVE", "required_actual_data": "quote/account timestamps and timezone", "validation": "stale quote or account snapshot blocks order creation"},
        {"item": "REAL_SPREAD_IMPACT_CALIBRATION", "severity": "WARN_PAPER_ONLY", "required_actual_data": "bid/ask snapshots and realized fills", "validation": "model-vs-real slippage distribution by ticker and participation bucket"},
    ])


def _annual_returns(runs: dict[str, dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for policy_id, run in runs.items():
        for label in ("69", "79"):
            nav = run[f"account{label}"].set_index("date")["nav_krw"]
            annual = nav.resample("YE").last().pct_change()
            first_year = annual.index.min()
            if pd.notna(first_year):
                annual.loc[first_year] = nav.loc[:first_year].iloc[-1] / 10_000_000.0 - 1.0
            for date, value in annual.dropna().items():
                rows.append({"policy": policy_id, "strategy": f"V{label}", "year": int(date.year), "return_pct": float(value * 100.0)})
    return pd.DataFrame(rows)


def run(root: Path | str) -> dict[str, Any]:
    root = Path(root); cfg = _load_cfg(root)
    out = root / "reports" / REPORT; out.mkdir(parents=True, exist_ok=True)
    runs, capital_runs = _load_run_matrix(root)
    metrics = _metric_table(runs, int(cfg["promotion"]["purge_sessions"]))
    promotion = _promotion(root, metrics, runs)
    parity = _parent_parity(root, runs[ACTIVE_POLICY])
    capacity = _capacity(root, runs[ACTIVE_POLICY], capital_runs)
    gaps = _operational_gaps()
    annual = _annual_returns(runs)
    active_orders = pd.concat([runs[ACTIVE_POLICY]["orders69"], runs[ACTIVE_POLICY]["orders79"]], ignore_index=True)
    active_intents = pd.concat([runs[ACTIVE_POLICY]["intents69"], runs[ACTIVE_POLICY]["intents79"]], ignore_index=True)
    active_daily = pd.concat([runs[ACTIVE_POLICY]["account69"], runs[ACTIVE_POLICY]["account79"]], ignore_index=True)
    gates = {
        "parent_nav_parity_under_1krw": bool(parity.abs_error_krw.lt(1.0).all()),
        "parent_negative_cash_zero": bool(metrics[metrics.policy.eq(ACTIVE_POLICY)].negative_cash_days.eq(0).all()),
        "intent_final_qty_never_exceeds_requested": bool((active_intents.final_quantity <= active_intents.requested_quantity).all()),
        "participation_never_exceeds_policy": bool(active_orders.empty or active_orders.participation_of_d1_adv.le(v77._load_config(root).base_execution.max_participation_of_d1_adv + 1e-12).all()),
        "all_target_tracking_finite": bool(np.isfinite(active_daily.max_abs_tracking_error_close).all()),
        "broker_contract_unverified_blocks_live": yaml.safe_load((root / "config/v101_broker_execution_contract.yaml").read_text())["status"] == "UNVERIFIED_EXTERNAL",
        "candidate_auto_promotion_blocked": not bool(promotion.promoted.any()),
        "live_blocked": not bool(cfg["live_execution_allowed"]),
    }
    metrics.to_csv(out / "v101_strategy_metrics.csv", index=False)
    promotion.to_csv(out / "v101_candidate_promotion.csv", index=False)
    parity.to_csv(out / "v101_parent_parity.csv", index=False)
    capacity.to_csv(out / "v101_capacity_diagnostics.csv", index=False)
    gaps.to_csv(out / "v101_operational_gap_register.csv", index=False)
    annual.to_csv(out / "v101_annual_returns.csv", index=False)
    active_orders.to_csv(out / "v101_active_fill_audit.csv", index=False)
    active_intents.to_csv(out / "v101_active_order_intents.csv", index=False)
    pd.DataFrame([{"gate": k, "passed": v} for k, v in gates.items()]).to_csv(out / "v101_quality_gates.csv", index=False)
    registry = {
        "agent": "RiskExecutionAgent", "version": "V101", "active_policy": ACTIVE_POLICY,
        "parent_strategy_unchanged": True, "automatic_parent_mutation": False,
        "live_authority": False, "broker_contract_status": "UNVERIFIED_EXTERNAL",
        "candidates": promotion.to_dict(orient="records"),
    }
    (out / "v101_risk_execution_registry.json").write_text(json.dumps(registry, indent=2), encoding="utf-8")
    summary = {
        "status": "v101_risk_execution_agent_complete_live_blocked",
        "active_policy": ACTIVE_POLICY, "gates": gates,
        "metrics": metrics.to_dict(orient="records"),
        "promotion": promotion.to_dict(orient="records"),
        "parent_parity": parity.to_dict(orient="records"),
        "live_execution_allowed": False,
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    if not all(gates.values()):
        raise RuntimeError({k: v for k, v in gates.items() if not v})
    return summary
