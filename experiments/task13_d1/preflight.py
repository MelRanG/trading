"""D0 feature reuse and evaluation-window admissibility, without return labels."""
from collections import Counter
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from experiments.task13_d0.precheck import CONTROLS, ROOT, R0, digest, feature_frame, mask

OUT = ROOT / "runtime/task13_d1"
D0 = ROOT / "runtime/task13_d0"
CUTOFF = pd.Timestamp("2024-12-31")


def read(path):
    return json.loads(path.read_text())


def write(name, payload):
    path = OUT / name
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(payload, allow_nan=False, indent=2) + "\n")
    temp.replace(path)


def prices(path, columns, days):
    frame = pd.read_csv(path, usecols=["date", *columns], index_col="date", parse_dates=True)
    assert frame.index.is_unique and frame.index.is_monotonic_increasing, path
    return frame.loc[:CUTOFF].reindex(days)


def admissible(path):
    return path.notna() & np.isfinite(path) & path.gt(0)


def main():
    assert not (OUT/"seal.json").exists() and not (OUT/"preflight.json").exists()
    start = time.process_time()
    contract = read(D0/"screen_plan.json")
    d0 = read(D0/"precheck.json")
    assert contract["horizon"] == 20 and contract["controls"] == CONTROLS
    assert d0["feature_gate"] and read(D0/"decision_seal.json")["selected"] == ["US_GRADUAL_WINNERS_H20"]
    evidence = (read(D0/"decision_seal.json")["hashes"] | d0["inputs"])
    for name, wanted in evidence.items():
        assert digest(ROOT/name) == wanted, name
    assets = [a for a in read(R0/"native_manifest/assets.json") if a["market"]=="US" and a["cohort"]=="CORE"]
    assert len(assets)==len({a["symbol"] for a in assets})==176
    index_file = R0/"accepted/US/^GSPC/quote.csv"
    days = pd.DatetimeIndex(pd.read_csv(index_file,usecols=["date"]).date)
    assert days.is_unique and days.is_monotonic_increasing
    days = days[days<=CUTOFF]
    schedule = days[(days>="2023-04-03")][::21]
    assert [str(t.date()) for t in schedule] == list(d0["observed_schedule_mask_ceiling"])
    market_ok = mask(index_file.parent/"quality_mask.csv",days)
    by_date = {}
    for t in schedule:
        pos = days.get_loc(t)
        path = days[pos+1:pos+22]
        issue = None
        if len(path)!=21:
            issue = "UNMATURED_BY_CUTOFF"
        elif not market_ok.loc[path].all():
            issue = "INHERITED_INDEX_MASK"
        by_date[t] = {"entry":str(path[0].date()) if len(path)==21 else None,
                      "exit":str(path[-1].date()) if len(path)==21 else None,
                      "date_path_reason":issue,"excluded":Counter(),"rows":[]}
    for asset in assets:
        path = ROOT/asset["adjusted_path"]
        qmask = mask(path.parent/"quality_mask.csv",days)
        native = mask(ROOT/asset["eligibility_path"],days)
        assert not (native & ~qmask).any(),asset["symbol"]
        eligible = qmask & native
        bars = prices(path,["open","close"],days)
        # Eligibility of outcome marks uses booleans only; no ratios or outcome ranks.
        open_valid = admissible(bars.open) & eligible
        close = bars.close.where(admissible(bars.close) & eligible)
        data = feature_frame(close).loc[schedule]
        for t, bucket in by_date.items():
            if bucket["date_path_reason"]:
                continue
            i = days.get_loc(t)
            f = data.loc[t]
            if not eligible.iloc[i-251:i+1].all():
                reason = "INCOMPLETE_NATIVE_FEATURE_WINDOW"
            elif not np.isfinite(f.to_numpy(float)).all():
                reason = "NONFINITE_FEATURE_OR_CONTROL"
            elif f.formation<=0:
                reason = "NONPOSITIVE_FORMATION"
            elif not open_valid.iloc[i+1:i+22].all():
                reason = "INVALID_STOCK_H20_PATH"
            else:
                bucket["rows"].append({"symbol":asset["symbol"],**{k:float(v) for k,v in f.items()}})
                continue
            bucket["excluded"][reason] += 1

    sample, diagnostics = {}, []
    for t, bucket in by_date.items():
        date = str(t.date())
        rows = bucket.pop("rows")
        reason = bucket["date_path_reason"]
        if reason is None and len(rows)<50:
            reason = "BELOW_50_COMPLETE_NAMES"
        if reason is None:
            ranks = pd.DataFrame(rows)[["score",*CONTROLS]].rank().to_numpy()
            design = np.column_stack([np.ones(len(rows)),ranks[:,1:]])
            coefs,_,rank,_ = np.linalg.lstsq(design,ranks[:,0],rcond=None)
            if rank!=design.shape[1] or np.std(ranks[:,0]-design@coefs)<1e-12:
                reason = "UNIDENTIFIED_SIGNAL_RESIDUAL"
        if reason is None:
            sample[date] = {**{k:bucket[k] for k in ["entry","exit"]},"rows":rows}
        diagnostics.append({"date":date,"eligible_names":len(rows),"reason":reason,**bucket})
    write("sample.json",sample)
    write("preflight.json",{"status":"PREFLIGHT_PASS" if len(sample)>=15 else "SAMPLE_INSUFFICIENT",
          "schedule":diagnostics,"dates":len(sample),"rows":sum(len(x["rows"]) for x in sample.values()),
          "symbols":len({r["symbol"] for g in sample.values() for r in g["rows"]}),
          "provenance":evidence,"future_return_calculations":0,"cpu_seconds":time.process_time()-start})
    print(len(sample),[(d["date"], d["eligible_names"],d["reason"]) for d in diagnostics])


if __name__=="__main__":
    main()
