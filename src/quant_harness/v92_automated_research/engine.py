from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from quant_harness.v77_corrected_price_allocation import engine as v77
from quant_harness.v83_independent_self_research import engine as v83
from quant_harness.v91_hypothesis_generator.engine import _effective_events, _issue_rows

REPORT = "v92_automated_research"


def _cfg(root: Path) -> dict[str, Any]:
    return yaml.safe_load((root / "config/v93_feedback_research.yaml").read_text(encoding="utf-8"))


def _metrics(account: pd.DataFrame, initial: float) -> dict[str, float]:
    return v83._period_fold_metrics(account, initial)


def _regime_returns(account: pd.DataFrame, regime: pd.Series) -> dict[str, float]:
    nav = account.set_index(pd.to_datetime(account["date"]))["nav_krw"].astype(float)
    returns = nav.pct_change(fill_method=None).fillna(0.0)
    labels = regime.reindex(returns.index).fillna("UNKNOWN")
    result: dict[str, float] = {}
    for label, values in returns.groupby(labels):
        result[str(label)] = float(((1.0 + values).prod() - 1.0) * 100.0)
    return result


def _issue_score(
    decisions: pd.DataFrame,
    scenario: str,
    issue: str,
    year: int,
    sessions: pd.DatetimeIndex,
    cfg: dict[str, Any],
) -> tuple[float, int]:
    frame = decisions[(decisions["scenario"].eq(scenario)) & (decisions["decision_date"].dt.year == year) & decisions["matured_60d"].astype(bool)].copy()
    frame = _effective_events(frame.sort_values("decision_date"), sessions, int(cfg["attribution"]["effective_event_spacing_sessions"]))
    table = _issue_rows(frame, cfg)
    selected = table[table["issue"].eq(issue)]
    if selected.empty:
        return 0.0, len(frame)
    row = selected.iloc[0]
    return float(row["rate"] + row["severity"]), len(frame)


def run(root: Path | str) -> dict[str, Any]:
    root = Path(root)
    out_dir = root / "reports" / REPORT
    out_dir.mkdir(parents=True, exist_ok=True)
    cfg = _cfg(root)
    hypotheses_path = root / "reports/v91_hypothesis_generator/v91_hypotheses.csv"
    decisions_path = root / "reports/v90_trade_attribution/v90_decision_attribution.csv"
    regime_path = root / "reports/v90_trade_attribution/v90_regime_d1.csv"
    if not hypotheses_path.exists():
        from quant_harness.v91_hypothesis_generator.engine import run as run_v91
        run_v91(root)
    hypotheses = pd.read_csv(hypotheses_path)
    hypotheses["evidence_cutoff"] = pd.to_datetime(hypotheses["evidence_cutoff"])
    decisions = pd.read_csv(decisions_path)
    decisions["decision_date"] = pd.to_datetime(decisions["decision_date"])
    decisions["matured_60d"] = decisions["matured_60d"].astype(str).str.lower().eq("true")
    regime_frame = pd.read_csv(regime_path)
    regime_frame["date"] = pd.to_datetime(regime_frame["date"])
    regime = regime_frame.set_index("date")["regime_d1"]
    sessions = pd.DatetimeIndex(regime.index)

    cfg77 = v77._load_config(root)
    from dataclasses import replace
    cfg77 = replace(cfg77, end_date=str(cfg["data_end"]))
    market = v77.load_adjusted_market(root, cfg77)
    targets, _ = v83._build_all_targets(root, market, cfg77)

    rows: list[dict[str, Any]] = []
    for hyp in hypotheses.to_dict("records"):
        family, year = str(hyp["family"]), int(hyp["test_year"])
        parent, candidate, issue = str(hyp["parent"]), str(hyp["candidate"]), str(hyp["issue"])
        dates = market["close"].index[market["close"].index.year == year]
        if len(dates) == 0:
            continue
        start, end = dates.min(), dates.max()
        parent_account, parent_orders, _ = v83._execute_target(market, targets[parent], cfg77, f"{family}_{year}_PARENT", start=start, end=end)
        parent_stress, _, _ = v83._execute_target(market, targets[parent], cfg77, f"{family}_{year}_PARENT_STRESS", stress=True, start=start, end=end)
        proposal = bool(hyp.get("proposal_created", False)) and candidate != parent
        if proposal:
            candidate_account, candidate_orders, _ = v83._execute_target(market, targets[candidate], cfg77, f"{family}_{year}_CANDIDATE", start=start, end=end)
            candidate_stress, _, _ = v83._execute_target(market, targets[candidate], cfg77, f"{family}_{year}_CANDIDATE_STRESS", stress=True, start=start, end=end)
        else:
            candidate_account, candidate_orders, candidate_stress = parent_account, parent_orders, parent_stress
        pm, cm = _metrics(parent_account, cfg77.initial_capital_krw), _metrics(candidate_account, cfg77.initial_capital_krw)
        psm, csm = _metrics(parent_stress, cfg77.initial_capital_krw), _metrics(candidate_stress, cfg77.initial_capital_krw)
        p_issue, p_events = _issue_score(decisions, parent, issue, year, sessions, cfg) if proposal else (0.0, 0)
        c_issue, c_events = _issue_score(decisions, candidate, issue, year, sessions, cfg) if proposal else (0.0, 0)
        issue_reduction = (p_issue - c_issue) / p_issue if p_issue > 1e-12 else 0.0
        p_regime = _regime_returns(parent_account, regime)
        c_regime = _regime_returns(candidate_account, regime)
        common = sorted(set(p_regime) & set(c_regime))
        regime_deltas = {k: c_regime[k] - p_regime[k] for k in common}
        worst_regime = min(regime_deltas.values()) if regime_deltas else np.nan
        turnover_ratio = len(candidate_orders) / max(len(parent_orders), 1)
        return_gate = cm["return_pct"] - pm["return_pct"] >= float(cfg["research"]["return_delta_min_pp"])
        mdd_gate = cm["mdd_pct"] >= pm["mdd_pct"] - float(cfg["research"]["mdd_tolerance_pp"])
        stress_gate = csm["return_pct"] - psm["return_pct"] >= float(cfg["research"]["stress_return_delta_min_pp"])
        issue_gate = issue_reduction >= float(cfg["research"]["issue_reduction_min"]) and min(p_events, c_events) >= 2
        turnover_gate = turnover_ratio <= float(cfg["research"]["turnover_ratio_max"])
        regime_gate = bool(regime_deltas) and worst_regime >= float(cfg["research"]["worst_regime_delta_min_pp"])
        passed = bool(proposal and return_gate and mdd_gate and stress_gate and issue_gate and turnover_gate and regime_gate)
        rows.append({
            "family": family, "test_year": year, "parent": parent, "candidate": candidate, "issue": issue,
            "changed_component": hyp.get("changed_component", "NONE"), "statement": hyp.get("statement", ""),
            "proposal_created": proposal, "parent_return_pct": pm["return_pct"], "candidate_return_pct": cm["return_pct"],
            "return_delta_pp": cm["return_pct"] - pm["return_pct"], "parent_mdd_pct": pm["mdd_pct"], "candidate_mdd_pct": cm["mdd_pct"],
            "stress_delta_pp": csm["return_pct"] - psm["return_pct"], "parent_orders": len(parent_orders), "candidate_orders": len(candidate_orders),
            "turnover_ratio": turnover_ratio, "parent_issue_score": p_issue, "candidate_issue_score": c_issue,
            "issue_reduction": issue_reduction, "issue_events_parent": p_events, "issue_events_candidate": c_events,
            "worst_regime_delta_pp": worst_regime, "regime_deltas_json": json.dumps(regime_deltas, sort_keys=True),
            "gate_return": return_gate, "gate_mdd": mdd_gate, "gate_stress": stress_gate, "gate_issue_reduction": issue_gate,
            "gate_turnover": turnover_gate, "gate_regime": regime_gate, "passed_backtest": passed,
        })
    folds = pd.DataFrame(rows)

    summaries: list[dict[str, Any]] = []
    proposed = folds[folds["proposal_created"].astype(bool)].copy()
    for (family, candidate), group in proposed.groupby(["family", "candidate"]):
        summaries.append({
            "family": family,
            "candidate": candidate,
            "evaluated_folds": len(group),
            "passed_folds": int(group["passed_backtest"].astype(bool).sum()),
            "median_return_delta_pp": float(group["return_delta_pp"].median()),
            "median_stress_delta_pp": float(group["stress_delta_pp"].median()),
            "median_issue_reduction": float(group["issue_reduction"].median()),
            "worst_mdd_delta_pp": float((group["candidate_mdd_pct"] - group["parent_mdd_pct"]).min()),
            "shadow_eligible": bool(
                len(group) >= int(cfg["shadow"]["minimum_evaluated_folds"])
                and int(group["passed_backtest"].astype(bool).sum()) >= int(cfg["shadow"]["minimum_passed_folds"])
                and float(group["return_delta_pp"].median()) >= float(cfg["shadow"]["median_return_delta_min_pp"])
                and float(group["stress_delta_pp"].median()) >= float(cfg["shadow"]["median_stress_delta_min_pp"])
            ),
        })
    summary_frame = pd.DataFrame(summaries, columns=["family", "candidate", "evaluated_folds", "passed_folds", "median_return_delta_pp", "median_stress_delta_pp", "median_issue_reduction", "worst_mdd_delta_pp", "shadow_eligible"])

    v83_metrics = pd.read_csv(root / "reports/v83_independent_self_research/v83_strategy_metrics.csv")
    scenarios = sorted(set(["V69_PARENT", "V79_PARENT"]) | set(proposed["candidate"].dropna().astype(str)))
    strategy_metrics = v83_metrics[v83_metrics["scenario"].isin(scenarios)].copy()
    quality = pd.DataFrame([
        {"gate": "NO_SAME_FOLD_MUTATION", "passed": True, "detail": "candidate is evaluated as a separate account only"},
        {"gate": "BASE_AND_STRESS_COSTS_REQUIRED", "passed": bool((folds.loc[folds["proposal_created"].astype(bool), "gate_stress"].notna()).all()), "detail": f"proposal_folds={int(folds['proposal_created'].astype(bool).sum())}"},
        {"gate": "INTENDED_ISSUE_EFFECT_MEASURED", "passed": bool(folds.loc[folds["proposal_created"].astype(bool), "issue_reduction"].notna().all()), "detail": "parent versus candidate own-trade issue score"},
        {"gate": "ONE_COMPONENT_ABLATION_RETAINED", "passed": bool(folds.loc[folds["proposal_created"].astype(bool), "changed_component"].ne("NONE").all()), "detail": "hypothesis catalog"},
        {"gate": "NO_AUTOMATIC_CAPITAL_AUTHORITY", "passed": cfg["shadow"]["automatic_capital_authority"] is False, "detail": "backtest can only mark shadow eligibility"},
    ])
    folds.to_csv(out_dir / "v92_fold_results.csv", index=False)
    summary_frame.to_csv(out_dir / "v92_candidate_summary.csv", index=False)
    strategy_metrics.to_csv(out_dir / "v92_strategy_metrics.csv", index=False)
    quality.to_csv(out_dir / "v92_quality_gates.csv", index=False)
    result = {"proposal_folds": int(folds["proposal_created"].astype(bool).sum()), "passed_folds": int(folds["passed_backtest"].astype(bool).sum()), "shadow_eligible_candidates": int(summary_frame["shadow_eligible"].astype(bool).sum()) if not summary_frame.empty else 0, "quality_gates_passed": bool(quality["passed"].all()), "live_allowed": False}
    (out_dir / "v92_summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
