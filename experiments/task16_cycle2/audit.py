"""Read-only evidence recheck. No native compute, evaluation or model calls."""
import json

import numpy as np
import pandas as pd

from experiments.task16_cycle2.run import FACTORY, OUT, ROOT, native_receipt, read, sha
from quant_harness.alpha_research_factory import find_review_hypothesis
from quant_harness.investment.research import digest
from quant_harness.investment.research_feedback import decide


def audit():
    seal=read(OUT/"seal.json")
    assert all(sha(ROOT/p)==h for p,h in seal["hashes"].items())
    assert all(read(OUT/"native_receipt.json")[k]==v for k,v in native_receipt().items())
    req=read(OUT/"contract_receipt.json")
    assert req["input_hash"]==digest(seal)
    claim=read(OUT/"claim.json")
    receipt=read(OUT/"result.json")
    assert find_review_hypothesis(ROOT,req,directory=FACTORY)==claim["attempt"]
    reservations=(FACTORY/"experiment_reservations.jsonl").read_text().splitlines()
    assert [json.loads(r) for r in reservations]==[claim["reservation"]]
    results=(FACTORY/"diagnostic_registry.jsonl").read_text().splitlines()
    assert [json.loads(r) for r in results]==[receipt]
    daily=pd.read_csv(OUT/"US_daily.csv")
    r=receipt["result"]
    assert len(daily)==seal["days"] and daily.names.sum()==seal["pairs"]
    assert np.isclose(daily.partial.mean(),r["primary"]["mean"],rtol=0,atol=1e-12)
    assert np.isclose(daily.lift.mean(),r["gross_lift"]["mean"],rtol=0,atol=1e-12)
    lift=pd.read_csv(OUT/"US_issuer_lift.csv")["additive_gross_lift"]
    assert np.isclose(lift.sum(),r["gross_lift"]["mean"],rtol=0,atol=1e-12)
    feedback=read(OUT/"feedback.json")
    assert decide(feedback["case"],feedback["history"])==feedback["decision"]
    return {"verified":True,"existing_reservations":len(reservations),"new_evaluations":0,"new_calls":0}


if __name__=="__main__":
    print(json.dumps(audit(),indent=2))
