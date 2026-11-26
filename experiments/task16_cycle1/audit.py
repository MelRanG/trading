"""Verify the frozen Cycle 1 evidence without calls, outcome recomputation or Factory writes."""
import json

import numpy as np
import pandas as pd

from experiments.task16_cycle1.run import FACTORY, MARKETS, OUT, ROOT, fingerprint, read
from quant_harness.alpha_research_factory import find_review_hypothesis
from quant_harness.investment.research import digest
from quant_harness.investment.research_feedback import decide


def audit():
    seal=read(OUT/"seal.json")
    assert fingerprint()==seal["hashes"]
    request=read(OUT/"contract_receipt.json")
    assert request["input_hash"]==digest(seal)
    claim=read(OUT/"evaluation_claim.json")
    receipt=read(OUT/"result.json")
    assert find_review_hypothesis(ROOT,request,directory=FACTORY)==claim["attempt"]
    reservations=(FACTORY/"experiment_reservations.jsonl").read_text().splitlines()
    assert [json.loads(r) for r in reservations]==[claim["reservation"]]
    assert [json.loads(r) for r in (FACTORY/"diagnostic_registry.jsonl").read_text().splitlines()]==[receipt]
    results=receipt["result"]["markets"]
    for market in MARKETS:
        if market not in results:
            continue
        daily=pd.read_csv(OUT/f"{market}_daily.csv")
        r=results[market]
        assert len(daily)==seal["coverage"][market]["dates"] and daily.names.sum()==seal["coverage"][market]["rows"]
        assert np.isclose(daily.partial.mean(),r["primary"]["mean"],rtol=0,atol=1e-12)
        assert np.isclose(daily.lift.mean(),r["gross_lift"]["mean"],rtol=0,atol=1e-12)
        stocks=pd.read_csv(OUT/f"{market}_issuer_lift.csv")["additive_gross_lift"]
        assert np.isclose(stocks.sum(),r["gross_lift"]["mean"],rtol=0,atol=1e-12)
        feedback=read(OUT/f"{market}_feedback.json")
        assert decide(feedback["case"],feedback["history"])==feedback["decision"]
    return {"verified":True,"existing_reservations":len(reservations),
            "verified_market_results":list(results),"new_evaluations":0,"new_calls":0}


if __name__=="__main__":
    print(json.dumps(audit(),indent=2))
