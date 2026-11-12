"""Minimal, fail-closed control plane for preregistered alpha research.

This module deliberately does not calculate alpha performance, call V101, or
invoke an operational replay.  It only records immutable proposal contracts
and routes them to deterministic vetoes or the next explicitly bounded stage.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

import yaml


SCHEMA_VERSION = "ALPHA_RESEARCH_FACTORY_CONTROL_PLANE_V1"
TERMINAL_REJECTIONS = {
    "REJECTED_DUPLICATE",
    "REJECTED_DIAGNOSTIC",
    "REJECTED_FEASIBILITY",
}
NEXT_STAGES = {"EXECUTION_FEASIBILITY_PENDING", "OPERATIONAL_REPLAY_PENDING", "FORWARD_SHADOW_ONLY"}


def _canonical(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(payload: Any) -> str:
    return sha256(_canonical(payload).encode("utf-8")).hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(_canonical(row) + "\n")


def _logical_payload(row: dict[str, Any]) -> dict[str, str]:
    return {
        "strategy_family": str(row["strategy_family"]),
        "universe_contract": str(row["universe_contract"]),
        "signal_semantics": str(row["signal_semantics"]),
        "decision_timing": str(row["decision_timing"]),
    }


def _contract(row: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    if row.get("proposal_origin") != "LLM_PROPOSAL_ONLY":
        raise ValueError("proposal origin must be LLM_PROPOSAL_ONLY")
    if any(key in row for key in ("metric_output", "return_pct", "score", "parameter_grid")):
        raise ValueError("LLM proposal cannot carry numeric metric output or a parameter grid")
    payload = _logical_payload(row)
    return {
        "schema_version": SCHEMA_VERSION,
        "proposal_id": str(row["proposal_id"]),
        "proposal_origin": "LLM_PROPOSAL_ONLY",
        "logical_payload": payload,
        "duplicate_fingerprint": _hash(payload),
        "requested_diagnostic": str(row["requested_diagnostic"]),
        "required_inputs": sorted(str(x) for x in row.get("required_inputs", [])),
        "universe_pit_limitation": str(cfg["universe_pit_limitation"]),
        "metric_output": {"producer": "DETERMINISTIC_METRIC_WORKER_ONLY", "status": "NOT_RUN"},
        "execution_feasibility": {"producer": "V101_ONLY", "status": "NOT_RUN"},
        "operational_replay": {"producer": "EXPLICIT_FROZEN_REPLAY_ONLY", "status": "NOT_RUN"},
        "capital_mutation_allowed": False,
        "promotion_requires_human_approval": True,
    }


def _status(contract: dict[str, Any], cfg: dict[str, Any]) -> tuple[str, str, str | None]:
    known = {_hash(_logical_payload(row)): str(row["existing_contract"]) for row in cfg.get("known_semantic_duplicates", [])}
    fingerprint = contract["duplicate_fingerprint"]
    if fingerprint in known:
        return "REJECTED_DUPLICATE", "SEMANTIC_DUPLICATE", known[fingerprint]
    if "historical_pit_news" in contract["required_inputs"]:
        return "REJECTED_FEASIBILITY", "DATA_BLOCKED_NO_HISTORICAL_PIT_NEWS", "config/v102_market_evidence_agent.yaml"
    # The factory never treats an LLM proposal as a measured diagnostic.  A
    # deterministic IC/spread worker must create the next event in a later,
    # separately approved job.
    return "BLOCKED_DIAGNOSTIC_NOT_RUN", "DETERMINISTIC_DIAGNOSTIC_NOT_RUN", None


def _agent_trace(contract: dict[str, Any], status: str, veto: str) -> list[dict[str, Any]]:
    steps = [
        ("UniverseAgent", "PIT_FEASIBILITY", "INVOKED", "OBSERVED_FIRST_BAR_PROXY_LIMITATION_RECORDED"),
        ("MarketRegimeAgent", "REGIME_ROBUSTNESS", "NOT_INVOKED", "PRE_DIAGNOSTIC_VETO"),
        ("SectorThemeAgent", "TAXONOMY_ROBUSTNESS", "NOT_INVOKED", "PRE_DIAGNOSTIC_VETO"),
        ("PainSupplyAgent", "FLOW_FEASIBILITY", "NOT_INVOKED", "PRE_DIAGNOSTIC_VETO"),
        ("SentimentNewsAgent", "NEWS_PIT_FEASIBILITY", "INVOKED" if veto == "DATA_BLOCKED_NO_HISTORICAL_PIT_NEWS" else "NOT_INVOKED", veto if veto == "DATA_BLOCKED_NO_HISTORICAL_PIT_NEWS" else "NOT_REQUIRED"),
        ("CandidateSelectionAgent", "BASELINE_OVERLAP_AND_IC_SPREAD", "NOT_INVOKED", "DETERMINISTIC_DIAGNOSTIC_REQUIRED"),
        ("StrategyAgent", "TARGET_LEDGER", "NOT_INVOKED", "NO_DIAGNOSTIC_PASS"),
        ("RiskExecutionAgent", "V101_EXECUTION_FEASIBILITY", "NOT_INVOKED", "SEPARATE_STAGE_AFTER_DIAGNOSTIC"),
        ("ReviewFeedbackAgent", "PREREGISTRATION_AND_REGISTRY", "INVOKED", status),
    ]
    return [{
        "proposal_id": contract["proposal_id"], "agent": agent, "research_role": role,
        "invocation": invoked, "reason": reason, "capital_mutation": False,
    } for agent, role, invoked, reason in steps]


def run(root: Path | str, *, output_dir: Path | str | None = None) -> dict[str, Any]:
    root = Path(root)
    cfg = yaml.safe_load((root / "config/alpha_research_factory.yaml").read_text(encoding="utf-8"))
    if cfg["schema_version"] != SCHEMA_VERSION or cfg["factory_mode"] != "DRY_RUN_ONLY":
        raise ValueError("unsupported factory contract")
    proposals = list(cfg.get("proposals", []))
    if len(proposals) > int(cfg["proposal_budget_per_cycle"]):
        raise ValueError("proposal budget exceeded")
    out = Path(output_dir) if output_dir else root / "runtime/alpha_research_factory"
    contracts_dir = out / "contracts"
    attempt_path, event_path, trace_path = out / "attempt_registry.jsonl", out / "state_events.jsonl", out / "agent_invocation_trace.jsonl"
    existing_attempts = _read_jsonl(attempt_path)
    events: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []
    trace: list[dict[str, Any]] = []
    replay_count = 0
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    for proposal in proposals:
        contract = _contract(proposal, cfg)
        contract_hash = _hash(contract)
        contract["contract_hash"] = contract_hash
        path = contracts_dir / f"{contract['proposal_id']}.json"
        if path.exists() and json.loads(path.read_text(encoding="utf-8"))["contract_hash"] != contract_hash:
            raise RuntimeError(f"immutable preregistration conflict: {contract['proposal_id']}")
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        status, veto, evidence = _status(contract, cfg)
        attempt_id = _hash({"proposal_id": contract["proposal_id"], "contract_hash": contract_hash})
        duplicate_prior = any(x.get("attempt_id") == attempt_id for x in existing_attempts)
        attempt = {
            "attempt_id": attempt_id, "timestamp_utc": now, "proposal_id": contract["proposal_id"],
            "contract_hash": contract_hash, "duplicate_fingerprint": contract["duplicate_fingerprint"],
            "status": status, "veto": veto, "evidence": evidence,
            "universe_pit_limitation": contract["universe_pit_limitation"],
            "execution_feasibility_status": "NOT_RUN", "operational_replay_status": "NOT_RUN",
            "promotion_status": "NOT_ELIGIBLE", "capital_mutation": False,
        }
        if not duplicate_prior:
            attempts.append(attempt)
            events.extend([
                {"timestamp_utc": now, "attempt_id": attempt_id, "from": None, "to": "PREREGISTERED", "reason": "IMMUTABLE_CONTRACT_WRITTEN"},
                {"timestamp_utc": now, "attempt_id": attempt_id, "from": "PREREGISTERED", "to": status, "reason": veto},
            ])
            trace.extend(_agent_trace(contract, status, veto))
        if status == "OPERATIONAL_REPLAY_PENDING":
            replay_count += 1
    if replay_count > int(cfg["operational_replay_budget_per_cycle"]):
        raise ValueError("operational replay budget exceeded")
    _append_jsonl(attempt_path, attempts)
    _append_jsonl(event_path, events)
    _append_jsonl(trace_path, trace)
    all_attempts = _read_jsonl(attempt_path)
    report = {
        "status": "ALPHA_FACTORY_CONTROL_PLANE_VALID",
        "schema_version": SCHEMA_VERSION,
        "dry_run": True,
        "proposal_budget": {"limit": int(cfg["proposal_budget_per_cycle"]), "submitted": len(proposals), "passed": len(proposals) <= int(cfg["proposal_budget_per_cycle"])},
        "operational_replay_budget": {"limit": int(cfg["operational_replay_budget_per_cycle"]), "requested": replay_count, "passed": replay_count <= int(cfg["operational_replay_budget_per_cycle"])},
        "attempts_written": len(attempts), "existing_attempts_skipped": len(proposals) - len(attempts),
        "statuses": {p["proposal_id"]: next((a["status"] for a in all_attempts if a["proposal_id"] == p["proposal_id"]), "NOT_WRITTEN") for p in proposals},
        "v101_called": False, "operational_replay_called": False, "broker_mutation_calls": 0,
        "capital_mutation": False, "promotion_above_forward_shadow": False,
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "dry_run_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report
