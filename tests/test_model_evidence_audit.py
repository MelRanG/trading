from hashlib import sha256
import json
from pathlib import Path
import runpy

import pandas as pd
import pytest

AUDIT = runpy.run_path(str(Path(__file__).resolve().parents[1] / "scripts/audit_current_model_evidence.py"))


def _fixture(folder: Path) -> None:
    folder.mkdir()
    contract = {"candidate_id": "V69_PARENT", "initial_capital_krw": "10000000",
                "period": {"start": "2026-07-01", "end": "2026-07-02"},
                "execution_contract": {"hash": AUDIT["EXECUTION_HASH"]}}
    contract["fingerprint"] = sha256(json.dumps(contract, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    summary = {"candidate_id": "V69_PARENT", "replay_fingerprint": contract["fingerprint"],
               "database_scope": "TEST_DATABASE_URL_ONLY", "execution_contract": contract["execution_contract"],
               "metrics": {"total_trading_days": 2, "initial_capital_krw": "10000000", "final_nav_krw": "10004995",
                           "total_fee_krw": "5", "total_slippage_krw": "100"},
               "validation": {"reconciliation_failures": 0, "negative_cash": False, "negative_position": False}, "parity": {}}
    checkpoint = {"contract": contract, "status": "COMPLETED", "completed_dates": ["2026-07-01", "2026-07-02"]}
    for name, data in (("replay_summary.json", summary), ("replay_contract.json", checkpoint), ("parity_summary.json", {})):
        (folder / name).write_text(json.dumps(data), encoding="utf-8")
    pd.DataFrame([{"as_of": "2026-07-01", "cash_krw": 9899995, "positions_value_krw": 100000, "nav_krw": 9999995},
                  {"as_of": "2026-07-02", "cash_krw": 9899995, "positions_value_krw": 105000, "nav_krw": 10004995}]).to_csv(folder / "daily_nav.csv", index=False)
    pd.DataFrame([{"as_of": "2026-07-01", "paper_fill_id": "fill", "cash_delta": -100005,
                   "side": "BUY", "fill_price": 1000, "quantity_delta": 100,
                   "fee": 5, "slippage": 1, "fill_quantity": 100}]).to_csv(folder / "trades.csv", index=False)
    (folder / "validation.log").write_text("fixture", encoding="utf-8")


def test_evidence_audit_is_read_only_and_not_model_validation(tmp_path, monkeypatch) -> None:
    import psycopg
    def forbidden(*args, **kwargs):
        raise AssertionError("database access forbidden")
    monkeypatch.setattr(psycopg, "connect", forbidden)
    folder = tmp_path / "run"
    _fixture(folder)
    before = {p.name: p.read_bytes() for p in folder.iterdir()}
    result = AUDIT["audit_run"](folder, "V69_PARENT")
    assert result["cash_nav_export_audit"] == "PASSED"
    assert result["signal_parity_scope"] == "SHARED_BUILDER_WIRING_NOT_INDEPENDENT_VALIDATION"
    assert {p.name: p.read_bytes() for p in folder.iterdir()} == before


@pytest.mark.parametrize("change", ["cash", "duplicate", "fee", "contract", "candidate", "fill_price"])
def test_evidence_audit_fails_closed_on_corrupt_export(tmp_path, change) -> None:
    folder = tmp_path / "run"
    _fixture(folder)
    if change in {"cash", "duplicate"}:
        path = folder / "daily_nav.csv"
        rows = pd.read_csv(path)
        if change == "cash":
            rows.loc[1, "cash_krw"] += 1
        else:
            rows = pd.concat([rows, rows.iloc[:1]], ignore_index=True)
        rows.to_csv(path, index=False)
    elif change == "fill_price":
        path = folder / "trades.csv"
        rows = pd.read_csv(path)
        rows.loc[0, "fill_price"] += 1
        rows.to_csv(path, index=False)
    else:
        path = folder / ("replay_contract.json" if change == "contract" else "replay_summary.json")
        data = json.loads(path.read_text())
        if change == "contract":
            data["contract"]["initial_capital_krw"] = "20000000"
        elif change == "candidate":
            data["candidate_id"] = "V79_NO63_VOL_GUARD"
        else:
            data["metrics"]["total_fee_krw"] = "0"
        path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        AUDIT["audit_run"](folder, "V69_PARENT")


def test_evidence_freeze_is_idempotent_and_never_overwrites(tmp_path) -> None:
    path = tmp_path / "audit.json"
    report = {"evidence_bundle_hash": "frozen", "status": "LIMITED"}
    AUDIT["save_report"](path, report)
    before = path.read_bytes()
    AUDIT["save_report"](path, report)
    assert path.read_bytes() == before
    with pytest.raises(ValueError, match="frozen evidence"):
        AUDIT["save_report"](path, {**report, "status": "PASSED"})
    assert path.read_bytes() == before


def test_evidence_freeze_rejects_concurrent_writer(tmp_path) -> None:
    path = tmp_path / "audit.json"
    lock = path.with_suffix(".json.lock")
    lock.write_text("active", encoding="utf-8")
    with pytest.raises(FileExistsError):
        AUDIT["save_report"](path, {"status": "OTHER_WRITER"})
    assert not path.exists()
    assert lock.read_text() == "active"
