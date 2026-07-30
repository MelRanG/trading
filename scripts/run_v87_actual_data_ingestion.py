from pathlib import Path
from quant_harness.v87_actual_data_ingestion.engine import run

if __name__ == "__main__":
    print(run(Path(".")))
