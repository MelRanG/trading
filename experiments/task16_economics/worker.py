"""One predeclared nominal next-open experiment, using the R4 execution worker."""
from collections import Counter
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

from experiments.task13_f1_r4.execution import Account, trade_open, usable
from experiments.task13_f1_r5.run import spec
from quant_harness.alpha_research_factory import _hash, _read_jsonl
from quant_harness.investment.research_feedback import decide

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "runtime/task16_economics"
LEDGER = ROOT / "runtime/alpha_research_factory/task4"
APPROVAL = "USER_OFFLINE_ECONOMICS_20261126"
DATA = ROOT / "runtime/task13_f1_r5"
CAPITAL = 10_000_000
HOLD_DAYS = 5
TERMINAL = 20
ARMS = ("candidate", "incumbent", "hold")


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    with path.open("x") as output:
        json.dump(value, output, indent=2, ensure_ascii=False, allow_nan=False)
        output.write("\n")


def load_inputs():
    locked = {
        "sealed_inputs.pkl": "75f6dc2dbb1a515b195807ac139cade280dc85fd72ae659a05b9352fd7def223",
        "sealed_targets.csv": "cb50675b107b1037d542bb8cc315906aacf3b3a597abdccf5bd9bad3dd9239c4",
    }
    for name, expected in locked.items():
        if sha(DATA / name) != expected:
            raise ValueError("R5 approved source changed")
    bundle = pd.read_pickle(DATA / "sealed_inputs.pkl")
    targets = bundle["targets"]
    audit = pd.read_csv(DATA / "sealed_targets.csv", index_col="date", parse_dates=True)
    if (not targets.index.equals(audit.index) or not targets.index.is_unique or
            not targets.index.is_monotonic_increasing or
            not targets[["decision", "risk_on", "candidates"]].equals(audit[["decision", "risk_on", "candidates"]]) or
            targets.targets.tolist() != audit.weights.map(json.loads).tolist()):
        raise ValueError("frozen target calendar mismatch")
    entries = [i for i, row in enumerate(targets.itertuples())
               if i + TERMINAL < len(targets) and row.decision and row.risk_on and row.targets]
    if not entries:
        raise ValueError("no predeclared eligible entry dates")
    files = [Path(__file__).with_name("contract.json"),
             ROOT / "config/task3_equity_contract.json",
             ROOT / "experiments/task13_f1_r4/execution.py",
             ROOT / "experiments/task13_f1_r5/run.py",
             ROOT / "src/quant_harness/v77_corrected_price_allocation/engine.py",
             DATA / "preflight.json"]
    snapshot = {
        "files": {str(path.relative_to(ROOT)): sha(path) for path in files},
        "r5_artifacts": locked, "calendar_sessions": len(targets),
        "scheduled_entries": [targets.index[i].date().isoformat() for i in entries],
    }
    return snapshot, bundle, entries


def quotes(bars, actions, names, date, prior_closes, adv):
    previous, opening, ends, volumes = {}, {}, {}, {}
    for symbol in names:
        bar = bars[symbol].loc[date]
        previous[symbol] = prior_closes[symbol].at[date]
        ends[symbol] = bar.close
        volumes[symbol] = adv[symbol].at[date]
        eligible = (symbol not in actions or date not in actions[symbol])
        can_open = (eligible and bar.volume > 0 and usable(bar.open) and usable(previous[symbol])
                    and abs(bar.open / previous[symbol] - 1) < .29)
        opening[symbol] = bar.open if can_open else None
    return previous, opening, ends, volumes


def incumbents_pending(account, targets, previous):
    """R4 scheduled trim on the original basket with the buy side disabled."""
    if not all(usable(previous.get(s)) for s in account.positions):
        account.pending_sells = {s: 0 for s in account.positions if s not in targets}
        return
    nav = account.cash + sum(q * previous[s] for s, q in account.positions.items())
    desired = {s: int(nav * targets.get(s, 0) / previous[s]) for s in account.positions}
    account.pending_sells = {s: q for s, q in desired.items() if q < account.positions[s]}


def advance(account, arm, age, row, previous, opening, adv, costs):
    if age == TERMINAL or (arm != "hold" and not row.risk_on) or (arm == "candidate" and age >= HOLD_DAYS):
        account.pending_sells = dict.fromkeys(account.positions, 0)
    elif arm == "incumbent" and row.decision:
        incumbents_pending(account, row.targets, previous)
    fills, _, _ = trade_open(account, {}, previous, opening, adv, costs, rebalance=False, risk_on=True)
    return fills


def portfolio_mark(account, ends):
    if any(not usable(ends.get(s)) for s in account.positions):
        raise ValueError("held nominal close missing")
    stock = sum(q * ends[s] for s, q in account.positions.items())
    if account.cash < -1e-6 or account.cash + stock <= 0:
        raise ValueError("invalid episode NAV")
    return account.cash + stock, stock / (account.cash + stock)


def compound_path(account, arm, rows, entry_fills, date_index, names, bars, actions, previous, adv, costs):
    money_cost = turnover = 0.
    equity, nav, filled, spent = [], [], [], []
    for age, (date, row) in enumerate(rows.iterrows()):
        p, op, end, liquidity = quotes(bars, actions, names, date, previous, adv)
        if any(date in actions.get(s, {}) for s in account.positions):
            raise ValueError(f"unsettled held action {date.date()} {arm}")
        before = deepcopy(account)
        fills = advance(account, arm, age, row, p, op, liquidity, costs) if age else entry_fills
        if age:
            for fill in fills:
                s, q = fill["symbol"], fill["quantity"]
                before.cash += q * fill["fill_price"] - fill["fee"]
                before.positions[s] -= q
                if not before.positions[s]:
                    del before.positions[s]
            if before.positions != account.positions or abs(before.cash - account.cash) > 1e-6:
                raise ValueError("independent sell-ledger reconciliation failed")
        for fill in fills:
            slip = abs(fill["fill_price"] - fill["reference_open"]) * fill["quantity"]
            money_cost += slip + fill["fee"]
            turnover += fill["open_notional"]
            filled.append({"date": date.date().isoformat(), **fill})
        value, exposure = portfolio_mark(account, end)
        nav.append(value)
        equity.append(exposure)
        spent.append({"date": date.date().isoformat(), "nav": value, "cash": account.cash,
                      "exposure": exposure, "positions": dict(account.positions), "pending": dict(account.pending_sells)})
    etf = bars["069500.KS"]
    etf_move = etf.loc[date_index, "close"].pct_change(fill_method=None).iloc[1:]
    if not np.isfinite(etf_move).all():
        raise ValueError("missing same-calendar KODEX200 marks")
    ref = float(np.prod(1 + np.asarray(equity[:-1]) * etf_move.to_numpy()) - 1)
    path = np.asarray([CAPITAL, *nav]) / CAPITAL
    downside = np.minimum(np.diff(path) / path[:-1], 0)
    return {"net_return": path[-1] - 1, "mdd": float(np.min(path / np.maximum.accumulate(path) - 1)),
            "mean_exposure": float(np.mean(equity)), "invested_days": int(np.count_nonzero(equity)),
            "downside_rms": float(np.sqrt(np.mean(downside**2))), "cost_krw": money_cost,
            "turnover_notional_krw": turnover, "matched_etf_after_entry_close": ref,
            "portfolio_after_entry_close": nav[-1] / nav[0] - 1,
            "remaining_shares_by_name": dict(account.positions), "fills": filled, "marks": spent}


def doubled(costs):
    return replace(costs, buy_fee_bps=2*costs.buy_fee_bps, sell_fee_bps=2*costs.sell_fee_bps,
                   half_spread_bps=2*costs.half_spread_bps, impact_bps_at_1pct_adv=2*costs.impact_bps_at_1pct_adv,
                   max_impact_bps=2*costs.max_impact_bps)


def compare(bundle, entries):
    targets, bars, actions = (bundle[k] for k in ("targets", "nominal", "actions"))
    adv = {s: (bars[s].close * bars[s].volume).rolling(20, min_periods=20).mean().shift() for s in bundle["assets"]}
    previous = {s: bars[s].close.shift() for s in adv}
    costs = spec()
    results = []
    for scenario, terms in (("base", costs), ("double_cost", doubled(costs))):
        for number in entries:
            rows = targets.iloc[number:number + TERMINAL + 1]
            date = rows.index[0]
            names = tuple(rows.targets.iloc[0])
            day = date.date().isoformat()
            p, op, end, liquidity = quotes(bars, actions, names, date, previous, adv)
            start = Account(CAPITAL)
            fills, events, _ = trade_open(start, rows.targets.iloc[0], p, op, liquidity, terms,
                                         rebalance=True, risk_on=True)
            if any(fill["side"] != "BUY" for fill in fills):
                raise ValueError("invalid common entry")
            start_cash = CAPITAL - sum(t["quantity"] * t["fill_price"] + t["fee"] for t in fills)
            if (abs(start.cash - start_cash) > 1e-6 or
                    start.positions != {t["symbol"]: t["quantity"] for t in fills}):
                raise ValueError("independent entry-ledger reconciliation failed")
            item = {"scenario": scenario, "date": day, "block": number // 21, "entry": dict(start.positions),
                    "events": events, "arms": {}}
            if fills:
                for arm in ARMS:
                    item["arms"][arm] = compound_path(deepcopy(start), arm, rows, fills, rows.index, names, bars,
                                                      actions, previous, adv, terms)
            results.append(item)
    return results


def summarize(results):
    report = {}
    rng = np.random.default_rng(16101)
    metrics = ("net_return", "mdd", "downside_rms", "mean_exposure", "invested_days", "cost_krw",
               "turnover_notional_krw", "matched_etf_after_entry_close", "portfolio_after_entry_close")
    for scenario in ("base", "double_cost"):
        all_rows = [r for r in results if r["scenario"] == scenario]
        rows = [r for r in all_rows if r["arms"]]
        if not rows:
            raise ValueError("no common filled entries")
        blocks = len({r["block"] for r in rows})
        summary = {arm: {key: float(np.mean([r["arms"][arm][key] for r in rows])) for key in metrics}
                   for arm in ARMS}
        for arm, means in summary.items():
            means["episodes_with_residual"] = sum(bool(r["arms"][arm]["remaining_shares_by_name"]) for r in rows)
        pairs = {}
        for arm in ("incumbent", "hold"):
            group = pd.DataFrame({"block": [r["block"] for r in rows], "month": [r["date"][:7] for r in rows],
                                  "delta": [r["arms"]["candidate"]["net_return"] - r["arms"][arm]["net_return"] for r in rows]})
            chunks = group.groupby("block").delta.agg(["sum", "size"]).to_numpy()
            samples = chunks[rng.integers(blocks, size=(5000, blocks))].sum(axis=1)
            lo, hi = np.quantile(samples[:, 0] / samples[:, 1], [.0125, .9875])
            pairs[arm] = {"value": float(group.delta.mean()), "lo": float(lo), "hi": float(hi),
                          "mean_positive_delta_over_all_entries": float(group.delta.clip(lower=0).mean()),
                          "mean_negative_delta_over_all_entries": float(group.delta.clip(upper=0).mean()),
                          "by_entry_month": group.groupby("month").delta.mean().to_dict()}
        report[scenario] = {"scheduled": len(all_rows), "filled": len(rows), "occupied_blocks": blocks, "means": summary,
                            "pairs": pairs, "issuer_episode_counts": dict(Counter(s for r in rows for s in r["entry"]))}
    base = report["base"]
    downside_ok = all(base["means"]["candidate"]["mdd"] >= base["means"][arm]["mdd"]
                      and base["means"]["candidate"]["downside_rms"] <= base["means"][arm]["downside_rms"]
                      for arm in ("incumbent", "hold"))
    promising = (base["occupied_blocks"] >= 12 and downside_ok and
                 all(base["pairs"][arm]["lo"] > 0 and report["double_cost"]["pairs"][arm]["value"] >= 0
                     for arm in ("incumbent", "hold")))
    return {"status": "EXPLORATORY_ECONOMICS_COMPLETED", "cases": base["filled"],
            "economic_judgment": "PROMISING_CONDITIONAL" if promising else "NO_CONFIRMED_INCREMENT",
            "sensitivity": report, "alpha": "ALPHA_NOT_VALIDATED"}


def guard():
    if Path.cwd() != OUT or (OUT / "worker_result.json").exists():
        raise ValueError("unexpected worker working directory or prior result")
    marker = read(OUT / "worker.started.json")
    attempt = next(r for r in _read_jsonl(LEDGER / "attempt_registry.jsonl") if r["attempt_id"] == marker["attempt_id"])
    contract = read(LEDGER / "contracts" / (attempt["proposal_id"] + ".json"))
    cfg = read(ROOT / "config/task4_review_contract.json")["exploratory_economics"][APPROVAL]
    if (marker["contract_hash"] != contract["contract_hash"] or contract["proposal"] != cfg["proposal"]
            or _hash({k: v for k, v in contract.items() if k != "contract_hash"}) != contract["contract_hash"]
            or contract["proposal"]["worker_hash"] != sha(Path(__file__))
            or not any(r["attempt_id"] == marker["attempt_id"] and r["contract_hash"] == marker["contract_hash"]
                       for r in _read_jsonl(LEDGER / "experiment_reservations.jsonl"))):
        raise ValueError("no matching official reservation")
    with (OUT / "evaluator.entered").open("x"):
        pass
    return contract


def main(mode):
    if mode == "preflight":
        snapshot, _, _ = load_inputs()
        write(OUT / "snapshot.json", snapshot)
        return
    if mode != "evaluate":
        raise ValueError("worker mode")
    contract = guard()
    snapshot, bundle, entries = load_inputs()
    if snapshot != read(OUT / "snapshot.json") or _hash(snapshot) != contract["proposal"]["input_hash"]:
        raise ValueError("economic spec or approved input drift")
    results = compare(bundle, entries)
    write(OUT / "episode_ledger.json", results)
    result = summarize(results)
    result["episode_ledger_sha256"] = sha(OUT / "episode_ledger.json")
    write(OUT / "worker_result.json", result)


if __name__ == "__main__":
    main(sys.argv[1])
