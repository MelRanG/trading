from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import yaml

from .adapter import load_candidate_specs, load_config, replay_candidate

PARENT_BY_STRATEGY = {"V69": "V69_PARENT", "V79": "V79_PARENT"}
DEFAULT_OUTPUT = Path("reports/runtime/v104_forward_observations.csv")


def _order_signature(orders: pd.DataFrame, session: pd.Timestamp) -> str:
    if orders.empty:
        return sha256(b"").hexdigest()
    frame = orders.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame.loc[frame["date"].eq(session)].copy()
    if frame.empty:
        return sha256(b"").hexdigest()
    cols = [
        c for c in (
            "ticker", "side", "quantity", "reference_open_krw", "execution_price_krw",
            "fee_krw", "half_spread_cost_krw", "impact_cost_krw", "reason",
        ) if c in frame.columns
    ]
    payload = frame.sort_values([c for c in ("ticker", "side") if c in frame.columns])[cols].to_dict("records")
    return sha256(json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")).hexdigest()


def _latest_row(frame: pd.DataFrame, session: pd.Timestamp) -> pd.Series:
    work = frame.copy()
    work["date"] = pd.to_datetime(work["date"])
    rows = work.loc[work["date"].eq(session)]
    if len(rows) != 1:
        raise ValueError(f"expected one row for {session.date()}, found {len(rows)}")
    return rows.iloc[0]


def build_session_observations(
    root: Path | str,
    *,
    candidate_ids: Iterable[str] | None = None,
    as_of: str | pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Build one reconciled parent/candidate observation for each enabled adapter.

    This function deliberately performs a full deterministic replay.  It is slower
    than a broker-state incremental runner, but it guarantees that a new daily
    observation is reproducible from the sealed inputs while the external broker
    contract remains unverified.
    """
    root = Path(root)
    cfg = load_config(root)
    contract = yaml.safe_load((root / "config/v104_challenger_runtime_contract.yaml").read_text(encoding="utf-8"))
    enabled = list(candidate_ids or contract.get("enabled_candidates", []))
    specs = load_candidate_specs(root)
    unknown = sorted(set(enabled) - set(specs))
    if unknown:
        raise ValueError(f"unknown V104 runtime candidates: {unknown}")
    required = sorted(set(enabled) | {PARENT_BY_STRATEGY[specs[c].strategy] for c in enabled})
    runs = {candidate_id: replay_candidate(root, specs[candidate_id]) for candidate_id in required}
    latest_dates = {candidate_id: pd.to_datetime(run["account"]["date"]).max() for candidate_id, run in runs.items()}
    if len(set(latest_dates.values())) != 1:
        raise ValueError(f"candidate data cutoffs differ: {latest_dates}")
    session = pd.Timestamp(as_of) if as_of is not None else next(iter(latest_dates.values()))
    if any(session > latest for latest in latest_dates.values()):
        raise ValueError(f"requested session {session.date()} is later than available data")
    freeze_end = pd.Timestamp(cfg["historical_data_end"])
    rows: list[dict[str, Any]] = []
    contract_candidates = contract.get("candidates", {})
    for candidate_id in enabled:
        candidate = runs[candidate_id]
        spec = specs[candidate_id]
        parent_id = PARENT_BY_STRATEGY[spec.strategy]
        parent = runs[parent_id]
        crow = _latest_row(candidate["account"], session)
        prow = _latest_row(parent["account"], session)
        ctarget = _latest_row(candidate["ledger"], session)
        ptarget = _latest_row(parent["ledger"], session)
        expected = contract_candidates.get(candidate_id, {})
        if expected and expected.get("candidate_fingerprint") != spec.fingerprint:
            raise ValueError(f"candidate fingerprint mutation detected for {candidate_id}")
        if candidate["input_hash"] != parent["input_hash"]:
            raise ValueError(f"parent/candidate input hash mismatch for {candidate_id}")
        rows.append({
            "session": session.date().isoformat(),
            "candidate_id": candidate_id,
            "parent_candidate_id": parent_id,
            "strategy": spec.strategy,
            "paper_account_id": expected.get("paper_account_id", f"PAPER-V104-{candidate_id}"),
            "candidate_fingerprint": spec.fingerprint,
            "input_hash": candidate["input_hash"],
            "candidate_target_hash": str(ctarget["target_hash"]),
            "parent_target_hash": str(ptarget["target_hash"]),
            "target_changed": bool(str(ctarget["target_hash"]) != str(ptarget["target_hash"])),
            "candidate_order_signature": _order_signature(candidate["orders"], session),
            "parent_order_signature": _order_signature(parent["orders"], session),
            "candidate_nav_krw": float(crow["nav_krw"]),
            "parent_nav_krw": float(prow["nav_krw"]),
            "candidate_minus_parent_nav_krw": float(crow["nav_krw"] - prow["nav_krw"]),
            "candidate_cash_krw": float(crow["cash_krw"]),
            "parent_cash_krw": float(prow["cash_krw"]),
            "historical_replay_only": bool(session <= freeze_end),
            "new_forward_observation": bool(session > freeze_end),
            "data_gate_passed": True,
            "reconciliation_passed": True,
            "live_execution_allowed": False,
        })
    return pd.DataFrame(rows).sort_values(["session", "candidate_id"]).reset_index(drop=True)


def append_new_forward_observations(
    root: Path | str,
    *,
    output_path: Path | str | None = None,
    candidate_ids: Iterable[str] | None = None,
    as_of: str | pd.Timestamp | None = None,
) -> dict[str, Any]:
    """Append only genuinely new post-freeze sessions, fail-closed and idempotent."""
    root = Path(root)
    rows = build_session_observations(root, candidate_ids=candidate_ids, as_of=as_of)
    if rows.empty:
        return {"status": "NO_ENABLED_CANDIDATES", "rows_appended": 0, "live_execution_allowed": False}
    if not rows["new_forward_observation"].all():
        return {
            "status": "NO_NEW_SESSION_AFTER_V104_FREEZE",
            "session": str(rows["session"].iloc[0]),
            "rows_appended": 0,
            "historical_replay_rows": int(rows["historical_replay_only"].sum()),
            "live_execution_allowed": False,
        }
    target = root / (Path(output_path) if output_path is not None else DEFAULT_OUTPUT)
    target.parent.mkdir(parents=True, exist_ok=True)
    key = ["session", "candidate_id"]
    if target.exists():
        existing = pd.read_csv(target, dtype=str)
        combined = existing.copy()
        for row in rows.to_dict("records"):
            mask = existing["session"].astype(str).eq(str(row["session"])) & existing["candidate_id"].astype(str).eq(str(row["candidate_id"]))
            if mask.any():
                old = existing.loc[mask].iloc[0].to_dict()
                normalized = {k: str(v) for k, v in row.items()}
                if any(str(old.get(k)) != normalized[k] for k in normalized):
                    raise ValueError(f"forward observation idempotency conflict: {row['session']} {row['candidate_id']}")
                continue
            combined = pd.concat([combined, pd.DataFrame([row])], ignore_index=True)
    else:
        combined = rows.copy()
    combined.sort_values(key).to_csv(target, index=False)
    return {
        "status": "NEW_FORWARD_OBSERVATIONS_APPENDED",
        "session": str(rows["session"].iloc[0]),
        "rows_appended": int(len(rows)),
        "output": str(target.relative_to(root)),
        "live_execution_allowed": False,
    }
