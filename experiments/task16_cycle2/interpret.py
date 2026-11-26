"""One outcome-only, non-authoritative review call via the existing relay."""
import json
from experiments.task10.model_relay import Relay
from experiments.task13_h1.prepare_inputs import write_json
from experiments.task16_cycle2.run import OUT, read
from quant_harness.investment.research_feedback import bind_comment


def main():
    artifact=read(OUT/"feedback.json")
    result=read(OUT/"result.json")["result"]
    evidence={k:result[k] for k in ("primary","family49","gross_lift","years","lift_excluding_five","status")}
    packet={"case_id":artifact["case"]["case_id"],"E":evidence,
            "decision":artifact["decision"]["action"],
            "options":[
                "Distinct native peer-correlation candidate: approximate missing peers; need strict dated complete-peer design, one-per-day Factory diagnostic cap already consumed.",
                "Two observational fill/cost audits: R5 sequence incomplete, no separate Task15 economic approval. R1 no incremental value over lower-frequency control."
            ]}
    body={"messages":[{"role":"system","content":
                       "Review supplied evidence only. In Korean, distinguish the single hypothesis from the whole cycle. "
                       "Explain conflicting tail/primary evidence and estimate research value only qualitatively. Do not generate another candidate or approve anything. "
                       "No tools, no new facts. Output JSON {case_id,evidence_ids:[\"E\"],interpretation:string,competing_explanations:[string],proposal:null}, under 320 tokens."},
                      {"role":"user","content":json.dumps(packet)}],
          "response_format":{"type":"json_object"}}
    try:
        reply=Relay(OUT/"feedback_model").call("review",body)
        raw=json.loads(reply["choices"][0]["message"]["content"])
        normalized=isinstance(raw.get("competing_explanations"),str)
        if normalized:
            raw={**raw,"competing_explanations":[raw["competing_explanations"]]}
        advice=bind_comment(artifact["case"],artifact["decision"],raw)
        write_json(OUT/"model_feedback.json",{"call":"ACTUAL","model":reply["model"],"usage":reply["usage"],
                   "mechanical_string_to_array":normalized,"advice":advice})
    except (OSError,ValueError,KeyError,TypeError) as exc:
        write_json(OUT/"model_feedback.json",{"call":"FAILED_OR_REJECTED","reason":str(exc),
                   "deterministic_feedback_preserved":True})


if __name__=="__main__":
    main()
