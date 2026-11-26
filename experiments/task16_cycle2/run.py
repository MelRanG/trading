"""Sealed Task13/14 diagnostic through existing Factory functions."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd

from experiments.task13_h1.prepare_inputs import ROOT, OUT as H1, sha, write_json
from experiments.task14.stats_eval import block_mean, corr, residual
from experiments.task16_b.evidence import memory
from quant_harness.alpha_research_factory import (
    find_review_hypothesis, record_review_experiment, register_review_proposal, reserve_review_experiment,
)
from quant_harness.investment.research import digest
from quant_harness.investment.research_feedback import decide

HERE = Path(__file__).resolve().parent
OUT = ROOT/"runtime/task16_cycle2"
VIBE = ROOT.parent/"quant-diligence/vibe-original"
FACTORY = OUT/"isolated_factory"
PANEL = H1/"US_panel.npz"
BASE = ["REV5","MOM20","MOM63","MAX21","VOL20","DOWNSIDE_SHARE20","DVOL20","H1"]
H = 20


def read(path):
    return json.loads(path.read_bytes())


def native_receipt():
    revision = subprocess.check_output(["git","-C",str(VIBE),"rev-parse","HEAD"],text=True).strip()
    changes = subprocess.check_output(["git","-C",str(VIBE),"status","--porcelain"],text=True)
    assert not changes,"native working tree must be clean"
    sources = [VIBE/"agent/src/factors"/p for p in ("zoo/academic/retskew.py","registry.py","base.py")]
    return dict(revision=revision,files={str(p):sha(p) for p in sources})


def verify_panel():
    inputs, gate = read(H1/"input_receipt.json"), read(H1/"feature_gate.json")
    assert sha(H1/"input_receipt.json")==gate["inputs_sha256"]
    assert sha(PANEL)==inputs["checks"]["US"]["panel_sha256"]
    assert sha(H1/"US_features.npz")==gate["members"]["US"]["sha256"]


def native():
    verify_panel()
    proof=native_receipt()
    subprocess.run([sys.executable,str(HERE/"native.py"),str(PANEL),str(OUT/"US_native.npy")],
                   env={"PYTHONPATH":str(VIBE/"agent"),"OPENBLAS_NUM_THREADS":"1", "PYTHONDONTWRITEBYTECODE":"1"},
                   cwd=OUT,check=True,timeout=60)
    assert native_receipt()==proof
    write_json(OUT/"native_receipt.json",{**proof,"input_hash":sha(PANEL),"output_hash":sha(OUT/"US_native.npy"),
               "component":"original registry.compute('academic_retskew')","uses_outcomes":False})


def inputs():
    verify_panel()
    proof=read(OUT/"native_receipt.json")
    assert proof["output_hash"]==sha(OUT/"US_native.npy") and proof["input_hash"]==sha(PANEL)
    assert all(proof[k]==v for k,v in native_receipt().items())
    with np.load(PANEL) as z, np.load(H1/"US_features.npz") as f:
        dates, names = pd.DatetimeIndex(z["dates"]), z["symbols"]
        op, c, volume = (pd.DataFrame(z[k],index=dates,columns=names) for k in ("open","close","volume"))
        state=pd.Series(z["regime"],index=dates)
        prior=pd.DataFrame(f["score"],index=dates,columns=names)
    assert dates.is_unique and dates.is_monotonic_increasing and c.columns.is_unique
    r = c.pct_change(fill_method=None)
    sq = r**2
    raw = {"candidate":pd.DataFrame(np.load(OUT/"US_native.npy"),index=dates,columns=names),
           "REV5":1-c/c.shift(5), "MOM20":c/c.shift(20)-1,"MOM63":c/c.shift(63)-1,
           "MAX21":r.rolling(21).max(),"VOL20":r.rolling(20).std(ddof=0),
           "DOWNSIDE_SHARE20":sq.where(r.lt(0),0).where(r.notna()).rolling(20).sum()/sq.rolling(20).sum(),
           "DVOL20":np.log((c*volume).rolling(20).mean()),"H1":prior}
    valid = c.notna().rolling(64).sum().eq(64)
    for f in raw.values():
        valid &= np.isfinite(f)
    scores={k:v.where(valid).rank(axis=1,pct=True) for k,v in raw.items()}
    maturity = valid.copy()
    for j in range(1,H+2):
        maturity &= (op.notna() & op.gt(0)).shift(-j,fill_value=False)
    exit_date = dates.to_series().shift(-H-1)
    calendar=dates[(dates >= "2023-04-03") & (dates <= "2024-12-31") & exit_date.dt.year.eq(dates.year)]
    mask=maturity.loc[calendar]
    mask=mask.loc[mask.sum(axis=1)>=50]
    # Feature-only overlap does not condition on future label availability.
    prior_mask=(dates.year==2023) & valid.sum(axis=1).ge(50)
    overlap={k:float(scores["candidate"].loc[prior_mask].corrwith(scores[k].loc[prior_mask],axis=1).mean()) for k in BASE}
    count=mask.groupby(mask.index.year).size().to_dict()
    eligible=len(mask)>=252 and all(count.get(y,0)>=100 for y in (2023,2024)) and all(np.isfinite(list(overlap.values()))) and max(map(abs,overlap.values()))<.95
    files=[HERE/k for k in ("contract.json","run.py","native.py","propose.py")]+[
        OUT/k for k in ("TEAM2.json","context.json","native_receipt.json","US_native.npy","selection.json")
    ]+[PANEL,H1/"US_features.npz",H1/"input_receipt.json",H1/"feature_gate.json",ROOT/"experiments/task14/stats_eval.py"]
    snap=dict(hashes={str(x.relative_to(ROOT)):sha(x) for x in files},eligible=eligible,
              days=len(mask),pairs=int(mask.sum().sum()),names=int(mask.any().sum()),year_days={str(y):n for y,n in count.items()},
              feature_overlap=overlap,mask_hash=digest(mask.to_json(orient="split",date_format="iso")),earliest=str(mask.index.min()),latest=str(mask.index.max()))
    return snap, op, scores, valid, mask, calendar, state


def evaluate(op,scores,valid,mask,calendar,state):
    labels=op.shift(-21)/op.shift(-1)-1
    rows=[]
    contribution=pd.Series(0.,index=op.columns)
    for dt, available in mask.iterrows():
        names = available.index[available]
        earlier = valid.columns[valid.loc[dt]]
        f = pd.DataFrame({k:scores[k].loc[dt,earlier] for k in BASE})
        s=scores["candidate"].loc[dt,earlier]
        adjusted,_=residual(s,f)
        y=labels.loc[dt,names]
        bx,_=residual(s.loc[names],f.loc[names])
        by,_=residual(y.rank(pct=True),f.loc[names])
        base=(f.REV5+f.MOM20+f.MOM63-f.MAX21-f.VOL20)/5
        combined=(base.rank(pct=True)+pd.Series(adjusted,index=earlier).rank(pct=True))/2
        ref=base.loc[names].rank(ascending=False).le(len(names)//5)
        aug=combined.loc[names].rank(ascending=False).le(len(names)//5)
        w=aug/aug.sum()-ref/ref.sum()
        contribution.loc[names]+=w*y
        rows.append(dict(date=dt,regime=state.at[dt],names=len(names),partial=corr(bx,by),
                         candidate=corr(s.loc[names],y,rank=True),base=corr(base.loc[names],y,rank=True),
                         augmented=corr(combined.loc[names],y,rank=True),lift=float(w@y),
                         **{k:corr(f.loc[names,k],y,rank=True) for k in BASE}))
    daily=pd.DataFrame(rows).set_index("date")
    assert np.isfinite(daily.select_dtypes("number")).all().all()
    daily.to_csv(OUT/"US_daily.csv")
    contribution/=len(daily)
    top=contribution.abs().nlargest(5).index
    assert abs(contribution.sum()-daily.lift.mean())<1e-12
    contribution.to_csv(OUT/"US_issuer_lift.csv",header=["additive_gross_lift"])
    primary=block_mean(daily.partial.reindex(calendar),21,seed=163201)
    lift=block_mean(daily.lift.reindex(calendar),21,seed=163201)
    years={str(y):float(v) for y,v in daily.groupby(daily.index.year).partial.mean().items()}
    adj=min(1.,49*primary["p_positive"])
    trimmed=float(contribution.drop(top).sum())
    passed=primary["CI95"][0]>0 and adj<.05 and min(years.values())>0 and lift["mean"]>0 and trimmed>0
    status="FORWARD_REQUIRED" if passed else "REJECTED" if primary["CI95"][1]<0 and lift["CI95"][1]<0 else "INSUFFICIENT_EVIDENCE"
    return dict(status=status,cases=len(daily)//21,primary=primary,family49=adj,gross_lift=lift,years=years,
                regime={k:{"days":len(g),"partial":float(g.partial.mean())} for k,g in daily.groupby("regime")},
                RankIC=daily[["candidate","base","augmented",*BASE]].mean().to_dict(),
                lift_excluding_five=trimmed,largest_five=contribution.loc[top].to_dict(),economic="NOT_EVALUATED",
                KR="NOT_TESTED_OUTSIDE_NATIVE_UNIVERSE",alpha="ALPHA_NOT_VALIDATED")


def feedback():
    artifact=OUT/"result.json"
    report=read(artifact)
    r=report["result"]
    now=datetime.now(timezone.utc).isoformat()
    history=memory()
    cycle1=ROOT/"runtime/task16_cycle1/result.json"
    history.append(dict(family="GAP_ABSORPTION_SIGNED_PRODUCT",status="LIMITED",
                        available_at=read(cycle1)["timestamp_utc"],source=str(cycle1.relative_to(ROOT)),source_hash=sha(cycle1)))
    score=r["primary"]
    assert read(OUT/"seal.json")["hashes"][str((HERE/"run.py").relative_to(ROOT))]==sha(HERE/"run.py")
    packet={"case_id":"CYCLE2_US_RETSKEW","kind":"SIGNAL","family":"ACADEMIC_RETURN_SKEW",
            "mechanism":"own-return lottery proxy","baseline":"same-name REV5/MOM and MAX21/volatility controls",
            "decision_as_of":"2023-04-03T00:00:00+00:00","evaluation_as_of":now,
            "gates":{"data":"ELIGIBLE","matched_ledger":False,"mature":True},
            "evidence":[{"id":"E","source":str(artifact.relative_to(ROOT)),"source_hash":sha(artifact),
                         "available_at":report["timestamp_utc"],"stage":"RESEARCH_OUTCOME"}],
            "metrics":{"increment":{"value":score["mean"],"lo":score["CI95"][0],"hi":score["CI95"][1],"evidence_id":"E"},
                       "gross_lift":{"value":r["gross_lift"]["mean"],"evidence_id":"E"}},
            "reevaluation":"Require an independent PIT sample, positive stable increments and preregistration; no same-sample variant."}
    write_json(OUT/"feedback.json",dict(case=packet,decision=decide(packet,history),history=history))


def main():
    p=argparse.ArgumentParser()
    p.add_argument("phase",choices=["native","seal","evaluate","feedback"])
    phase=p.parse_args().phase
    if phase=="native":
        native()
        return
    if phase=="feedback":
        feedback()
        return
    data=inputs()
    snap=data[0]
    if phase=="seal":
        write_json(OUT/"seal.json",snap)
        if not snap["eligible"]:
            return
        cfg=read(ROOT/"config/task4_review_contract.json")
        contract=dict(target="strategy",champion="PRICE_AND_MAX21_VOL_CONTROLS",challenger="VIBE_ACADEMIC_RETSKEW_H20",
                      problem_evidence={"selection":sha(OUT/"selection.json"),"seal":sha(OUT/"seal.json")},
                      expected_effect="Positive controlled H20 stock rank",falsification="No stable controlled upside and gross long lift.",
                      input_hash=digest(snap),worker_hash=digest({k:v for k,v in snap["hashes"].items() if k.endswith(".py")}),
                      budget={"experiments":1,"parameter_search":0},stop_conditions=["input drift","data gate failure","no independent economic approval"],
                      evaluation_metric="US H20 partial RankIC",minimum_cases=cfg["minimum_independent_cases"],
                      split="PROCESS_DIAGNOSTIC_ONLY")
        write_json(OUT/"contract_receipt.json",contract)
        return
    assert snap["eligible"] and read(OUT/"seal.json")==snap
    req=read(OUT/"contract_receipt.json")
    assert req["input_hash"]==digest(snap)
    if find_review_hypothesis(ROOT,req,directory=FACTORY) or (OUT/"claim.json").exists():
        raise SystemExit("already registered")
    attempt=register_review_proposal(ROOT,req,directory=FACTORY)
    claim=reserve_review_experiment(ROOT,attempt,directory=FACTORY)
    write_json(OUT/"claim.json",{"attempt":attempt,"reservation":claim,"seal":sha(OUT/"seal.json")})
    r=evaluate(*data[1:])
    result=record_review_experiment(ROOT,attempt,{**r,"input_hash":req["input_hash"],"worker_hash":req["worker_hash"]},directory=FACTORY)
    write_json(OUT/"result.json",result)


if __name__=="__main__":
    main()
