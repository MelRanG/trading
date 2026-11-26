"""Use a single existing research relay call to compare native candidates and policy ideas."""
import json
from pathlib import Path
from experiments.task8b.model_relay import Relay
from experiments.task13_h1.prepare_inputs import write_json

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/"runtime/task16_cycle2"


def main():
    context = {
        "daily": "H1/R0 adjusted stocks only 2022-07 to 2024-12 US176/KR119; audited price masks. Exposed survivor, no historical intraday/PIT universe/consensus; no new feeds.",
        "event_data": "US 8-K past 84 eligible EPS cases, out-of-fit EPS YoY mixed; zero profit crossings in eval; no verified CEO corpus. KR DART insufficient.",
        "policy_data": "R4/R5 existing MOM63 nominal fills, targets, costs, NAV with path limits. R1 rank buffer lost to low-turnover; R5 causality/pending fills imperfect. No Task15 approval for new economic replay; ETF benchmark only.",
        "already_tested": "FLOW5/Q0/Q1/RD_SMALL/H1/MA20/D1/C4 not established. ST/PTHxTO blocked. Cycle1 signed opening-gap absorption no increment, absolute same family not run. No retuning or ETF sleeve.",
        "native_candidates": [
            {"id":"academic_retskew","definition":"Vibe original negative 60-day daily simple return sample skew, cross-section z-score; US supported.",
             "question":"Lottery-demand premium beyond MAX21, return, total and downside variation. This is a proxy, not conditional coskewness."},
            {"id":"academic_corr_rewire","definition":"Vibe original negative mean absolute change of peer correlations, trailing 20 vs preceding 120 days; US supported.",
             "constraint":"Native accepts 90% window coverage and approximates incomplete correlation by zero centered contributions. Strict complete-peer alternative is separate; no missing returns may be silently imputed.",
             "question":"Exposure instability vs plain beta/volatility; native author calls structural risk lens, not validated return forecast."},
        ],
        "budget":"One same-day Factory diagnostic; analyze value of a second different family but no budget override."
    }
    request = {
        "messages":[
            {"role":"system","content":"You are Team2 research review and policy proposal for Quant Harness. Use only these facts. Compare both native Team3 candidates before labels. Supply two distinct stock-only policy proposals within the evidence, with counterfactual, mechanism, matched costs/risk, data gate, falsification and approval blocker. Rank all four by research value and choose one feasible diagnostic if possible. No returns, ETF positions, new data downloads, parameter search or duplicate families. Output JSON {native_review:[...],policy_candidates:[...],ranking:[...],selection:string,reason:string}. Under 750 tokens."},
            {"role":"user","content":json.dumps(context)}],
        "response_format":{"type":"json_object"},
    }
    write_json(OUT/"context.json",context)
    result=Relay(OUT/"model_calls").call("analysis",request)
    content=json.loads(result["choices"][0]["message"]["content"])
    assert len(content["policy_candidates"])==2 and len(content["native_review"])==2
    write_json(OUT/"TEAM2.json",{"model":result["model"],"usage":result["usage"],"output":content})


if __name__=="__main__":
    main()
