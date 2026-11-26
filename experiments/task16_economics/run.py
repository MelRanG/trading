"""Register the approved policy in Task4, then execute and hand off its evidence."""
import argparse
from datetime import datetime, timezone

from experiments.task16_economics.worker import APPROVAL, LEDGER, OUT, ROOT, load_inputs, read, sha, write
from experiments.task16_b.evidence import memory
from quant_harness.alpha_research_factory import _hash, execute_review_economics, register_review_proposal
from quant_harness.investment.research_feedback import decide
from quant_harness.investment.research_feedback_dispatch import verify_dispatch_receipts


def main(mode):
    approved = read(ROOT / "config/task4_review_contract.json")["exploratory_economics"][APPROVAL]
    proposal = approved["proposal"]
    snapshot, _, _ = load_inputs()
    if _hash(snapshot) != proposal["input_hash"] or snapshot != read(OUT / "snapshot.json"):
        raise ValueError("official approval and input snapshot mismatch")
    attempt = register_review_proposal(ROOT, proposal)
    print(attempt["proposal_id"], flush=True)
    if mode == "register":
        return
    record = execute_review_economics(ROOT, attempt)
    result = record["result"]
    if result["status"] != "EXPLORATORY_ECONOMICS_COMPLETED":
        raise RuntimeError("Factory recorded worker failure. Inspect worker.log.")
    evidence_path = LEDGER / "diagnostic_registry.jsonl"
    trace = OUT / "research_result.json"
    write(trace, {"factory_ledger": str(evidence_path.relative_to(ROOT)), "record": record})
    pairs = result["sensitivity"]["base"]["pairs"]
    matured = result["sensitivity"]["base"]["occupied_blocks"] >= proposal["minimum_cases"]
    # Minimum against both controls with simultaneous conservative bounds. The
    # diagnostic never lets exploratory evidence authorize a use of capital.
    metric = {key: min(x[key] for x in pairs.values()) for key in ("value", "lo", "hi")}
    mature_feedback = matured and (metric["hi"] < 0 or result["economic_judgment"] == "PROMISING_CONDITIONAL")
    now = datetime.now(timezone.utc).isoformat()
    case = {
        "case_id": "KR_R5_FIVE_HOLD_NEXT_OPEN_V1", "kind": "POLICY", "family": "FIXED_FIVE_HOLD_NEXT_OPEN",
        "mechanism": "Test whether time-based liquidation after identical entry reduces adverse exposure net of opportunity costs.",
        "baseline": "Fixed incumbent trims/removals and passive same-basket hold",
        "decision_as_of": attempt["timestamp_utc"], "evaluation_as_of": now,
        "gates": {"data": "ELIGIBLE", "mature": mature_feedback, "matched_ledger": True},
        "evidence": [{"id": "E", "source": str(trace.relative_to(ROOT)), "source_hash": sha(trace),
                      "available_at": record["timestamp_utc"], "stage": "RESEARCH_OUTCOME"}],
        "metrics": {"net_vs_best_control": {**metric, "evidence_id": "E"}},
        "reevaluation": "No tuning on this sample. Only test a frozen, promising specification on new data with independent evidence and comparable costs.",
    }
    history = memory()
    verify_dispatch_receipts(ROOT, case, history)
    write(OUT / "feedback.json", {"case": case, "decision": decide(case, history)})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("register", "run"))
    main(parser.parse_args().mode)
