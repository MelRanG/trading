"""Replay evidence, decisions and saved model guidance without calls or side effects."""
import json

from experiments.task16_b.evidence import OUT
from experiments.task16_b.run import compare, metrics, read
from quant_harness.alpha_research_factory import find_review_hypothesis
from quant_harness.investment.research import digest
from quant_harness.investment.research_feedback import bind_comment
from quant_harness.investment.research_feedback_dispatch import file_hash
from experiments.task16_b.evidence import ROOT


def audit():
    inputs, rubric, cycle = (read(f"{p}.json") for p in ("inputs", "rubric", "cycle"))
    seal = read("seal.json")
    for key, filename in [("inputs","inputs.json"),("rubric","rubric.json")]:
        assert file_hash(OUT/filename)==seal[key]
    for key, filename in [("worker","run.py"),("decision","research_feedback.py"),
                          ("dispatch","research_feedback_dispatch.py")]:
        assert file_hash(OUT/"implementation_snapshot"/filename)==seal[key]
    for label, saved in [("development","development.json"),("evaluation","evaluation_result.json")]:
        recomputed, _ = compare(inputs,label,False)
        old = read(saved)["rows"]
        assert all((r["A"],r["B"],r["input_hash"]) == (s["A"],s["B"],s["input_hash"])
                   for r,s in zip(recomputed,old,strict=True))
    messages = list((OUT/"model_calls/review").glob("*.response.json"))
    assert len(messages)==1
    raw = json.loads(messages[0].read_bytes())["choices"][0]["message"]["content"]
    replies = {r["case_id"]:r for r in json.loads(raw)["comments"]}
    for row, case in zip(read("development.json")["rows"], inputs["development"], strict=True):
        assert bind_comment(case,row["B"],replies[case["case_id"]]) == row["advisory"]
    folder = OUT/"isolated_factory"
    request = cycle["request"]
    prior = find_review_hypothesis(ROOT, request, directory=folder)
    assert prior == cycle["attempt"]
    reservation = (folder/"experiment_reservations.jsonl").read_text().splitlines()
    assert len(reservation)==1 and json.loads(reservation[0])["attempt_id"]==prior["attempt_id"]
    bundle = json.loads((folder/(prior["attempt_id"]+".input.json")).read_bytes())
    assert digest(bundle)==request["input_hash"]==cycle["record"]["result"]["input_hash"]
    assert cycle["record"]["result"]["status"]=="INSUFFICIENT_EVIDENCE"
    assert digest(cycle["record"]["result"])==read("closed_loop.json")["factory_result_hash"]
    assert read("closed_loop.json")["decision"]["allowed_routes"]==[]
    m = read("evaluation_result.json")
    assert metrics(m["rows"],rubric["expected"])==m["metrics"]
    return {"A_B_recomputed": True, "grounded_model_reply_replayed": True,
            "duplicate_detected":True, "factory_reservations":1, "new_calls":0,
            "new_experiments":0, "metrics":m["metrics"]}


if __name__ == "__main__":
    print(json.dumps(audit(),ensure_ascii=False,indent=2))
