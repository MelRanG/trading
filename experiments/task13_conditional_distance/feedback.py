"""Run existing Task16-A Review against the sealed signal diagnostics."""
from datetime import datetime, timezone
import json

from experiments.task13_conditional_distance.run import OUT, ROOT, sha, write_json
from experiments.task16_a.diagnose import baseline, diagnose, native
from quant_harness.investment.review import policy


def main():
    source = OUT / "result.json"
    result = json.loads(source.read_bytes())
    seal = json.loads((OUT / "seal.json").read_bytes())
    case = {
        "case_id": "MA20_DISTANCE_CONDITIONAL_H20",
        "decision_as_of": "2024-01-01T00:00:00Z",
        "evaluation_as_of": datetime.now(timezone.utc).isoformat(),
        "evidence_class": "EXPOSED_HISTORICAL_SIGNAL_DIAGNOSTIC",
        "facts": {
            "independent_validation_available": False,
            "result": result["decision"],
            "portfolio_runs": result["portfolio_runs"],
            "h20_rank_ic_delta": {m: s["primary"]["mean"] for m, s in result["markets"].items()},
            "upper_quintile_return_delta": {m: s["top_lift"] for m, s in result["markets"].items()},
            "coverage": {m: s["eval"]["states"] for m, s in seal["markets"].items()},
        },
    }
    reviewed = native(case, policy(ROOT))
    original = baseline(case, reviewed)
    diagnosis = diagnose(case, reviewed, {})
    write_json(OUT / "feedback.json", {
        "case": case, "prediction_result_sha256": sha(source),
        "review_code_sha256": sha(ROOT / "experiments/task16_a/diagnose.py"),
        "native_review": reviewed, "baseline": original, "feedback": diagnosis,
        "research_disposition": "INSUFFICIENT_EVIDENCE_DO_NOT_REOPEN_FIXED_HYPOTHESIS",
        "disposition_revisit": "Only new independent evidence and a distinct preregistered mechanism justify a proposal.",
        "unsupported": [
            "Native Review needs a serialized decision packet even though the aggregate research comparison is available",
            "No dedicated schema for paired out-of-fit rank IC, uncertainty, coverage or contribution concentration",
            "No realized cost, entry, exit, reentry, averaging or sizing attribution without comparable ledgers",
        ],
        "automatic_actions": 0,
    })
    print({"native": reviewed["process_status"], "decision": diagnosis["recommended_action"]})


if __name__ == "__main__":
    main()
