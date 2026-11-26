"""Pass frozen research evidence to the unchanged Task16-A diagnostic."""
from datetime import datetime, timezone
import json

from experiments.task13_earnings_strength.run import OUT, ROOT, sha, write_json
from experiments.task16_a.diagnose import baseline, diagnose, native
from quant_harness.investment.review import policy


def main():
    result_file = OUT / "result.json"
    result = json.loads(result_file.read_bytes())
    seal = json.loads((OUT / "seal.json").read_bytes())
    markets = {market: result[market] for market in ("US", "KR")}
    case = {
        "case_id": "SEC_REPORTED_DILUTED_EPS_YOY_H20",
        "decision_as_of": "2024-01-01T00:00:00Z",
        "evaluation_as_of": datetime.now(timezone.utc).isoformat(),
        "evidence_class": "EXPOSED_HISTORICAL_SIGNAL_DIAGNOSTIC",
        "facts": {"independent_validation_available": False, "portfolio_runs": result["portfolio_runs"],
                  "market_results": markets, "coverage": {k: seal[k] for k in markets},
                  "reevaluation_condition": "New independently dated earnings data, frozen predictions, comparably defined expectations if testing surprise, and sufficient PIT coverage."},
    }
    review = native(case, policy(ROOT))
    output = diagnose(case, review, {})
    write_json(OUT/"feedback.json", {
        "case": case, "native_review": review, "baseline": baseline(case, review), "feedback": output,
        "result_sha256": sha(result_file), "seal_sha256": sha(OUT/"seal.json"),
        "review_code_sha256": sha(ROOT/"experiments/task16_a/diagnose.py"),
        "unsupported_evidence": [
            "Existing native Review requires a per-decision packet.",
            "Task16-A does not consume paired predictive increment, confidence interval, overlap, long-only lift, or concentration from a research run.",
            "Reevaluation requirements remain research evidence until a new Task16/17 integration is approved.",
        ],
        "automatic_actions": 0,
    })
    print(review["process_status"], output["primary_cause"], output["recommended_action"])


if __name__ == "__main__":
    main()
