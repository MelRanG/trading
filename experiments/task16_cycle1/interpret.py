"""One existing Feedback relay call on scoped, completed result evidence."""
import argparse
import json

from experiments.task10.model_relay import Relay
from experiments.task13_h1.prepare_inputs import write_json
from experiments.task16_cycle1.run import MARKETS, OUT, read
from quant_harness.investment.research_feedback import bind_comment


def bind_saved(reply, markets, *, normalize=False):
    notes = json.loads(reply["choices"][0]["message"]["content"])["comments"]
    assert len(notes)==len({x["case_id"] for x in notes})==len(markets)
    indexed = {n["case_id"]:n for n in notes}
    checked = {}
    normalized = []
    for market in markets:
        old=read(OUT/f"{market}_feedback.json")
        key=old["case"]["case_id"]
        note = indexed[key]
        if normalize and isinstance(note.get("competing_explanations"), str):
            note = {**note, "competing_explanations":[note["competing_explanations"]]}
            normalized.append(market)
        checked[market]=bind_comment(old["case"],old["decision"],note)
    return checked, normalized


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rebind-saved", action="store_true")
    args = parser.parse_args()
    verdict = read(OUT/"result.json")["result"]["markets"]
    if args.rebind_saved:
        (response,) = (OUT/"feedback_model/review").glob("*.response.json")
        checked, normalized = bind_saved(read(response), verdict, normalize=True)
        write_json(OUT/"model_feedback_rebound.json",
                   {"source":response.name,"normalized_text_arrays":normalized,
                    "bound_advice":checked,"new_calls":0,"followup_executions":0})
        return
    inputs = []
    for market in MARKETS:
        if market not in verdict:
            continue
        old = read(OUT/f"{market}_feedback.json")
        values = verdict[market]
        inputs.append({"case_id":old["case"]["case_id"],"decision":old["decision"],
                       "E":{k:values[k] for k in ("primary","holm","half","gross_lift","passed")},
                       "C":{k:values[k] for k in ("lift_excluding_largest_five","largest_five")},
                       "history":[(r["family"],r["status"]) for r in old["history"]]})
    instructions = (
        "Interpret only these pre-computed Quant Harness results in Korean. One short JSON comment per case: "
        "return {comments:[{case_id,evidence_ids,interpretation,competing_explanations,proposal:null}]}. "
        "Refer only to E and C and their actual values. Explain competing economic and data explanations, "
        "whether to stop this frozen hypothesis and what evidence would justify reconsideration. "
        "Do not invent costs, recommendations, tasks or ETF allocation. No new variants. Tools disabled. Under 500 tokens.")
    body = {"messages":[{"role":"system","content":instructions},{"role":"user","content":json.dumps(inputs)}],
            "response_format":{"type":"json_object"}}
    try:
        reply = Relay(OUT/"feedback_model").call("review",body)
        checked, _ = bind_saved(reply, verdict)
        write_json(OUT/"model_feedback.json",{"status":"ACTUAL_CALL","model":reply["model"],"usage":reply["usage"],
                   "bound_advice":checked,"followup_executions":0})
    except (ValueError, KeyError, OSError, TypeError, AssertionError) as exc:
        write_json(OUT/"model_feedback.json",{"status":"MODEL_PATH_FAILED","reason":str(exc),
                   "deterministic_feedback_preserved":True,"followup_executions":0})


if __name__=="__main__":
    main()
