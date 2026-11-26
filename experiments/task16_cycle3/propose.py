"""Generate candidates using separate Team2 and original Team3 planner calls."""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import types

from experiments.task8b.model_relay import Relay
from experiments.task13_h1.prepare_inputs import sha, write_json

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "runtime/task16_cycle3"
NATIVE = ROOT.parent / "quant-diligence/quanta-original"
CONTEXT = (
    "US176 and KR119 exposed survivor daily OHLCV, 2022-07 through 2024-12. No historical depth, ticks, "
    "intraday or complete point-in-time listing/delisting. 84 eligible US earnings cases, no robust EPS "
    "increment or historical consensus. KR DART insufficient. R4/R5 KR nominal execution ledgers, "
    "benchmark and sessions available, but some auction fills unverifiable. ETF benchmark only. "
    "Already tried: MOM63 historical only, FLOW5/Q0/Q1/RD_SMALL/H1/R1 no increment, "
    "ST/PTHxTO blocked, MA20 regime distance/EPS inconclusive or blocked, Cycle1 gap absorption no increment, "
    "Cycle2 60-day skew HOLD; correlation rewiring requires complete dated peers. "
    "Existing Factory authorizes one process diagnostic and no unapproved economic replay. "
    "Frozen policy comparisons can be proposed for separate approval. No new feeds, grids, or live use."
)


def respond(scope, system, user):
    request = {
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "response_format": {"type": "json_object"},
    }
    response = Relay(OUT / "model").call(scope, request)
    return response["choices"][0]["message"]["content"]


def team2():
    raw = respond(
        "analysis",
        "You are Quant Harness Team2. Generate two independently verifiable equity research directions: "
        "one stock-selection idea grounded in corporate or industry economics, one narrow trading or sizing "
        "policy using existing evidence. Be concrete about information date, control, required evidence, "
        "and whether data or economy approval blocks testing. Propose tests only, no measured results. "
        "Return JSON with candidates list of two objects with id, type, mechanism, rule, control, and gate. "
        "No parameter search. Max 450 words.",
        CONTEXT,
    )
    candidates = json.loads(raw)["candidates"]
    if len(candidates) != 2:
        raise ValueError("Team2 candidate bound")
    write_json(OUT / "team2.json", {"candidates": candidates})


def team3():
    from unittest.mock import patch

    planner_path = NATIVE / "quantaalpha/pipeline/planning.py"
    prompt_path = planner_path.parent / "prompts/planning_prompts.yaml"
    revision = subprocess.check_output(["git", "-C", str(NATIVE), "rev-parse", "HEAD"], text=True).strip()
    if subprocess.check_output(["git", "-C", str(NATIVE), "status", "--porcelain"]):
        raise ValueError("dirty original")
    spec = importlib.util.spec_from_file_location("cycle3_native_planning", planner_path)
    planner = importlib.util.module_from_spec(spec)
    transport = types.ModuleType("quantaalpha.llm.client")

    class Backend:
        def build_messages_and_create_chat_completion(self, *, user_prompt, system_prompt, json_mode):
            return respond("discovery", system_prompt, user_prompt)

    transport.APIBackend = Backend
    log_adapter = types.ModuleType("quantaalpha.log")
    import logging
    log_adapter.logger = logging.getLogger("quantaalpha")
    # Only transport and logging dependencies are adapted. The planner, prompt
    # rendering, model invocation point and output parser are upstream code.
    with patch.dict(sys.modules, {"quantaalpha.llm.client": transport, "quantaalpha.log": log_adapter}):
        spec.loader.exec_module(planner)
        directions = planner.generate_parallel_directions(
            CONTEXT + "\nPropose one price/volume selection hypothesis and one entry/exit/sizing policy. "
            "Specify one measurable formula or rule, comparison, and blocker each, briefly. "
            "Use only stated evidence and avoid prior mechanisms or results.",
            2, prompt_path, max_attempts=1, allow_fallback=False,
        )
    write_json(OUT / "team3.json", {
        "revision": revision, "planner_sha256": sha(planner_path), "prompts_sha256": sha(prompt_path),
        "directions": directions, "realization": "ORIGINAL_PLANNER_TRANSPORT_ADAPTER", "max_tries": 1,
    })
    if len(directions) != 2:
        raise ValueError("native planner did not produce two candidates")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("role", choices=["team2", "team3"])
    {"team2": team2, "team3": team3}[parser.parse_args().role]()
