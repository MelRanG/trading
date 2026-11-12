"""Fail-closed manual intake for official KRX market-flow downloads."""
from __future__ import annotations

from datetime import datetime, time, timezone
from hashlib import sha256
import json
from pathlib import Path
import shutil
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import yaml


SCHEMA_VERSION = "KRX_MARKET_FLOW_PACK_V1"
FINAL_BLOCKED = "KRX_FLOW_DATA_BLOCKED"


def file_checksum(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_csv(path: Path) -> pd.DataFrame:
    errors: list[str] = []
    for encoding in ("utf-8-sig", "cp949", "utf-8"):
        try:
            return pd.read_csv(path, encoding=encoding)
        except UnicodeDecodeError as exc:
            errors.append(f"{encoding}:{exc}")
    raise ValueError(f"unsupported CSV encoding: {path.name}; {errors}")


def next_session(date: pd.Timestamp, sessions: pd.DatetimeIndex) -> pd.Timestamp | None:
    later = sessions[sessions.normalize() > date.normalize()]
    return later[0].normalize() if len(later) else None


def validate_canonical(frame: pd.DataFrame, required: list[str]) -> dict[str, Any]:
    missing = sorted(set(required).difference(frame.columns))
    duplicates = int(frame.duplicated(["observation_date", "source_dataset_id", "metric_name", "instrument_or_market", "investor_type"]).sum()) if not missing else 0
    values = pd.to_numeric(frame.get("value", pd.Series(dtype=float)), errors="coerce")
    obs = pd.to_datetime(frame.get("observed_at_utc", pd.Series(dtype=str)), utc=True, errors="coerce")
    avail = pd.to_datetime(frame.get("available_at_utc", pd.Series(dtype=str)), utc=True, errors="coerce")
    effective = pd.to_datetime(frame.get("effective_date", pd.Series(dtype=str)), errors="coerce")
    violations = int((avail.dt.tz_convert(None).dt.normalize() <= effective.dt.normalize()).sum()) if len(frame) and not missing else 0
    return {
        "missing_columns": missing, "duplicate_rows": duplicates,
        "invalid_values": int(values.isna().sum()), "invalid_observed_at": int(obs.isna().sum()),
        "invalid_available_at": int(avail.isna().sum()), "availability_not_tplus1": violations,
        "passed": not missing and duplicates == 0 and not values.isna().any() and not obs.isna().any() and not avail.isna().any() and violations == 0,
    }


def archive_raw(source: Path, raw_root: Path, dataset_id: str) -> tuple[Path, str, bool]:
    checksum = file_checksum(source)
    target = raw_root / dataset_id / f"{checksum}_{source.name}"
    created = False
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".tmp")
        shutil.copy2(source, temporary)
        if file_checksum(temporary) != checksum:
            temporary.unlink(missing_ok=True)
            raise RuntimeError("raw archive checksum mismatch")
        temporary.replace(target)
        created = True
    return target, checksum, created


def canonicalize_with_sidecar(
    raw: pd.DataFrame, sidecar: dict[str, Any], *, checksum: str,
    sessions: pd.DatetimeIndex, required_columns: list[str],
) -> pd.DataFrame:
    date_col = sidecar["observation_date_column"]
    investor_col = sidecar.get("investor_type_column")
    instrument_col = sidecar.get("instrument_column")
    dates = pd.to_datetime(raw[date_col], errors="raise").dt.normalize()
    rows: list[dict[str, Any]] = []
    retrieved = pd.Timestamp(sidecar["retrieved_at_utc"])
    if retrieved.tzinfo is None:
        raise ValueError("retrieved_at_utc must be timezone-aware")
    for index, observation_date in dates.items():
        available_date = next_session(observation_date, sessions)
        if available_date is None:
            continue
        for metric in sidecar["metrics"]:
            rows.append({
                "observation_date": observation_date.date().isoformat(),
                "effective_date": observation_date.date().isoformat(),
                "observed_at_utc": datetime.combine(observation_date.date(), time(15, 30), tzinfo=ZoneInfo("Asia/Seoul")).astimezone(timezone.utc).isoformat(),
                "available_at_utc": datetime.combine(available_date.date(), time(0), tzinfo=timezone.utc).isoformat(),
                "market_session": "KRX_REGULAR",
                "source_name": "KRX_DATA_MARKETPLACE",
                "source_dataset_id": sidecar["source_dataset_id"],
                "revision_id": "NO_HISTORICAL_REVISION_LEDGER",
                "source_checksum": checksum,
                "metric_name": metric["metric_name"],
                "instrument_or_market": str(raw.loc[index, instrument_col]) if instrument_col else str(sidecar["instrument_or_market"]),
                "investor_type": str(raw.loc[index, investor_col]) if investor_col else str(sidecar.get("investor_type", "ALL")),
                "value": pd.to_numeric(raw.loc[index, metric["column"]], errors="raise"),
                "unit": metric["unit"],
                "availability_policy": "PIT_CONSERVATIVE_OFFICIAL_EOD_TPLUS1",
                "pit_quality": "READY_PIT_CONSERVATIVE_TPLUS1",
            })
    frame = pd.DataFrame(rows, columns=required_columns)
    validation = validate_canonical(frame, required_columns)
    if not validation["passed"]:
        raise RuntimeError(f"canonical validation failed: {validation}")
    return frame


def _trading_sessions(root: Path) -> pd.DatetimeIndex:
    path = root / "data/toss_v19c_daily/069500_1d.csv"
    frame = pd.read_csv(path, usecols=["timestamp"])
    timestamps = pd.to_datetime(frame["timestamp"], utc=True).dt.tz_convert("Asia/Seoul").dt.tz_localize(None).dt.normalize()
    return pd.DatetimeIndex(sorted(timestamps.unique()))


def run(
    root: Path | str, *, drop_zone: Path | str | None = None,
    data_root: Path | str | None = None, output_dir: Path | str | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    root = Path(root).resolve()
    cfg = yaml.safe_load((root / "config/krx_market_flow_pack_v1.yaml").read_text(encoding="utf-8"))
    if cfg["schema_version"] != SCHEMA_VERSION:
        raise RuntimeError("unsupported KRX flow contract")
    drop = Path(drop_zone) if drop_zone else root / "data/krx_market_flow_pack_v1/drop_zone"
    store = Path(data_root) if data_root else root / "data/krx_market_flow_pack_v1"
    out = Path(output_dir) if output_dir else root / "runtime/krx_market_flow_pack_v1"
    drop.mkdir(parents=True, exist_ok=True); out.mkdir(parents=True, exist_ok=True)
    sessions = _trading_sessions(root)
    requirements: list[dict[str, Any]] = []
    manifest: list[dict[str, Any]] = []
    canonical_parts: list[pd.DataFrame] = []
    ready_ids: set[str] = set()
    for spec in cfg["datasets"]:
        requirements.append({
            "source_dataset_id": spec["id"], "official_menu_path": spec["menu"],
            "filters": spec["filters"], "required_period": f"{cfg['preferred_raw_start']}..{cfg['source_end']}",
            "frequency": "DAILY", "minimum_fields": "|".join(spec["minimum_fields"]),
            "expected_filename": spec["expected_pattern"], "download_format": "CSV",
            "save_directory": str(drop),
        })
        files = sorted(drop.glob(spec["expected_pattern"]))
        if not files:
            manifest.append({"source_name": cfg["source_name"], "source_dataset_id": spec["id"], "official_menu_path": spec["menu"], "retrieved_at_utc": None, "status": "HUMAN_DATA_DOWNLOAD_REQUIRED", "path": None, "source_file_checksum": None, "row_count": 0, "observation_start": None, "observation_end": None, "raw_schema": None})
            continue
        dataset_ok = True
        for file in files:
            raw = _read_csv(file)
            checksum = file_checksum(file)
            sidecar_path = file.with_suffix(file.suffix + ".metadata.json")
            row = {"source_name": cfg["source_name"], "source_dataset_id": spec["id"], "official_menu_path": spec["menu"], "retrieved_at_utc": None, "status": "PARTIAL_REPAIRABLE", "path": str(file), "source_file_checksum": checksum, "row_count": len(raw), "observation_start": None, "observation_end": None, "raw_schema": list(raw.columns)}
            missing_fields = sorted(set(spec["minimum_fields"]).difference(raw.columns))
            if missing_fields:
                row["status"] = "SCHEMA_MISMATCH"; row["error"] = f"missing official fields: {missing_fields}"; dataset_ok = False
            elif not sidecar_path.exists():
                row["status"] = "HUMAN_METADATA_MAPPING_REQUIRED"; row["error"] = f"sidecar required: {sidecar_path.name}"; dataset_ok = False
            else:
                sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
                row["retrieved_at_utc"] = sidecar.get("retrieved_at_utc")
                date_col = sidecar["observation_date_column"]
                dates = pd.to_datetime(raw[date_col], errors="coerce")
                row["observation_start"] = str(dates.min().date()) if dates.notna().any() else None
                row["observation_end"] = str(dates.max().date()) if dates.notna().any() else None
                coverage_ok = bool(dates.notna().any() and dates.min() <= pd.Timestamp(cfg["research_start"]) and dates.max() >= pd.Timestamp(cfg["source_end"]))
                if not coverage_ok:
                    row["status"] = "COVERAGE_TOO_SHORT"; row["error"] = f"required {cfg['research_start']}..{cfg['source_end']}"; dataset_ok = False
                else:
                    canonical_part = canonicalize_with_sidecar(raw, sidecar, checksum=checksum, sessions=sessions, required_columns=cfg["canonical_columns"])
                if coverage_ok and not dry_run:
                    archived, checksum, _ = archive_raw(file, store / "raw", spec["id"])
                    row["archived_path"] = str(archived)
                    canonical_parts.append(canonical_part)
                if coverage_ok:
                    row["status"] = "READY_PIT_CONSERVATIVE_TPLUS1" if not dry_run else "READY_FOR_INGESTION"
            manifest.append(row)
        if dataset_ok and not dry_run:
            ready_ids.add(spec["id"])
    if canonical_parts and not dry_run:
        canonical = pd.concat(canonical_parts, ignore_index=True)
        validation = validate_canonical(canonical, cfg["canonical_columns"])
        if not validation["passed"]:
            raise RuntimeError(f"pack validation failed: {validation}")
        target = store / "canonical/krx_market_flow_pack_v1.csv"
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_suffix(".csv.tmp")
        canonical.to_csv(temp, index=False, encoding="utf-8")
        temp.replace(target)
    pd.DataFrame(requirements).to_csv(out / "human_download_requirements.csv", index=False, encoding="utf-8")
    pd.DataFrame(manifest).to_csv(out / "raw_source_manifest.csv", index=False, encoding="utf-8")
    quality_rows: list[dict[str, Any]] = []
    for part in canonical_parts:
        for (dataset_id, metric), group in part.groupby(["source_dataset_id", "metric_name"], sort=True):
            dates = pd.to_datetime(group["observation_date"])
            values = pd.to_numeric(group["value"], errors="coerce")
            quality_rows.append({
                "source_dataset_id": dataset_id, "metric_name": metric,
                "start": str(dates.min().date()), "end": str(dates.max().date()),
                "rows": len(group), "missing_pct": float(values.isna().mean() * 100),
                "duplicate_rows": int(group.duplicated(["observation_date", "instrument_or_market", "investor_type"]).sum()),
                "trading_calendar_join_pct": float(dates.isin(sessions).mean() * 100),
                "units": "|".join(sorted(group["unit"].astype(str).unique())),
                "investor_types": "|".join(sorted(group["investor_type"].astype(str).unique())),
                "availability_policy": "PIT_CONSERVATIVE_OFFICIAL_EOD_TPLUS1",
                "revision_provenance": "NO_HISTORICAL_REVISION_LEDGER",
                "automatic_incremental_update": False,
            })
    pd.DataFrame(quality_rows, columns=["source_dataset_id", "metric_name", "start", "end", "rows", "missing_pct", "duplicate_rows", "trading_calendar_join_pct", "units", "investor_types", "availability_policy", "revision_provenance", "automatic_incremental_update"]).to_csv(out / "data_quality_report.csv", index=False, encoding="utf-8")
    data_dictionary = {"schema_version": SCHEMA_VERSION, "columns": cfg["canonical_columns"], "availability_policy": cfg["availability_policy"], "revision_policy": cfg["revision_policy"]}
    (out / "data_dictionary.json").write_text(json.dumps(data_dictionary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    missing_files = any(row["status"] == "HUMAN_DATA_DOWNLOAD_REQUIRED" for row in manifest)
    intake_status = "HUMAN_DATA_DOWNLOAD_REQUIRED" if missing_files else ("READY_FOR_INGESTION" if dry_run else ("READY_PIT_CONSERVATIVE_TPLUS1" if len(ready_ids) == len(cfg["datasets"]) else "PARTIAL_REPAIRABLE"))
    readiness = {
        "pack": SCHEMA_VERSION, "status": intake_status,
        "required_datasets": len(cfg["datasets"]), "ready_datasets": len(ready_ids),
        "missing_datasets": [x["id"] for x in cfg["datasets"] if x["id"] not in ready_ids],
        "official_open_api_supports_requested_flow_metrics": False,
        "official_access_contract": "KRX Data Marketplace screen download or data purchase",
        "hypotheses_created": 0, "diagnostics_run": 0, "operational_replays_run": 0,
        "availability_policy": cfg["availability_policy"], "revision_policy": cfg["revision_policy"],
    }
    (out / "data_readiness_report.json").write_text(json.dumps(readiness, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    trace = [
        {"agent": "UniverseAgent", "invoked": True, "input": "KRX official access and local raw inventory", "output": readiness["status"], "veto": True, "capital_mutation": False},
        {"agent": "PainSupplyAgent", "invoked": False, "reason": "no canonical READY flow data", "capital_mutation": False},
        {"agent": "MarketRegimeAgent", "invoked": False, "reason": "feasibility veto", "capital_mutation": False},
        {"agent": "SectorThemeAgent", "invoked": False, "reason": "feasibility veto", "capital_mutation": False},
        {"agent": "SentimentNewsAgent", "invoked": False, "reason": "source family excludes news", "capital_mutation": False},
        {"agent": "CandidateSelectionAgent", "invoked": False, "reason": "feasibility veto", "capital_mutation": False},
        {"agent": "StrategyAgent", "invoked": False, "reason": "no hypothesis", "capital_mutation": False},
        {"agent": "RiskExecutionAgent", "invoked": False, "reason": "no execution-qualified attempt", "capital_mutation": False},
        {"agent": "ReviewFeedbackAgent", "invoked": True, "input": "budget and provenance", "output": FINAL_BLOCKED, "capital_mutation": False},
    ]
    (out / "agent_invocation_trace.json").write_text(json.dumps(trace, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    decision = {
        "final_status": FINAL_BLOCKED if readiness["status"] != "READY_PIT_CONSERVATIVE_TPLUS1" else "KRX_FLOW_READY_NO_ALPHA_CANDIDATE",
        "data_status": readiness["status"], "research_round_executed": False,
        "proposal_budget": {"used": 0, "limit": 3}, "operational_replay_budget": {"used": 0, "limit": 1},
        "broker_mutation_calls": 0, "paper_primary_access": False, "operating_database_access": False,
        "live_build_capability": False, "current_release_live_authority": False,
        "rerun_dry_run": "python scripts/run_krx_market_flow_pack.py --dry-run",
        "rerun_ingest": "python scripts/run_krx_market_flow_pack.py --ingest",
    }
    for name, payload in (("budget_provenance_safety_audit.json", {"budget": decision["operational_replay_budget"], "safety": decision}), ("final_decision_report.json", decision)):
        (out / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return decision


__all__ = ["SCHEMA_VERSION", "archive_raw", "canonicalize_with_sidecar", "file_checksum", "next_session", "run", "validate_canonical"]
