from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path
from typing import Any


VALIDATION_STATES = frozenset({"NOT_RUN", "UNKNOWN", "BLOCKED", "FAILED", "PASSED"})
VALIDATOR_VERSION = "v104-receipt-validator/1"
RECEIPT_DIR = Path("reports/runtime/v104_receipts")


def _canonical(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def receipt_path(root: Path, check_id: str, session: str, candidate_id: str) -> Path:
    safe = f"{check_id}__{session}__{candidate_id}".replace(":", "_")
    return root / RECEIPT_DIR / f"{safe}.json"


def issue_receipt(
    root: Path,
    *,
    check_id: str,
    session: str,
    candidate_id: str,
    input_hash: str,
    result_status: str,
    evidence: dict[str, Any],
    observed_at: str | None = None,
) -> dict[str, Any]:
    """Persist a validator-produced receipt; callers cannot mark rows passed directly."""
    if result_status not in {"PASSED", "FAILED", "BLOCKED"}:
        raise ValueError(f"invalid receipt result status: {result_status}")
    body = {
        "check_id": check_id,
        "session": session,
        "candidate_id": candidate_id,
        "input_hash": input_hash,
        "validated_at_utc": observed_at or datetime.now(UTC).isoformat(),
        "validator_version": VALIDATOR_VERSION,
        "result_status": result_status,
        "evidence": evidence,
    }
    body["receipt_hash"] = sha256(_canonical(body).encode("utf-8")).hexdigest()
    path = receipt_path(root, check_id, session, candidate_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body, sort_keys=True, indent=2, ensure_ascii=False), encoding="utf-8")
    return body


def receipt_status(
    root: Path,
    *,
    check_id: str,
    session: str,
    candidate_id: str,
    input_hash: str,
    expected_evidence: dict[str, Any],
) -> str:
    """Return PASSED only for an authentic, matching validator receipt.

    A bool/string field in an observation is intentionally not considered here.
    """
    path = receipt_path(root, check_id, session, candidate_id)
    if not path.exists():
        return "NOT_RUN"
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
        supplied_hash = receipt.pop("receipt_hash")
        if sha256(_canonical(receipt).encode("utf-8")).hexdigest() != supplied_hash:
            return "FAILED"
        if receipt.get("validator_version") != VALIDATOR_VERSION:
            return "FAILED"
        if any(receipt.get(key) != value for key, value in {
            "check_id": check_id, "session": session, "candidate_id": candidate_id,
            "input_hash": input_hash,
        }.items()):
            return "FAILED"
        if receipt.get("evidence") != expected_evidence:
            return "FAILED"
        return "PASSED" if receipt.get("result_status") == "PASSED" else "FAILED"
    except (OSError, TypeError, ValueError, json.JSONDecodeError, KeyError):
        return "FAILED"
