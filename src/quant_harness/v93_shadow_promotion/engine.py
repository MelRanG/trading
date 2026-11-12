from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

REPORT = "v93_shadow_promotion"


def _cfg(root: Path) -> dict[str, Any]:
    return yaml.safe_load((root / "config/v93_feedback_research.yaml").read_text(encoding="utf-8"))


def run(root: Path | str, *, output_dir: Path | str | None = None) -> dict[str, Any]:
    root = Path(root)
    out_dir = Path(output_dir) if output_dir is not None else root / "reports" / REPORT
    out_dir.mkdir(parents=True, exist_ok=True)
    cfg = _cfg(root)
    summary_path = root / "reports/v92_automated_research/v92_candidate_summary.csv"
    folds_path = root / "reports/v92_automated_research/v92_fold_results.csv"
    if not summary_path.exists():
        from quant_harness.v92_automated_research.engine import run as run_v92
        run_v92(root)
    summaries = pd.read_csv(summary_path) if summary_path.exists() else pd.DataFrame()
    folds = pd.read_csv(folds_path)
    candidates: list[dict[str, Any]] = []
    if not summaries.empty:
        for row in summaries.to_dict("records"):
            family = str(row["family"])
            scenario = str(row["candidate"])
            strategy_id = f"feedback_{scenario.lower()}"
            source_rows = folds[(folds["family"].eq(family)) & (folds["candidate"].eq(scenario))]
            issue_names = sorted(source_rows["issue"].dropna().astype(str).unique().tolist())
            changed = sorted(source_rows["changed_component"].dropna().astype(str).unique().tolist())
            eligible = bool(row["shadow_eligible"])
            candidates.append({
                "strategy_id": strategy_id,
                "scenario": scenario,
                "label": scenario.replace("_", " ").title(),
                "role": "SHADOW",
                "status": "SHADOW_ELIGIBLE" if eligible else "BACKTEST_REJECTED",
                "parent_strategy_id": cfg["families"][family]["strategy_id"],
                "created_by": "FeedbackAgent",
                "managed_by": "v93",
                "source": "reports/v92_automated_research/v92_candidate_summary.csv",
                "runtime_compatible": False,
                "account_id": None,
                "capital_authority": "NONE",
                "parameters": {"issues": issue_names, "changed_components": changed},
                "backtest_summary": row,
                "backtest_metrics": {
                    "median_return_delta_pp": row.get("median_return_delta_pp"),
                    "median_stress_delta_pp": row.get("median_stress_delta_pp"),
                    "passed_folds": row.get("passed_folds"),
                    "evaluated_folds": row.get("evaluated_folds"),
                },
            })
    payload = {
        "schema_version": 1,
        "release": "V93_FEEDBACK_RESEARCH",
        "policy": {
            "parent_in_place_mutation": False,
            "automatic_champion_change": False,
            "automatic_capital_authority": False,
            "eligible_candidates_may_enter_frozen_shadow_only": True,
        },
        "candidates": candidates,
    }
    registry_path = out_dir / "v93_feedback_candidate_registry.json"
    registry_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    quality = pd.DataFrame([
        {"gate": "ALL_CANDIDATES_HAVE_NO_CAPITAL_AUTHORITY", "passed": all(x["capital_authority"] == "NONE" for x in candidates), "detail": f"candidates={len(candidates)}"},
        {"gate": "NO_PARENT_IN_PLACE_MUTATION", "passed": payload["policy"]["parent_in_place_mutation"] is False, "detail": "new scenario only"},
        {"gate": "NO_AUTOMATIC_CHAMPION_CHANGE", "passed": payload["policy"]["automatic_champion_change"] is False, "detail": "human governance required"},
        {"gate": "ONLY_BACKTEST_PASSED_CAN_BE_SHADOW_ELIGIBLE", "passed": all((x["status"] != "SHADOW_ELIGIBLE") or int(x["backtest_summary"]["passed_folds"]) >= int(cfg["shadow"]["minimum_passed_folds"]) for x in candidates), "detail": "fold gate"},
    ])
    quality.to_csv(out_dir / "v93_quality_gates.csv", index=False)
    result = {"registered_candidates": len(candidates), "shadow_eligible": sum(x["status"] == "SHADOW_ELIGIBLE" for x in candidates), "quality_gates_passed": bool(quality["passed"].all()), "live_allowed": False}
    (out_dir / "v93_summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
