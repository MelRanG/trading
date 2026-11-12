from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from hashlib import sha256
from functools import lru_cache
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from quant_harness.v69_dynamic_theme_leadership import engine as v69
from quant_harness.v77_corrected_price_allocation import engine as v77
from quant_harness.v79_generic_trend_sleeve import engine as v79
from quant_harness.v94_universe_agent import engine as v94
from quant_harness.v95_market_regime_agent import engine as v95
from quant_harness.v95_market_regime_agent.policy import build_market_regime_panel
from quant_harness.v100_strategy_agent.policy import build_v69_target_ledger, build_v79_target_ledger
from quant_harness.v101_risk_execution_agent import engine as v101
from quant_harness.v102_market_evidence_agent.policy import (
    apply_evidence_policy,
    build_flow_evidence,
    build_fundamental_evidence,
)


@dataclass(frozen=True)
class CandidateSpec:
    candidate_id: str
    strategy: str
    universe_policy: str
    regime_policy: str
    base_selection_policy: str
    sleeve_selection_policy: str
    strategy_policy: str
    evidence_policy: str
    execution_policy: str
    purpose: str = ""
    audit_only: bool = False

    @classmethod
    def from_mapping(cls, row: dict[str, Any]) -> "CandidateSpec":
        values = dict(row)
        values["audit_only"] = bool(values.get("audit_only", False))
        return cls(**values)

    @property
    def fingerprint(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return sha256(payload.encode("utf-8")).hexdigest()


def load_config(root: Path) -> dict[str, Any]:
    return yaml.safe_load((root / "config/v104_end_to_end_causal_challenger_audit.yaml").read_text(encoding="utf-8"))


def load_candidate_specs(root: Path) -> dict[str, CandidateSpec]:
    cfg = load_config(root)
    specs = [CandidateSpec.from_mapping(row) for row in cfg["candidates"]]
    result = {s.candidate_id: s for s in specs}
    if len(result) != len(specs):
        raise ValueError("duplicate V104 candidate_id")
    return result


def _candidate_params(root: Path, policy: str) -> dict[str, Any]:
    if policy == "UNCERTAINTY_AWARE_ROTATION":
        cfg = yaml.safe_load((root / "config/v98_candidate_selection_agent.yaml").read_text(encoding="utf-8"))
        for row in cfg.get("research_candidates", []):
            if row.get("policy_id") == policy:
                return {k: v for k, v in row.items() if k != "policy_id"}
    return {}


def _input_hash(root: Path) -> str:
    """Hash every sealed input that can change a candidate decision or fill.

    V103/V104 prototypes initially hashed configuration and the universe only.
    That was insufficient for Forward operation because appending a new market
    session could leave the hash unchanged.  The executable contract now binds
    configs plus all point-in-time market, flow and filing inputs.
    """
    files = [
        root / "config/active_strategy.yaml",
        root / "config/strategy_registry_v84.yaml",
        root / "config/v69_dynamic_theme_leadership.yaml",
        root / "config/v77_corrected_price_allocation.yaml",
        root / "config/v79_generic_trend_sleeve.yaml",
        root / "config/v85_operations.yaml",
        root / "config/v95_market_regime_agent.yaml",
        root / "config/v98_candidate_selection_agent.yaml",
        root / "config/v100_strategy_agent.yaml",
        root / "config/v101_risk_execution_agent.yaml",
        root / "config/v102_market_evidence_contract.yaml",
        root / "config/v104_end_to_end_causal_challenger_audit.yaml",
        root / "data/toss_v19c_daily/universe.csv",
        root / "data/all_prices_long_v62_9_expanded.csv",
        root / "data/canonical/v84_market_manifest.csv",
        root / "data/agent_ready_v62_16/agent_etf_to_stock_mapping_v62_16.csv",
        root / "data/historical_investor_flow/market_investor_flow_daily.csv",
        root / "data/opendart_quarterly_pit.csv",
    ]
    files.extend(sorted((root / "data/toss_v19c_daily").glob("*_1d.csv")))
    digest = sha256()
    for path in sorted({p.resolve() for p in files if p.exists()}, key=lambda p: str(p)):
        digest.update(str(path.relative_to(root.resolve())).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


@lru_cache(maxsize=8)
def _cached_context(root_text: str, use_common_cutoff: bool, input_hash: str) -> dict[str, Any]:
    root = Path(root_text)
    cfg77 = v77._load_config(root, use_common_cutoff=use_common_cutoff)
    market = v77.load_adjusted_market(root, cfg77)
    cfg69 = replace(
        v69._load_config(root),
        end_date=cfg77.end_date,
        core_ticker=cfg77.core_ticker,
        benchmark_ticker=cfg77.benchmark_ticker,
        leader_weight=0.80,
    )
    universe = v69._load_universe(root, cfg69)
    cfg79 = v79._load_config(root)["trend_sleeve"]
    f69 = v94._strict_v69_features(market["close"], market["value"], universe, cfg69)
    f79 = v94._strict_v79_features(market["close"], market["value"], universe, cfg79)
    flow = build_flow_evidence(root, market["close"].index)
    fundamental_risk, events = build_fundamental_evidence(root, market["close"].index)
    return {
        "cfg77": cfg77, "market": market, "cfg69": cfg69, "universe": universe, "cfg79": cfg79,
        "f69": f69, "f79": f79, "flow": flow, "fundamental_risk": fundamental_risk, "fundamental_events": events,
    }


def _runtime_context(root: Path, market_override: dict[str, Any] | None = None, *, use_common_cutoff: bool = False) -> dict[str, Any]:
    current_input_hash = _input_hash(root)
    if market_override is None:
        return _cached_context(str(root.resolve()), use_common_cutoff, current_input_hash)
    cfg77 = v77._load_config(root, use_common_cutoff=use_common_cutoff)
    market = market_override
    cfg69 = replace(
        v69._load_config(root), end_date=cfg77.end_date, core_ticker=cfg77.core_ticker,
        benchmark_ticker=cfg77.benchmark_ticker, leader_weight=0.80,
    )
    universe = v69._load_universe(root, cfg69)
    cfg79 = v79._load_config(root)["trend_sleeve"]
    f69 = v94._strict_v69_features(market["close"], market["value"], universe, cfg69)
    f79 = v94._strict_v79_features(market["close"], market["value"], universe, cfg79)
    cached = _cached_context(str(root.resolve()), use_common_cutoff, current_input_hash)
    flow = cached["flow"]
    fundamental_risk = cached["fundamental_risk"]
    events = cached["fundamental_events"]
    return {
        "cfg77": cfg77, "market": market, "cfg69": cfg69, "universe": universe, "cfg79": cfg79,
        "f69": f69, "f79": f79, "flow": flow, "fundamental_risk": fundamental_risk, "fundamental_events": events,
    }


def build_candidate_ledgers(
    root: Path | str,
    spec: CandidateSpec,
    *,
    market_override: dict[str, Any] | None = None,
    use_common_cutoff: bool = False,
) -> dict[str, Any]:
    root = Path(root)
    ctx = _runtime_context(root, market_override, use_common_cutoff=use_common_cutoff)
    cfg77, market, cfg69, universe, cfg79 = (
        ctx["cfg77"], ctx["market"], ctx["cfg69"], ctx["universe"], ctx["cfg79"]
    )
    f69 = ctx["f69"]
    f79 = ctx["f79"]
    if spec.universe_policy == "FORCE_ALL_THEME_INELIGIBLE_MUTATION":
        f69 = dict(f69)
        f79 = dict(f79)
        f69["universe_gate"] = dict(f69["universe_gate"])
        f79["universe_gate"] = dict(f79["universe_gate"])
        f69["universe_gate"]["gate"] = f69["universe_gate"]["gate"].copy() & False
        f79["universe_gate"]["gate"] = f79["universe_gate"]["gate"].copy() & False
        f69["eligible"] = f69["eligible"].copy() & False
        f79["eligible"] = f79["eligible"].copy() & False
    elif spec.universe_policy != "STRICT_PIT_CORRECTNESS":
        raise ValueError(f"unsupported universe policy {spec.universe_policy}")

    regime = build_market_regime_panel(
        market["close"],
        benchmark_ticker=cfg69.benchmark_ticker,
        theme_tickers=universe["ticker"].astype(str).tolist(),
        universe_gate_d1=f69["universe_gate"]["gate"],
        policy=spec.regime_policy,
        **v95._policy_kwargs(v95._load_config(root), spec.regime_policy),
    )
    f69 = dict(f69)
    f69["benchmark_trend"] = regime["risk_on"]
    params69 = _candidate_params(root, spec.base_selection_policy)
    params79 = _candidate_params(root, spec.sleeve_selection_policy)
    index = market["close"].index
    selection69 = v69.select_dynamic_leader(
        index, universe, f69, cfg69,
        selection_policy=spec.base_selection_policy,
        selection_policy_params=params69,
    )
    selection69["target_leader_weight"] = selection69["leader_ticker"].notna().astype(float) * 0.80
    selection79 = v79.select_persistent_trend_leader(
        index, universe, f79,
        minimum_hold_sessions=int(cfg79["minimum_hold_sessions"]),
        challenger_score_margin=float(cfg79["challenger_score_margin"]),
        confirmation_reviews=int(cfg79["challenger_confirmation_reviews"]),
        selection_policy=spec.sleeve_selection_policy,
        selection_policy_params=params79,
    )
    cfg104 = load_config(root)
    strategy_params = dict(cfg104["strategy_parameters"])
    sector_by_ticker = universe.set_index(universe["ticker"].astype(str))["sector"].astype(str).to_dict()
    ledger69 = build_v69_target_ledger(
        selection69,
        core_ticker=cfg77.core_ticker,
        policy=spec.strategy_policy,
        params=strategy_params,
    )
    ledger79 = build_v79_target_ledger(
        selection69, selection79,
        core_ticker=cfg77.core_ticker,
        base_share=0.70,
        policy=spec.strategy_policy,
        params=strategy_params,
        sector_by_ticker=sector_by_ticker,
    )
    flow = ctx["flow"]
    fundamental_risk = ctx["fundamental_risk"]
    ledger69 = apply_evidence_policy(
        ledger69, policy_id=spec.evidence_policy, flow=flow,
        fundamental_risk=fundamental_risk, core_ticker=cfg77.core_ticker, strategy="V69",
    )
    ledger79 = apply_evidence_policy(
        ledger79, policy_id=spec.evidence_policy, flow=flow,
        fundamental_risk=fundamental_risk, core_ticker=cfg77.core_ticker, strategy="V79",
    )
    ledger = ledger69 if spec.strategy == "V69" else ledger79
    selection = selection69 if spec.strategy == "V69" else selection79
    return {
        **ctx,
        "regime": regime,
        "selection69": selection69,
        "selection79": selection79,
        "ledger69": ledger69,
        "ledger79": ledger79,
        "ledger": ledger,
        "selection": selection,
        "candidate_fingerprint": spec.fingerprint,
        "input_hash": _input_hash(root),
    }


def replay_candidate(
    root: Path | str,
    spec: CandidateSpec,
    *,
    market_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = Path(root)
    built = build_candidate_ledgers(root, spec, market_override=market_override)
    execution = v101._policy(root, spec.execution_policy)
    cfg77 = built["cfg77"]
    account, orders, intents = v101.replay(
        built["market"]["close"], built["market"]["open"], built["market"]["adv20_d1"], built["ledger"],
        initial_capital=float(cfg77.initial_capital_krw), spec=cfg77.base_execution,
        policy=execution, strategy=spec.strategy, core_ticker=cfg77.core_ticker,
    )
    stress_account, stress_orders, stress_intents = v101.replay(
        built["market"]["close"], built["market"]["open"], built["market"]["adv20_d1"], built["ledger"],
        initial_capital=float(cfg77.initial_capital_krw), spec=cfg77.stress_execution,
        policy=execution, strategy=spec.strategy, core_ticker=cfg77.core_ticker,
    )
    return {
        "spec": spec,
        "execution": execution,
        "ledger": built["ledger"],
        "selection": built["selection"],
        "selection69": built["selection69"],
        "selection79": built["selection79"],
        "regime": built["regime"],
        "candidate_fingerprint": built["candidate_fingerprint"],
        "input_hash": built["input_hash"],
        "initial_capital_krw": float(cfg77.initial_capital_krw),
        "core_ticker": cfg77.core_ticker,
        "account": account,
        "orders": orders,
        "intents": intents,
        "stress_account": stress_account,
        "stress_orders": stress_orders,
        "stress_intents": stress_intents,
    }


def future_mutation_invariant(root: Path | str, spec: CandidateSpec, cutoff: str = "2024-12-31") -> tuple[bool, int]:
    root = Path(root)
    base = build_candidate_ledgers(root, spec)
    changed_market = {k: v.copy() if hasattr(v, "copy") else v for k, v in base["market"].items()}
    cutoff_ts = pd.Timestamp(cutoff)
    future = changed_market["close"].index > cutoff_ts
    tickers = list(changed_market["close"].columns)
    changed_market["close"].loc[future, tickers] *= 1.37
    changed_market["open"].loc[future, tickers] *= 0.79
    changed = build_candidate_ledgers(root, spec, market_override=changed_market)
    left = base["ledger"].loc[base["ledger"]["date"].le(cutoff_ts), ["date", "target_hash"]].reset_index(drop=True)
    right = changed["ledger"].loc[changed["ledger"]["date"].le(cutoff_ts), ["date", "target_hash"]].reset_index(drop=True)
    diffs = int(left["target_hash"].ne(right["target_hash"]).sum())
    return bool(left.equals(right)), diffs
