"""One bounded diagnostic using old account receipts, never a portfolio replay."""
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import argparse
import json

from experiments.task13_opportunity_diagnostic.audit import archived, csv
from experiments.task13_r1_st_preflight.audit import R4, R5, checked, read
from experiments.task13_h1.prepare_inputs import sha, write_json
from experiments.task16_b.evidence import memory
from experiments.task16_cycle3.propose import OUT, ROOT
from quant_harness.alpha_research_factory import (
    find_review_hypothesis, record_review_experiment, register_review_proposal, reserve_review_experiment,
)
from quant_harness.investment.research import digest
from quant_harness.investment.research_feedback import decide
from quant_harness.investment.research_feedback_dispatch import verify_dispatch_receipts

HERE = Path(__file__).resolve().parent
FACTORY = OUT / "isolated_factory"
CFG = ROOT / "config/task4_review_contract.json"
R4_FILL = "runtime/task13_f1_r4/T1_A_fills.csv"
FILES = {
    R4: ("T1_A_nav.csv",),
    R5: ("nav.csv", "fills.csv", "events.csv", "independent_verification.json"),
}


def prepare():
    base = {R4: "runtime/task13_f1_r4", R5: "runtime/task13_f1_r5"}
    sources = {}
    for folder, names in FILES.items():
        manifest = read(folder / "artifact_manifest.json")
        for name in names:
            path = folder / name
            expected = manifest[f"{base[folder]}/{name}"]
            checked(path, expected)
            sources[str(path.relative_to(ROOT))] = expected
    index = ROOT / "runtime/research_reference/index.json"
    sources[str(index.relative_to(ROOT))] = sha(index)
    old_fill = archived({R4_FILL})[R4_FILL]
    expected = read(R4 / "artifact_manifest.json")[R4_FILL]
    if sha256(old_fill).hexdigest() != expected:
        raise ValueError("R4 archived fills differ from ledger manifest")
    frozen = {str(path.relative_to(ROOT)): sha(path) for path in (
        HERE / "audit.py", HERE / "diagnostic.json", CFG, OUT / "team2.json", OUT / "team3.json",
        OUT / "selection.json", ROOT / "experiments/task13_opportunity_diagnostic/audit.py",
    )}
    return {"sources": sources, "archive_member": {"path": R4_FILL, "sha256": expected}, "frozen": frozen}, old_fill


def counts(nav, fills):
    if not nav.index.is_unique or not fills.index.isin(nav.index).all():
        raise ValueError("fill dates do not match account")
    return {"sessions": len(nav), "sessions_with_fills": fills.index.nunique(), "fills": len(fills),
            "fill_side": dict(Counter(fills.side))}


def evaluate(old_fill):
    nav4 = csv((R4 / "T1_A_nav.csv").read_bytes())
    nav5 = csv((R5 / "nav.csv").read_bytes())
    f4 = csv(old_fill)
    f5 = csv((R5 / "fills.csv").read_bytes())
    events = csv((R5 / "events.csv").read_bytes())
    old = read(R5 / "independent_verification.json")["window_diagnostics"]
    unresolved = events[events.detail.str.startswith("FILL_UNCERTAIN", na=False)]
    if not events.index.isin(nav5.index).all() or nav5.stress_open.dtype != bool:
        raise ValueError("invalid R5 evidence")
    stress = nav5.index[nav5.stress_open]
    stress_fills = f5.loc[f5.index.isin(stress)]
    observed = {str(date.date()): group[["symbol", "side", "quantity"]].values.tolist()
                for date, group in stress_fills.groupby(level=0, sort=True)}
    if observed != old["stress_open_fills"]:
        raise ValueError("R5 historical stress evidence mismatch")
    r4 = {**counts(nav4, f4), "auction_status": "UNKNOWN_NO_DATED_FLAGS_OR_AUCTION"}
    r5 = counts(nav5, f5)
    blocked = nav5.index[nav5.blocked_boards.map(lambda value: bool(json.loads(value)))]
    flagged = stress.union(blocked).union(unresolved.index).unique()
    is_flagged = f5.index.isin(flagged)
    r5.update({"stress_open_sessions": len(stress), "stress_open_sessions_with_fills": len(observed),
               "stress_open_fills": len(stress_fills), "blocked_board_sessions": len(blocked),
               "explicit_unfilled_events": len(unresolved), "explicit_unfilled_dates": sorted(
                   {str(value.date()) for value in unresolved.index}),
               "flagged_sessions": len(flagged), "flagged_fill_days": f5.index[is_flagged].nunique(),
               "flagged_fills": int(is_flagged.sum()),
               "unflagged_sessions": len(nav5) - len(flagged),
               "unflagged_sessions_with_fills": f5.index[~is_flagged].nunique(),
               "unflagged_fills": int((~is_flagged).sum()),
               "auction_status": "EX_POST_FLAGS_ONLY_EXACT_FILLS_UNCERTIFIED"})
    if not len(flagged) or not len(f5):
        raise ValueError("R5 coverage unexpectedly empty")
    return {"R4": r4, "R5": r5, "status": "INSUFFICIENT_EVIDENCE", "cases": 0,
            "portfolio_runs": 0, "economics": "NOT_EVALUATED", "confirmed_auction_receipts_in_inputs": 0}


def feedback():
    result = OUT / "result.json"
    now = datetime.now(timezone.utc).isoformat()
    history = memory()
    case = {
        "case_id": "CYCLE3_AUCTION_COVERAGE", "kind": "POLICY", "family": "FIVE_SESSION_CLOSE_EXIT",
        "mechanism": "Fixed holding time may limit adverse holding duration, depending on verified execution.",
        "baseline": "Same initial stock baskets, existing policy and simple hold",
        "decision_as_of": read(OUT / "seal.json")["sealed_at"], "evaluation_as_of": now,
        "gates": {"data": "BLOCKED", "mature": True, "matched_ledger": False},
        "evidence": [{"id": "E", "source": str(result.relative_to(ROOT)), "source_hash": sha(result),
                      "available_at": read(result)["timestamp_utc"], "stage": "RESEARCH_OUTCOME"}],
        "reevaluation": "Reopen only with separately approved economic contract and equivalent admissible opening/closing auction data; require matched costs and risk and both stress and full-calendar results.",
    }
    verify_dispatch_receipts(ROOT, case, history)
    write_json(OUT / "feedback.json", {"case": case, "decision": decide(case, history), "history": history})


def source_day_use():
    day = datetime.now(timezone.utc).date().isoformat()
    logs = set((ROOT / "runtime").glob("task16*/**/experiment_reservations.jsonl"))
    logs.add(ROOT / "runtime/alpha_research_factory/task4/experiment_reservations.jsonl")
    return {str(path.relative_to(ROOT)): sum(
        json.loads(line)["timestamp_utc"].startswith(day) for line in path.read_text().splitlines() if line
    ) for path in sorted(logs) if path.is_file()}


def main(phase):
    if phase == "feedback":
        feedback()
        return
    snap, old_fill = prepare()
    if phase == "seal":
        if (OUT / "seal.json").exists():
            raise ValueError("sealed already")
        write_json(OUT / "seal.json", {"sealed_at": datetime.now(timezone.utc).isoformat(), "snapshot": snap})
        return
    if read(OUT / "seal.json")["snapshot"] != snap:
        raise ValueError("sealed source drift")
    if phase == "verify":
        final = read(OUT / "result.json")["result"]
        if final["input_hash"] != digest(snap) or final["portfolio_runs"] != 0:
            raise ValueError("receipt mismatch")
        claims = (FACTORY / "experiment_reservations.jsonl").read_text().splitlines()
        if len(claims) != 1 or json.loads(claims[0])["attempt_id"] != read(OUT / "result.json")["attempt_id"]:
            raise ValueError("reservation mismatch")
        print(json.dumps({"verified": True, "reservations": len(claims), "new_runs": 0}))
        return
    request = {
        "target": "strategy", "champion": "R4_R5_SAVED_NOMINAL_LEDGERS",
        "challenger": "KR_AUCTION_EVIDENCE_COVERAGE",
        "problem_evidence": {"selection_sha256": sha(OUT / "selection.json")},
        "expected_effect": "Measure feasibility of admissible execution comparisons on actual calendars.",
        "falsification": "Missing auction observations prevent a causal economic replay.",
        "input_hash": digest(snap), "budget": {"experiments": 1, "parameter_search": 0},
        "stop_conditions": read(HERE / "diagnostic.json")["stops"],
        "evaluation_metric": "Dated coverage by auction-evidence severity",
        "minimum_cases": read(CFG)["minimum_independent_cases"], "split": "PROCESS_DIAGNOSTIC_ONLY",
        "worker_hash": sha(HERE / "audit.py"),
    }
    before = source_day_use()
    cap = read(CFG)["experiment_budget_per_utc_day"]
    if sum(before.values()) >= cap or find_review_hypothesis(ROOT, request, directory=FACTORY):
        raise ValueError("daily reservation unavailable or duplicate")
    write_json(OUT / "budget_preflight.json", {"known_utc_day_reservations": before, "cap": cap})
    attempt = register_review_proposal(ROOT, request, directory=FACTORY)
    claim = reserve_review_experiment(ROOT, attempt, directory=FACTORY)
    write_json(OUT / "claim.json", {"request": request, "reservation": claim, "proposal_id": attempt["proposal_id"]})
    result = {**evaluate(old_fill), "input_hash": request["input_hash"], "worker_hash": request["worker_hash"]}
    write_json(OUT / "result.json", record_review_experiment(ROOT, attempt, result, directory=FACTORY))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["seal", "run", "feedback", "verify"])
    main(parser.parse_args().phase)
