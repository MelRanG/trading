from pathlib import Path

from quant_harness.v103_review_feedback_agent.engine import run

if __name__ == "__main__":
    print(run(Path(__file__).resolve().parents[1]))
