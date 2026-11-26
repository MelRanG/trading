"""Hash-sealed single historical evaluation. No external or operating calls."""
from datetime import datetime, timezone
import json
import resource
import time

import pandas as pd

from preflight import ROOT, OUT, R0, frame, read, sha, write, gate
from evaluate import evaluate


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def open_to_open(opens, entry, exit):
    i, j = opens.index.get_loc(pd.Timestamp(entry)), opens.index.get_loc(pd.Timestamp(exit))
    if j-i != 252:
        raise ValueError("Expected exactly 252 intervals on the uncompressed session calendar")
    path = opens.iloc[i:j+1]
    if not (path.notna() & path.gt(0)).all():
        raise ValueError("Missing or invalid mark on sealed path")
    return float(path.iloc[-1]/path.iloc[0]-1)


def main():
    seal = read(OUT/"seal.json")
    for name, digest in seal["hashes"].items():
        if sha(ROOT/name) != digest:
            raise ValueError(f"Sealed artifact changed: {name}")
    for name, digest in read(OUT/"input_hashes.json").items():
        if sha(ROOT/name) != digest:
            raise ValueError(f"Sealed source changed: {name}")
    rows = read(OUT/"sample.json")["rows"]
    assert gate(rows)
    lease = OUT/"execution.json"
    with lease.open("x") as f:
        json.dump({"status":"RUNNING","started":timestamp(),"seal_sha256":sha(OUT/"seal.json")},f)
    begin = time.monotonic()
    cpu = time.process_time()
    try:
        assets = {a["symbol"]:a for a in read(R0/"native_manifest/assets.json") if a["market"]=="US"}
        days = frame(R0/"accepted/US/^GSPC/quote.csv", []).index
        opens = {s:frame(ROOT/assets[s]["adjusted_path"], ["open"]).open.reindex(days)
                 for s in {r["symbol"] for r in rows}}
        outcomes = [{**r,"outcome":open_to_open(opens[r["symbol"]], r["entry"], r["exit"])} for r in rows]
        write("paired.json",outcomes)
        old = read(ROOT/"runtime/task14/validation.json")["primary_tests"]
        prior = read(ROOT/"runtime/task13_c1/evaluation.json")["US"]["local_family1_p"]
        result = evaluate(pd.DataFrame(outcomes),task14_primary_tests=old,c1_primary_p=prior)
        write("result.json",result)
    except BaseException as exc:
        write("execution.json",{"status":"INVALID_EVALUATION","error":repr(exc),"finished":timestamp(),"reserved_attempts":1})
        raise
    write("execution.json",{"status":"COMPLETED","finished":timestamp(),"reserved_attempts":1,
          "seal_sha256":sha(OUT/"seal.json"),"result_sha256":sha(OUT/"result.json"),
          "cpu_seconds":time.process_time()-cpu,"wall_seconds":time.monotonic()-begin,
          "max_rss_kib":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
          "SEC_HTTP":0,"price_downloads":0,"LLM_research_calls":0})


if __name__ == "__main__":
    main()
