"""Check the real entry point and run one sealed evaluation when invoked explicitly."""
import argparse
from datetime import datetime,timezone
import inspect
import json
from pathlib import Path
import time

import numpy as np
import pandas as pd

from experiments.task12.readiness import labels
from experiments.task13_d1.evaluate import calculate
from experiments.task13_d1.preflight import ROOT, OUT, R0, CUTOFF, digest, prices, read, write


def now():
    return datetime.now(timezone.utc).isoformat()


def open_label(opens,entry,exit):
    a,b = opens.index.get_loc(pd.Timestamp(entry)),opens.index.get_loc(pd.Timestamp(exit))
    path = opens.iloc[a:b+1]
    if b-a!=20 or not (np.isfinite(path)&path.gt(0)).all():
        raise ValueError("Invalid sealed H20 path")
    return float(path.iloc[-1]/path.iloc[0]-1)


def smoke():
    assert Path(inspect.getfile(calculate)).resolve()==ROOT/"experiments/task13_d1/evaluate.py"
    assert Path(inspect.getfile(labels)).resolve()==ROOT/"experiments/task12/readiness.py"
    inspect.signature(calculate).bind({},[],[])
    days=pd.bdate_range("2000-01-01",periods=23)
    opens=pd.Series(np.arange(1.,24),index=days)
    y,end=labels({"US_BENCHMARK":opens.to_frame("open"),"X":opens.to_frame("open")},"US",20,days[-1])
    assert end.iloc[0]==days[21] and y.X.iloc[0]==open_label(opens,days[1],days[21])
    opens.iloc[5]=np.nan
    try:
        open_label(opens,days[1],days[21])
    except ValueError:
        pass
    else:
        raise AssertionError("missing path guard")
    assert read(OUT/"preflight.json")["status"]=="PREFLIGHT_PASS"
    assert len(read(OUT/"sample.json"))>=15
    print("PASS actual CLI imports/signature, Task12 synthetic H20 parity, missing-path guard, frozen sample path")


def evaluate_once():
    seal=read(OUT/"seal.json")
    for name,h in (seal["hashes"]|read(OUT/"preflight.json")["provenance"]).items():
        assert digest(ROOT/name)==h,name
    sample=read(OUT/"sample.json")
    contract=read(OUT/"execution_contract.json")
    assert len(sample)>=15 and len(contract["prior"])==40
    days=pd.DatetimeIndex(pd.read_csv(R0/"accepted/US/^GSPC/quote.csv",usecols=["date"]).date)
    days=days[days<=CUTOFF]
    assets={a["symbol"]:a for a in read(R0/"native_manifest/assets.json") if a["market"]=="US" and a["cohort"]=="CORE"}
    lease=OUT/"execution.json"
    with lease.open("x") as f:
        json.dump({"status":"RUNNING","attempt":1,"started":now(),"seal_sha":digest(OUT/"seal.json")},f)
    start=time.process_time()
    try:
        opens={s:prices(ROOT/assets[s]["adjusted_path"],["open"],days).open
               for s in {r["symbol"] for g in sample.values() for r in g["rows"]}}
        for g in sample.values():
            for r in g["rows"]:
                r["H20"]=open_label(opens[r["symbol"]],g["entry"],g["exit"])
        write("paired.json",sample)
        result=calculate(sample,contract["schedule"],contract["prior"])
        write("result.json",result)
    except BaseException as exc:
        write("execution.json",{"status":"FAILED","attempt":1,"error":repr(exc),
              "primary_file_exists":(OUT/"result.json").exists(),"seal_sha":digest(OUT/"seal.json"),"finished":now()})
        raise
    write("execution.json",{"status":"COMPLETED","attempt":1,"finished":now(),
         "seal_sha":digest(OUT/"seal.json"),"result_sha":digest(OUT/"result.json"),
         "paired_sha":digest(OUT/"paired.json"),"cpu_seconds":time.process_time()-start})


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase",choices=["check","evaluate"])
    if parser.parse_args().phase=="check":
        smoke()
    else:
        evaluate_once()
