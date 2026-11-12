from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

REPORT = "v91_hypothesis_generator"
PARENTS = {"V69": "V69_PARENT", "V79": "V79_PARENT"}


def _cfg(root: Path) -> dict[str, Any]:
    return yaml.safe_load((root / "config/v93_feedback_research.yaml").read_text(encoding="utf-8"))


def _weighted(frame: pd.DataFrame, prefix: str) -> pd.Series:
    a = pd.to_numeric(frame[f"{prefix}_20d"], errors="coerce")
    b = pd.to_numeric(frame[f"{prefix}_60d"], errors="coerce")
    return 0.40 * a + 0.60 * b


def _effective_events(frame: pd.DataFrame, sessions: pd.DatetimeIndex, spacing: int) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    pos = {d: i for i, d in enumerate(sessions)}
    keep: list[int] = []
    last = -10**9
    for idx, date in zip(frame.index, pd.to_datetime(frame["decision_date"])):
        p = pos.get(date)
        if p is None:
            continue
        if p - last >= spacing:
            keep.append(idx)
            last = p
    return frame.loc[keep].copy()


def _issue_rows(evidence: pd.DataFrame, cfg: dict[str, Any]) -> pd.DataFrame:
    if evidence.empty:
        return pd.DataFrame(columns=["issue", "rate", "severity", "score", "effective_events", "regimes"])
    chosen = _weighted(evidence, "chosen_return")
    runner = _weighted(evidence, "runner_return")
    old = _weighted(evidence, "old_return")
    core = _weighted(evidence, "core_return")
    chosen_mae = 0.40 * pd.to_numeric(evidence["chosen_mae_20d"], errors="coerce") + 0.60 * pd.to_numeric(evidence["chosen_mae_60d"], errors="coerce")
    exit_comparator = chosen.where(evidence["event_type"].eq("ROTATION"), core)
    specs = {
        "selection_error": (runner - chosen, (runner - chosen) > float(cfg["attribution"]["selection_error_threshold"])),
        "early_exit": (old - exit_comparator, evidence["event_type"].isin(["EXIT", "ROTATION"]) & ((old - exit_comparator) > float(cfg["attribution"]["early_exit_threshold"]))),
        "broad_rally_undercapture": (core - chosen, ((pd.to_numeric(evidence["core_return_20d"], errors="coerce") >= float(cfg["attribution"]["core_return_broad_rally_20d"])) | (pd.to_numeric(evidence["core_return_60d"], errors="coerce") >= float(cfg["attribution"]["core_return_broad_rally_60d"]))) & ((core - chosen) > 0.05)),
        "volatility_pain": (-chosen_mae, chosen_mae < float(cfg["attribution"]["volatility_mae_threshold"])),
    }
    rows: list[dict[str, Any]] = []
    for name, (severity_raw, mask) in specs.items():
        valid = severity_raw.where(mask).replace([np.inf, -np.inf], np.nan).dropna()
        rate = float(mask.fillna(False).mean())
        severity = float(valid.clip(lower=0).mean()) if len(valid) else 0.0
        regimes = sorted(evidence.loc[mask.fillna(False), "regime_d1"].dropna().astype(str).unique().tolist())
        rows.append({
            "issue": name,
            "rate": rate,
            "severity": severity,
            "score": rate + 3.0 * min(severity, 0.25),
            "effective_events": len(evidence),
            "regimes": "|".join(regimes),
        })
    return pd.DataFrame(rows).sort_values(["score", "severity"], ascending=False).reset_index(drop=True)


def run(root: Path | str, *, output_dir: Path | str | None = None) -> dict[str, Any]:
    root = Path(root)
    out_dir = Path(output_dir) if output_dir is not None else root / "reports" / REPORT
    out_dir.mkdir(parents=True, exist_ok=True)
    cfg = _cfg(root)
    decision_path = root / "reports/v90_trade_attribution/v90_decision_attribution.csv"
    regime_path = root / "reports/v90_trade_attribution/v90_regime_d1.csv"
    if not decision_path.exists() or not regime_path.exists():
        from quant_harness.v90_trade_attribution.engine import run as run_v90
        run_v90(root)
    decisions = pd.read_csv(decision_path)
    decisions["decision_date"] = pd.to_datetime(decisions["decision_date"])
    decisions["information_cutoff"] = pd.to_datetime(decisions["information_cutoff"])
    regimes = pd.read_csv(regime_path)
    sessions = pd.DatetimeIndex(pd.to_datetime(regimes["date"]))
    hypotheses: list[dict[str, Any]] = []
    issue_tables: list[dict[str, Any]] = []
    spacing = int(cfg["attribution"]["effective_event_spacing_sessions"])
    purge = int(cfg["hypothesis"]["purge_sessions"])
    rolling = int(cfg["hypothesis"]["rolling_evidence_sessions"])
    minimum = int(cfg["hypothesis"]["minimum_effective_events"])

    for family, parent in PARENTS.items():
        family_rows = decisions[decisions["scenario"].eq(parent)].copy()
        for year in [int(y) for y in cfg["research"]["test_years"]]:
            test_dates = sessions[sessions.year == year]
            if len(test_dates) == 0:
                continue
            start = test_dates.min()
            start_pos = int(sessions.searchsorted(start))
            cutoff_pos = max(start_pos - purge - 1, 0)
            cutoff = sessions[cutoff_pos]
            window_start = sessions[max(cutoff_pos - rolling, 0)]
            evidence = family_rows[(family_rows["decision_date"] >= window_start) & (pd.to_datetime(family_rows["decision_date"]) <= cutoff)].copy()
            evidence = evidence[pd.to_datetime(evidence["decision_date"]) + pd.offsets.BDay(0) <= cutoff]
            evidence = evidence[pd.to_numeric(evidence["matured_60d"], errors="coerce").astype(bool)]
            evidence = evidence[pd.to_datetime(evidence["decision_date"]) <= cutoff]
            # A 60-day result is allowed only when its recorded horizon is fully before the evidence cutoff.
            horizon_end = evidence["decision_date"].map(lambda d: sessions[min(int(sessions.searchsorted(d)) + 60, len(sessions) - 1)])
            evidence = evidence[horizon_end <= cutoff]
            effective = _effective_events(evidence.sort_values("decision_date"), sessions, spacing)
            issues = _issue_rows(effective, cfg)
            for row in issues.to_dict("records"):
                issue_tables.append({"family": family, "test_year": year, "evidence_start": window_start, "evidence_cutoff": cutoff, **row})
            if len(effective) < minimum or issues.empty:
                hypotheses.append({"family": family, "test_year": year, "parent": parent, "candidate": parent, "issue": "INSUFFICIENT_EFFECTIVE_SELF_TRADES", "changed_component": "NONE", "statement": "No strategy change proposed.", "effective_events": len(effective), "evidence_cutoff": cutoff, "proposal_created": False, "one_component_only": True})
                continue
            best = issues.iloc[0]
            if float(best["rate"]) < float(cfg["hypothesis"]["minimum_issue_rate"]) or float(best["severity"]) < float(cfg["hypothesis"]["minimum_issue_severity"]):
                hypotheses.append({"family": family, "test_year": year, "parent": parent, "candidate": parent, "issue": "NO_DOMINANT_SELF_ERROR", "changed_component": "NONE", "statement": "No strategy change proposed.", "effective_events": len(effective), "evidence_cutoff": cutoff, "proposal_created": False, "one_component_only": True})
                continue
            meta = cfg["families"][family]["hypotheses"].get(str(best["issue"]))
            if not meta:
                hypotheses.append({"family": family, "test_year": year, "parent": parent, "candidate": parent, "issue": "NO_PREREGISTERED_HYPOTHESIS", "changed_component": "NONE", "statement": "No strategy change proposed.", "effective_events": len(effective), "evidence_cutoff": cutoff, "proposal_created": False, "one_component_only": True})
                continue
            hypotheses.append({
                "family": family,
                "test_year": year,
                "parent": parent,
                "candidate": str(meta["candidate"]),
                "issue": str(best["issue"]),
                "changed_component": str(meta["changed_component"]),
                "statement": str(meta["statement"]),
                "effective_events": len(effective),
                "issue_rate": float(best["rate"]),
                "issue_severity": float(best["severity"]),
                "evidence_cutoff": cutoff,
                "proposal_created": True,
                "one_component_only": True,
            })

    hypotheses_frame = pd.DataFrame(hypotheses)
    issue_frame = pd.DataFrame(issue_tables)
    quality = pd.DataFrame([
        {"gate": "ONLY_PARENT_SELF_TRADES_USED", "passed": True, "detail": json.dumps(PARENTS, sort_keys=True)},
        {"gate": "PURGED_EVIDENCE_PRECEDES_TEST", "passed": bool((pd.to_datetime(hypotheses_frame["evidence_cutoff"]) < pd.to_datetime(hypotheses_frame["test_year"].astype(str) + "-01-01")).all()), "detail": f"purge_sessions={purge}"},
        {"gate": "ONE_COMPONENT_PER_HYPOTHESIS", "passed": bool(hypotheses_frame["one_component_only"].all()), "detail": "fixed hypothesis catalog"},
        {"gate": "PROPOSAL_BUDGET_ENFORCED", "passed": not hypotheses_frame.duplicated(["family", "test_year"]).any(), "detail": "maximum one proposal per family and fold"},
        {"gate": "NO_CROSS_FAMILY_CANDIDATE", "passed": all(str(r.candidate).startswith(str(r.family)) or str(r.candidate) == str(r.parent) for r in hypotheses_frame.itertuples(index=False)), "detail": "V69 and V79 remain independent"},
    ])
    hypotheses_frame.to_csv(out_dir / "v91_hypotheses.csv", index=False)
    issue_frame.to_csv(out_dir / "v91_issue_scores.csv", index=False)
    quality.to_csv(out_dir / "v91_quality_gates.csv", index=False)
    summary = {"hypotheses": int(hypotheses_frame["proposal_created"].sum()), "folds": len(hypotheses_frame), "quality_gates_passed": bool(quality["passed"].all()), "live_allowed": False}
    (out_dir / "v91_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
