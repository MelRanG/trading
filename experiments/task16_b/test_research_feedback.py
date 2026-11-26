from copy import deepcopy
from datetime import datetime, timedelta

import pytest

from experiments.task16_b.evidence import ROOT, historical, memory, synthetic
from quant_harness.investment.research_feedback import PROPOSAL_FIELDS, bind_comment, decide
from quant_harness.investment.research_feedback_dispatch import dispatch, perform


def test_research_outcome_is_eligible_but_same_timestamp_is_not_decision_evidence():
    cases, _, _ = synthetic()
    case = cases[2]
    assert decide(case, [])["cause"] == "INFORMATION_MISSING"
    case["evidence"][0]["stage"] = "DECISION_INPUT"
    with pytest.raises(ValueError, match="post-decision"):
        decide(case, [])


def test_advisory_cannot_use_invented_citations_or_change_route():
    cases, _, _ = synthetic()
    case = cases[8]
    result = decide(case, [])
    candidate = {"case_id":case["case_id"],"evidence_ids":["E"],"interpretation":"Interpretation",
                 "competing_explanations":["Alternative"],
                 "proposal":{"route":"DISCLOSURE_PROVENANCE", **dict.fromkeys(PROPOSAL_FIELDS, "Detail")}}
    assert bind_comment(case,result,candidate)["proposal"]
    switched = deepcopy(candidate)
    switched["proposal"]["route"] = "PIT_EXPOSURE_FEASIBILITY"
    assert bind_comment(case,result,switched)["proposal"] is None
    candidate["evidence_ids"].append("unobserved")
    assert bind_comment(case,result,candidate)["status"] == "COMMENT_REJECTED"


def test_registered_prior_family_blocks_same_diagnostic_and_no_operating_directory():
    case = next(c for c in historical() if "diagnostic" in c)
    item = {"family":case["diagnostic"]["family"],"status":"INSUFFICIENT_EVIDENCE",
            "source_hash":"receipt","available_at":case["evaluation_as_of"]}
    assert decide(case,[*memory(),item])["action"]=="HOLD"
    with pytest.raises(ValueError, match="operating paths"):
        dispatch(ROOT, ROOT/"runtime/alpha_research_factory/task4",case,[],{},{})


def test_team2_worker_reuses_numeric_provenance(tmp_path):
    from hashlib import sha256
    folder = tmp_path/"runtime"
    folder.mkdir()
    raw = b'{"eps":2}'
    (folder/"filing.json").write_bytes(raw)
    fact = dict(source_path="runtime/filing.json",metric="EarningsPerShareDiluted",raw_value="2",
                value="2",multiplier=1,unit="PER_SHARE",currency="USD",basis="CFS",
                period_start="2024-01-01",period_end="2024-03-31",published="2024-05-01",
                source_hash=sha256(raw).hexdigest(),locator={"kind":"json","path":["eps"]})
    bundle={"route":"DISCLOSURE_PROVENANCE","payload":{"asof":"2024-05-02",
            "cases":[{"symbol":"TEST","facts":[fact]}]}}
    result=perform(tmp_path,bundle)
    assert result["verified_numeric_facts"]==1
    assert result["status"]=="INSUFFICIENT_EVIDENCE" and result["portfolio_runs"]==0
    fact["unit"]="CURRENCY"
    assert len(perform(tmp_path,bundle)["failures"])==1


def test_repeated_shortfall_requires_a_review_deadline_and_matched_evidence():
    cases, _, _ = synthetic()
    case = cases[1]
    assert decide(case, [])["action"] == "MAINTAIN"
    case["facts"]["repeated_shortfall"] = "E"
    result = decide(case, [])
    assert result["action"] == "HOLD"
    assert result["review"]["status"] == "DEADLINE_REQUIRED"
    assert "equal dates, capital, exposure and risk" in result["review"]["required_evidence"][0]
    assert "contribution dates and amounts" in result["review"]["required_evidence"][1]
    now = datetime.fromisoformat(case["evaluation_as_of"])
    case["review_due"] = (now + timedelta(days=1)).isoformat()
    assert decide(case, [])["review"]["status"] == "SCHEDULED"
    case["review_due"] = case["evaluation_as_of"]
    due = decide(case, [])
    assert due["review"]["status"] == "REVIEW_DUE"
    assert not due["capital_mutation"] and due["allowed_routes"] == []


@pytest.mark.parametrize(("interval", "action"), [
    ({}, "HOLD"), ({"lo": -.06, "hi": .01}, "HOLD"), ({"lo": -.06, "hi": -.01}, "REJECT"),
])
def test_negative_economics_requires_evidence_beyond_the_point_estimate(interval, action):
    cases, _, _ = synthetic()
    case = cases[4]
    case["metrics"]["net_vs_best_control"] = {"value": -.03, "evidence_id": "E", **interval}
    assert decide(case, [])["action"] == action


@pytest.mark.parametrize(("field", "value"), [
    ("data", "UNKNOWN"), ("mature", "false"), ("matched_ledger", "False"),
])
def test_evidence_gate_rejects_ambiguous_data_and_truthy_flags(field, value):
    cases, _, _ = synthetic()
    case = cases[8]
    case["gates"][field] = value
    with pytest.raises(ValueError, match="invalid evidence gates"):
        decide(case, [])


def test_diagnostic_requires_a_nonempty_receipt_binding():
    cases, _, _ = synthetic()
    case = cases[8]
    case["diagnostic"]["evidence_ids"] = []
    with pytest.raises(ValueError, match="unlinked diagnostic"):
        decide(case, [])


def test_dispatch_checks_actual_source_bytes_before_factory_registration(tmp_path):
    cases, _, _ = synthetic()
    case = cases[8]
    (tmp_path / "config").mkdir()
    (tmp_path / "config/task4_review_contract.json").write_text("{}")
    (tmp_path / "evidence.json").write_text('{"changed":true}')
    case["evidence"][0]["source"] = "evidence.json"
    candidate = {"case_id": case["case_id"], "evidence_ids": ["E"], "interpretation": "Evidence",
                 "competing_explanations": ["Alternative"],
                 "proposal": {"route": "DISCLOSURE_PROVENANCE", **dict.fromkeys(PROPOSAL_FIELDS, "Detail")}}
    out = tmp_path / "runtime/task16_b/diagnostic"
    with pytest.raises(ValueError, match="receipt missing or changed"):
        dispatch(tmp_path, out, case, [], candidate, {"route": "DISCLOSURE_PROVENANCE"})
    assert not out.exists()
