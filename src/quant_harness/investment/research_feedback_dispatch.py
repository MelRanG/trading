"""Use Factory's existing diagnostic registry from a bounded offline workflow."""
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from quant_harness.alpha_research_factory import (
    find_review_hypothesis, record_review_experiment, register_review_proposal, reserve_review_experiment,
)
from .research import bounded, digest
from .research_dispatcher import evaluate_numeric_bundle
from .research_feedback import ROUTES, bind_comment, decide


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def worker_hash():
    return digest({name: file_hash(Path(__file__).with_name(name)) for name in
                   ("research_feedback_dispatch.py", "research.py", "financial_packet.py", "research_dispatcher.py")})


def evidence_path(root, relative):
    source = (root / relative).resolve()
    if Path(relative).is_absolute() or not source.is_relative_to(root.resolve() / "runtime"):
        raise ValueError("diagnostic inputs must be under runtime")
    return source


def verify_dispatch_receipts(root, case, history):
    for receipt in (*case["evidence"], *history):
        relative = Path(receipt.get("source", ""))
        path = (root / relative).resolve()
        if (relative.is_absolute() or not path.is_relative_to(root) or not path.is_file()
                or file_hash(path) != receipt["source_hash"]):
            raise ValueError("research receipt missing or changed")


def team3_preflight(root, payload):
    """Assess historical target coverage and opportunity, without producing any orders."""
    signals = payload["inputs"]
    union = []
    for key in ("targets", "nav"):
        source = evidence_path(root, signals[key]["path"])
        if file_hash(source) != signals[key]["sha256"]:
            raise ValueError("historical input hash mismatch")
        with source.open() as stream:
            rows = list(csv.DictReader(stream))
        if key == "targets":
            targets = {r["date"]: json.loads(r["target_weights_json"]) for r in rows}
        else:
            union = rows
    # R4 NAV has a risk flag; R2 frozen targets are indexed by the same date.
    by_year = {}
    for row in union:
        day = row["date"]
        if day not in targets or row["risk_on"] not in ("True", "False"):
            raise ValueError("unaligned or invalid risk input")
        weights = targets[day]
        capped = bounded(weights, {"gross_cap": .8, "single_name_cap": .2})
        if capped != weights:
            raise ValueError("historical target exceeds the sealed cap")
        info = by_year.setdefault(day[:4], {"sessions": 0, "gate_on_with_vacancy": 0})
        info["sessions"] += 1
        if row["risk_on"] == "True" and len(weights) < 4 and sum(weights.values()) < .8 - 1e-10:
            info["gate_on_with_vacancy"] += 1
    return {"status": "INSUFFICIENT_EVIDENCE", "cases": 0,
            "historical_target_coverage": by_year,
            "reason": "Historical coverage only. No independent test of net ETF substitution or matched execution."}


def perform(root, bundle):
    if bundle["route"] == "PIT_EXPOSURE_FEASIBILITY":
        trace = team3_preflight(root, bundle["payload"])
    elif bundle["route"] == "DISCLOSURE_PROVENANCE":
        trace = evaluate_numeric_bundle(root, bundle["payload"])
    else:
        raise ValueError("unregistered diagnostic route")
    return {**trace, "input_hash": digest(bundle), "worker_hash": worker_hash(), "portfolio_runs": 0}


def create_request(case, decision, advisory, bundle, minimum_cases):
    model = advisory["proposal"]
    if model is None or model["route"] not in decision["allowed_routes"] or bundle["route"] != model["route"]:
        raise ValueError("no admissible diagnostic")
    owner, _, split = ROUTES[model["route"]]
    return {
        "target": "source" if owner == "TEAM2" else "strategy",
        "champion": case["baseline"], "challenger": model["route"],
        "input_hash": digest(bundle), "worker_hash": worker_hash(),
        "budget": {"experiments": 1, "parameter_search": 0}, "split": split, "minimum_cases": minimum_cases,
        "problem_evidence": {"case": case["case_id"], "case_hash": digest(case), "ids": advisory["evidence_ids"]},
        "expected_effect": model["hypothesis"], "falsification": model["failure"],
        "evaluation_metric": model["verification"], "stop_conditions": ["Evidence or worker hash mismatch",
            "Research budget exhausted", "Economic evaluation requires a separate approval"],
        "research_owner": owner, "research_draft": model, "research_family": case["diagnostic"]["family"],
    }


def dispatch(root, directory, case, history, advisory, bundle):
    """The caller must supply an isolated directory. No production default."""
    root, directory = Path(root).resolve(), Path(directory).resolve()
    research = root / "runtime/task16_b"
    # Resolve symlinks before checking any destination.
    if directory == research or not directory.is_relative_to(research):
        raise ValueError("operating paths cannot be used for the research pilot")
    decision = decide(case, history)
    cfg = json.loads((root / "config/task4_review_contract.json").read_text())
    rebound = bind_comment(case, decision, {"case_id": case["case_id"], **advisory})
    if rebound["proposal"] is None:
        raise ValueError("unbound research proposal")
    verify_dispatch_receipts(root, case, history)
    request = create_request(case, decision, rebound, bundle, cfg["minimum_independent_cases"])
    prior = find_review_hypothesis(root, request, directory=directory)
    if prior:
        return {"status": "DUPLICATE", "prior": prior, "portfolio_runs": 0}
    attempt = register_review_proposal(root, request, directory=directory)
    # Exclusive claim prevents a second invocation after an interrupted worker.
    claim = directory / (attempt["attempt_id"] + ".input.json")
    with claim.open("x") as stream:
        json.dump(bundle, stream, sort_keys=True, allow_nan=False)
    reserve_review_experiment(root, attempt, directory=directory)
    output = claim.with_suffix(".result.json")
    reply = subprocess.run(
        [sys.executable, "-m", __spec__.name, str(root), str(claim), str(output)],
        cwd=directory, env={"PYTHONPATH": str(root / "src"), "OPENBLAS_NUM_THREADS": "1"},
        timeout=30, capture_output=True, text=True, check=False,
    )
    if reply.returncode:
        return {"status": "WORKER_FAILED", "attempt": attempt, "stderr": reply.stderr, "portfolio_runs": 0}
    diagnostic = json.loads(output.read_text())
    record = record_review_experiment(root, attempt, diagnostic, directory=directory)
    return {"status": "DIAGNOSTIC_RECORDED", "request": request, "attempt": attempt, "record": record,
            "next": "HOLD_FOR_INDEPENDENT_DATA_AND_SEPARATE_ECONOMIC_APPROVAL", "portfolio_runs": 0}


if __name__ == "__main__":
    root, source, output = map(Path, sys.argv[1:])
    result = perform(root, json.loads(source.read_text()))
    with output.open("x") as stream:
        json.dump(result, stream, allow_nan=False)
