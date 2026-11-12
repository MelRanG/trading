"""Readiness only. Never turn missing/reconstructed flow into a safe signal."""
from hashlib import sha256
from pathlib import Path

import pandas as pd


def inspect_flow(path: Path, *, required_source_date: str) -> dict:
    required = pd.Timestamp(required_source_date)
    if required.tzinfo is not None or required != required.normalize():
        raise ValueError("explicit preceding-session date required")
    result = {"capital_authority": "NONE", "flow_risk": None, "metrics_executed": False,
              "required_source_date": required.date().isoformat(), "source_path": str(path),
              "status": "BLOCKED_PAIN_SUPPLY_DATA", "missing_dependencies": []}
    if not path.exists():
        return {**result, "missing_dependencies": ["FLOW_SOURCE_MISSING"]}
    result["source_file_sha256"] = sha256(path.read_bytes()).hexdigest()
    frame = pd.read_csv(path, dtype=str)
    fields = {"as_of_date", "market", "foreign_net_buy_100m_krw", "institution_net_buy_100m_krw",
              "source_id", "downloaded_at", "data_status", "provenance_hash"}
    if not fields.issubset(frame):
        return {**result, "missing_dependencies": ["FLOW_SCHEMA_INVALID"]}
    frame = frame[frame.market.eq("KOSPI")].copy()
    dates = pd.to_datetime(frame.as_of_date, errors="coerce")
    eligible = frame[dates <= required].copy()
    if eligible.empty:
        return {**result, "missing_dependencies": ["NO_FLOW_AT_OR_BEFORE_CUTOFF"]}
    if dates.isna().any() or frame.duplicated(["as_of_date", "market"]).any():
        result["missing_dependencies"].append("INVALID_OR_DUPLICATE_FLOW_DATE")
    latest = pd.to_datetime(eligible.as_of_date).max()
    result.update({"latest_source_date_at_cutoff": latest.date().isoformat(),
                   "source_ids": sorted(eligible.source_id.dropna().unique().tolist()),
                   "source_statuses": sorted(eligible.data_status.dropna().unique().tolist()),
                   "temporal_freshness": "STALE" if latest < required else "PASSED"})
    if latest < required:
        result["missing_dependencies"].append("LATEST_REQUIRED_FLOW_SESSION_MISSING")
    if not eligible.data_status.eq("READY_FORWARD_PIT").all():
        result["missing_dependencies"].append("OFFICIAL_FORWARD_PIT_PROVENANCE_UNVERIFIED")
    # Matching a status string alone is not proof of source licensing/PIT/revisions.
    # No new provider or capital policy is inferred by this readiness inspector.
    result["missing_dependencies"].append("VERIFIED_FORWARD_SOURCE_AND_REVISION_CONTRACT_REQUIRED")
    return result
