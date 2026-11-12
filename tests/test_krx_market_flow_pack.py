from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from quant_harness.krx_market_flow_pack import (
    archive_raw,
    canonicalize_with_sidecar,
    file_checksum,
    next_session,
    run,
    validate_canonical,
)


ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    "observation_date", "effective_date", "observed_at_utc", "available_at_utc",
    "market_session", "source_name", "source_dataset_id", "revision_id",
    "source_checksum", "metric_name", "instrument_or_market", "investor_type",
    "value", "unit", "availability_policy", "pit_quality",
]


def test_next_trading_session_is_conservative_tplus1() -> None:
    sessions = pd.DatetimeIndex(pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-05"]))
    assert next_session(pd.Timestamp("2024-01-03"), sessions) == pd.Timestamp("2024-01-05")
    assert next_session(pd.Timestamp("2024-01-05"), sessions) is None


def test_canonical_schema_and_availability_pass() -> None:
    raw = pd.DataFrame({"일자": ["2024-01-02", "2024-01-03"], "투자자구분": ["외국인", "외국인"], "순매수거래대금": [10, -5]})
    sidecar = {
        "source_dataset_id": "TEST", "retrieved_at_utc": "2026-08-07T00:00:00+00:00",
        "observation_date_column": "일자", "instrument_or_market": "KOSPI",
        "investor_type_column": "투자자구분",
        "metrics": [{"column": "순매수거래대금", "metric_name": "net_buy_value", "unit": "KRW"}],
    }
    frame = canonicalize_with_sidecar(raw, sidecar, checksum="a" * 64, sessions=pd.DatetimeIndex(pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"])), required_columns=REQUIRED)
    assert len(frame) == 2
    assert frame["availability_policy"].eq("PIT_CONSERVATIVE_OFFICIAL_EOD_TPLUS1").all()
    assert validate_canonical(frame, REQUIRED)["passed"] is True


def test_same_day_availability_and_duplicate_fail_closed() -> None:
    row = {column: "x" for column in REQUIRED}
    row.update({"observation_date": "2024-01-02", "effective_date": "2024-01-02", "observed_at_utc": "2024-01-03T00:00:00Z", "available_at_utc": "2024-01-02T00:00:00Z", "value": 1})
    frame = pd.DataFrame([row, row])
    result = validate_canonical(frame, REQUIRED)
    assert result["passed"] is False
    assert result["duplicate_rows"] == 1
    assert result["availability_not_tplus1"] == 2


def test_raw_archive_checksum_and_idempotency(tmp_path: Path) -> None:
    source = tmp_path / "official.csv"
    source.write_bytes("일자,값\n2024-01-02,1\n".encode("utf-8"))
    first, checksum, created = archive_raw(source, tmp_path / "raw", "TEST")
    second, checksum2, created2 = archive_raw(source, tmp_path / "raw", "TEST")
    assert first == second and checksum == checksum2 == file_checksum(source)
    assert created is True and created2 is False


def test_missing_official_files_blocks_research_and_replay(tmp_path: Path) -> None:
    result = run(ROOT, drop_zone=tmp_path / "drop", data_root=tmp_path / "data", output_dir=tmp_path / "runtime", dry_run=True)
    assert result["final_status"] == "KRX_FLOW_DATA_BLOCKED"
    assert result["proposal_budget"] == {"used": 0, "limit": 3}
    assert result["operational_replay_budget"] == {"used": 0, "limit": 1}
    assert result["broker_mutation_calls"] == 0
    readiness = json.loads((tmp_path / "runtime/data_readiness_report.json").read_text(encoding="utf-8"))
    assert readiness["status"] == "HUMAN_DATA_DOWNLOAD_REQUIRED"
    assert readiness["ready_datasets"] == 0
    assert readiness["hypotheses_created"] == readiness["diagnostics_run"] == readiness["operational_replays_run"] == 0


def test_dry_run_is_idempotent(tmp_path: Path) -> None:
    kwargs = {"drop_zone": tmp_path / "drop", "data_root": tmp_path / "data", "output_dir": tmp_path / "runtime", "dry_run": True}
    first = run(ROOT, **kwargs)
    before = (tmp_path / "runtime/raw_source_manifest.csv").read_bytes()
    second = run(ROOT, **kwargs)
    assert first == second
    assert (tmp_path / "runtime/raw_source_manifest.csv").read_bytes() == before

