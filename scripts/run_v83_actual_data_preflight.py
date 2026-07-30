from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from quant_harness.v83_independent_self_research.engine import run


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate replacement market data against the frozen V83 result contract.")
    parser.add_argument("--actual-root", type=Path, required=True, help="Unpacked project root containing replacement data in the documented paths")
    parser.add_argument("--reference-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--return-tolerance-pp", type=float, default=2.0)
    parser.add_argument("--order-count-tolerance-ratio", type=float, default=0.05)
    parser.add_argument("--minimum-target-agreement", type=float, default=0.99)
    args = parser.parse_args()

    reference_report = args.reference_root / "reports/v83_independent_self_research"
    reference_metrics = pd.read_csv(reference_report / "v83_strategy_metrics.csv").set_index("scenario")
    reference_targets = {
        path.name: pd.read_csv(path).set_index("date")["target_weights_json"].astype(str)
        for path in reference_report.glob("v83_target_*.csv")
    }

    result = run(args.actual_root)
    actual_report = args.actual_root / "reports/v83_independent_self_research"
    actual_metrics = pd.read_csv(actual_report / "v83_strategy_metrics.csv").set_index("scenario")
    rows = []
    for scenario in ["V69_PARENT", "V79_PARENT", "V83_V69_INDEPENDENT_SELF_RESEARCH", "V83_V79_INDEPENDENT_SELF_RESEARCH"]:
        ref, actual = reference_metrics.loc[scenario], actual_metrics.loc[scenario]
        return_delta = float(actual["return_pct"] - ref["return_pct"])
        order_ratio = abs(float(actual["order_count"] - ref["order_count"])) / max(float(ref["order_count"]), 1.0)
        rows.append({
            "scenario": scenario,
            "reference_return_pct": float(ref["return_pct"]),
            "actual_return_pct": float(actual["return_pct"]),
            "return_delta_pp": return_delta,
            "reference_order_count": int(ref["order_count"]),
            "actual_order_count": int(actual["order_count"]),
            "order_count_delta_ratio": order_ratio,
            "return_within_tolerance": abs(return_delta) <= args.return_tolerance_pp,
            "orders_within_tolerance": order_ratio <= args.order_count_tolerance_ratio,
        })
    comparison = pd.DataFrame(rows)

    agreements = []
    for name, ref in reference_targets.items():
        actual_path = actual_report / name
        if not actual_path.exists():
            agreements.append({"target_file": name, "agreement": 0.0})
            continue
        actual = pd.read_csv(actual_path).set_index("date")["target_weights_json"].astype(str)
        common = ref.index.intersection(actual.index)
        agreements.append({"target_file": name, "agreement": float((ref.loc[common] == actual.loc[common]).mean()) if len(common) else 0.0})
    target_agreement = pd.DataFrame(agreements)

    output_dir = actual_report / "actual_data_preflight"
    output_dir.mkdir(parents=True, exist_ok=True)
    comparison.to_csv(output_dir / "metric_comparison.csv", index=False)
    target_agreement.to_csv(output_dir / "target_agreement.csv", index=False)
    passed = bool(
        result["quality_gates_passed"]
        and comparison[["return_within_tolerance", "orders_within_tolerance"]].all().all()
        and target_agreement["agreement"].min() >= args.minimum_target_agreement
    )
    summary = {
        "passed": passed,
        "quality_gates_passed": bool(result["quality_gates_passed"]),
        "minimum_target_agreement": float(target_agreement["agreement"].min()),
        "return_tolerance_pp": args.return_tolerance_pp,
        "order_count_tolerance_ratio": args.order_count_tolerance_ratio,
        "minimum_target_agreement_required": args.minimum_target_agreement,
    }
    (output_dir / "preflight_result.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not passed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
