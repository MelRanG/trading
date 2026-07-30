from __future__ import annotations
import os, time, traceback
from pathlib import Path
from quant_harness.v85_operational_hardening.engine import AlertSink, run_operating_day

ROOT=Path(__file__).resolve().parents[1]
INTERVAL=max(int(os.getenv("V85_SCHEDULER_INTERVAL_SECONDS","3600")),3600)
ONCE=os.getenv("V85_SCHEDULER_ONCE","false").lower()=="true"
alert=AlertSink(ROOT/"data/runtime/v85_alerts.jsonl")
while True:
    try:
        result=run_operating_day(ROOT,rebuild=False)
        print({"scheduler":"ok","run_id":result["run_id"],"status":result["status"]},flush=True)
    except Exception as exc:
        alert.emit("CRITICAL","ORCHESTRATOR_FAILURE",str(exc),traceback=traceback.format_exc(limit=8))
        print({"scheduler":"error","error":str(exc)},flush=True)
    if ONCE:
        break
    time.sleep(INTERVAL)
