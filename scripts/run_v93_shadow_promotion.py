from pathlib import Path
from quant_harness.v90_trade_attribution.engine import run as run90
from quant_harness.v91_hypothesis_generator.engine import run as run91
from quant_harness.v92_automated_research.engine import run as run92
from quant_harness.v93_shadow_promotion.engine import run as run93
if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    print({"v90": run90(root), "v91": run91(root), "v92": run92(root), "v93": run93(root)})
