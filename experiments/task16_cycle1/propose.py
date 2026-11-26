"""Run separate tool-free research prompts using the existing Task8b relay."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path

from experiments.task8b.model_relay import Relay
from experiments.task16_b.evidence import memory

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "runtime/task16_cycle1"


def generate(role, scope, mandate, context):
    prompt = ("You are the isolated " + role + " proposal pass for Quant Harness. "
              "Independently propose exactly two economically distinct single-equity research candidates. "
              "Give each a short English id, mechanism, exact formula and sign, horizon (5 or 20 exchange sessions if a signal), "
              "baselines, data, clock, falsification, key risk and why it differs from the failed history. "
              "Do not use an ETF position, analyst consensus acquisition, tuning, additional databases or trading. "
              "At least one candidate must be immediately testable with the provided daily OHLCV only and no external feed. "
              "For that candidate use a small vectorized expression with fixed integer windows, float math and no training; "
              "it should rank equities and differ economically from plain return or a volume confirmation of momentum. "
              "No outcome values available. No claims on future performance. Return JSON {candidates:[...]} only. "
              "Keep the whole response within 850 tokens. " + mandate)
    body = {"messages":[{"role":"system","content":prompt},
                        {"role":"user","content":json.dumps(context,ensure_ascii=False)}],
            "response_format":{"type":"json_object"}}
    response = Relay(OUT/"model_calls").call(scope,body)
    content = json.loads(response["choices"][0]["message"]["content"])
    assert isinstance(content["candidates"],list) and len(content["candidates"])==2
    return {"role":role,"relay_scope":scope,"usage":response["usage"],"model":response["model"],**content}


def main():
    context = {"inputs": [
        "H1 SHA-verified 176 US and 119 KR single-equity adjusted daily open, high, low, close, volume from July 2022 to December 2024; R0 quality masks, survivor snapshot. No robust sector vintage.",
        "US original 8-K filing and GAAP EPS documents (300 targets, 136 literal EPS, 84 eligible prior EPS study events). B2 limited guides. KR few DART records. No defensible historical consensus.",
        "Historical R4/R5 daily trade and exposure ledgers on survivor sample; no approval for new realized economic policy comparisons. Signal-only Task13/14 allowed, same open-to-open labels and matched price baselines.",
        "No verified historical broad intraday tape, live WebSocket is separate. Early period and 2024 exposed, no new holdout."],
        "memory": [{"family":h["family"],"status":h["status"],"scope":h["scope"]} for h in memory()],
        "more_history":["R0 MA20 conditional distance tested with older signed efficiency x market state; do not repeat.",
                        "D1 gradual positive-return frequency/momentum and Q0 Q1 reversal/volume momentum are related; distinguish economically.",
                        "R5 stress/re-entry is exposed; prior ETF vacant slot proposal excluded.",
                        "For the feasible rank candidate, early feasibility must use only non-outcome checks; 2024 daily matched validation, then stop on no increment."]}
    with (OUT/"context.json").open("x") as f:
        json.dump(context,f,ensure_ascii=False,indent=2)
    roles = [("TEAM2","analysis","Start from issuer behavior, industry or market economics. Consider which existing public data prove availability."),
             ("TEAM3","discovery","Start independently from quant implementation. Look for an economically interpretable signal beyond known price controls.")]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(generate,*role,context) for role in roles]
        for role, future in zip(roles,futures):
            with (OUT/f"{role[0]}.json").open("x") as f:
                json.dump(future.result(),f,ensure_ascii=False,indent=2)


if __name__=="__main__":
    main()
