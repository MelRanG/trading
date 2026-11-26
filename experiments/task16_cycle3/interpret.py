"""Bind one existing review-relay interpretation to the policy data gate."""
import json

from experiments.task10.model_relay import Relay
from experiments.task13_h1.prepare_inputs import write_json
from experiments.task16_cycle3.audit import OUT, read
from quant_harness.investment.research_feedback import bind_comment


def main():
    artifact = read(OUT / "feedback.json")
    result = read(OUT / "result.json")["result"]
    packet = {
        "case_id": artifact["case"]["case_id"],
        "decision": artifact["decision"],
        "evidence": {key: result[key] for key in ("R4", "R5", "economics", "confirmed_auction_receipts_in_inputs")},
    }
    body = {
        "messages": [
            {"role": "system",
             "content": "Interpret the evidence for Quant Harness. Explain in Korean what flagged and unflagged "
             "simulation days mean for testing a five-session close exit. Discuss competing explanations "
             "and permission and evidence gates. Do not infer returns, allocate, or invent proposal. "
             "Return JSON keys case_id, evidence_ids (array ['E']), interpretation (string), "
             "competing_explanations (array of strings), proposal (null). Under 250 words."},
            {"role": "user", "content": json.dumps(packet)},
        ],
        "response_format": {"type": "json_object"},
    }
    response = Relay(OUT / "feedback_model").call("review", body)
    raw = json.loads(response["choices"][0]["message"]["content"])
    advice = bind_comment(artifact["case"], artifact["decision"], raw)
    write_json(OUT / "model_feedback.json", {"model": response["model"], "usage": response["usage"], "advice": advice})


if __name__ == "__main__":
    main()
