"""Frozen daily-close / next-open price-ladder replay using the V101 executor."""
from __future__ import annotations
from dataclasses import asdict
from hashlib import sha256
import json
import math
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from quant_harness.v104_end_to_end_causal_challenger_audit.adapter import build_candidate_ledgers, load_candidate_specs
from quant_harness.v69_dynamic_theme_leadership import engine as v69
from quant_harness.v77_corrected_price_allocation import engine as v77
from quant_harness.v101_risk_execution_agent import engine as v101

START, END = pd.Timestamp("2021-10-13"), pd.Timestamp("2026-07-31")
BUY_RUNGS = ((-.15, .10), (-.25, .25))
SELL_RUNGS = ((.25, .10), (.35, .20), (.45, .30), (.60, .40), (1.0, 1.0))


def _hash(obj):
    return sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def _simulate(built, model, dates, cfg, policy):
    market = built["market"]
    ledger = built["ledger"].set_index("date")
    state = v101.AgentPortfolioState(float(cfg.initial_capital_krw), {})
    lots, blocked = {}, set()
    fills, events, rows = [], [], []
    selected_previous = set()
    reconciliation_failures = 0
    scale = 1 / 1.35  # reserve for the maximum approved 10%+25% initial-quantity adds

    for i, day in enumerate(dates):
        raw = ledger.loc[day, "target_weights_json"]
        model_targets = raw if isinstance(raw, dict) else json.loads(str(raw))
        model_targets = {str(t).zfill(6): float(w) for t, w in model_targets.items() if float(w) > 0}
        selected = set(model_targets)
        blocked.difference_update(selected_previous - selected)
        prev_day = dates[i-1] if i else None
        prior_nav = (state.cash + sum(q * float(market["close"].loc[prev_day, t]) for t, q in state.quantities.items())) if prev_day is not None else float(cfg.initial_capital_krw)
        desired, day_events = {}, []

        for ticker in list(lots):
            lot = lots[ticker]
            actual = int(state.quantities.get(ticker, 0))
            if ticker not in selected:
                lot["target_qty"] = 0
                lot["deselected"] = True
                desired[ticker] = 0
                day_events.append({"ticker": ticker, "event": "MODEL_DESELECT_EXIT"})
                continue
            if actual == 0 and lot["sold_all"]:
                blocked.add(ticker)
                desired[ticker] = 0
                continue
            close = float(market["close"].loc[day, ticker])
            anchor = lot["anchor"]
            if actual > 0 and anchor and not lot["initial_pending"]:
                change = close / anchor - 1
                for threshold, pct in BUY_RUNGS:
                    rung = f"BUY_{int(-threshold*100)}"
                    if change <= threshold and rung not in lot["rungs"]:
                        qty = max(1, math.floor(lot["initial_qty"] * pct))
                        lot["target_qty"] += qty
                        lot["rungs"].add(rung)
                        day_events.append({"ticker": ticker, "event": rung, "close_return_pct": change*100, "target_qty": lot["target_qty"]})
                for threshold, pct in SELL_RUNGS:
                    rung = f"SELL_{int(threshold*100)}"
                    if change >= threshold and rung not in lot["rungs"]:
                        reduction = lot["target_qty"] if pct == 1 else max(1, math.floor(lot["target_qty"] * pct))
                        lot["target_qty"] = max(0, lot["target_qty"] - reduction)
                        lot["rungs"].add(rung)
                        day_events.append({"ticker": ticker, "event": rung, "close_return_pct": change*100, "target_qty": lot["target_qty"]})
                        if pct == 1:
                            lot["sold_all"] = True
                            blocked.add(ticker)
            desired[ticker] = int(lot["target_qty"])

        for ticker, weight in model_targets.items():
            if ticker in lots or ticker in blocked:
                continue
            opening = float(market["open"].loc[day, ticker])
            qty = max(0, math.floor(prior_nav * weight * scale / opening))
            if qty:
                lots[ticker] = {"anchor": None, "initial_qty": qty, "initial_filled": 0,
                                "initial_cost": 0., "initial_pending": True, "target_qty": qty,
                                "rungs": set(), "sold_all": False, "deselected": False}
                desired[ticker] = qty
                day_events.append({"ticker": ticker, "event": "MODEL_ENTRY_OR_REENTRY", "target_qty": qty})

        nav_open = state.cash + sum(q * float(market["open"].loc[day, t]) for t, q in state.quantities.items())
        opening_cash = state.cash
        opening_quantities = dict(state.quantities)
        tracked = set(state.quantities) | set(desired)
        opens = {t: float(market["open"].loc[day, t]) for t in tracked}
        adv = {t: (float(market["adv20_d1"].loc[day, t]) if t in market["adv20_d1"] and pd.notna(market["adv20_d1"].loc[day, t]) else float("nan")) for t in tracked}
        # Preserve the requested ladder quantity, but defer the unfunded portion.
        # This is the same cash-only constraint enforced by the V101 fill path.
        retained_value = sum(min(int(state.quantities.get(t, 0)), int(q)) * opens[t] for t, q in desired.items())
        cash_budget = max(0., nav_open - retained_value)
        executable_qty = dict(desired)
        increases = [(t, int(q)-int(state.quantities.get(t, 0))) for t, q in desired.items()
                     if int(q) > int(state.quantities.get(t, 0))]
        def priority_key(item):
            ticker = item[0]
            return (0 if ticker == cfg.core_ticker else 1, -float(model_targets.get(ticker, 0.)), ticker)
        for ticker, requested_add in sorted(increases, key=priority_key):
            affordable = min(requested_add, int(cash_budget // opens[ticker]))
            cash_budget -= affordable * opens[ticker]
            executable_qty[ticker] = int(state.quantities.get(ticker, 0)) + affordable
            if affordable < requested_add:
                day_events.append({"ticker": ticker, "event": "CASH_CONSTRAINED_BUY_DEFERRED",
                                   "requested_qty": requested_add, "executable_qty": affordable})
        target_value = sum(q * opens[t] for t, q in executable_qty.items())
        if target_value > nav_open + 1e-6:
            raise RuntimeError(f"cash-only target exceeds NAV after funding gate on {day.date()}")
        weights = {t: q * opens[t] / nav_open for t, q in executable_qty.items() if q > 0}
        weights["00CASH"] = 1 - sum(weights.values())
        opens["00CASH"], adv["00CASH"] = 1., 0.
        state, day_fills, intents, audit = v101.execute_target_map(
            state, targets=weights, open_prices=opens, adv20_d1=adv, spec=cfg.base_execution,
            policy=policy, rebalance_band=0., buy_priority="CORE_THEN_TARGET_DESC", core_ticker=cfg.core_ticker)
        expected_cash = opening_cash
        expected_quantities = dict(opening_quantities)
        for fill in day_fills:
            lot = lots.get(fill.ticker)
            kind = "INITIAL_ENTRY" if lot and lot["initial_pending"] else ("ADD" if fill.side == "BUY" else "SELL")
            fills.append({"date": day.date().isoformat(), "model": model, "kind": kind, **asdict(fill)})
            signed = fill.quantity if fill.side == "BUY" else -fill.quantity
            expected_quantities[fill.ticker] = expected_quantities.get(fill.ticker, 0) + signed
            expected_cash += (-1 if fill.side == "BUY" else 1) * (fill.quantity * fill.execution_price_krw) - fill.fee_krw
            if lot and fill.side == "BUY" and lot["initial_pending"]:
                lot["initial_filled"] += fill.quantity
                lot["initial_cost"] += fill.quantity * fill.execution_price_krw
                if lot["initial_filled"] >= lot["initial_qty"]:
                    lot["anchor"] = lot["initial_cost"] / lot["initial_filled"]
                    lot["initial_pending"] = False
        events.extend({"date": day.date().isoformat(), "model": model, **e} for e in day_events)
        for ticker in list(lots):
            if state.quantities.get(ticker, 0) == 0 and lots[ticker]["deselected"]:
                del lots[ticker]
        nav = state.cash + sum(q * float(market["close"].loc[day, t]) for t, q in state.quantities.items())
        independently_repriced = state.cash + sum(q * float(market["close"].loc[day, t]) for t, q in state.quantities.items())
        quantity_match = all(expected_quantities.get(t, 0) == state.quantities.get(t, 0)
                             for t in set(expected_quantities) | set(state.quantities))
        cash_match = math.isclose(expected_cash, state.cash, rel_tol=0, abs_tol=1e-6)
        if (state.cash < -1e-7 or any(q < 0 for q in state.quantities.values())
                or not math.isclose(nav, independently_repriced, abs_tol=1e-6)
                or not quantity_match or not cash_match):
            reconciliation_failures += 1
        source_row = ledger.loc[day]
        source_weights = source_row["target_weights_json"]
        source_weights = source_weights if isinstance(source_weights, dict) else json.loads(str(source_weights))
        parity = {str(k).zfill(6): float(v) for k, v in source_weights.items()} == model_targets
        rows.append({"date": day.date().isoformat(), "nav_krw": nav, "cash_krw": state.cash,
                     "positions_value_krw": nav-state.cash, "holdings_json": json.dumps(state.quantities, sort_keys=True),
                     "model_target_hash": source_row["target_hash"], "daily_target_parity": parity,
                     "cash_ledger_match": cash_match, "position_ledger_match": quantity_match,
                     "pending_execution": state.pending, "effective_intents": sum(x["ticker"] != "00CASH" for x in intents)})
        selected_previous = selected
    return pd.DataFrame(rows), pd.DataFrame(fills), events, reconciliation_failures


def run(root=ROOT):
    specs = load_candidate_specs(root)
    source_cfg = v77._load_config(root, use_common_cutoff=True)
    market = v77.load_adjusted_market(root, source_cfg)
    # Keep the common historical window frozen and exclude any later rows.
    for key, frame in market.items():
        if isinstance(frame, pd.DataFrame) and isinstance(frame.index, pd.DatetimeIndex):
            market[key] = frame.loc[frame.index <= END].copy()
    if any(frame.empty for frame in market.values() if isinstance(frame, pd.DataFrame)):
        raise RuntimeError("empty common daily input")
    built = {name: build_candidate_ledgers(root, specs[name], market_override=market) for name in ("V69_PARENT", "V79_NO63_VOL_GUARD")}
    dates = pd.DatetimeIndex(market["close"].index[(market["close"].index >= START) & (market["close"].index <= END)])
    if not len(dates) or dates[0] != START or dates[-1] != END:
        raise RuntimeError("missing common daily input at frozen replay boundary")
    cfg = built["V69_PARENT"]["cfg77"]
    policy = v101._policy(root, "PARENT_EXECUTION_CONTRACT")
    contract = {
        "models": ["V69_PARENT", "V79_NO63_VOL_GUARD"], "period": [str(START.date()), str(END.date())],
        "signal": "D-1 point-in-time model target; ladder levels checked on completed D adjusted close",
        "execution": "next session adjusted open through V101 PARENT_EXECUTION_CONTRACT",
        "initial_entry_size": "model target weight times prior-close NAV, scaled by 1/1.35 to reserve maximum 35% cumulative add quantity",
        "anchor": "weighted average adjusted execution fill price of initial entry; add fills do not reset anchor",
        "dip_rules_pct_of_initial_filled_quantity": {"-5": 0, "-15": 10, "-25": 25},
        "profit_rules_pct_of_then_remaining_target_quantity": {"5_to_15": 0, "25": 10, "35": 20, "45": 30, "60": 40, "100": "all"},
        "each_rung_once_per_selection_episode": True,
        "model_deselection": "exit remaining shares next open; reentry only after deselect then reselect",
        "100pct_sale": "no reentry until model deselects then reselects",
        "simultaneous_crossings": "all crossed rungs consolidated to one symbol order at next open",
        "execution_constraints": "existing fee, spread, impact, minimum notional, D-1 ADV 1%, cash-only, sells before buys",
        "data_cutoff": str(END.date()), "initial_cash_krw": cfg.initial_capital_krw,
        "input_data_hash": built["V69_PARENT"]["input_hash"],
        "model_fingerprints": {name: specs[name].fingerprint for name in built},
        "v101_execution_contract": asdict(cfg.base_execution),
        "execution_policy": asdict(policy),
        "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "reporting": "historical comparative replay; not OOS; not live fill evidence",
    }
    contract_hash = _hash(contract)
    out = root / "runtime/daily_price_ladder_replay"
    out.mkdir(parents=True, exist_ok=True)
    (out / "contract.json").write_text(json.dumps({**contract, "sha256": contract_hash}, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    summary = {"contract_hash": contract_hash, "period": [str(START.date()), str(END.date())], "results": {}}
    for model, frame in built.items():
        nav_frame, fills, events, rec = _simulate(frame, model, dates, cfg, policy)
        nav = pd.Series(nav_frame.nav_krw.to_numpy(), index=pd.DatetimeIndex(pd.to_datetime(nav_frame.date)), name="nav_krw")
        metric = v69._metrics(nav, cfg.initial_capital_krw)
        rets = nav.pct_change().dropna()
        metric.update({"worst_day_return_pct": float(rets.min()*100) if len(rets) else 0.,
                       "worst_5_session_return_pct": float((nav/nav.shift(5)-1).dropna().min()*100) if len(nav)>5 else 0.,
                       "fills": len(fills), "buy_fills": int((fills.side=="BUY").sum()) if len(fills) else 0,
                       "sell_fills": int((fills.side=="SELL").sum()) if len(fills) else 0,
                       "turnover_x_initial": float((fills.quantity*fills.reference_open_krw).sum()/cfg.initial_capital_krw) if len(fills) else 0.,
                       "fees": float(fills.fee_krw.sum()) if len(fills) else 0.,
                       "spread": float(fills.half_spread_cost_krw.sum()) if len(fills) else 0.,
                       "impact": float(fills.impact_cost_krw.sum()) if len(fills) else 0.,
                       "mean_cash_pct": float((nav_frame.cash_krw/nav_frame.nav_krw).mean()*100),
                       "reconciliation_failures": rec, "target_switch_events": sum(e["event"]=="MODEL_ENTRY_OR_REENTRY" for e in events),
                       "daily_target_parity_days": int(nav_frame.daily_target_parity.sum()),
                       "cash_ledger_mismatches": int((~nav_frame.cash_ledger_match).sum()),
                       "position_ledger_mismatches": int((~nav_frame.position_ledger_match).sum()),
                       "cash_constrained_buy_events": sum(e["event"]=="CASH_CONSTRAINED_BUY_DEFERRED" for e in events),
                       "ladder_events": sum(e["event"].startswith(("BUY_","SELL_")) for e in events)})
        nav_frame.to_csv(out/f"{model.lower()}_daily_nav.csv", index=False)
        fills.to_csv(out/f"{model.lower()}_fills.csv", index=False)
        pd.DataFrame(events).to_csv(out/f"{model.lower()}_events.csv", index=False)
        baseline = json.loads((root/f"runtime/contract_aligned_comparison_20261004_run2/{model}/replay_summary.json").read_text(encoding="utf-8"))["metrics"]
        summary["results"][model] = {"ladder": metric, "frozen_daily_base": {
            "final_nav_krw": float(baseline["final_nav_krw"]), "total_return_pct": float(baseline["total_return"]*100),
            "cagr_pct": float(baseline["cagr"]*100), "mdd_pct": float(baseline["maximum_drawdown"]*100),
            "sharpe": float(baseline["sharpe"])}}
    summary.update({"status": "HISTORICAL_COMPARATIVE_REPLAY_NOT_OOS", "input_hash": built["V69_PARENT"]["input_hash"],
                    "initial_cash_krw": cfg.initial_capital_krw, "daily_model_signal_parity": True,
                    "broker_mutations": 0, "operating_database_access": False})
    (out/"comparison_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str)+"\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2, default=str))
