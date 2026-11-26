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


# Task4 extends the official Factory with review-origin proposals. The legacy
# fixed LLM dry-run contract and its vetoes above retain their existing behavior.
ECONOMIC_SPLIT = "EXPLORATORY_ECONOMICS"


def _economic_scope(root, cfg, proposal, out):
    """Bind an individually authorized offline worker to the official ledger."""
    approved = cfg.get("exploratory_economics", {}).get(proposal.get("approval_id"))
    if out.resolve() != root.resolve() / "runtime/alpha_research_factory/task4":
        raise ValueError("economic research uses the official Task4 reservation ledger")
    if not approved or approved["proposal"] != proposal:
        raise ValueError("economic proposal does not match the documented user scope")
    worker = root / approved["worker"]
    if root.resolve() not in worker.resolve().parents or sha256(worker.read_bytes()).hexdigest() != proposal["worker_hash"]:
        raise ValueError("approved economic worker changed")
    return approved, worker


def _economic_day_reservations(root, out, day):
    # Previously authorized isolated reviews count here as well. Backups and test
    # fixtures are outside these historical locations.
    logs = set((root / "runtime").glob("task16*/isolated_factory/experiment_reservations.jsonl"))
    logs.add(out / "experiment_reservations.jsonl")
    return sum(row["timestamp_utc"][:10] == day for path in logs for row in _read_jsonl(path))


def register_review_proposal(root: Path | str, proposal: dict[str, Any], *, directory: Path | None = None) -> dict[str, Any]:
    """Immutable preregistration with a shared filesystem lock and daily budget."""
    import fcntl
    import os
    from contextlib import contextmanager

    @contextmanager
    def locked(out):
        out.mkdir(parents=True, exist_ok=True)
        with (out / '.registry.lock').open('a') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            yield

    root = Path(root)
    cfg = json.loads((root / 'config/task4_review_contract.json').read_text())
    required = {'problem_evidence', 'target', 'expected_effect', 'falsification', 'champion', 'challenger',
                'input_hash', 'budget', 'stop_conditions', 'evaluation_metric', 'minimum_cases', 'split', 'worker_hash'}
    if not required <= proposal.keys() or any(proposal[k] in (None, '', [], {}) for k in required):
        raise ValueError('incomplete review proposal')
    if proposal['target'] not in {'source', 'prompt', 'strategy', 'review'}:
        raise ValueError('unsupported change target')
    if proposal['minimum_cases'] < cfg['minimum_independent_cases']:
        raise ValueError('sample requirement cannot be weakened')
    if proposal['split'] not in {'PROCESS_DIAGNOSTIC_ONLY', 'PREREGISTERED_FORWARD', ECONOMIC_SPLIT}:
        raise ValueError('unregistered data split')
    if proposal['budget'] != {'experiments': 1, 'parameter_search': 0}:
        raise ValueError('unregistered experiment budget')
    if any(k in proposal for k in ('return_pct', 'score', 'parameter_grid', 'holdout_results')):
        raise ValueError('proposal may not carry final evaluation results')
    out = Path(directory) if directory else root / 'runtime/alpha_research_factory/task4'
    economics = proposal['split'] == ECONOMIC_SPLIT
    if economics:
        _economic_scope(root, cfg, proposal, out)
    fingerprint = _hash({k: proposal[k] for k in ('target', 'champion', 'challenger', 'input_hash', 'split', 'worker_hash')})
    proposal_id = 'REVIEW-' + fingerprint[:24]
    contract = {'schema_version': 'ALPHA_FACTORY_REVIEW_V1', 'proposal_id': proposal_id,
                'proposal_origin': 'INDEPENDENT_REVIEW_PROPOSAL', 'duplicate_fingerprint': fingerprint,
                'proposal': proposal, 'promotion_ceiling': 'NOT_ELIGIBLE' if economics else cfg['promotion_ceiling'],
                'capital_mutation_allowed': False, 'promotion_requires_human_approval': True}
    contract['contract_hash'] = _hash(contract)
    with locked(out):
        registry = out / 'attempt_registry.jsonl'
        rows = _read_jsonl(registry)
        existing = next((r for r in rows if r['duplicate_fingerprint'] == fingerprint), None)
        if existing:
            path = out / 'contracts' / (proposal_id + '.json')
            prior = json.loads(path.read_text())
            if prior != contract:
                raise ValueError('immutable review contract conflict')
            return existing
        for prior_attempt in rows:
            prior_contract=json.loads((out/'contracts'/(prior_attempt['proposal_id']+'.json')).read_text())
            prior=prior_contract['proposal']
            if all(prior[k]==proposal[k] for k in ('target','champion','challenger')):
                raise ValueError('duplicate hypothesis family; new data requires explicit follow-up preregistration')
        day = datetime.now(timezone.utc).date().isoformat()
        if sum(r['timestamp_utc'][:10] == day for r in rows) >= cfg['proposal_budget_per_utc_day']:
            raise ValueError('Factory daily proposal budget exhausted')
        path = out / 'contracts' / (proposal_id + '.json')
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and json.loads(path.read_text()) != contract:
            raise ValueError('immutable review contract conflict')
        temporary = path.with_suffix('.tmp')
        temporary.write_text(_canonical(contract))
        with temporary.open('r') as handle:
            os.fsync(handle.fileno())
        temporary.replace(path)
        ready = 'READY_FOR_EXPLORATORY_ECONOMICS' if economics else 'READY_FOR_DIAGNOSTIC'
        attempt = {'attempt_id': _hash({'proposal_id': proposal_id, 'contract_hash': contract['contract_hash']}),
                   'timestamp_utc': datetime.now(timezone.utc).isoformat(), 'proposal_id': proposal_id,
                   'contract_hash': contract['contract_hash'], 'duplicate_fingerprint': fingerprint,
                   'status': ready, 'promotion_status': 'NOT_ELIGIBLE',
                   'capital_mutation': False, 'execution_feasibility_status': 'NOT_RUN', 'operational_replay_status': 'NOT_RUN'}
        _append_jsonl(registry, [attempt])
        _append_jsonl(out / 'state_events.jsonl', [{'attempt_id': attempt['attempt_id'], 'from': 'PREREGISTERED',
                        'to': ready, 'reason': 'REVIEW_CONTRACT_REGISTERED', 'contract_hash': contract['contract_hash']}])
        return attempt


def record_review_experiment(root: Path | str, attempt: dict[str, Any], result: dict[str, Any], *, directory: Path | None = None) -> dict[str, Any]:
    """Evaluator-only diagnostic result; never raises promotion authority."""
    import fcntl
    import os
    root = Path(root)
    out = Path(directory) if directory else root / 'runtime/alpha_research_factory/task4'
    cfg = json.loads((root / 'config/task4_review_contract.json').read_text())
    with (out / '.registry.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        contract = json.loads((out / 'contracts' / (attempt['proposal_id'] + '.json')).read_text())
        if _hash({k:v for k,v in contract.items() if k!='contract_hash'})!=contract['contract_hash']:
            raise ValueError('Factory contract integrity failure')
        json.dumps(result,allow_nan=False)
        if contract['contract_hash'] != attempt['contract_hash'] or result['input_hash'] != contract['proposal']['input_hash']:
            raise ValueError('Factory evaluation provenance mismatch')
        if result['worker_hash'] != contract['proposal']['worker_hash']:
            raise ValueError('Factory worker fingerprint changed')
        economics = contract['proposal']['split'] == ECONOMIC_SPLIT
        if economics:
            approved, _ = _economic_scope(root, cfg, contract['proposal'], out)
            statuses = ('EXPLORATORY_ECONOMICS_COMPLETED', 'EXPLORATORY_ECONOMICS_FAILED')
            if result.get('evidence_grade') != 'EXPOSED_CONDITIONAL_ONLY':
                raise ValueError('economic evidence grade mismatch')
            art = root / approved["artifacts"]
            marker = art / "worker.started.json"
            if not marker.is_file() or json.loads(marker.read_text()) != {
                "attempt_id": attempt["attempt_id"], "contract_hash": attempt["contract_hash"]
            }:
                raise ValueError("economic worker has not started")
            if result["status"] == statuses[0]:
                payload = json.loads((art / "worker_result.json").read_text())
                trace = {k: result[k] for k in ("input_hash", "worker_hash", "evidence_grade")}
                if result != {**payload, **trace}:
                    raise ValueError("economic output differs from worker evidence")
        else:
            statuses = ('INSUFFICIENT_EVIDENCE', 'REJECTED', 'FORWARD_REQUIRED')
        if result['status'] not in statuses:
            raise ValueError('no automatic approval status permitted')
        reservations=_read_jsonl(out/'experiment_reservations.jsonl')
        if not any(r['attempt_id']==attempt['attempt_id'] and r['contract_hash']==attempt['contract_hash'] for r in reservations):
            raise ValueError('evaluation budget was not reserved')
        log = out / 'diagnostic_registry.jsonl'
        records = _read_jsonl(log)
        old = next((r for r in records if r['attempt_id'] == attempt['attempt_id']), None)
        record = {'attempt_id': attempt['attempt_id'], 'contract_hash': attempt['contract_hash'],
                  'result': result, 'timestamp_utc': datetime.now(timezone.utc).isoformat(), 'promotion_status': 'NOT_ELIGIBLE'}
        if old:
            if old['result'] != result:
                raise ValueError('immutable evaluation conflict')
            return old
        day = datetime.now(timezone.utc).date().isoformat()
        if sum(r['timestamp_utc'][:10] == day for r in records) >= cfg['experiment_budget_per_utc_day']:
            raise ValueError('Factory daily experiment budget exhausted')
        if not economics and result['status'] != 'INSUFFICIENT_EVIDENCE' and result['cases'] < contract['proposal']['minimum_cases']:
            raise ValueError('insufficient sample cannot be passed or rejected as efficacy')
        _append_jsonl(log, [record])
        with log.open('r') as handle:
            os.fsync(handle.fileno())
        ready = 'READY_FOR_EXPLORATORY_ECONOMICS' if economics else 'READY_FOR_DIAGNOSTIC'
        _append_jsonl(out / 'state_events.jsonl', [{'attempt_id': attempt['attempt_id'], 'from': ready,
             'to': result['status'], 'reason': 'DETERMINISTIC_DIAGNOSTIC_EXECUTED', 'result_hash': _hash(result)}])
        return record


def reserve_review_experiment(root: Path | str, attempt: dict[str, Any], *, directory: Path | None = None) -> dict[str, Any]:
    """Reserve the budget BEFORE executing, surviving worker crashes/restarts."""
    import fcntl
    root=Path(root)
    out=Path(directory) if directory else root/'runtime/alpha_research_factory/task4'
    cfg=json.loads((root/'config/task4_review_contract.json').read_text())
    with (out/'.registry.lock').open('a') as handle:
        fcntl.flock(handle,fcntl.LOCK_EX)
        contract = json.loads((out / 'contracts' / (attempt['proposal_id'] + '.json')).read_text())
        if (_hash({k: v for k, v in contract.items() if k != 'contract_hash'}) != attempt['contract_hash']
                or contract['contract_hash'] != attempt['contract_hash']
                or _hash({'proposal_id': attempt['proposal_id'], 'contract_hash': attempt['contract_hash']}) != attempt['attempt_id']):
            raise ValueError('reservation does not match preregistered review')
        economics = contract['proposal']['split'] == ECONOMIC_SPLIT
        if economics:
            _economic_scope(root, cfg, contract['proposal'], out)
        rows=_read_jsonl(out/'experiment_reservations.jsonl')
        existing=next((r for r in rows if r['attempt_id']==attempt['attempt_id']),None)
        if existing:return existing
        day=datetime.now(timezone.utc).date().isoformat()
        used = _economic_day_reservations(root, out, day) if economics else sum(r['timestamp_utc'][:10] == day for r in rows)
        if used >= cfg['experiment_budget_per_utc_day']:
            raise ValueError('Factory daily experiment budget exhausted before execution')
        row={'attempt_id':attempt['attempt_id'],'contract_hash':attempt['contract_hash'],'timestamp_utc':datetime.now(timezone.utc).isoformat()}
        _append_jsonl(out/'experiment_reservations.jsonl',[row])
        return row


def execute_review_economics(root: Path | str, attempt: dict[str, Any]) -> dict[str, Any]:
    """Run the approved offline worker after claiming the shared slot."""
    import os
    import subprocess
    import sys

    root = Path(root).resolve()
    out = root / "runtime/alpha_research_factory/task4"
    cfg = json.loads((root / "config/task4_review_contract.json").read_text())
    contract = json.loads((out / "contracts" / (attempt["proposal_id"] + ".json")).read_text())
    proposal = contract["proposal"]
    if proposal["split"] != ECONOMIC_SPLIT:
        raise ValueError("not an economic proposal")
    approved, worker = _economic_scope(root, cfg, proposal, out)
    art = root / approved["artifacts"]
    if (art != art.resolve() or not art.is_relative_to(root / "runtime")
            or art == root / "runtime" or art.is_relative_to(out.parent)):
        raise ValueError("economic worker artifacts must use the configured research directory")
    reserve_review_experiment(root, attempt)
    art.mkdir(exist_ok=True, parents=True)
    with (art / "worker.started.json").open("x") as stream:
        stream.write(_canonical({"attempt_id": attempt["attempt_id"], "contract_hash": attempt["contract_hash"]}))
        stream.flush()
        os.fsync(stream.fileno())
    trace = {"input_hash": proposal["input_hash"], "worker_hash": proposal["worker_hash"],
             "evidence_grade": "EXPOSED_CONDITIONAL_ONLY"}
    with (art / "worker.log").open("x") as log:
        try:
            subprocess.run([sys.executable, str(worker), "evaluate"], cwd=art, check=True, timeout=120,
                           env={"PYTHONPATH": f"{root / 'src'}:{root}", "OPENBLAS_NUM_THREADS": "1"},
                           stdout=log, stderr=subprocess.STDOUT)
            payload = json.loads((art / "worker_result.json").read_text())
            if payload.get("status") != "EXPLORATORY_ECONOMICS_COMPLETED":
                raise ValueError("economic worker returned an invalid status")
            result = {**payload, **trace}
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            result = {**trace, "status": "EXPLORATORY_ECONOMICS_FAILED", "cases": 0, "failure": type(exc).__name__}
    return record_review_experiment(root, attempt, result)


def find_review_hypothesis(root: Path | str, proposal: dict[str, Any], *, directory: Path | None = None) -> dict[str, Any] | None:
    """Same problem/method is a follow-up, not a new search just by changing data."""
    out=Path(directory) if directory else Path(root)/'runtime/alpha_research_factory/task4'
    for attempt in _read_jsonl(out/'attempt_registry.jsonl'):
        contract=json.loads((out/'contracts'/(attempt['proposal_id']+'.json')).read_text())
        fingerprint=contract.pop('contract_hash')
        if _hash(contract)!=fingerprint:raise ValueError('Factory contract integrity failure')
        prior=contract['proposal']
        if all(prior[k]==proposal[k] for k in ('target','champion','challenger')):
            return attempt
    return None
