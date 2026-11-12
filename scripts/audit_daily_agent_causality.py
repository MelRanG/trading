"""Output-consumption probes only: no execution replay or performance experiment.

Mutations are temporary in-memory injections, never deployable model candidates.
The full historical warmup is retained; comparisons use the fixed run2 window.
"""
from __future__ import annotations

from contextlib import ExitStack
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import socket
import sys
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quant_harness.v104_end_to_end_causal_challenger_audit import adapter
from quant_harness.v100_strategy_agent.policy import _target_hash
from quant_harness import paper_decision_runtime as paper

START, END = "2021-10-13", "2026-07-31"
MODELS = ("V69_PARENT", "V79_NO63_VOL_GUARD")
PROBES = ("UniverseAgent", "MarketRegimeAgent", "SectorThemeAgent", "CandidateSelectionAgent", "StrategyAgent", "PainSupplyAgent")
SOURCES = {
    "UniverseAgent": "src/quant_harness/v104_end_to_end_causal_challenger_audit/adapter.py:build_candidate_ledgers; f69/f79 eligible and universe_gate outputs",
    "MarketRegimeAgent": "src/quant_harness/v104_end_to_end_causal_challenger_audit/adapter.py:build_candidate_ledgers; risk_on -> f69 benchmark_trend (not V79 sleeve)",
    "SectorThemeAgent": "src/quant_harness/v98_candidate_selection_agent/policy.py:build_sector_representative_panel; merged selector helper, no standalone dispatch",
    "CandidateSelectionAgent": "src/quant_harness/v104_end_to_end_causal_challenger_audit/adapter.py:build_candidate_ledgers; selection69/79 -> build_v69/v79_target_ledger",
    "StrategyAgent": "src/quant_harness/paper_decision_runtime.py:_build_strategy_preview_cached; ledger target_weights_json -> preview targets",
    "PainSupplyAgent": "src/quant_harness/v102_market_evidence_agent/policy.py:apply_evidence_policy; MARKET_EVIDENCE_DIAGNOSTIC_ONLY effective=raw_targets",
    "SentimentNewsAgent": "src/quant_harness/v104_end_to_end_causal_challenger_audit/adapter.py:build_candidate_ledgers; no news argument/consumer",
    "RiskExecutionAgent": "src/quant_harness/paper_decision_runtime.py:build_intent_previews; synthetic account, registered V101 policy output intervention, no fills",
    "ReviewFeedbackAgent": "src/quant_harness/v103_review_feedback_agent/engine.py; capital_authority=NONE; not imported by Daily adapter",
}


def _forbidden(*args, **kwargs):
    raise RuntimeError("DB, network and execution replay are forbidden in this audit")


def source_hashes(root: Path) -> dict:
    paths = {source.split(":", 1)[0].split(";", 1)[0] for source in SOURCES.values()}
    paths.update({"src/quant_harness/v100_strategy_agent/policy.py",
                  "src/quant_harness/v69_dynamic_theme_leadership/engine.py",
                  "src/quant_harness/v79_generic_trend_sleeve/engine.py",
                  "src/quant_harness/v94_universe_agent/engine.py",
                  "src/quant_harness/v94_universe_agent/policy.py",
                  "src/quant_harness/v95_market_regime_agent/policy.py"})
    paths.add("src/quant_harness/v101_risk_execution_agent/engine.py")
    return {path: sha256((root / path).read_bytes()).hexdigest() for path in sorted(paths)}


def safety_guards(stack: ExitStack) -> None:
    import psycopg
    import sqlite3
    from quant_harness import paper_execution_runtime
    stack.enter_context(patch.object(psycopg, "connect", _forbidden))
    stack.enter_context(patch.object(sqlite3, "connect", _forbidden))
    stack.enter_context(patch.object(paper_execution_runtime, "run_paper_execution_cycle", _forbidden))
    stack.enter_context(patch.object(paper_execution_runtime, "execute_paper_order", _forbidden))
    stack.enter_context(patch.object(adapter, "replay_candidate", _forbidden))
    stack.enter_context(patch.object(adapter.v101, "replay", _forbidden))
    stack.enter_context(patch.object(socket, "create_connection", _forbidden))
    stack.enter_context(patch.object(socket.socket, "connect", _forbidden))
    stack.enter_context(patch.object(socket.socket, "connect_ex", _forbidden))


def perturb_strategy_output(frame: pd.DataFrame) -> pd.DataFrame:
    """Transfer 5pp between existing symbols, retaining sum=1 and <=90% cap."""
    result = frame.copy(deep=True)
    for idx, row in result.iterrows():
        weights = json.loads(row["target_weights_json"])
        positive = sorted((float(w), t) for t, w in weights.items() if float(w) > 0)
        if len(positive) < 2 or max(weights.values()) > 0.90:
            continue
        low, high = positive[0][1], positive[-1][1]
        delta = min(0.05, float(weights[high]) / 2, 0.90 - float(weights[low]))
        weights[high] -= delta
        weights[low] += delta
        result.at[idx, "target_weights_json"] = json.dumps(weights, sort_keys=True)
        result.at[idx, "target_hash"] = _target_hash(weights)
    return result


def _window(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["date"] = pd.to_datetime(result["date"])
    if result["date"].isna().any() or result["date"].duplicated().any():
        raise ValueError("invalid or duplicate output dates")
    return result.set_index("date").sort_index().loc[START:END]


def _contract_counts(built: dict, changed_dates: pd.Index) -> dict:
    """Only weight/selection gate classification; NOT an execution approval."""
    ledger, selection = _window(built["ledger"]), _window(built["selection"])
    counts = {"WITHIN_WEIGHT_CAP_ONLY": 0, "HOLD_ONLY_UNSELECTED_OVER_CAP": 0,
              "REJECT_SELECTED_OVER_CAP": 0, "INVALID_WEIGHT_SUM": 0}
    for date in changed_dates:
        weights = json.loads(ledger.loc[date, "target_weights_json"])
        values = [float(v) for v in weights.values()]
        if not values or any(not pd.notna(v) or v < 0 for v in values) or abs(sum(values) - 1) > 1e-9:
            counts["INVALID_WEIGHT_SUM"] += 1
            continue
        selected_row = selection.loc[date]
        selected = any(column in selected_row and pd.notna(selected_row[column])
                       for column in ("leader_ticker", "sleeve_ticker", "top_candidate_ticker"))
        key = ("REJECT_SELECTED_OVER_CAP" if selected else "HOLD_ONLY_UNSELECTED_OVER_CAP") if max(values) > .90 else "WITHIN_WEIGHT_CAP_ONLY"
        counts[key] += 1
    return counts


def compare_outputs(baseline: dict, mutated: dict, *, agent: str, output_changed: bool) -> dict:
    before, after = _window(baseline["ledger"]), _window(mutated["ledger"])
    if before.empty or not before.index.equals(after.index):
        raise ValueError("empty or non-identical comparison dates")
    for frame in (before, after):
        expected = frame["target_weights_json"].map(lambda value: _target_hash(json.loads(value)))
        if not expected.eq(frame["target_hash"]).all():
            raise ValueError("target hash does not bind target weights")
    changed_dates = before.index[before["target_hash"].ne(after["target_hash"])]
    if len(changed_dates) and not output_changed:
        raise ValueError("target changed without an observed output intervention")
    negative_control = agent == "PainSupplyAgent"
    if negative_control and len(changed_dates):
        raise ValueError("diagnostic-only evidence unexpectedly changed targets")
    status = ("NOT_EXERCISED" if not output_changed else
              "NEGATIVE_CONTROL_CONFIRMED" if negative_control else
              "TARGET_CAUSAL_OBSERVED" if len(changed_dates) else "NO_TARGET_EFFECT_OBSERVED")
    return {"agent": agent, "status": status, "output_changed": output_changed,
            "comparison_days": len(before), "target_hash_changed_days": len(changed_dates),
            "changed_date_examples": [str(date.date()) for date in changed_dates[:3]],
            "changed_target_gate_classification": _contract_counts(mutated, changed_dates),
            "gate_classification_scope": "WEIGHT_AND_SELECTION_ONLY_NOT_EXECUTION_APPROVAL",
            "signed_paper_preview_effect": "NOT_TESTED",
            "operational_intent_and_fill_effect": "NOT_TESTED", "cost_adjusted_incremental_utility": "NOT_MEASURED",
            "source": SOURCES[agent]}


def probe(root: Path, spec, baseline: dict, agent: str) -> dict:
    if agent not in PROBES:
        raise ValueError("unknown output probe")
    observed = {"changed": False}
    with ExitStack() as stack:
        if agent in {"UniverseAgent", "PainSupplyAgent"}:
            original = adapter._runtime_context
            def context(*args, **kwargs):
                result = deepcopy(original(*args, **kwargs))
                if agent == "UniverseAgent":
                    for name in ("f69", "f79"):
                        features = result[name]
                        observed["changed"] |= bool(features["eligible"].any().any())
                        features["eligible"] = features["eligible"] & False
                        features["universe_gate"]["gate"] = features["universe_gate"]["gate"] & False
                else:
                    flow = result["flow"]
                    observed["changed"] |= not flow.empty
                    flow["flow_risk"] = ~flow["flow_risk"].astype(bool)
                return result
            stack.enter_context(patch.object(adapter, "_runtime_context", context))
        elif agent == "MarketRegimeAgent":
            original = adapter.build_market_regime_panel
            def regime(*args, **kwargs):
                result = deepcopy(original(*args, **kwargs))
                observed["changed"] |= not result["risk_on"].empty
                result["risk_on"] = ~result["risk_on"].astype(bool)
                return result
            stack.enter_context(patch.object(adapter, "build_market_regime_panel", regime))
        elif agent == "SectorThemeAgent":
            for owner in (adapter.v69, adapter.v79):
                original = owner.build_sector_representative_panel
                def sector(*args, _original=original, **kwargs):
                    result = _original(*args, **kwargs).copy(deep=True)
                    if "representative_ticker" in result:
                        observed["changed"] |= bool(result["representative_ticker"].notna().any())
                        result["representative_ticker"] = None
                    return result
                stack.enter_context(patch.object(owner, "build_sector_representative_panel", sector))
        else:
            targets = ((adapter.v69, "select_dynamic_leader"), (adapter.v79, "select_persistent_trend_leader")) if agent == "CandidateSelectionAgent" else (
                (adapter, "build_v69_target_ledger"), (adapter, "build_v79_target_ledger"))
            for owner, name in targets:
                original = getattr(owner, name)
                def transform(*args, _original=original, **kwargs):
                    before = _original(*args, **kwargs)
                    after = before.copy(deep=True)
                    if agent == "CandidateSelectionAgent":
                        for column in ("leader_ticker", "sleeve_ticker", "top_candidate_ticker"):
                            if column in after:
                                after[column] = None
                    else:
                        after = perturb_strategy_output(after)
                    observed["changed"] |= not before.equals(after)
                    return after
                stack.enter_context(patch.object(owner, name, transform))
        mutated = adapter.build_candidate_ledgers(root, spec, use_common_cutoff=True)
    return compare_outputs(baseline, mutated, agent=agent, output_changed=observed["changed"])


def probe_risk_preview(root: Path, spec, preview: dict) -> dict:
    """Consume a genuine signed preview, but never submit or simulate fills.

    The empty synthetic account deliberately has drift from the approved
    target. Raising the loaded policy's band to 1 is a wiring intervention,
    not a registered candidate, strategy recommendation, or performance test.
    """
    account = {"paper_account_id": paper.PAPER_ACCOUNT_ID, "status": "ACTIVE",
               "cash_krw": Decimal("10000000"), "positions": {},
               "previous_target_hash": preview["target_hash"], "execution_pending": False}
    before, changed, held = (deepcopy(preview) for _ in range(3))
    baseline = paper.build_intent_previews(before, deepcopy(account))
    original = paper.v101._policy
    calls = []
    def policy(policy_root, policy_id):
        loaded = original(policy_root, policy_id)
        if Path(policy_root).resolve() != root.resolve() or policy_id != spec.execution_policy:
            raise ValueError("unexpected execution policy consumption")
        calls.append(policy_id)
        return replace(loaded, v69_rebalance_band=1.0, v79_rebalance_band=1.0)
    with patch.object(paper.v101, "_policy", policy):
        mutated = paper.build_intent_previews(changed, deepcopy(account))
    hold_account = {**account, "status": "HOLD_ONLY"}
    hold_intents = paper.build_intent_previews(held, hold_account)
    observed = bool(calls and baseline and not mutated
                    and changed.get("decision_status") == "NO_REBALANCE_WITHIN_REGISTERED_BAND")
    hold_observed = bool(hold_intents and all(row["authority_status"] == "HOLD_ONLY" for row in hold_intents))
    if baseline and not all(row["authority_status"] == "PREVIEW_ONLY" for row in baseline):
        raise ValueError("baseline synthetic intent unexpectedly blocked")
    return {"agent": "RiskExecutionAgent", "status": "INTENT_POLICY_CAUSAL_OBSERVED" if observed else "NOT_EXERCISED",
            "source": SOURCES["RiskExecutionAgent"], "probe_date": str(preview["as_of"]),
            "candidate_id": spec.candidate_id, "registered_policy_id": spec.execution_policy,
            "policy_output_intervention": "FORCED_REBALANCE_BAND_1_NOT_REGISTERED_CANDIDATE",
            "registered_policy_consumption_calls": len(calls), "synthetic_account": True,
            "baseline_intents": len(baseline), "intervention_intents": len(mutated),
            "hold_account_intents": len(hold_intents), "hold_only_authority_observed": hold_observed,
            "target_hash_unchanged": before["target_hash"] == changed["target_hash"] == held["target_hash"],
            "operational_intent_effect": "PURE_MEMORY_PREVIEW_ONLY", "operational_fill_effect": "NOT_TESTED",
            "cost_adjusted_incremental_utility": "NOT_MEASURED"}


def probe_risk(root: Path, spec, baseline: dict) -> dict:
    ledger = _window(baseline["ledger"])
    valid_dates = [date for date, row in ledger.iterrows()
                   if (weights := json.loads(row["target_weights_json"]))
                   and all(0 <= float(weight) <= .90 for weight in weights.values())
                   and abs(sum(float(weight) for weight in weights.values()) - 1) <= 1e-9]
    if not valid_dates:
        return {"agent": "RiskExecutionAgent", "status": "NOT_EXERCISED_NO_VALID_TARGET",
                "source": SOURCES["RiskExecutionAgent"], "cost_adjusted_incremental_utility": "NOT_MEASURED"}
    preview = paper.build_candidate_strategy_preview(root, spec.candidate_id, as_of=str(valid_dates[0].date()))
    if preview["target_hash"] != ledger.loc[valid_dates[0], "target_hash"]:
        raise ValueError("signed preview differs from baseline target")
    return probe_risk_preview(root, spec, preview)


def run_audit(root: Path) -> dict:
    with ExitStack() as stack:
        safety_guards(stack)
        input_hash = adapter._input_hash(root)
        sources = source_hashes(root)
        specs = adapter.load_candidate_specs(root)
        runs = []
        for candidate_id in MODELS:
            spec = specs[candidate_id]
            baseline = adapter.build_candidate_ledgers(root, spec, use_common_cutoff=True)
            dates = _window(baseline["ledger"]).index
            if dates.empty or str(dates[0].date()) != START or str(dates[-1].date()) != END:
                raise ValueError("fixed run2 period not fully covered")
            rows = [probe(root, spec, baseline, agent) for agent in PROBES]
            rows.append(probe_risk(root, spec, baseline))
            for agent, status in (("SentimentNewsAgent", "NO_CONSUMER"), ("ReviewFeedbackAgent", "NO_CONSUMER")):
                rows.append({"agent": agent, "status": status, "source": SOURCES[agent],
                             "operational_intent_and_fill_effect": "NOT_TESTED",
                             "cost_adjusted_incremental_utility": "NOT_MEASURED"})
            runs.append({"candidate_id": candidate_id, "candidate_fingerprint": spec.fingerprint, "agents": rows})
        if adapter._input_hash(root) != input_hash or source_hashes(root) != sources:
            raise ValueError("inputs or source changed during audit")
    return {"scope": "CURRENT_TARGET_AND_SYNTHETIC_INTENT_CONSUMPTION_PROBE_NOT_RUN2_NAV_ATTRIBUTION",
            "period": {"start": START, "end": END}, "input_hash": input_hash,
            "script_sha256": sha256(Path(__file__).read_bytes()).hexdigest(), "source_sha256": sources, "runs": runs,
            "model_validation_passed": False, "cost_adjusted_incremental_utility": "NOT_MEASURED",
            "execution_replay_calls": 0, "database_calls": 0, "network_calls": 0,
            "limitations": ["FORCED_INTERVENTIONS_ARE_NOT_DEPLOYABLE_CANDIDATES", "INTENTS_USE_SYNTHETIC_ACCOUNT_NO_FILLS",
                            "CURRENT_CODE_NOT_RECONSTRUCTED_RUN2_SOURCE", "NO_FORWARD_OR_OUT_OF_SAMPLE_UTILITY_TEST"]}


def main() -> None:
    report = run_audit(ROOT)
    payload = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    digest = sha256(payload.encode()).hexdigest()
    output = ROOT / "runtime/current_agent_causality_audit" / f"target_output_probe_{digest}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output.open("x", encoding="utf-8") as handle:
            handle.write(payload)
    except FileExistsError:
        if output.read_text(encoding="utf-8") != payload:
            raise ValueError("immutable audit output conflict")
    print(json.dumps({"output": str(output), "cost_adjusted_incremental_utility": "NOT_MEASURED"}))


if __name__ == "__main__":
    main()
