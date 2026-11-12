from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
import runpy

import pandas as pd
import pytest

AUDIT = runpy.run_path(str(Path(__file__).resolve().parents[1] / "scripts/audit_daily_agent_causality.py"))


def built(weights, selected="091180"):
    return {"ledger": pd.DataFrame([{"date": "2022-01-03", "target_weights_json": json.dumps(weights),
                                    "target_hash": AUDIT["_target_hash"](weights)}]),
            "selection": pd.DataFrame([{"date": "2022-01-03", "leader_ticker": selected}])}


def test_target_change_is_not_claimed_as_execution_or_profit():
    result = AUDIT["compare_outputs"](built({"069500": .2, "091180": .8}), built({"069500": .25, "091180": .75}),
                                      agent="StrategyAgent", output_changed=True)
    assert result["status"] == "TARGET_CAUSAL_OBSERVED"
    assert result["target_hash_changed_days"] == 1
    assert result["operational_intent_and_fill_effect"] == "NOT_TESTED"
    assert result["cost_adjusted_incremental_utility"] == "NOT_MEASURED"


def test_forced_core_target_classifies_hold_not_executable():
    result = AUDIT["compare_outputs"](built({"069500": .2, "091180": .8}), built({"069500": 1}, None),
                                      agent="UniverseAgent", output_changed=True)
    assert result["changed_target_gate_classification"]["HOLD_ONLY_UNSELECTED_OVER_CAP"] == 1
    assert result["changed_target_gate_classification"]["WITHIN_WEIGHT_CAP_ONLY"] == 0


def test_changed_output_without_target_change_does_not_claim_causality():
    base = built({"069500": .2, "091180": .8})
    result = AUDIT["compare_outputs"](base, deepcopy(base), agent="MarketRegimeAgent", output_changed=True)
    assert result["status"] == "NO_TARGET_EFFECT_OBSERVED"


def test_diagnostic_negative_control_requires_intervention_and_target_invariance():
    base = built({"069500": .2, "091180": .8})
    compare = AUDIT["compare_outputs"]
    assert compare(base, base, agent="PainSupplyAgent", output_changed=True)["status"] == "NEGATIVE_CONTROL_CONFIRMED"
    assert compare(base, base, agent="PainSupplyAgent", output_changed=False)["status"] == "NOT_EXERCISED"
    with pytest.raises(ValueError, match="diagnostic-only"):
        compare(base, built({"069500": 1}, None), agent="PainSupplyAgent", output_changed=True)


def test_strategy_perturbation_is_valid_and_does_not_mutate_source():
    base = built({"069500": .14, "091180": .86})["ledger"]
    before = base.copy(deep=True)
    result = AUDIT["perturb_strategy_output"](base)
    weights = json.loads(result.iloc[0]["target_weights_json"])
    assert sum(weights.values()) == pytest.approx(1)
    assert max(weights.values()) <= .90
    assert result.iloc[0]["target_hash"] != base.iloc[0]["target_hash"]
    pd.testing.assert_frame_equal(base, before)


def test_comparison_fails_closed_on_wrong_hash_or_different_dates():
    base = built({"069500": .2, "091180": .8})
    bad = deepcopy(base)
    bad["ledger"].loc[0, "target_hash"] = "not-a-hash"
    with pytest.raises(ValueError, match="target hash"):
        AUDIT["compare_outputs"](base, bad, agent="StrategyAgent", output_changed=True)
    bad = deepcopy(base)
    bad["ledger"].loc[0, "date"] = "2022-01-04"
    with pytest.raises(ValueError, match="comparison dates"):
        AUDIT["compare_outputs"](base, bad, agent="StrategyAgent", output_changed=True)


def test_safety_guards_block_execution_database_and_network():
    from contextlib import ExitStack
    import psycopg
    import socket
    with ExitStack() as stack:
        AUDIT["safety_guards"](stack)
        for call in (psycopg.connect, AUDIT["adapter"].replay_candidate, AUDIT["adapter"].v101.replay, socket.create_connection):
            with pytest.raises(RuntimeError, match="forbidden"):
                call()


def test_strategy_probe_calls_builder_and_restores_hooks(monkeypatch):
    adapter = AUDIT["adapter"]
    original = adapter.build_v69_target_ledger
    selection = pd.DataFrame([{"date": pd.Timestamp("2022-01-03"), "leader_ticker": "091180"}])
    calls = []
    def builder(*args, **kwargs):
        calls.append(True)
        ledger = adapter.build_v69_target_ledger(selection, core_ticker="069500", policy="FIXED_PARENT_ALLOCATIONS", params={})
        return {"ledger": ledger, "selection": selection}
    monkeypatch.setattr(adapter, "build_candidate_ledgers", builder)
    baseline = builder()
    result = AUDIT["probe"](Path("."), None, baseline, "StrategyAgent")
    assert len(calls) == 2
    assert result["status"] == "TARGET_CAUSAL_OBSERVED"
    assert adapter.build_v69_target_ledger is original


def test_probe_restores_hooks_on_builder_failure(monkeypatch):
    adapter = AUDIT["adapter"]
    original = adapter.build_v69_target_ledger
    def fail(*args, **kwargs):
        raise ValueError("builder failed")
    monkeypatch.setattr(adapter, "build_candidate_ledgers", fail)
    with pytest.raises(ValueError, match="builder failed"):
        AUDIT["probe"](Path("."), None, {}, "StrategyAgent")
    assert adapter.build_v69_target_ledger is original


def test_sector_probe_calls_real_merged_helper_and_restores_hooks(monkeypatch):
    adapter = AUDIT["adapter"]
    original = adapter.v69.build_sector_representative_panel
    dates = pd.DatetimeIndex(["2022-01-03"])
    universe = pd.DataFrame([{"ticker": "091180", "sector": "autos"}])
    score = pd.DataFrame({"091180": [1.0]}, index=dates)
    def builder(*args, **kwargs):
        panel = adapter.v69.build_sector_representative_panel(dates, dates, universe, score, score > 0, score)
        selected = panel.iloc[0]["representative_ticker"]
        return built({"069500": .2, "091180": .8} if selected else {"069500": 1}, selected)
    monkeypatch.setattr(adapter, "build_candidate_ledgers", builder)
    result = AUDIT["probe"](Path("."), None, builder(), "SectorThemeAgent")
    assert result["status"] == "TARGET_CAUSAL_OBSERVED"
    assert result["changed_target_gate_classification"]["HOLD_ONLY_UNSELECTED_OVER_CAP"] == 1
    assert result["cost_adjusted_incremental_utility"] == "NOT_MEASURED"
    assert adapter.v69.build_sector_representative_panel is original


def signed_preview(candidate):
    paper = AUDIT["paper"]
    root = Path(__file__).resolve().parents[1]
    spec = AUDIT["adapter"].load_candidate_specs(root)[candidate]
    weights = {"069500": .2, "091180": .8}
    preview = {"root": str(root), "candidate_id": candidate, "candidate_fingerprint": spec.fingerprint,
               "as_of": "2022-01-03", "session_id": "SYNTHETIC-AUDIT", "input_hash": "synthetic-input",
               "strategy_build_hash": "synthetic-build", "selected_candidates": ["091180"],
               "target_weights": weights, "target_hash": AUDIT["_target_hash"](weights),
               "allowed_symbols": list(weights), "market_data_status": "CURRENT_FOR_AS_OF",
               "broker_observation_status": "NOT_REQUESTED", "execution_policy": spec.execution_policy,
               "targets": [{"symbol": symbol, "target_weight": weight,
                            "target_notional": Decimal("10000000") * Decimal(str(weight)),
                            "target_quantity": Decimal("100000") * Decimal(str(weight)),
                            "reference_price": Decimal(100), "adv20_d1_krw": Decimal("1000000000")}
                           for symbol, weight in weights.items()]}
    evidence = {key: preview[key] for key in ("strategy_build_hash", "input_hash", "candidate_fingerprint", "selected_candidates", "target_hash")}
    evidence.update(decision_uses_same_day_close=False, execution_targets_hash=paper._execution_targets_hash(preview["targets"]))
    receipt = {"status": "PASSED", "evidence": evidence}
    preview["decision_receipt"] = {**receipt, "receipt_hash": paper._digest(receipt)}
    return root, spec, preview


@pytest.mark.parametrize("candidate", AUDIT["MODELS"])
def test_risk_probe_consumes_real_intent_function_and_registered_policy(candidate):
    from contextlib import ExitStack
    root, spec, preview = signed_preview(candidate)
    saved = deepcopy(preview)
    original = AUDIT["paper"].v101._policy
    with ExitStack() as stack:
        AUDIT["safety_guards"](stack)
        result = AUDIT["probe_risk_preview"](root, spec, preview)
    assert result["status"] == "INTENT_POLICY_CAUSAL_OBSERVED"
    assert result["baseline_intents"] == 2
    assert result["intervention_intents"] == 0
    assert result["hold_only_authority_observed"] is True
    assert result["target_hash_unchanged"] is True
    assert result["operational_fill_effect"] == "NOT_TESTED"
    assert result["cost_adjusted_incremental_utility"] == "NOT_MEASURED"
    assert preview == saved
    assert AUDIT["paper"].v101._policy is original


def test_risk_probe_does_not_bypass_receipt_guard():
    root, spec, preview = signed_preview("V69_PARENT")
    preview["targets"][0]["target_quantity"] += 1
    with pytest.raises(AUDIT["paper"].PaperPreviewError, match="payload"):
        AUDIT["probe_risk_preview"](root, spec, preview)


def test_nine_agent_report_slots_cover_both_models_without_profit_claim():
    assert len(set(AUDIT["PROBES"]) | {"RiskExecutionAgent", "SentimentNewsAgent", "ReviewFeedbackAgent"}) == 9
    assert len(AUDIT["MODELS"]) == 2
