"""Deterministic, non-execution diagnostic stage for Alpha Research Factory."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from quant_harness.alpha_research_factory import _append_jsonl, _canonical, _hash, _read_jsonl
from quant_harness.v77_corrected_price_allocation.engine import _load_config, load_adjusted_market


SCHEMA_VERSION = "ALPHA_RESEARCH_DIAGNOSTIC_V1"


def _file_hash(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _verify_contract(path: Path, proposal_id: str) -> dict[str, Any]:
    contract = json.loads(path.read_text(encoding="utf-8"))
    claimed = contract.pop("contract_hash", None)
    if not claimed or _hash(contract) != claimed:
        raise RuntimeError("BLOCKED_CONTRACT_TAMPER")
    if contract.get("proposal_id") != proposal_id:
        raise RuntimeError("BLOCKED_CONTRACT_PROPOSAL_MISMATCH")
    if contract.get("metric_output", {}).get("status") != "NOT_RUN":
        raise RuntimeError("BLOCKED_CONTRACT_METRIC_STATE_INVALID")
    contract["contract_hash"] = claimed
    return contract


def _verify_existing_artifact(path: Path, *, contract_hash: str, data_hash: str) -> dict[str, Any] | None:
    if not path.exists():
        return None
    previous = json.loads(path.read_text(encoding="utf-8"))
    if previous.get("contract_hash") != contract_hash or previous.get("data_hash") != data_hash:
        raise RuntimeError("BLOCKED_CONTRACT_OR_DATA_HASH_MISMATCH")
    return previous


def assert_next_stage_allowed(status: str, requested_stage: str) -> None:
    """Prevent feasibility/replay from bypassing a verified diagnostic pass."""
    if requested_stage not in {"EXECUTION_FEASIBILITY", "OPERATIONAL_REPLAY"}:
        raise ValueError("unknown research stage")
    if status != "READY_FOR_ROBUSTNESS":
        raise RuntimeError("BLOCKED_STAGE_SKIP_DIAGNOSTIC")


def _data_hash(root: Path, tickers: list[str], cfg: Any) -> str:
    paths = [root / cfg.etf_source / "universe.csv"] + [root / cfg.etf_source / f"{ticker}_1d.csv" for ticker in tickers]
    digest = sha256()
    for path in sorted(paths, key=lambda x: str(x)):
        digest.update(str(path.relative_to(root)).replace("\\", "/").encode())
        digest.update(_file_hash(path).encode())
    return digest.hexdigest()


def calculate_d1_reversal_metrics(
    close: pd.DataFrame, *, horizons: list[int], minimum_cross_section_observations: int,
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Rank D-1 5-day reversal against close-to-close future returns.

    A decision at D sees close through D-1. Labels are D close to D+h close;
    they are research outcomes, never executable inputs.
    """
    signal = -close.pct_change(5, fill_method=None).shift(1)
    rows: list[dict[str, Any]] = []
    reasons: Counter[str] = Counter()
    for horizon in horizons:
        future = close.pct_change(horizon, fill_method=None).shift(-horizon)
        for date in close.index:
            score, outcome = signal.loc[date], future.loc[date]
            valid = score.notna() & outcome.notna()
            count = int(valid.sum())
            if count < minimum_cross_section_observations:
                if score.notna().sum() < minimum_cross_section_observations:
                    reasons["SIGNAL_WARMUP_OR_MISSING_CLOSE"] += 1
                elif outcome.notna().sum() < minimum_cross_section_observations:
                    reasons["FORWARD_HORIZON_UNAVAILABLE"] += 1
                else:
                    reasons["INSUFFICIENT_JOINT_COVERAGE"] += 1
                continue
            ranked_score = score[valid].rank(method="average")
            ranked_return = outcome[valid].rank(method="average")
            ic = float(ranked_score.corr(ranked_return, method="pearson"))
            ordered = score[valid].sort_values(ascending=False)
            top, bottom = ordered.index[:3], ordered.index[-3:]
            spread = float(outcome.loc[top].mean() - outcome.loc[bottom].mean())
            rows.append({"date": date, "horizon_sessions": horizon, "rank_ic": ic, "top3_bottom3_spread": spread, "coverage": count})
    return pd.DataFrame(rows, columns=["date", "horizon_sessions", "rank_ic", "top3_bottom3_spread", "coverage"]), dict(reasons)


def summarize_metrics(metrics: pd.DataFrame, *, horizons: list[int], minimum_usable_dates: int, criteria: dict[str, Any], nan_reasons: dict[str, int]) -> tuple[pd.DataFrame, str]:
    rows: list[dict[str, Any]] = []
    for horizon in horizons:
        part = metrics[metrics["horizon_sessions"].eq(horizon)]
        count = len(part)
        rows.append({
            "horizon_sessions": horizon,
            "usable_dates": count,
            "coverage_mean": float(part["coverage"].mean()) if count else np.nan,
            "rank_ic_mean": float(part["rank_ic"].mean()) if count else np.nan,
            "rank_ic_ir": float(part["rank_ic"].mean() / part["rank_ic"].std(ddof=1)) if count > 1 and float(part["rank_ic"].std(ddof=1)) > 0 else np.nan,
            "top3_bottom3_spread_mean": float(part["top3_bottom3_spread"].mean()) if count else np.nan,
            "positive_ic_ratio": float(part["rank_ic"].gt(0).mean()) if count else np.nan,
            "coverage_gate": count >= minimum_usable_dates,
        })
    summary = pd.DataFrame(rows)
    if metrics.empty:
        return summary, "BLOCKED_DIAGNOSTIC_NOT_RUN"
    positive_ic = int((summary["coverage_gate"] & summary["rank_ic_mean"].gt(0)).sum())
    positive_spread = int((summary["coverage_gate"] & summary["top3_bottom3_spread_mean"].gt(0)).sum())
    unknown_nan = int(nan_reasons.get("UNKNOWN", 0))
    passed = (
        positive_ic >= int(criteria["minimum_horizons_with_positive_rank_ic"])
        and positive_spread >= int(criteria["minimum_horizons_with_positive_top3_bottom3_spread"])
        and unknown_nan <= int(criteria["unknown_nan_reasons_allowed"])
    )
    return summary, "READY_FOR_ROBUSTNESS" if passed else "REJECTED_DIAGNOSTIC"


def run(root: Path | str, *, output_dir: Path | str | None = None) -> dict[str, Any]:
    root = Path(root)
    cfg_path = root / "config/reversal_5d_diagnostic_v1.yaml"
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    if cfg.get("schema_version") != SCHEMA_VERSION:
        raise RuntimeError("BLOCKED_DIAGNOSTIC_CONFIG")
    contract_path = root / cfg["proposal_contract"]
    if not contract_path.exists():
        return {"status": "ALPHA_FACTORY_DIAGNOSTIC_STAGE_INVALID", "attempt_status": "BLOCKED_DIAGNOSTIC_NOT_RUN", "reason": "MISSING_IMMUTABLE_CONTRACT"}
    contract = _verify_contract(contract_path, str(cfg["proposal_id"]))
    v77_cfg = _load_config(root)
    market = load_adjusted_market(root, v77_cfg)
    all_tickers = [str(t) for t in market["close"].columns if str(t) not in {v77_cfg.benchmark_ticker, *cfg["exclude_tickers"]}]
    if len(all_tickers) != 25:
        raise RuntimeError(f"BLOCKED_UNIVERSE_SIZE expected=25 actual={len(all_tickers)}")
    close = market["close"].reindex(columns=all_tickers)
    data_hash = _data_hash(root, all_tickers, v77_cfg)
    out = Path(output_dir) if output_dir else root / "runtime/alpha_research_factory"
    artifact_path = out / "diagnostics" / "REVERSAL_5D_metrics.json"
    previous = _verify_existing_artifact(artifact_path, contract_hash=contract["contract_hash"], data_hash=data_hash)
    if previous is not None:
        return previous["report"]
    horizons = [int(x) for x in cfg["forward_return_horizons_sessions"]]
    metrics, nan_reasons = calculate_d1_reversal_metrics(close, horizons=horizons, minimum_cross_section_observations=int(cfg["minimum_cross_section_observations"]))
    summary, next_status = summarize_metrics(metrics, horizons=horizons, minimum_usable_dates=int(cfg["minimum_usable_dates_per_horizon"]), criteria=cfg["pass_criteria"], nan_reasons=nan_reasons)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    attempt_id = _hash({"proposal_id": contract["proposal_id"], "contract_hash": contract["contract_hash"]})
    report = {
        "status": "ALPHA_FACTORY_DIAGNOSTIC_STAGE_VALID",
        "attempt_status": next_status,
        "proposal_id": contract["proposal_id"], "contract_hash": contract["contract_hash"], "data_hash": data_hash,
        "calculation_version": cfg["calculation_version"], "data_cutoff": str(close.index.max().date()),
        "universe_size": len(all_tickers), "horizons": horizons, "nan_reasons": nan_reasons,
        "v101_called": False, "operational_replay_called": False, "operational_replay_budget": {"used": 0, "limit": 1},
        "broker_mutation_calls": 0, "capital_mutation": False,
    }
    artifact = {"contract_hash": contract["contract_hash"], "data_hash": data_hash, "report": report, "summary": summary.to_dict("records"), "metrics": metrics.to_dict("records")}
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    registry_path, events_path, trace_path = out / "diagnostic_registry.jsonl", out / "state_events.jsonl", out / "agent_invocation_trace.jsonl"
    existing = _read_jsonl(registry_path)
    key = _hash({"attempt_id": attempt_id, "contract_hash": contract["contract_hash"], "data_hash": data_hash, "calculation_version": cfg["calculation_version"]})
    if not any(row.get("diagnostic_key") == key for row in existing):
        _append_jsonl(registry_path, [{"diagnostic_key": key, "attempt_id": attempt_id, "timestamp_utc": now, **report}])
        _append_jsonl(events_path, [{"timestamp_utc": now, "attempt_id": attempt_id, "from": "BLOCKED_DIAGNOSTIC_NOT_RUN", "to": next_status, "reason": "DETERMINISTIC_METRICS_VERIFIED"}])
        _append_jsonl(trace_path, [
            {"proposal_id": contract["proposal_id"], "agent": "CandidateSelectionAgent", "research_role": "RANK_IC_AND_SPREAD", "invocation": "INVOKED", "reason": "DETERMINISTIC_D1_METRICS", "capital_mutation": False},
            {"proposal_id": contract["proposal_id"], "agent": "RiskExecutionAgent", "research_role": "V101_EXECUTION_FEASIBILITY", "invocation": "NOT_INVOKED", "reason": "SEPARATE_STAGE", "capital_mutation": False},
            {"proposal_id": contract["proposal_id"], "agent": "ReviewFeedbackAgent", "research_role": "STATE_TRANSITION", "invocation": "INVOKED", "reason": next_status, "capital_mutation": False},
        ])
    return report
