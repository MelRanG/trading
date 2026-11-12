"""Freeze evidence for the two completed daily runs; never execute a model or DB.

This is an artifact audit, not a new backtest or independent alpha validation.
Original summaries, contracts, trades and NAV files are read-only.
"""
from __future__ import annotations

import csv
import io
from decimal import Decimal
from hashlib import sha256
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quant_harness.historical_operational_replay import REPLAY_CODE_FILES, REPLAY_INPUT_FILES, _hash_files
from quant_harness.v104_end_to_end_causal_challenger_audit.adapter import _input_hash

MODELS = ("V69_PARENT", "V79_NO63_VOL_GUARD")
FILES = ("replay_summary.json", "replay_contract.json", "daily_nav.csv", "trades.csv", "parity_summary.json", "validation.log")
EXECUTION_HASH = "c22dc5b2620ce1d5ace63b2daa5387b4f6d108cb2580cd6a848a2c62ebfdf0c5"
TOLERANCE = Decimal("0.00000001")


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def audit_run(folder: Path, model: str) -> dict:
    # Hash and validate exactly the same bytes, even if another process writes.
    snapshot = {name: (folder / name).read_bytes() for name in FILES}
    hashes = {name: sha256(content).hexdigest() for name, content in snapshot.items()}
    summary, checkpoint = (json.loads(snapshot[name]) for name in FILES[:2])
    contract = checkpoint["contract"]
    body = {k: v for k, v in contract.items() if k != "fingerprint"}
    fingerprint = sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if contract["fingerprint"] != fingerprint or summary["replay_fingerprint"] != fingerprint:
        raise ValueError("replay contract fingerprint mismatch")
    if summary["candidate_id"] != model or contract["candidate_id"] != model:
        raise ValueError("candidate identity mismatch")
    if summary["database_scope"] != "TEST_DATABASE_URL_ONLY" or checkpoint["status"] != "COMPLETED":
        raise ValueError("not a completed isolated historical run")
    if contract["execution_contract"]["hash"] != EXECUTION_HASH or summary["execution_contract"]["hash"] != EXECUTION_HASH:
        raise ValueError("execution contract mismatch")
    nav, trades = (list(csv.DictReader(io.StringIO(snapshot[name].decode("utf-8-sig"))))
                   for name in ("daily_nav.csv", "trades.csv"))
    dates = [r["as_of"] for r in nav]
    if not dates or dates != sorted(set(dates)) or dates != checkpoint["completed_dates"]:
        raise ValueError("NAV dates duplicate, unordered or incomplete")
    metrics = summary["metrics"]
    if (dates[0], dates[-1], len(dates)) != (contract["period"]["start"], contract["period"]["end"], metrics["total_trading_days"]):
        raise ValueError("replay period mismatch")
    initial = Decimal(contract["initial_capital_krw"])
    if initial != Decimal(metrics["initial_capital_krw"]) or initial != Decimal("10000000"):
        raise ValueError("initial capital mismatch")
    fills = [r for r in trades if r.get("paper_fill_id")]
    fill_ids = [r["paper_fill_id"] for r in fills]
    if len(fill_ids) != len(set(fill_ids)) or any(r["as_of"] not in dates for r in trades):
        raise ValueError("duplicate fills or trade outside period")
    cash = initial
    fee = Decimal("0")
    slippage = Decimal("0")
    fills_by_date: dict[str, list] = {}
    for fill in fills:
        quantity, price, fill_fee = (Decimal(fill[k]) for k in ("fill_quantity", "fill_price", "fee"))
        if fill["side"] not in {"BUY", "SELL"} or quantity <= 0 or price <= 0 or fill_fee < 0:
            raise ValueError("invalid fill side, quantity, price or fee")
        signed_quantity = quantity if fill["side"] == "BUY" else -quantity
        expected_cash = -signed_quantity * price - fill_fee
        if abs(Decimal(fill["cash_delta"]) - expected_cash) > TOLERANCE or Decimal(fill["quantity_delta"]) != signed_quantity:
            raise ValueError("fill accounting identity mismatch")
        fills_by_date.setdefault(fill["as_of"], []).append(fill)
        fee += Decimal(fill["fee"])
        slippage += Decimal(fill["slippage"]) * Decimal(fill["fill_quantity"])
    for row in nav:
        cash += sum((Decimal(f["cash_delta"]) for f in fills_by_date.get(row["as_of"], [])), Decimal("0"))
        actual_cash, equity, position_value = (Decimal(row[k]) for k in ("cash_krw", "nav_krw", "positions_value_krw"))
        if cash < 0 or abs(cash - actual_cash) > TOLERANCE or abs(equity - actual_cash - position_value) > TOLERANCE:
            raise ValueError("unexplained daily cash or NAV difference")
    if abs(Decimal(nav[-1]["nav_krw"]) - Decimal(metrics["final_nav_krw"])) > TOLERANCE:
        raise ValueError("final NAV mismatch")
    if abs(fee - Decimal(metrics["total_fee_krw"])) > TOLERANCE or abs(slippage - Decimal(metrics["total_slippage_krw"])) > TOLERANCE:
        raise ValueError("fill cost metric mismatch")
    validation = summary["validation"]
    if validation["reconciliation_failures"] != 0 or validation["negative_cash"] or validation["negative_position"]:
        raise ValueError("recorded reconciliation failed")
    return {"candidate_id": model, "source": str(folder.relative_to(ROOT)) if folder.is_relative_to(ROOT) else str(folder),
            "artifact_sha256": hashes, "recorded_contract": contract, "metrics": metrics,
            "cash_nav_export_audit": "PASSED", "fill_cost_export_audit": "PASSED",
            "fill_cash_quantity_identity_audit": "PASSED",
            "days": len(dates), "fills": len(fills), "original_legacy_parity": summary["parity"],
            "signal_parity_scope": "SHARED_BUILDER_WIRING_NOT_INDEPENDENT_VALIDATION",
            "limitations": ["REUSED_HISTORICAL_SAMPLE_NOT_FORWARD", "ETF_UNIVERSE_PIT_LIMITED_OBSERVED_FIRST_BAR_PROXY",
                            "LIVE_RAW_VS_ADJUSTED_AND_DISTRIBUTIONS_NOT_PROVEN", "SLIPPAGE_NOT_SEPARATELY_TRACKED_IN_LEDGER",
                            "POSITION_MARKS_NOT_INDEPENDENTLY_REPRICED", "ORIGINAL_SOURCE_SNAPSHOT_NOT_ARCHIVED"]}


def save_report(output: Path, report: dict) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    lock = output.with_suffix(".json.lock")
    descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        if output.exists():
            if _json(output) != report:
                raise ValueError("frozen evidence audit changed; use a separately approved new audit")
            return
        temporary = output.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(output)
    finally:
        os.close(descriptor)
        lock.unlink()


def main() -> None:
    base = ROOT / "runtime/contract_aligned_comparison_20261004_run2"
    runs = [audit_run(base / model, model) for model in MODELS]
    for key in ("data_input_hash", "configuration_and_manifest_hash", "code_hash", "period", "initial_capital_krw", "execution_contract"):
        if runs[0]["recorded_contract"][key] != runs[1]["recorded_contract"][key]:
            raise ValueError(f"comparison contracts differ: {key}")
    current = {"data_input_hash": _input_hash(ROOT), "configuration_and_manifest_hash": _hash_files(ROOT, REPLAY_INPUT_FILES),
               "code_hash": _hash_files(ROOT, REPLAY_CODE_FILES)}
    for run in runs:
        run["current_workspace_matches_recorded"] = {k: current[k] == run["recorded_contract"][k] for k in current}
    report = {"status": "EVIDENCE_EXPORTS_VERIFIED_WITH_LIMITATIONS", "scope": "EXISTING_ARTIFACT_AUDIT_NO_REPLAY",
              "runs": runs, "current_workspace_hashes": current, "model_validation_passed": False,
              "forward_authority": "HOLD_ONLY_PENDING_FROZEN_TRIAL_AND_HUMAN_RISK_APPROVAL",
              "operational_database_access": False, "paper_primary_access": False, "broker_mutation_calls": 0}
    report["evidence_bundle_hash"] = sha256(json.dumps(report, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    output = ROOT / "runtime/current_model_evidence_audit/verified_exports_v3.json"
    save_report(output, report)
    print(json.dumps({"status": report["status"], "evidence_bundle_hash": report["evidence_bundle_hash"],
                      "output": str(output), "days": [r["days"] for r in runs],
                      "workspace_matches": [r["current_workspace_matches_recorded"] for r in runs],
                      "model_validation_passed": False, "broker_mutation_calls": 0}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
