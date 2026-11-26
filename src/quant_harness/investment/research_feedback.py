"""Offline research interpretation and proposal admission."""
from datetime import datetime
import math

from .research import digest

KINDS = {"SIGNAL", "POLICY", "INVESTMENT", "SOURCE", "SYSTEM"}
ACTIONS = {"MAINTAIN", "MONITOR", "REJECT", "HOLD", "REPAIR", "PROPOSE"}
ROUTES = {
    "PIT_EXPOSURE_FEASIBILITY": ("TEAM3", "POLICY", "PROCESS_DIAGNOSTIC_ONLY"),
    "DISCLOSURE_PROVENANCE": ("TEAM2", "SOURCE", "PROCESS_DIAGNOSTIC_ONLY"),
}
# Worker admission keys describe the diagnostic, not authorization of the strategy.


def timestamp(value):
    instant = datetime.fromisoformat(value)
    if instant.utcoffset() is None:
        raise ValueError("point-in-time receipt needs a timezone")
    return instant


def validate(case, history):
    if case["kind"] not in KINDS or not case["mechanism"] or not case["baseline"]:
        raise ValueError("unknown research contract")
    cutoff = timestamp(case["evaluation_as_of"])
    if timestamp(case["decision_as_of"]) > cutoff:
        raise ValueError("evaluation precedes decision")
    gates = case["gates"]
    if (gates.get("data") not in {"ELIGIBLE", "BLOCKED"}
            or any(type(gates.get(k)) is not bool for k in ("mature", "matched_ledger"))):
        raise ValueError("invalid evidence gates")
    if not isinstance(case.get("reevaluation"), str) or not case["reevaluation"].strip():
        raise ValueError("missing reevaluation condition")
    available = {}
    for fact in case["evidence"]:
        identity = fact["id"]
        observed = timestamp(fact["available_at"])
        if identity in available or not fact["source"] or not fact["source_hash"] or observed > cutoff:
            raise ValueError("duplicate or unavailable evidence")
        if fact["stage"] not in {"DECISION_INPUT", "RESEARCH_OUTCOME", "INVENTORY"}:
            raise ValueError("unknown stage")
        if fact["stage"] == "DECISION_INPUT" and observed > timestamp(case["decision_as_of"]):
            raise ValueError("post-decision evidence in decision input")
        available[identity] = fact
    metrics = case.get("metrics", {})
    for value in metrics.values():
        if value.get("evidence_id") not in available:
            raise ValueError("metric lacks receipt")
        for k in ("value", "lo", "hi"):
            if k in value and (type(value[k]) not in (int, float) or not math.isfinite(value[k])):
                raise ValueError("nonfinite metric")
        if ("lo" in value) != ("hi" in value) or (
                "lo" in value and not value["lo"] <= value["value"] <= value["hi"]):
            raise ValueError("invalid uncertainty interval")
    for item in history:
        if timestamp(item["available_at"]) > cutoff or not item["source_hash"]:
            raise ValueError("unavailable memory")
    if case.get("diagnostic"):
        refs = case["diagnostic"]["evidence_ids"]
        if not refs or not set(refs) <= available.keys():
            raise ValueError("unlinked diagnostic")
    if "repeated_shortfall" in case.get("facts", {}):
        if case["facts"]["repeated_shortfall"] not in available:
            raise ValueError("repeated shortfall lacks receipt")
        if case.get("review_due") is not None:
            timestamp(case["review_due"])
    return available


def decide(case, history):
    """Evidence gates applied before qualitative advisory interpretation."""
    evidence = validate(case, history)
    facts = case.get("facts", {})
    gates = case["gates"]
    metrics = case.get("metrics", {})
    secondary = []
    reevaluate = case["reevaluation"]
    allowed = []
    repeated = facts.get("repeated_shortfall") in evidence
    if facts.get("verified_defect") in evidence:
        action, cause = "REPAIR", "DATA_ERROR"
        rule = "Verified technical defect; require identical-input reconciliation before policy research."
    elif gates["data"] == "BLOCKED":
        action, cause = "HOLD", "INFORMATION_MISSING"
        rule = "Missing or ineligible inputs; economics and sign remain undetermined."
    elif any(h["family"] == case["family"] and h["status"] in {"REJECT", "DUPLICATE"} for h in history):
        action, cause = "REJECT", "DUPLICATE"
        rule = "Fixed rejected or duplicate family remains closed under the same specification."
    elif case["kind"] == "INVESTMENT" and not gates["matched_ledger"]:
        action, cause = "HOLD", "UNDETERMINED"
        rule = "Matched ledger and decision-time counterfactual are needed for loss attribution."
    elif not repeated and facts.get("within_budgeted_variability") in evidence and gates["matched_ledger"]:
        action, cause = "MAINTAIN", "STOCHASTIC_LOSS"
        rule = "One ordinary fluctuation with no established breach needs observation."
    elif (case["kind"] == "SIGNAL" and gates["mature"] and
          metrics.get("increment", {}).get("value", 0) < 0 and metrics.get("increment", {}).get("hi", 0) < 0):
        action, cause = "REJECT", "NO_INCREMENTAL_SIGNAL"
        rule = "Fixed signal lost to the paired baseline over the measured scope."
    elif (case["kind"] == "POLICY" and gates["matched_ledger"] and gates["mature"] and
          metrics.get("net_vs_best_control", {}).get("value", 0) < 0 and
          metrics.get("net_vs_best_control", {}).get("hi", 0) < 0):
        action, cause = "REJECT", "NO_INCREMENTAL_ECONOMIC_VALUE"
        rule = "Paired economic comparison favors the stronger control in this sample."
    elif (case["kind"] == "POLICY" and gates["mature"] and gates["matched_ledger"] and
          metrics.get("net_vs_best_control", {}).get("lo", 0) > 0):
        action, cause = "HOLD", "PROMISING_UNAPPROVED"
        rule = "Positive paired economics merits independent confirmation under approval."
    elif case.get("diagnostic") and gates["data"] == "ELIGIBLE":
        offer = case["diagnostic"]
        blocked = any(h["family"] == offer["family"] for h in history)
        match = ROUTES.get(offer["route"])
        if match and match[1] == case["kind"] and not blocked:
            allowed.append(offer["route"])
        action, cause = ("PROPOSE", "UNDETERMINED") if allowed else ("HOLD", "UNDETERMINED")
        rule = "Bounded data/feasibility diagnostic can distinguish competing explanations."
    elif metrics.get("increment"):
        action, cause = "HOLD", "UNDETERMINED"
        rule = "No stable paired increment; no tuning on the same sample."
        if metrics.get("overlap", {}).get("value", 0):
            secondary.append("SHARED_SIGNAL_INFORMATION_POSSIBLE")
        if facts.get("concentration") in evidence:
            secondary.append("CONCENTRATION_SENSITIVITY")
    else:
        action, cause = "HOLD", "UNDETERMINED"
        rule = "Independent evidence is insufficient across the relevant economic alternatives."
    economics = "PAIRED_OBSERVATION" if gates["matched_ledger"] else "NOT_EVALUATED"
    result = dict(case_id=case["case_id"], input_hash=digest(case), action=action, cause=cause,
                rule=rule, secondary=secondary, reevaluate=reevaluate, economics=economics,
                allowed_routes=allowed, evidence_ids=list(evidence), model_authority="ADVISORY",
                capital_mutation=False, task15_approved=False, promotion_approved=False)
    if repeated:
        due = case.get("review_due")
        status = ("DEADLINE_REQUIRED" if due is None else
                  "REVIEW_DUE" if timestamp(due) <= timestamp(case["evaluation_as_of"]) else "SCHEDULED")
        result["review"] = {
            "status": status, "due": due, "shortfall_evidence_id": facts["repeated_shortfall"],
            "required_evidence": [
                "Mature paired net returns on equal dates, capital, exposure and risk, including applicable alternatives.",
                "Matching contribution dates and amounts for any ETF savings-plan comparison.",
                reevaluate,
            ],
        }
    return result


PROPOSAL_FIELDS = ("opportunity", "alternative_explanation", "hypothesis", "novelty", "data_plan",
                   "baseline", "verification", "failure", "cost_value", "restart")


def bind_comment(case, decision, comment):
    """Store grounded prose, but grant authority only through deterministic gates."""
    if (not isinstance(comment, dict) or not isinstance(comment.get("evidence_ids"), list)
            or comment.get("case_id") != case["case_id"] or not comment["evidence_ids"]
            or not all(isinstance(x, str) for x in comment["evidence_ids"])
            or not set(comment["evidence_ids"]) <= set(decision["evidence_ids"])):
        return {"status": "COMMENT_REJECTED", "proposal": None}
    interpretation = comment.get("interpretation")
    alternatives = comment.get("competing_explanations")
    if (not isinstance(interpretation, str) or not 0 < len(interpretation.strip()) <= 1800
            or not isinstance(alternatives, list) or not 1 <= len(alternatives) <= 4
            or not all(isinstance(x, str) and 0 < len(x.strip()) <= 600 for x in alternatives)):
        return {"status": "COMMENT_REJECTED", "proposal": None}
    proposal = comment.get("proposal")
    accepted = (isinstance(proposal, dict) and isinstance(proposal.get("route"), str)
                and proposal["route"] in decision["allowed_routes"]
                and set(proposal) == {"route", *PROPOSAL_FIELDS}
                and all(isinstance(proposal[k], str) and 0 < len(proposal[k].strip()) <= 600 for k in PROPOSAL_FIELDS)
                and set(case.get("diagnostic", {}).get("evidence_ids", [])) <= set(comment["evidence_ids"]))
    return {"status": "ADVISORY_GROUNDED_REFERENCES", "interpretation": interpretation,
            "competing_explanations": alternatives, "evidence_ids": comment["evidence_ids"],
            "model_proposal_rejected": proposal is not None and not accepted,
            "proposal": proposal if accepted else None}
