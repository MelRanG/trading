from pathlib import Path
from quant_harness.v86_control_plane_dashboard.engine import run

if __name__ == "__main__":
    print(run(Path(".")))
