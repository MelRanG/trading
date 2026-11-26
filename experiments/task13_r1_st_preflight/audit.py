"""Read sealed ledgers and diagnose rank turnover without replaying strategies."""
import hashlib
import io
import json
import tarfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "runtime"
R2 = RUNTIME / "task13_f1_r2"
R5 = RUNTIME / "task13_f1_r5"
R4 = RUNTIME / "research_reference/task13_f1_r4"


def read(path):
    return json.loads(path.read_bytes())


def checked(path, expected):
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError(f"source hash mismatch: {path}")
    return data


def books(fills, nav, capital, positions_column):
    prior = nav.nav.shift(fill_value=capital)
    fills = fills.join(nav[["risk_on"]], on="date")
    fills["fee_and_slippage"] = fills.fee + (fills.fill_price - fills.reference_open).abs() * fills.quantity
    fills["type"] = "other_rebalance_or_trim"
    fills.loc[~fills.risk_on, "type"] = "risk_off"
    first = nav.index[0]
    if fills.date.eq(first).any() and nav.get("start_positions", pd.Series(["{}"], index=[first])).iloc[0] == "{}":
        fills.loc[fills.date.eq(first) & fills.side.eq("BUY"), "type"] = "initial_deployment"
    previous = nav[positions_column].shift(fill_value="{}").map(json.loads)
    current = nav[positions_column].map(json.loads)
    outgoing = dict(zip(nav.index, [set(x) - set(y) for x, y in zip(previous, current)]))
    incoming = dict(zip(nav.index, [set(y) - set(x) for x, y in zip(previous, current)]))
    cross = {d for d in nav.index if outgoing[d] and incoming[d] and nav.loc[d, "risk_on"]}
    for i, order in fills.iterrows():
        d, s = order.date, order.symbol
        if d in cross and ((order.side == "SELL" and s in outgoing[d]) or
                           (order.side == "BUY" and s in incoming[d])):
            fills.loc[i, "type"] = "same_day_full_replacement"
    return {
        "sessions": len(nav), "fills": len(fills), "trade_dates": fills.date.nunique(),
        "cost_krw": float(fills.fee_and_slippage.sum()),
        "cost_pct_initial": float(100*fills.fee_and_slippage.sum()/capital),
        "cost_pct_mean_nav": float(100*fills.fee_and_slippage.sum()/nav.nav.mean()),
        "two_way_turnover_prev_nav": float((fills.open_notional / fills.date.map(prior)).sum()),
        "by_side": fills.groupby("side").open_notional.agg(["size", "sum"]).to_dict("index"),
        "by_type": fills.groupby("type").fee_and_slippage.agg(["size", "sum"]).to_dict("index"),
        "same_day_replacement_dates": len(cross),
        "same_day_replacement_slots": sum(min(len(outgoing[d]), len(incoming[d])) for d in cross),
        "by_exchange": fills.assign(board=fills.symbol.str[-2:].map({"KS":"KOSPI","KQ":"KOSDAQ"})).groupby("board").agg(
            trade_dates=("date","nunique"), fills=("symbol","size"), notional=("open_notional","sum"),
            cost=("fee_and_slippage","sum")).to_dict("index"),
    }, previous, current


def main():
    refs = read(RUNTIME / "research_reference/index.json")
    inventory = json.loads(checked(Path(refs["archive_inventory"]), refs["archive_inventory_sha256"]))
    manifest = read(R4 / "artifact_manifest.json")
    needed = ["runtime/task13_f1_r4/T1_A_fills.csv", "runtime/task13_f1_r4/price_gate.json",
              "runtime/task13_f1_r3/decision_dates.csv"]
    extracted = {}
    with tarfile.open(refs["archive"], "r|gz") as archive:
        for member in archive:
            if member.name in needed:
                data = archive.extractfile(member).read()
                entry = inventory[member.name]
                expected = entry["sha256"] if isinstance(entry, dict) else entry
                assert hashlib.sha256(data).hexdigest() == expected
                extracted[member.name] = data
            if len(extracted) == len(needed):
                break
    assert set(extracted) == set(needed)
    f4 = pd.read_csv(io.BytesIO(extracted[needed[0]]), parse_dates=["date"])
    p4 = json.loads(extracted[needed[1]])
    dec = set(pd.read_csv(io.BytesIO(extracted[needed[2]]), parse_dates=["date"]).date)
    v4 = pd.read_csv(io.BytesIO(checked(R4/"T1_A_nav.csv", manifest["runtime/task13_f1_r4/T1_A_nav.csv"])),
                     parse_dates=["date"]).set_index("date")
    m5 = read(R5/"artifact_manifest.json")

    def r5csv(name, **kwargs):
        return pd.read_csv(io.BytesIO(checked(R5/name, m5[f"runtime/task13_f1_r5/{name}"])), parse_dates=["date"], **kwargs)

    f5 = r5csv("fills.csv")
    v5 = r5csv("nav.csv").set_index("date")
    stat4, before, after = books(f4, v4, 10_000_000, "positions_json")
    stat5, _, _ = books(f5, v5, float(v5.start_cash.iloc[0]), "positions")
    stat4["decision_days"] = len(dec)
    stat5["decision_days"] = int(v5.decision.sum())
    x = pd.read_pickle(io.BytesIO(checked(R2/"inputs.pkl", read(R2/"artifact_manifest.json")["runtime/task13_f1_r2/inputs.pkl"])))
    target = pd.read_csv(R2/"T1_A_targets.csv", parse_dates=["date"]).set_index("date").target_weights_json.map(json.loads)
    ranks, signals, candidates = {}, [], []
    for d in sorted(dec):
        mom = x["prior"]["MOM63"].loc[d]
        mom = mom[mom.gt(0) & x["flow"][1].loc[d].notna()].sort_values(ascending=False,kind="stable")
        ranks[d] = mom
        if not v4.loc[d,"risk_on"]:
            assert target[d] == {}
            continue
        assert list(mom.index[:4]) == list(target[d])
        old = set(before[d])
        if len(mom) > 4 and mom.index[4] in old and mom.index[3] not in old:
            candidates.append((d, mom.index[4], mom.index[3]))
        exits, entries = (old-set(after[d])), (set(after[d])-old)
        for out, incoming in zip(sorted(exits,key=lambda s:mom.get(s,-99),reverse=True),
                                 sorted(entries,key=lambda s:mom.get(s,-99))):
            if out in mom and incoming in mom:
                signals.append(float(100*(mom[incoming]-mom[out])))
    flagged = []
    for s, days in p4["corporate_actions"].items():
        for d, action in days.items():
            d = pd.Timestamp(d)
            if action["ratio"] is None:
                flagged.append((d,s))
    print(json.dumps({"R4":stat4,"R5":stat5,"R4_rank_check":{
        "risk_on_matches":sum(bool(v4.loc[d,"risk_on"]) for d in dec),
        "k_plus_1_hold_opportunities":len(candidates),
        "k_plus_1_by_year":pd.Series([d.year for d,_,_ in candidates]).value_counts().sort_index().to_dict(),
        "k_plus_1_signal_gap_pp_median":float(pd.Series([100*(ranks[d][b]-ranks[d][a]) for d,a,b in candidates]).median()),
        "measurable_signal_gap_pairs":len(signals),"measured_signal_gap_pp_median":float(pd.Series(signals).median()),
        "unresolved_noncash_events":len(flagged),
        "unresolved_events_reachable_in_recent_top5": [
            [str(d.date()),s] for d,s in flagged if any(s in ranks[t].index[:5] and v4.loc[t,"risk_on"] for t in
            [max(date for date in dec if date<=d)] if t<d)],
    }},indent=2,default=lambda value:value.item(),allow_nan=False))


if __name__ == "__main__":
    main()
