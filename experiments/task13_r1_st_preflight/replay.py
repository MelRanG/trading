"""Single sealed R4 comparison using the original replay and execution engines."""
import hashlib
import io
import json
import sys
import tarfile
import tempfile
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from experiments.task13_f1_r4 import replay as original
from experiments.task13_r1_st_preflight.audit import ROOT, RUNTIME, R2, checked, read

OUT = RUNTIME / "task13_r1_st_preflight"
TAX_BPS = ((pd.Timestamp("2024-12-27"), 15), (pd.Timestamp("2023-12-27"), 18), (pd.Timestamp("2023-01-01"), 20))
ARMS = ("D", "R1", "LOW_TURNOVER")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stage(root):
    """Read required, hash-checked files into a temporary replay tree."""
    reference = read(RUNTIME / "research_reference/index.json")
    inventory = json.loads(checked(Path(reference["archive_inventory"]), reference["archive_inventory_sha256"]))
    gate_path = "runtime/task13_f1_r4/price_gate.json"
    gate_entry = inventory[gate_path]
    # Gate can be read from a single small member without restoring the archive.
    with tarfile.open(reference["archive"], "r|gz") as archive:
        gate_data = next(archive.extractfile(member).read() for member in archive if member.name == gate_path)
    assert hashlib.sha256(gate_data).hexdigest() == gate_entry["sha256"]
    gate = json.loads(gate_data)
    needed = dict(gate["hashes"])
    for item in ["runtime/task13_f1_r2/artifact_manifest.json",
                 "runtime/task13_f1_r3/decision_dates.csv"]:
        if item not in needed:
            if item in inventory:
                needed[item] = inventory[item]["sha256"]
            else:
                needed[item] = sha(ROOT/item)
    needed["runtime/task13_r0/native_manifest/assets.json"] = inventory["runtime/task13_r0/native_manifest/assets.json"]["sha256"]

    missing = {}
    for name, expected in needed.items():
        options = [ROOT/name]
        if name.startswith("runtime/"):
            options += [RUNTIME/"research_reference"/name.removeprefix("runtime/")]
        options += [RUNTIME/"research_reference/frozen_code"/name]
        for item in options:
            if item.is_file() and sha(item) == expected:
                dest = root/name
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.symlink_to(item)
                break
        else:
            missing[name] = expected
    with tarfile.open(reference["archive"], "r|gz") as archive:
        for member in archive:
            if member.name in missing:
                value = archive.extractfile(member).read()
                assert hashlib.sha256(value).hexdigest() == missing.pop(member.name)
                dest = root/member.name
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(value)
            if not missing:
                break
    if missing:
        raise ValueError(f"missing sealed inputs: {sorted(missing)}")
    return gate


def gross_cost(fills):
    return fills.fee + fills.quantity * (fills.fill_price - fills.reference_open).abs()


def compare(root, check=False):
    out4 = root/"runtime/task13_f1_r4"
    with patch.multiple(original, ROOT=root, R0=root/"runtime/task13_r0",
                        R2=root/"runtime/task13_f1_r2", R3=root/"runtime/task13_f1_r3",
                        OUT=out4, RAW=out4/"raw",
                        __file__=str(root/"experiments/task13_f1_r4/replay.py")):
        dates, nominal, actions, _ = original.inputs()
        decisions = set(original.indices(original.R3/"decision_dates.csv"))
        proxy = original.dates_csv(root/"runtime/task6/data/accepted/069500.KS.csv").close
        risk = proxy.ge(proxy.rolling(63,min_periods=63).mean()).shift(1,fill_value=False).reindex(dates)
        assert risk.notna().all()
        panel = pd.read_pickle(io.BytesIO(checked(R2/"inputs.pkl", read(R2/"artifact_manifest.json")["runtime/task13_f1_r2/inputs.pkl"])))
        score = panel["prior"]["MOM63"]
        flow_mask = panel["flow"][1].notna()
        rankings = {d: list(score.loc[d][score.loc[d].gt(0)&flow_mask.loc[d]].sort_values(
            ascending=False,kind="stable").index) for d in decisions if risk.loc[d]}
        target = original.dates_csv(original.R2/"T1_A_targets.csv").target_weights_json.map(json.loads)
        assert all(list(target[d]) == values[:4] for d, values in rankings.items())
        if check:
            print("Repaired replay inputs valid:", len(dates), len(nominal), len(decisions), len(rankings))
            return
        turns = list(sorted(d for d in decisions if risk.loc[d] and (
            d == dates[0] or risk.loc[:d].iloc[-2])))
        skip = set(turns[1::2])
        costs = read(root/"config/task3_equity_contract.json")["execution_assumptions"]
        min_order = original.CAP * costs.pop("minimum_order_nav_fraction")
        basis = original.ExecutionSpec(**costs,minimum_order_notional_krw=min_order)
        engine = original.trade_open
        results = {}
        outputs = {}
        for multiplier in (1,2):
            for arm in ARMS:
                day_iter = iter(dates)
                counters = dict(buffer_kept=0, skipped=0)

                def trade(account, targets, prior, opening, adv, spec, *, rebalance, risk_on):
                    d = next(day_iter)
                    if rebalance and risk_on and arm == "R1":
                        ranked = rankings[d]
                        if len(ranked)>4 and ranked[4] in account.positions and ranked[4] not in account.pending_sells:
                            retained = [s for s in ranked[:5] if s in account.positions and s not in account.pending_sells]
                            picks = (retained + [s for s in ranked[:4] if s not in retained])[:4]
                            counters["buffer_kept"] += int(set(picks)!=set(targets))
                            targets = dict.fromkeys(picks,.2)
                    if rebalance and risk_on and arm == "LOW_TURNOVER" and d in skip:
                        rebalance = False
                        counters["skipped"] += 1
                    commission = spec.buy_fee_bps
                    altered = replace(spec,buy_fee_bps=commission*multiplier,
                                      sell_fee_bps=(commission+next(bps for start,bps in TAX_BPS if d>=start))*multiplier,
                                      half_spread_bps=spec.half_spread_bps*multiplier,
                                      impact_bps_at_1pct_adv=spec.impact_bps_at_1pct_adv*multiplier,
                                      max_impact_bps=spec.max_impact_bps*multiplier)
                    return engine(account,targets,prior,opening,adv,altered,rebalance=rebalance,risk_on=risk_on)

                with patch.object(original,"trade_open",trade):
                    metrics, nav, fills, _ = original.simulate("T1_A",dates,nominal,actions,risk,decisions,basis)
                assert next(day_iter,None) is None
                daily_cost = gross_cost(fills).groupby(fills.date).sum().reindex(dates,fill_value=0)
                nav["fixed_fills_pre_cost_nav"] = nav.nav + daily_cost.cumsum()
                nav["daily_cost"] = daily_cost
                metrics.update(counters, gross_fixed_fills_pct=(nav.fixed_fills_pre_cost_nav.iloc[-1]/original.CAP-1)*100,
                    two_way_turnover_prev_nav=(fills.open_notional/fills.date.map(nav.nav.shift(fill_value=original.CAP))).sum())
                mix = original.dates_csv(original.R3/"benchmark_nav.csv").loc[dates].MIX_35_25
                market_ret = mix/mix.shift(fill_value=original.CAP)-1
                metrics["lagged_exposure_mix_pct"] = 100*((1+market_ret*nav.equity.shift(fill_value=0)).prod()-1)
                key=f"{multiplier}x_{arm}"
                results[key] = metrics
                outputs[key] = nav, fills
        return results, outputs


def main(choice):
    OUT.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="r1_r4_readonly_") as temp:
        root=Path(temp)
        gate=stage(root)
        if choice == "check":
            print("R4 source staging verified:",len(gate["hashes"]))
            compare(root, check=True)
            return
        contract=OUT/"contract.json"
        if not contract.is_file() or read(contract)["code_sha"] != sha(Path(__file__)):
            raise ValueError("missing or changed evaluation seal")
        with (OUT/"reservation.json").open("x") as f:
            json.dump({"contract_sha":sha(contract),"period":"2023-04-03/2025-12-30","attempt":1},f)
        try:
            results, outputs=compare(root)
            for key,(nav,fills) in outputs.items():
                nav.to_csv(OUT/f"{key}_nav.csv")
                fills.to_csv(OUT/f"{key}_fills.csv",index=False)
            original.save(OUT/"result.json",results)
        except Exception as error:
            original.save(OUT/"failure.json",{"type":type(error).__name__,"error":str(error)})
            raise


if __name__=="__main__":
    main(sys.argv[1])
