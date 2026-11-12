from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any

import numpy as np
import pandas as pd
import yaml

from .policy import ACTIVE_REVIEW_FEEDBACK_POLICY, REVIEW_FEEDBACK_AGENT_VERSION

REPORT = "v103_review_feedback_agent"
RELEASE_TIMESTAMP = "2026-07-19T00:00:00Z"


@dataclass(frozen=True)
class SourceSpec:
    release: str
    path: str
    scope: str


def _cfg(root: Path) -> dict[str, Any]:
    return yaml.safe_load((root / "config/v103_review_feedback_agent.yaml").read_text(encoding="utf-8"))


def _sha_bytes(value: bytes) -> str:
    return sha256(value).hexdigest()


def _sha_file(path: Path) -> str:
    return _sha_bytes(path.read_bytes())


def _canonical_hash(payload: dict[str, Any]) -> str:
    return _sha_bytes(json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str, separators=(",", ":")).encode("utf-8"))


def _release_number(value: str) -> int:
    match = re.search(r"(\d+)", str(value))
    return int(match.group(1)) if match else 0


def _as_bool(value: Any) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _status_from_row(row: dict[str, Any]) -> str:
    raw = str(row.get("status", "")).strip()
    if raw and raw.lower() != "nan":
        return raw
    if _as_bool(row.get("promoted", False)):
        return "PROMOTED"
    if _as_bool(row.get("forward_shadow_only", False)) or _as_bool(row.get("shadow_eligible", False)):
        return "FORWARD_SHADOW_ONLY"
    if not _as_bool(row.get("applicable", True)):
        return "NOT_APPLICABLE"
    return "BACKTEST_REJECTED"


def _probability(row: dict[str, Any]) -> float | None:
    for key in (
        "validation_bootstrap_probability",
        "bootstrap_positive_probability",
        "bootstrap_probability",
    ):
        value = pd.to_numeric(pd.Series([row.get(key)]), errors="coerce").iloc[0]
        if pd.notna(value):
            return float(value)
    return None


def _familywise_probability(row: dict[str, Any]) -> float | None:
    for key in ("familywise_probability_lower_bound", "familywise_probability"):
        value = pd.to_numeric(pd.Series([row.get(key)]), errors="coerce").iloc[0]
        if pd.notna(value):
            return float(value)
    return None


def _add_attempt(
    rows: list[dict[str, Any]],
    *,
    release: str,
    source_report: str,
    source_row: int,
    scope: str,
    policy: str,
    strategy: str,
    status: str,
    raw: dict[str, Any],
    cfg: dict[str, Any],
) -> None:
    policy = str(policy).strip()
    strategy = str(strategy).strip().upper() or "ALL"
    status = str(status).strip()
    applicable = "NOT_APPLICABLE" not in status
    data_blocked = "DATA_BLOCKED" in status
    forward_candidate = "FORWARD_SHADOW" in status
    promoted = status == "PROMOTED" or _as_bool(raw.get("promoted", False))
    canonical = {
        "policy": policy,
        "strategy": strategy,
        "release": release,
        "source_report": source_report,
        "source_row": int(source_row),
    }
    fingerprint = _canonical_hash(canonical)
    attempt_id = f"ATTEMPT-{release}-{source_row:03d}-{fingerprint[:10]}"
    rows.append(
        {
            "attempt_id": attempt_id,
            "source_release": release,
            "source_release_number": _release_number(release),
            "source_report": source_report,
            "source_row": int(source_row),
            "agent_scope": scope,
            "strategy": strategy,
            "policy": policy,
            "status": status,
            "applicable": applicable,
            "data_blocked": data_blocked,
            "forward_candidate": forward_candidate,
            "promoted": promoted,
            "raw_bootstrap_probability": _probability(raw),
            "reported_familywise_probability": _familywise_probability(raw),
            "historical_data_end": cfg["historical_data_end"],
            "research_epoch": cfg["research_epoch"],
            "historical_promotion_allowed": False,
            "capital_authority": "NONE",
            "candidate_fingerprint": fingerprint,
            "raw_result_json": json.dumps(raw, sort_keys=True, ensure_ascii=False, default=str),
        }
    )


def _collect_attempts(root: Path, cfg: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    # V90~V93 automated feedback candidates: count unique tested configurations, not no-op folds.
    v92 = root / "reports/v92_automated_research/v92_candidate_summary.csv"
    if v92.exists():
        frame = pd.read_csv(v92)
        for idx, row in enumerate(frame.to_dict("records"), 1):
            status = "FORWARD_SHADOW_ONLY" if _as_bool(row.get("shadow_eligible", False)) else "BACKTEST_REJECTED"
            _add_attempt(rows, release="V93", source_report=str(v92.relative_to(root)), source_row=idx, scope="LEGACY_FEEDBACK_RESEARCH", policy=row["candidate"], strategy=row["family"], status=status, raw=row, cfg=cfg)

    specs = [
        SourceSpec("V95", "reports/v95_market_regime_agent/v95_candidate_promotion.csv", "MARKET_REGIME"),
        SourceSpec("V96", "reports/v96_market_regime_extension/v96_candidate_promotion.csv", "MARKET_REGIME"),
        SourceSpec("V98", "reports/v98_candidate_selection_agent/v98_candidate_promotion.csv", "CANDIDATE_SELECTION"),
        SourceSpec("V99", "reports/v99_candidate_selection_deep_research/v99_candidate_promotion.csv", "CANDIDATE_SELECTION"),
        SourceSpec("V100", "reports/v100_strategy_agent/v100_candidate_promotion.csv", "STRATEGY_ALLOCATION"),
        SourceSpec("V101", "reports/v101_risk_execution_agent/v101_candidate_promotion.csv", "RISK_EXECUTION"),
        SourceSpec("V102", "reports/v102_market_evidence_agent/v102_candidate_promotion.csv", "MARKET_EVIDENCE"),
    ]
    for spec in specs:
        path = root / spec.path
        if not path.exists():
            continue
        frame = pd.read_csv(path)
        for idx, row in enumerate(frame.to_dict("records"), 1):
            policy = row.get("policy") or row.get("candidate") or row.get("scenario")
            strategy = row.get("strategy", "BOTH" if spec.scope == "MARKET_REGIME" else "ALL")
            status = _status_from_row(row)
            _add_attempt(rows, release=spec.release, source_report=spec.path, source_row=idx, scope=spec.scope, policy=policy, strategy=strategy, status=status, raw=row, cfg=cfg)

    attempts = pd.DataFrame(rows)
    if attempts.empty:
        return attempts
    attempts = attempts.sort_values(["source_release_number", "source_report", "source_row", "strategy", "policy"]).reset_index(drop=True)
    attempts["attempt_index_global"] = np.arange(1, len(attempts) + 1)
    attempts["counts_as_trial"] = attempts["applicable"].astype(bool)
    attempts["canonical_policy_key"] = attempts["agent_scope"].astype(str) + "|" + attempts["strategy"].astype(str) + "|" + attempts["policy"].astype(str)
    attempts["duplicate_prior_attempt"] = attempts.duplicated("canonical_policy_key", keep="first")
    attempts["counts_as_unique_trial"] = attempts["counts_as_trial"] & ~attempts["duplicate_prior_attempt"]
    return attempts


def _expand_strategy(strategy: str) -> list[str]:
    value = str(strategy).upper()
    if value in {"BOTH", "ALL"}:
        return ["V69", "V79"]
    if value in {"V69", "V79"}:
        return [value]
    return []


def _block_bootstrap_positive_probability(values: pd.Series, *, block: int = 20, samples: int = 1000) -> float:
    clean = pd.to_numeric(values, errors="coerce").dropna().to_numpy(dtype=float)
    n = len(clean)
    if n < 20:
        return 0.0
    rng = np.random.default_rng(103)
    wins = 0
    block = max(1, min(int(block), n))
    for _ in range(int(samples)):
        pieces: list[np.ndarray] = []
        size = 0
        while size < n:
            start = int(rng.integers(0, n))
            idx = (np.arange(start, start + block) % n).astype(int)
            piece = clean[idx]
            pieces.append(piece)
            size += len(piece)
        sample = np.concatenate(pieces)[:n]
        wins += int(float(sample.sum()) > 0.0)
    return float(wins / samples)


def _runtime_adapters(root: Path) -> dict[str, str]:
    path = root / "config/v103_shadow_runtime_contract.yaml"
    if not path.exists():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    result: dict[str, str] = {}
    for key, value in (payload.get("candidates") or {}).items():
        if isinstance(value, dict):
            result[str(key)] = str(value.get("adapter_status", "UNIMPLEMENTED"))
        else:
            result[str(key)] = str(value)
    return result


def _forward_lifecycle(attempts: pd.DataFrame, cfg: dict[str, Any], root: Path) -> pd.DataFrame:
    columns = [
        "candidate_id", "candidate_fingerprint", "parent_strategy", "policy", "agent_scope", "discovery_release",
        "source_report", "source_row", "historical_status", "historical_trial_count_strategy", "historical_raw_bootstrap_probability",
        "historical_familywise_probability_lower_bound", "queue_rank", "forward_status", "forward_sessions", "changed_decisions",
        "matured_20d_events", "matured_60d_events", "promotion_from_historical_allowed", "automatic_promotion_allowed",
        "capital_authority", "candidate_runtime_compatible", "adapter_status", "fingerprint_conflicts", "duplicate_session_rows", "data_failures", "reconciliation_failures",
        "cost_adjusted_excess_return_pp", "mdd_delta_pp", "forward_bootstrap_probability", "forward_raw_pvalue",
        "forward_evaluation_ready", "raw_promotion_review_ready", "holm_rank", "holm_threshold", "holm_passed",
        "promotion_decision", "reason",
    ]
    if attempts.empty:
        return pd.DataFrame(columns=columns)
    eligible = attempts[attempts["forward_candidate"].astype(bool) & attempts["counts_as_unique_trial"].astype(bool)].copy()
    expanded: list[dict[str, Any]] = []
    for row in eligible.to_dict("records"):
        for strategy in _expand_strategy(row["strategy"]):
            payload = {
                "source_fingerprint": row["candidate_fingerprint"],
                "strategy": strategy,
                "policy": row["policy"],
                "active_policy": ACTIVE_REVIEW_FEEDBACK_POLICY,
            }
            fingerprint = _canonical_hash(payload)
            expanded.append({**row, "parent_strategy": strategy, "expanded_fingerprint": fingerprint})
    lifecycle = pd.DataFrame(expanded)
    if lifecycle.empty:
        return pd.DataFrame(columns=columns)
    lifecycle = lifecycle.sort_values(["parent_strategy", "source_release_number", "source_report", "source_row", "policy"]).reset_index(drop=True)
    lifecycle["queue_rank"] = lifecycle.groupby("parent_strategy").cumcount() + 1
    maximum = int(cfg["experiment_governance"]["maximum_parallel_forward_candidates_per_strategy"])
    adapters = _runtime_adapters(root)

    obs_path = root / cfg["paths"]["forward_observations"]
    observations = pd.read_csv(obs_path) if obs_path.exists() else pd.DataFrame()
    result: list[dict[str, Any]] = []
    for row in lifecycle.to_dict("records"):
        strategy = row["parent_strategy"]
        cid = f"feedback_{strategy.lower()}_{str(row['policy']).lower()}".replace(" ", "_")
        cid = re.sub(r"[^a-z0-9_]+", "_", cid)
        candidate_obs = observations[observations.get("candidate_id", pd.Series(dtype=str)).astype(str).eq(cid)].copy() if len(observations) else pd.DataFrame()
        sessions = int(candidate_obs["session"].nunique()) if len(candidate_obs) and "session" in candidate_obs else 0
        duplicate_session_rows = int(candidate_obs.duplicated(["session", "candidate_id"]).sum()) if len(candidate_obs) and {"session", "candidate_id"}.issubset(candidate_obs.columns) else 0
        fingerprint_conflicts = 0
        if len(candidate_obs) and "candidate_fingerprint" in candidate_obs:
            fingerprint_conflicts = int(candidate_obs["candidate_fingerprint"].astype(str).ne(str(row["expanded_fingerprint"])).sum())
        changes = int(candidate_obs.get("changed_decision", pd.Series(dtype=bool)).map(_as_bool).sum()) if len(candidate_obs) else 0
        mature20 = int(candidate_obs.get("matured_20d", pd.Series(dtype=bool)).map(_as_bool).sum()) if len(candidate_obs) else 0
        mature60 = int(candidate_obs.get("matured_60d", pd.Series(dtype=bool)).map(_as_bool).sum()) if len(candidate_obs) else 0
        strategy_attempts = attempts[
            attempts["counts_as_unique_trial"].astype(bool)
            & attempts["strategy"].astype(str).str.upper().isin([strategy, "BOTH", "ALL"])
        ]
        n = int(len(strategy_attempts))
        raw_p = row.get("raw_bootstrap_probability")
        corrected = None
        if raw_p is not None and pd.notna(raw_p):
            corrected = max(0.0, 1.0 - n * (1.0 - float(raw_p)))
        adapter_status = adapters.get(cid, "UNIMPLEMENTED")
        runtime_compatible = adapter_status == "IMPLEMENTED_AND_TESTED"
        if int(row["queue_rank"]) > maximum:
            status = "FORWARD_QUEUED_CAPACITY"
        elif not runtime_compatible:
            status = "FORWARD_CONTRACT_READY_RUNTIME_BLOCKED"
        elif sessions == 0:
            status = "FORWARD_READY_NOT_STARTED"
        else:
            status = "FORWARD_RUNNING"

        data_failures = 0
        reconcile_failures = 0
        excess_return_pp = np.nan
        mdd_delta_pp = np.nan
        bootstrap_probability = 0.0
        if len(candidate_obs):
            data_failures = int((~candidate_obs.get("data_gate_passed", pd.Series(dtype=bool)).map(_as_bool)).sum())
            reconcile_failures = int((~candidate_obs.get("reconciliation_passed", pd.Series(dtype=bool)).map(_as_bool)).sum())
            parent_nav = pd.to_numeric(candidate_obs.get("parent_nav_krw"), errors="coerce").dropna()
            candidate_nav = pd.to_numeric(candidate_obs.get("candidate_nav_krw"), errors="coerce").dropna()
            if len(parent_nav) >= 2 and len(candidate_nav) >= 2:
                parent_total = float(parent_nav.iloc[-1] / parent_nav.iloc[0] - 1.0)
                candidate_total = float(candidate_nav.iloc[-1] / candidate_nav.iloc[0] - 1.0)
                excess_return_pp = (candidate_total - parent_total) * 100.0
            pmdd = pd.to_numeric(candidate_obs.get("parent_mdd_pct"), errors="coerce").dropna()
            cmdd = pd.to_numeric(candidate_obs.get("candidate_mdd_pct"), errors="coerce").dropna()
            if len(pmdd) and len(cmdd):
                mdd_delta_pp = float(cmdd.iloc[-1] - pmdd.iloc[-1])
            daily_excess = pd.to_numeric(candidate_obs.get("candidate_daily_return"), errors="coerce") - pd.to_numeric(candidate_obs.get("parent_daily_return"), errors="coerce")
            bootstrap_probability = _block_bootstrap_positive_probability(daily_excess)

        fcfg = cfg["forward"]
        evaluation_ready = (
            runtime_compatible
            and sessions >= int(fcfg["minimum_sessions_for_evaluation"])
            and changes >= int(fcfg["minimum_changed_decisions_for_evaluation"])
            and mature20 >= int(fcfg["minimum_matured_20d_events"])
            and mature60 >= int(fcfg["minimum_matured_60d_events"])
            and data_failures <= int(fcfg["data_failures_allowed"])
            and reconcile_failures <= int(fcfg["reconciliation_failures_allowed"])
            and fingerprint_conflicts == 0
            and duplicate_session_rows == 0
        )
        promotion_review_ready = (
            evaluation_ready
            and sessions >= int(fcfg["recommended_sessions_for_promotion_review"])
            and changes >= int(fcfg["minimum_changed_decisions_for_promotion_review"])
            and pd.notna(excess_return_pp)
            and float(excess_return_pp) > float(fcfg["minimum_cost_adjusted_excess_return_pp"])
            and pd.notna(mdd_delta_pp)
            and float(mdd_delta_pp) >= -float(fcfg["mdd_tolerance_pp"])
            and bootstrap_probability >= float(fcfg["bootstrap_probability_min"])
        )
        if fingerprint_conflicts > 0:
            promotion = "BLOCKED_CANDIDATE_FINGERPRINT_MISMATCH"
            reason = "Observed candidate fingerprint differs from the frozen candidate contract."
        elif duplicate_session_rows > 0:
            promotion = "BLOCKED_DUPLICATE_FORWARD_SESSION"
            reason = "More than one observation exists for the same candidate and session."
        elif not runtime_compatible:
            promotion = "BLOCKED_RUNTIME_ADAPTER_UNIMPLEMENTED"
            reason = "Candidate has historical screening evidence but no tested isolated forward runtime adapter."
        elif sessions == 0:
            promotion = "BLOCKED_NO_FORWARD_OBSERVATIONS"
            reason = "Historical results are screening evidence only; promotion requires new frozen forward observations."
        elif not evaluation_ready:
            promotion = "FORWARD_RUNNING_INSUFFICIENT"
            reason = "Forward observations exist but maturity, changed-decision, data, or reconciliation gates are incomplete."
        elif not promotion_review_ready:
            promotion = "FORWARD_EVALUATED_NOT_PROMOTION_READY"
            reason = "Forward evaluation is possible but 120-session performance, drawdown, or bootstrap gates are not all met."
        else:
            promotion = "PENDING_HOLM_MULTIPLE_TESTING_REVIEW"
            reason = "Raw forward gates pass; familywise Holm-Bonferroni and human review remain mandatory."
        result.append(
            {
                "candidate_id": cid,
                "candidate_fingerprint": row["expanded_fingerprint"],
                "parent_strategy": strategy,
                "policy": row["policy"],
                "agent_scope": row["agent_scope"],
                "discovery_release": row["source_release"],
                "source_report": row["source_report"],
                "source_row": int(row["source_row"]),
                "historical_status": row["status"],
                "historical_trial_count_strategy": n,
                "historical_raw_bootstrap_probability": raw_p,
                "historical_familywise_probability_lower_bound": corrected,
                "queue_rank": int(row["queue_rank"]),
                "forward_status": status,
                "forward_sessions": sessions,
                "changed_decisions": changes,
                "matured_20d_events": mature20,
                "matured_60d_events": mature60,
                "promotion_from_historical_allowed": False,
                "automatic_promotion_allowed": False,
                "capital_authority": "NONE",
                "candidate_runtime_compatible": runtime_compatible,
                "adapter_status": adapter_status,
                "fingerprint_conflicts": fingerprint_conflicts,
                "duplicate_session_rows": duplicate_session_rows,
                "data_failures": data_failures,
                "reconciliation_failures": reconcile_failures,
                "cost_adjusted_excess_return_pp": excess_return_pp,
                "mdd_delta_pp": mdd_delta_pp,
                "forward_bootstrap_probability": bootstrap_probability,
                "forward_raw_pvalue": 1.0 - bootstrap_probability,
                "forward_evaluation_ready": evaluation_ready,
                "raw_promotion_review_ready": promotion_review_ready,
                "holm_rank": np.nan,
                "holm_threshold": np.nan,
                "holm_passed": False,
                "promotion_decision": promotion,
                "reason": reason,
            }
        )
    frame = pd.DataFrame(result, columns=columns).sort_values(["parent_strategy", "queue_rank", "candidate_id"]).reset_index(drop=True)
    alpha = float(cfg["experiment_governance"]["nominal_alpha"])
    for strategy in ("V69", "V79"):
        eligible_idx = frame.index[(frame["parent_strategy"].eq(strategy)) & frame["raw_promotion_review_ready"].astype(bool)].tolist()
        ordered = sorted(eligible_idx, key=lambda i: (float(frame.at[i, "forward_raw_pvalue"]), str(frame.at[i, "candidate_id"])))
        family_size = len(ordered)
        continue_reject = True
        for rank, idx in enumerate(ordered, 1):
            threshold = alpha / max(family_size - rank + 1, 1)
            passed = continue_reject and float(frame.at[idx, "forward_raw_pvalue"]) <= threshold
            frame.at[idx, "holm_rank"] = rank
            frame.at[idx, "holm_threshold"] = threshold
            frame.at[idx, "holm_passed"] = passed
            if not passed:
                continue_reject = False
            if passed:
                frame.at[idx, "promotion_decision"] = "HUMAN_PROMOTION_REVIEW_ELIGIBLE"
                frame.at[idx, "reason"] = "Frozen forward gates and Holm-Bonferroni pass; human approval is still required and capital authority remains NONE."
            else:
                frame.at[idx, "promotion_decision"] = "FORWARD_MULTIPLE_TESTING_NOT_CLEARED"
                frame.at[idx, "reason"] = "Raw forward gates pass but the strategy-family Holm-Bonferroni threshold is not cleared."
    return frame


def _multiple_testing(attempts: pd.DataFrame, lifecycle: pd.DataFrame, cfg: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    alpha = float(cfg["experiment_governance"]["nominal_alpha"])
    for strategy in ("V69", "V79"):
        group = attempts[
            attempts["counts_as_unique_trial"].astype(bool)
            & attempts["strategy"].astype(str).str.upper().isin([strategy, "BOTH", "ALL"])
        ]
        n = int(len(group))
        fwd = lifecycle[lifecycle["parent_strategy"].eq(strategy)] if not lifecycle.empty else lifecycle
        rows.append(
            {
                "strategy": strategy,
                "unique_historical_trials": n,
                "rejected_trials": int(group["status"].astype(str).str.contains("REJECTED").sum()),
                "data_blocked_trials": int(group["data_blocked"].astype(bool).sum()),
                "forward_candidates": int(len(fwd)),
                "forward_contract_slots": int(fwd["queue_rank"].le(int(cfg["experiment_governance"]["maximum_parallel_forward_candidates_per_strategy"])).sum()) if len(fwd) else 0,
                "forward_runtime_ready": int(fwd["forward_status"].eq("FORWARD_READY_NOT_STARTED").sum()) if len(fwd) else 0,
                "forward_runtime_blocked": int(fwd["forward_status"].eq("FORWARD_CONTRACT_READY_RUNTIME_BLOCKED").sum()) if len(fwd) else 0,
                "forward_queued": int(fwd["forward_status"].eq("FORWARD_QUEUED_CAPACITY").sum()) if len(fwd) else 0,
                "nominal_alpha": alpha,
                "bonferroni_alpha_if_same_family_reused": alpha / max(n, 1),
                "historical_promotion_allowed": False,
                "method_for_new_forward_family": cfg["experiment_governance"]["multiple_testing_method"],
            }
        )
    return pd.DataFrame(rows)


def _legacy_quality(root: Path, cfg: dict[str, Any]) -> tuple[bool, list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    passed = True
    for rel in cfg["legacy_pipeline"]["required_quality_reports"]:
        path = root / rel
        if not path.exists() and cfg["legacy_pipeline"].get("run_if_missing", True):
            if "v90_" in rel:
                from quant_harness.v90_trade_attribution.engine import run as runner
            elif "v91_" in rel:
                from quant_harness.v91_hypothesis_generator.engine import run as runner
            elif "v92_" in rel:
                from quant_harness.v92_automated_research.engine import run as runner
            else:
                from quant_harness.v93_shadow_promotion.engine import run as runner
            runner(root)
        if not path.exists():
            ok = False
            detail = "missing"
        else:
            frame = pd.read_csv(path)
            ok = bool(frame["passed"].map(_as_bool).all())
            detail = f"gates={len(frame)}"
        passed = passed and ok
        rows.append({"source": rel, "passed": ok, "detail": detail})
    return passed, rows


def _unsafe_feedback_baseline(root: Path) -> dict[str, Any]:
    path = root / "reports/v78_preregistered_alpha_research/v78_existing_agent_ablation.csv"
    if not path.exists():
        return {}
    frame = pd.read_csv(path)
    diag = frame[frame["variant"].eq("NINE_AGENT_DIAGNOSTIC")]
    unsafe = frame[frame["variant"].eq("FEEDBACK_AUTHORITY")]
    if diag.empty or unsafe.empty:
        return {}
    d, u = diag.iloc[0], unsafe.iloc[0]
    return {
        "diagnostic_return_pct": float(d["return_pct"]),
        "unsafe_feedback_authority_return_pct": float(u["return_pct"]),
        "unsafe_feedback_return_delta_pp": float(u["return_delta_vs_diagnostic_pp"]),
        "unsafe_feedback_authority_days": int(u["authority_days"]),
    }


def run(root: Path | str, *, output_dir: Path | str | None = None) -> dict[str, Any]:
    root = Path(root)
    out_dir = Path(output_dir) if output_dir is not None else root / "reports" / REPORT
    out_dir.mkdir(parents=True, exist_ok=True)
    cfg = _cfg(root)

    legacy_passed, legacy_rows = _legacy_quality(root, cfg)
    attempts = _collect_attempts(root, cfg)
    lifecycle = _forward_lifecycle(attempts, cfg, root)
    testing = _multiple_testing(attempts, lifecycle, cfg)
    unsafe = _unsafe_feedback_baseline(root)

    active_counts = lifecycle[lifecycle["forward_status"].isin(["FORWARD_READY_NOT_STARTED", "FORWARD_CONTRACT_READY_RUNTIME_BLOCKED"])].groupby("parent_strategy").size().to_dict() if len(lifecycle) else {}
    maximum = int(cfg["experiment_governance"]["maximum_parallel_forward_candidates_per_strategy"])
    observations_exist = (root / cfg["paths"]["forward_observations"]).exists()
    promoted = int(lifecycle["promotion_decision"].astype(str).str.contains("PROMOTED").sum()) if len(lifecycle) else 0

    quality_rows = [
        {"gate": "LEGACY_V90_V93_QUALITY_GATES_PASS", "passed": legacy_passed, "detail": json.dumps(legacy_rows, sort_keys=True)},
        {"gate": "RESEARCH_ATTEMPT_IDS_UNIQUE", "passed": bool(not attempts["attempt_id"].duplicated().any()) if len(attempts) else False, "detail": f"rows={len(attempts)}"},
        {"gate": "CANDIDATE_FINGERPRINTS_UNIQUE", "passed": bool(not lifecycle["candidate_fingerprint"].duplicated().any()) if len(lifecycle) else True, "detail": f"forward_candidates={len(lifecycle)}"},
        {"gate": "HISTORICAL_RESULTS_CANNOT_PROMOTE", "passed": bool((~attempts["historical_promotion_allowed"].astype(bool)).all()) if len(attempts) else False, "detail": cfg["research_epoch"]},
        {"gate": "NO_AUTOMATIC_PARENT_MUTATION", "passed": cfg["automatic_parent_mutation"] is False, "detail": ACTIVE_REVIEW_FEEDBACK_POLICY},
        {"gate": "NO_AUTOMATIC_CAPITAL_AUTHORITY", "passed": cfg["automatic_capital_authority"] is False and (lifecycle["capital_authority"].eq("NONE").all() if len(lifecycle) else True), "detail": "all candidates shadow-only"},
        {"gate": "FORWARD_QUEUE_CAP_ENFORCED", "passed": all(int(v) <= maximum for v in active_counts.values()), "detail": json.dumps(active_counts, sort_keys=True)},
        {"gate": "RUNTIME_ADAPTER_REQUIRED_BEFORE_FORWARD", "passed": bool((~lifecycle["candidate_runtime_compatible"].astype(bool)).all()) if len(lifecycle) else True, "detail": "current candidates are contract-ready but runtime-blocked; no false READY claim"},
        {"gate": "QUEUE_NOT_SORTED_BY_PERFORMANCE", "passed": cfg["experiment_governance"]["queue_order"] == "PREREGISTRATION_RELEASE_THEN_SOURCE_ROW" and cfg["experiment_governance"]["performance_ranking_for_queue_forbidden"] is True, "detail": cfg["experiment_governance"]["queue_order"]},
        {"gate": "NO_FORWARD_OBSERVATION_NO_PROMOTION", "passed": (not observations_exist and promoted == 0) or observations_exist, "detail": f"observations_exist={observations_exist};promoted={promoted}"},
        {"gate": "SAME_HISTORY_RETUNING_FORBIDDEN", "passed": cfg["experiment_governance"]["same_historical_data_retuning_forbidden"] is True, "detail": f"historical_end={cfg['historical_data_end']}"},
        {"gate": "LIVE_EXECUTION_BLOCKED", "passed": cfg["live_execution_allowed"] is False, "detail": "human review required after frozen forward"},
    ]
    quality = pd.DataFrame(quality_rows)

    shadow_candidates = []
    for row in lifecycle.to_dict("records"):
        parent_strategy_id = "v69_fixed80_daily_control" if row["parent_strategy"] == "V69" else "v79_core70_generic_trend30"
        shadow_candidates.append(
            {
                "strategy_id": row["candidate_id"],
                "candidate_id": row["candidate_id"],
                "scenario": row["policy"],
                "label": f"{row['parent_strategy']} {str(row['policy']).replace('_', ' ').title()}",
                "role": "SHADOW",
                "status": row["forward_status"],
                "parent_strategy_id": parent_strategy_id,
                "created_by": "FeedbackAgent",
                "managed_by": "v103",
                "source": "reports/v103_review_feedback_agent/v103_candidate_lifecycle.csv",
                "account_id": None,
                "candidate_fingerprint": row["candidate_fingerprint"],
                "parent_strategy": row["parent_strategy"],
                "policy": row["policy"],
                "agent_scope": row["agent_scope"],
                "queue_rank": int(row["queue_rank"]),
                "historical_screening_status": row["historical_status"],
                "promotion_from_historical_allowed": False,
                "capital_authority": "NONE",
                "runtime_compatible": bool(row["candidate_runtime_compatible"]),
                "parameters": {
                    "candidate_fingerprint": row["candidate_fingerprint"],
                    "agent_scope": row["agent_scope"],
                    "queue_rank": int(row["queue_rank"]),
                    "historical_screening_status": row["historical_status"],
                },
                "backtest_metrics": {
                    "historical_trial_count_strategy": int(row["historical_trial_count_strategy"]),
                    "historical_raw_bootstrap_probability": row["historical_raw_bootstrap_probability"],
                    "historical_familywise_probability_lower_bound": row["historical_familywise_probability_lower_bound"],
                },
                "forward_observation_contract": "data/contracts/v103_feedback_forward_observation_template.csv",
            }
        )
    registry = {
        "schema_version": 2,
        "release": "V103_REVIEW_FEEDBACK_AGENT",
        "created_at": RELEASE_TIMESTAMP,
        "active_policy": ACTIVE_REVIEW_FEEDBACK_POLICY,
        "historical_epoch": {"end": cfg["historical_data_end"], "use": "SCREENING_ONLY", "promotion_allowed": False},
        "forward_policy": cfg["forward"],
        "experiment_governance": cfg["experiment_governance"],
        "candidates": shadow_candidates,
        "automatic_parent_mutation": False,
        "automatic_capital_authority": False,
        "live_execution_allowed": False,
    }
    memory = {
        "schema_version": 1,
        "release": "V103_REVIEW_FEEDBACK_AGENT",
        "snapshot_at": RELEASE_TIMESTAMP,
        "historical_data_end": cfg["historical_data_end"],
        "cumulative_attempt_rows": int(len(attempts)),
        "cumulative_unique_trials": int(attempts["counts_as_unique_trial"].sum()) if len(attempts) else 0,
        "rejected_unique_trials": int((attempts["counts_as_unique_trial"].astype(bool) & attempts["status"].astype(str).str.contains("REJECTED")).sum()) if len(attempts) else 0,
        "data_blocked_unique_trials": int((attempts["counts_as_unique_trial"].astype(bool) & attempts["data_blocked"].astype(bool)).sum()) if len(attempts) else 0,
        "forward_candidate_count": int(len(lifecycle)),
        "candidate_fingerprints": lifecycle["candidate_fingerprint"].tolist() if len(lifecycle) else [],
        "attempt_fingerprints": attempts["candidate_fingerprint"].tolist() if len(attempts) else [],
        "next_cycle_rules": {
            "new_hypotheses_per_strategy": int(cfg["experiment_governance"]["maximum_new_hypotheses_per_strategy_cycle"]),
            "must_preregister_before_backtest": True,
            "same_history_retuning_forbidden": True,
            "promotion_requires_new_forward": True,
        },
    }

    attempts.to_csv(out_dir / "v103_research_attempt_ledger.csv", index=False)
    lifecycle.to_csv(out_dir / "v103_candidate_lifecycle.csv", index=False)
    promotion_cols = [
        "candidate_id", "parent_strategy", "policy", "agent_scope", "historical_status", "forward_status",
        "forward_sessions", "changed_decisions", "matured_20d_events", "matured_60d_events",
        "candidate_runtime_compatible", "forward_bootstrap_probability", "holm_passed",
        "promotion_decision", "capital_authority", "automatic_promotion_allowed", "reason",
    ]
    lifecycle[promotion_cols].to_csv(out_dir / "v103_candidate_promotion.csv", index=False)
    testing.to_csv(out_dir / "v103_multiple_testing_audit.csv", index=False)
    quality.to_csv(out_dir / "v103_quality_gates.csv", index=False)
    pd.DataFrame(legacy_rows).to_csv(out_dir / "v103_legacy_pipeline_audit.csv", index=False)
    (out_dir / "v103_forward_shadow_registry.json").write_text(json.dumps(registry, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    (out_dir / "v103_research_memory.json").write_text(json.dumps(memory, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    parent_source = root / "reports/v102_market_evidence_agent/v102_parent_parity.csv"
    if parent_source.exists():
        parent_parity = pd.read_csv(parent_source)
        parent_parity["review_feedback_policy"] = ACTIVE_REVIEW_FEEDBACK_POLICY
        parent_parity["parent_mutated"] = False
        parent_parity.to_csv(out_dir / "v103_parent_parity.csv", index=False)
    feedback_reference = pd.DataFrame([
        {
            "variant": "LEGACY_DIRECT_FEEDBACK_AUTHORITY",
            "return_pct": unsafe.get("unsafe_feedback_authority_return_pct", np.nan),
            "delta_vs_diagnostic_pp": unsafe.get("unsafe_feedback_return_delta_pp", np.nan),
            "authority_days": unsafe.get("unsafe_feedback_authority_days", np.nan),
            "capital_authority": "HISTORICAL_ABLATION_ONLY",
            "decision": "REJECT_DIRECT_CAPITAL_AUTHORITY",
        },
        {
            "variant": "V103_FROZEN_RESEARCH_GOVERNANCE",
            "return_pct": unsafe.get("diagnostic_return_pct", np.nan),
            "delta_vs_diagnostic_pp": 0.0,
            "authority_days": 0,
            "capital_authority": "NONE",
            "decision": "ACTIVE_RESEARCH_GOVERNANCE_PARENT_UNCHANGED",
        },
    ])
    feedback_reference.to_csv(out_dir / "v103_feedback_backtest_reference.csv", index=False)

    operational = pd.DataFrame(
        [
            {"area": "REAL_FILL_ATTRIBUTION", "required_real_data": "broker order/fill lifecycle joined to strategy decision hash", "block_condition": "fill or correction cannot be joined deterministically", "status": "UNVERIFIED_EXTERNAL"},
            {"area": "FORWARD_CANDIDATE_RUNTIME", "required_real_data": "daily parent/candidate target, order, fill, NAV and cost ledgers", "block_condition": "candidate runtime path or isolated account is unavailable", "status": "READY_CONTRACT_ONLY"},
            {"area": "RESEARCH_MEMORY_PERSISTENCE", "required_real_data": "durable append-only experiment registry across releases", "block_condition": "attempt count can be reset or edited without audit", "status": "RELEASE_SNAPSHOT_ONLY"},
            {"area": "MULTIPLE_TESTING", "required_real_data": "all attempted hypotheses including failed and abandoned runs", "block_condition": "unreported trial count or family membership", "status": "HISTORICAL_LEDGER_RECONSTRUCTED"},
            {"area": "FORWARD_MATURITY", "required_real_data": "minimum 60 sessions; promotion review at 120 sessions and 10 changed decisions", "block_condition": "insufficient mature 20d/60d outcomes", "status": "READY_NOT_STARTED"},
            {"area": "HUMAN_GOVERNANCE", "required_real_data": "signed promotion decision and immutable candidate hash", "block_condition": "automatic parent mutation or capital authority", "status": "MANDATORY"},
        ]
    )
    operational.to_csv(out_dir / "v103_operational_gap_register.csv", index=False)

    summary = {
        "release": "V103_REVIEW_FEEDBACK_AGENT",
        "active_policy": ACTIVE_REVIEW_FEEDBACK_POLICY,
        "legacy_pipeline_passed": legacy_passed,
        "attempt_rows": int(len(attempts)),
        "unique_historical_trials": int(attempts["counts_as_unique_trial"].sum()) if len(attempts) else 0,
        "forward_candidates": int(len(lifecycle)),
        "forward_contract_slots": int(lifecycle["queue_rank"].le(maximum).sum()) if len(lifecycle) else 0,
        "forward_runtime_ready": int(lifecycle["forward_status"].eq("FORWARD_READY_NOT_STARTED").sum()) if len(lifecycle) else 0,
        "forward_runtime_blocked": int(lifecycle["forward_status"].eq("FORWARD_CONTRACT_READY_RUNTIME_BLOCKED").sum()) if len(lifecycle) else 0,
        "forward_queued": int(lifecycle["forward_status"].eq("FORWARD_QUEUED_CAPACITY").sum()) if len(lifecycle) else 0,
        "forward_observations": 0 if not observations_exist else None,
        "promoted_candidates": promoted,
        "unsafe_feedback_baseline": unsafe,
        "quality_gates_passed": bool(quality["passed"].all()),
        "parents_changed": False,
        "automatic_capital_authority": False,
        "live_allowed": False,
    }
    (out_dir / "v103_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return summary
