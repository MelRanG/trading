"""One fixed stock-signal diagnostic recorded by the existing Research Factory."""
from datetime import datetime, timezone
from hashlib import sha256
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from experiments.task13_h1.prepare_inputs import OUT as H1, ROOT, sha, write_json
from experiments.task14.stats_eval import block_mean, corr, holm, residual
from experiments.task16_b.evidence import memory
from quant_harness.alpha_research_factory import (
    find_review_hypothesis, record_review_experiment, register_review_proposal, reserve_review_experiment,
)
from quant_harness.investment.research import digest
from quant_harness.investment.research_feedback import decide

OUT = ROOT / "runtime/task16_cycle1"
HERE = Path(__file__).resolve().parent
FACTORY = OUT / "isolated_factory"
MARKETS = ("US","KR")
BASE = ["REV5","MOM20","MOM63","VOL20","OVERNIGHT20","INTRADAY20","GAP_ABS20","Q3","H1"]
H = 5


def read(path):
    return json.loads(path.read_bytes())


def features(op, close):
    g, d = np.log(op / close.shift(1)), np.log(close / op)
    ret = close.pct_change(fill_method=None)
    roll = lambda x: x.rolling(20).mean()
    fields = {
        "candidate": roll(-g*d/(g.abs()+.01)),
        "TEAM3_comparator": -roll(ret.abs())/(roll((op/close.shift(1)-1).abs())+1e-8),
        "REV5": 1-close/close.shift(5),
        "MOM20": close/close.shift(20)-1,
        "MOM63": close/close.shift(63)-1,
        "VOL20": ret.rolling(20).std(ddof=0),
        "OVERNIGHT20": roll(g),
        "INTRADAY20": roll(d),
        "GAP_ABS20": roll(g.abs()),
        "Q3": (g-d).rolling(20).sum(),
    }
    return fields


def dataset(market):
    receipt, feature_gate = read(H1/"input_receipt.json"), read(H1/"feature_gate.json")
    assert sha(H1/"input_receipt.json")==feature_gate["inputs_sha256"]
    raw, prior = H1/f"{market}_panel.npz", H1/f"{market}_features.npz"
    assert sha(raw)==receipt["checks"][market]["panel_sha256"]
    assert sha(prior)==feature_gate["members"][market]["sha256"]
    with np.load(raw) as z, np.load(prior) as p:
        d, s = pd.DatetimeIndex(z["dates"]), z["symbols"]
        op, close = (pd.DataFrame(z[name],index=d,columns=s) for name in ("open","close"))
        h1 = pd.DataFrame(p["score"],index=d,columns=s)
        regimes = pd.Series(z["regime"],index=d)
    assert d.is_unique and d.is_monotonic_increasing and op.columns.is_unique
    fields = features(op, close)
    cut = len(d)//2
    changed_open, changed_close = op.copy(), close.copy()
    changed_open.iloc[cut:] *= 1.09
    changed_close.iloc[cut:] *= .92
    for name, altered in features(changed_open, changed_close).items():
        pd.testing.assert_frame_equal(fields[name].iloc[:cut],altered.iloc[:cut])
    for name, prefix in features(op.iloc[:cut], close.iloc[:cut]).items():
        pd.testing.assert_frame_equal(fields[name].iloc[:cut],prefix)
    fields["H1"] = h1
    valid = close.notna().rolling(64).sum().eq(64)
    for name in BASE + ["candidate"]:
        valid &= np.isfinite(fields[name])
    ranks = {k:f.where(valid).rank(axis=1,pct=True) for k,f in fields.items()}
    mature = valid.copy()
    for i in range(1,H+2):
        mature &= (op.notna() & op.gt(0)).shift(-i,fill_value=False)
    last = d.to_series().shift(-H-1)
    calendar = d[(d.year==2024) & last.le("2024-12-31")]
    mask = mature.loc[calendar]
    rows = mask.loc[mask.sum(axis=1)>=50]
    overlap = {}
    for name in [*BASE,"TEAM3_comparator"]:
        left, right = ranks["candidate"].loc["2023"], ranks[name].loc["2023"]
        ar = left.corrwith(right,axis=1).loc[valid.loc["2023"].sum(axis=1)>=50]
        overlap[name] = float(ar.mean())
    summary = {"rows":int(rows.sum().sum()),"dates":len(rows),"names":int(rows.any().sum()),
               "n_2023_feature_days":int(valid.loc["2023"].sum(axis=1).ge(50).sum()),
               "2023_overlap":overlap,"eligible":len(rows)>=100 and all(np.isfinite(list(overlap.values())))
               and max(abs(overlap[k]) for k in BASE)<.95,
               "prefix_and_future_perturbation":True,
               "mask_hash":sha256(pd.util.hash_pandas_object(rows,index=True).to_numpy().tobytes()).hexdigest()}
    return op, ranks, valid, rows, calendar, regimes, summary


def fingerprint():
    files = [HERE/name for name in ("run.py","contract.json","propose.py")] + [
        OUT/name for name in ("TEAM2.json","TEAM3.json","selection.json","context.json")] + [
        H1/f"{m}_{kind}.npz" for m in MARKETS for kind in ("panel","features")] + [
        H1/"input_receipt.json", H1/"feature_gate.json", ROOT/"experiments/task14/stats_eval.py"]
    return {p.relative_to(ROOT).as_posix():sha(p) for p in files}


def top(s):
    return s.rank(ascending=False).le(len(s)//5)


def market_eval(market,data):
    op,ranks,valid,rows,calendar,regimes,_ = data
    labels = op.shift(-H-1)/op.shift(-1)-1
    records = []
    contrib = pd.Series(0.,index=op.columns)
    for day, mask in rows.iterrows():
        past = valid.columns[valid.loc[day]]
        sample = mask.index[mask]
        x = pd.DataFrame({k:ranks[k].loc[day,past] for k in BASE})
        signal = ranks["candidate"].loc[day,past]
        residual_x, _ = residual(signal,x)
        y = labels.loc[day,sample]
        base = x[["REV5","MOM20","MOM63"]].mean(axis=1)
        enhanced = (base.rank(pct=True)+pd.Series(residual_x,index=past).rank(pct=True))/2
        reference, candidate = top(base.loc[sample]), top(enhanced.loc[sample])
        weights = candidate/candidate.sum()-reference/reference.sum()
        contrib.loc[sample] += weights*y
        sx, _ = residual(signal.loc[sample],x.loc[sample])
        sy, _ = residual(y.rank(pct=True),x.loc[sample])
        records.append({"date":day,"regime":regimes.at[day],"names":len(sample),
            "partial":corr(sx,sy),"candidate":corr(signal.loc[sample],y,rank=True),
            "base":corr(base.loc[sample],y,rank=True),"enhanced":corr(enhanced.loc[sample],y,rank=True),
            "lift":float(weights @ y),
            **{k:corr(x.loc[sample,k],y,rank=True) for k in ("REV5","MOM20","MOM63","Q3","H1")}})
    daily=pd.DataFrame(records).set_index("date")
    assert np.isfinite(daily.select_dtypes("number")).all().all()
    daily.to_csv(OUT/f"{market}_daily.csv")
    contrib /= len(daily)
    names = contrib.abs().nlargest(5).index
    contrib.to_csv(OUT/f"{market}_issuer_lift.csv",header=["additive_gross_lift"])
    half = daily.groupby(np.where(daily.index.month<=6,"H1","H2")).partial.mean().to_dict()
    regimes_result = {k:{"dates":len(g),"partial":float(g.partial.mean())} for k,g in daily.groupby("regime")}
    assert abs(contrib.sum()-daily.lift.mean())<1e-12
    return {"primary":block_mean(daily.partial.reindex(calendar),2*H,seed=163101),
            "mean_RankIC":daily[["candidate","base","enhanced","REV5","MOM20","MOM63","Q3","H1"]].mean().to_dict(),
            "half":half,"regime":regimes_result,"gross_lift":block_mean(daily.lift.reindex(calendar),2*H,seed=163101),
            "lift_excluding_largest_five":float(contrib.drop(names).sum()),"largest_five":contrib.loc[names].to_dict()}


def evaluate(data, seal):
    proposal = read(OUT/"contract_receipt.json")
    attempt = find_review_hypothesis(ROOT,proposal,directory=FACTORY)
    if attempt or (OUT/"evaluation_claim.json").exists():
        raise SystemExit("Previously registered or claimed")
    attempt = register_review_proposal(ROOT,proposal,directory=FACTORY)
    reservation = reserve_review_experiment(ROOT,attempt,directory=FACTORY)
    write_json(OUT/"evaluation_claim.json",{"attempt":attempt,"reservation":reservation,"seal":sha(OUT/"seal.json")})
    markets = {m:market_eval(m,data[m]) for m in MARKETS if data[m][-1]["eligible"]}
    correction = holm([markets[m]["primary"]["p_positive"] if m in markets else 1 for m in MARKETS])
    for m,p in zip(MARKETS,correction):
        if m not in markets:
            continue
        r = markets[m]
        r["holm"] = p
        r["conservative_campaign45_p"] = min(1.,45*r["primary"]["p_positive"])
        r["passed"] = (p<.05 and r["primary"]["CI95"][0]>0 and len(r["half"])==2 and min(r["half"].values())>0
                       and r["gross_lift"]["mean"]>0 and r["lift_excluding_largest_five"]>0)
    status = ("FORWARD_REQUIRED" if any(v["passed"] for v in markets.values()) else
              "REJECTED" if all(v["primary"]["CI95"][1]<0 for v in markets.values())
              else "INSUFFICIENT_EVIDENCE")
    record = {"input_hash":proposal["input_hash"],"worker_hash":proposal["worker_hash"],
              "status":status,"cases":sum(r["primary"]["n"]//(2*H) for r in markets.values()),
              "markets":markets,"economic_evaluation":"NOT_EVALUATED","alpha":"ALPHA_NOT_VALIDATED"}
    receipt = record_review_experiment(ROOT,attempt,record,directory=FACTORY)
    write_json(OUT/"result.json",receipt)


def feedback():
    result = read(OUT/"result.json")
    ended = datetime.fromisoformat(result["timestamp_utc"])
    now = datetime.now(timezone.utc).isoformat()
    history = memory()
    for market, r in result["result"]["markets"].items():
        score = r["primary"]
        packet = {"case_id":"CYCLE1_GAP_"+market,"kind":"SIGNAL","family":"GAP_ABSORPTION_SIGNED_PRODUCT",
                  "mechanism":"intraday absorption of overnight price pressure","baseline":"REV5/MOM20/MOM63 and Q3/H1 controls",
                  "decision_as_of":"2024-01-01T00:00:00+00:00","evaluation_as_of":now,
                  "evidence":[{"id":"E","source":str((OUT/"result.json").relative_to(ROOT)),
                               "source_hash":sha(OUT/"result.json"),"stage":"RESEARCH_OUTCOME",
                               "available_at":ended.isoformat(),"market":market},{"id":"C","source":str((OUT/f"{market}_issuer_lift.csv").relative_to(ROOT)),
                               "source_hash":sha(OUT/f"{market}_issuer_lift.csv"),"stage":"RESEARCH_OUTCOME","available_at":ended.isoformat()}],
                  "gates":{"data":"ELIGIBLE","matched_ledger":False,"mature":True},
                  "metrics":{"increment":{"value":score["mean"],"lo":score["CI95"][0],"hi":score["CI95"][1],"evidence_id":"E"},
                             "gross_upper_lift":{"value":r["gross_lift"]["mean"],"evidence_id":"E"}},
                  "facts":{"concentration":"C"},"reevaluation":"Only independent point-in-time data and preregistered evidence of stable increment; no same-sample retuning."}
        decision = decide(packet,history)
        write_json(OUT/f"{market}_feedback.json",{"case":packet,"history":history,"decision":decision})


def main():
    arg = argparse.ArgumentParser()
    arg.add_argument("phase",choices=("seal","evaluate","feedback"))
    phase=arg.parse_args().phase
    if phase=="feedback":
        feedback()
        return
    data={m:dataset(m) for m in MARKETS}
    snap={"hashes":fingerprint(),"coverage":{m:d[-1] for m,d in data.items()}}
    if phase=="seal":
        write_json(OUT/"seal.json",snap)
        if not any(v["eligible"] for v in snap["coverage"].values()):
            return
        cfg = read(ROOT/"config/task4_review_contract.json")
        proposal = {"problem_evidence":{"seal":sha(OUT/"seal.json"),"selection":sha(OUT/"selection.json")},
            "target":"strategy","expected_effect":"Positive controlled stock-selection H5 evidence",
            "falsification":"No stable positive controlled net-of-baseline rank signal or gross upper-tail increment.",
            "champion":"DAILY_MATCHED_PRICE_AND_Q3_H1","challenger":"GAP_ABSORPTION_SIGNED_PRODUCT_20_H5",
            "input_hash":digest(snap),"budget":{"experiments":1,"parameter_search":0},
            "stop_conditions":["data mismatch","data gate fails","no stable increment","no Task15 approval"],
            "evaluation_metric":"2024 H5 partial RankIC on common date/name masks",
            "minimum_cases":cfg["minimum_independent_cases"],"split":"PROCESS_DIAGNOSTIC_ONLY",
            "worker_hash":digest({k:v for k,v in snap["hashes"].items() if k.endswith(".py")})}
        write_json(OUT/"contract_receipt.json",proposal)
        return
    assert read(OUT/"seal.json")==snap and any(v["eligible"] for v in snap["coverage"].values())
    assert read(OUT/"contract_receipt.json")["input_hash"]==digest(snap)
    evaluate(data,snap)


if __name__=="__main__":
    main()
