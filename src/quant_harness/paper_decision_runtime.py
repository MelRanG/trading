"""Single-account Paper decision and non-executable intent preview runtime."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, ROUND_FLOOR
from functools import lru_cache
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from quant_harness.paper_runtime_store import (
    PAPER_ACCOUNT_ID,
    PaperStoreError,
    ensure_paper_account,
    initialize_paper_schema,
    latest_paper_summaries,
    load_paper_account,
    save_paper_preview,
)
from quant_harness.toss_snapshot_runtime import run_toss_snapshot
from quant_harness.v101_risk_execution_agent import engine as v101
from quant_harness.v100_strategy_agent.policy import _target_hash
from quant_harness.v104_end_to_end_causal_challenger_audit.adapter import (
    _input_hash,
    build_candidate_ledgers,
    load_candidate_specs,
)
from quant_harness.v72_integration_ready.live_safety import (
    CURRENT_RELEASE_LIVE_AUTHORITY,
    LIVE_BUILD_CAPABILITY,
)


PaperPreviewError = PaperStoreError


INITIAL_CAPITAL_SOURCE = "config/v85_operations.yaml:initial_capital_krw"
STALE_MARKET_INPUT_MAX_AGE_DAYS = 3
PREOPEN_EXECUTION_CONTRACT = {
    "name": "D_MINUS_1_CLOSE_NAV_SIZE_D_OPEN_EXECUTION_V2",
    "signal_and_target_cutoff": "D-1 completed daily data",
    "quantity_sizing": "prior-session closing NAV * target weight / D-1 adjusted close, floored to whole shares",
    "execution": "D adjusted open, existing Paper execution costs and risk gates",
    "missing_open": "fail closed; no daily fallback",
}
PREOPEN_EXECUTION_CONTRACT_HASH = sha256(
    json.dumps(PREOPEN_EXECUTION_CONTRACT, sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()
BUILD_FILES = (
    "src/quant_harness/v69_dynamic_theme_leadership/engine.py",
    "src/quant_harness/v94_universe_agent/engine.py",
    "src/quant_harness/v94_universe_agent/policy.py",
    "src/quant_harness/v95_market_regime_agent/engine.py",
    "src/quant_harness/v95_market_regime_agent/policy.py",
    "src/quant_harness/v100_strategy_agent/policy.py",
    "src/quant_harness/v101_risk_execution_agent/engine.py",
    "src/quant_harness/v101_risk_execution_agent/policy.py",
    "src/quant_harness/v102_market_evidence_agent/policy.py",
    "src/quant_harness/v104_end_to_end_causal_challenger_audit/adapter.py",
)
CONFIG_FILES = (
    "config/active_strategy.yaml",
    "config/strategy_registry_v84.yaml",
    "config/v69_dynamic_theme_leadership.yaml",
    "config/v77_corrected_price_allocation.yaml",
    "config/v85_operations.yaml",
    "config/v94_universe_agent.yaml",
    "config/v95_market_regime_agent.yaml",
    "config/v100_strategy_agent.yaml",
    "config/v101_risk_execution_agent.yaml",
    "config/v102_market_evidence_contract.yaml",
    "config/v104_end_to_end_causal_challenger_audit.yaml",
)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _execution_targets_hash(targets: list[dict[str, Any]]) -> str:
    fields = ("symbol", "target_weight", "target_notional", "reference_price", "target_quantity", "adv20_d1_krw")
    rows = [{key: target.get(key) for key in fields} for target in sorted(targets, key=lambda row: str(row.get("symbol", "")))]
    return _digest(rows)


def _unselected_target_exceeds_cap(preview: dict[str, Any]) -> bool:
    if preview.get("selected_candidates"):
        return False
    return any(Decimal(str(weight)) > Decimal("0.90") for weight in preview.get("target_weights", {}).values())


def _hash_files(root: Path, files: tuple[str, ...]) -> str:
    digest = sha256()
    for relative in sorted(files):
        path = root / relative
        if not path.is_file():
            raise PaperPreviewError(f"required runtime input is missing: {relative}")
        digest.update(relative.replace("\\", "/").encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _dataset_id(root_text: str) -> str:
    manifest = Path(root_text) / "data/canonical/v84_market_manifest.csv"
    if not manifest.is_file():
        raise PaperPreviewError("canonical market manifest is missing")
    return sha256(manifest.read_bytes()).hexdigest()


def _validate_receipt(preview: dict[str, Any]) -> None:
    receipt = preview.get("decision_receipt")
    if not isinstance(receipt, dict):
        raise PaperPreviewError("strategy receipt is absent")
    supplied = receipt.get("receipt_hash")
    body = {k: v for k, v in receipt.items() if k != "receipt_hash"}
    if not supplied or supplied != _digest(body) or receipt.get("status") != "PASSED":
        raise PaperPreviewError("strategy receipt is invalid")
    evidence = receipt.get("evidence", {})
    if evidence.get("strategy_build_hash") != preview.get("strategy_build_hash"):
        raise PaperPreviewError("strategy build hash mismatch")
    if evidence.get("input_hash") != preview.get("input_hash"):
        raise PaperPreviewError("input manifest mismatch")
    if evidence.get("candidate_fingerprint") != preview.get("candidate_fingerprint"):
        raise PaperPreviewError("candidate fingerprint mismatch")
    if evidence.get("selected_candidates") != preview.get("selected_candidates"):
        raise PaperPreviewError("candidate selection does not match the approved receipt")
    if evidence.get("decision_uses_same_day_close") is not False:
        raise PaperPreviewError("strategy receipt violates point-in-time decision timing")
    normalized_weights = {str(symbol).zfill(6): float(weight) for symbol, weight in preview.get("target_weights", {}).items()}
    if _target_hash(normalized_weights) != preview.get("target_hash") or evidence.get("target_hash") != preview.get("target_hash"):
        raise PaperPreviewError("strategy target hash does not match target weights")
    target_weights = {str(row.get("symbol", "")).zfill(6): float(row.get("target_weight", 0)) for row in preview.get("targets", [])}
    if _target_hash(target_weights) != preview.get("target_hash"):
        raise PaperPreviewError("executable target rows differ from strategy target weights")
    if evidence.get("execution_targets_hash") != _execution_targets_hash(preview.get("targets", [])):
        raise PaperPreviewError("executable target payload does not match the approved receipt")


def _rebalance_trigger(
    *, target_changed: bool, pending: bool, max_abs_weight_drift: Decimal, band: Decimal
) -> bool:
    if max_abs_weight_drift < 0 or band < 0:
        raise PaperPreviewError("rebalance drift and band must be non-negative")
    return bool(pending or target_changed or max_abs_weight_drift >= band)


def apply_replay_preopen_sizing(
    preview: dict[str, Any],
    *,
    prior_session: str,
    sizing_prices: dict[str, Decimal | str | float],
    sizing_nav_krw: Decimal | str | float,
    execution_contract_hash: str,
    execution_contract_name: str = "D_MINUS_1_CLOSE_NAV_SIZE_D_OPEN_EXECUTION_V2",
    execution_price_contract: str = "D adjusted open",
) -> dict[str, Any]:
    """Bind replay quantities to prices known before the execution session.

    Strategy signals/weights remain untouched. Only the execution adapter's
    sizing reference changes from the same-session open to the prior completed
    close, which is observable before the next session opens.
    """
    result = deepcopy(preview)
    execution_date = pd.Timestamp(result["as_of"]).date()
    if prior_session is None or not str(prior_session).strip():
        raise PaperPreviewError("pre-open sizing requires a prior completed session")
    prior_date = pd.Timestamp(prior_session).date()
    if prior_date >= execution_date:
        raise PaperPreviewError("pre-open sizing price must precede execution date")
    if len(str(execution_contract_hash)) != 64 or any(ch not in "0123456789abcdef" for ch in str(execution_contract_hash).lower()):
        raise PaperPreviewError("execution contract hash must be a SHA-256 digest")
    _validate_receipt(preview)
    sizing_nav = Decimal(str(sizing_nav_krw))
    if not sizing_nav.is_finite() or sizing_nav <= 0:
        raise PaperPreviewError("prior-close NAV must be positive and finite")
    price_rows: dict[str, str] = {}
    for target in result.get("targets", []):
        symbol = str(target["symbol"]).zfill(6)
        try:
            price = Decimal(str(sizing_prices[symbol]))
        except (KeyError, ArithmeticError, ValueError) as exc:
            raise PaperPreviewError(f"missing prior-close sizing price for {symbol}") from exc
        if not price.is_finite() or price <= 0:
            raise PaperPreviewError(f"invalid prior-close sizing price for {symbol}")
        notional = sizing_nav * Decimal(str(target["target_weight"]))
        quantity = (notional / price).to_integral_value(rounding=ROUND_FLOOR)
        target["reference_price"] = price
        target["target_notional"] = notional
        target["target_quantity"] = quantity
        target["sizing_price_as_of"] = prior_date.isoformat()
        price_rows[symbol] = str(price)

    execution_contract = {
        "name": str(execution_contract_name),
        "hash": str(execution_contract_hash),
        "signal_cutoff": prior_date.isoformat(),
        "sizing_price_as_of": prior_date.isoformat(),
        "execution_session": execution_date.isoformat(),
        "execution_price": str(execution_price_contract),
        "sizing_nav_krw": str(sizing_nav),
        "quantity_policy": "prior_close_nav_times_target_weight_divided_by_prior_close_floor",
    }
    original_input_hash = str(result["input_hash"])
    result["execution_contract"] = execution_contract
    result["input_hash"] = _digest({
        "base_input_hash": original_input_hash,
        "execution_contract": execution_contract,
        "sizing_prices": price_rows,
    })
    result["session_id"] = f"PAPER-REPLAY-{execution_date.isoformat()}-{result['input_hash'][:16]}"
    result["decision_id"] = "DEC-" + _digest({
        "base_decision_id": result["decision_id"],
        "input_hash": result["input_hash"],
    })[:32]
    receipt = result["decision_receipt"]
    receipt_body = {key: value for key, value in receipt.items() if key != "receipt_hash"}
    receipt_body["evidence"]["input_hash"] = result["input_hash"]
    receipt_body["evidence"]["execution_contract_hash"] = execution_contract_hash
    receipt_body["evidence"]["sizing_price_as_of"] = prior_date.isoformat()
    receipt_body["evidence"]["execution_targets_hash"] = _execution_targets_hash(result.get("targets", []))
    result["decision_receipt"] = {**receipt_body, "receipt_hash": _digest(receipt_body)}
    _validate_receipt(result)
    return result


@lru_cache(maxsize=16)
def _strategy_base_cached(root_text: str, input_fingerprint: str) -> tuple[Any, dict[str, Any]]:
    root = Path(root_text)
    active = yaml.safe_load((root / "config/active_strategy.yaml").read_text(encoding="utf-8"))
    registry = yaml.safe_load((root / active["registry"]).read_text(encoding="utf-8"))
    strategy_id = str(active["active_strategy_id"])
    entries = [row for row in registry.get("strategies", []) if row.get("strategy_id") == strategy_id]
    if len(entries) != 1:
        raise PaperPreviewError("active strategy registry entry must be unique")
    entry = entries[0]
    if entry.get("status") != "PAPER_CHAMPION" or not entry.get("runtime_compatible"):
        raise PaperPreviewError("active strategy is not the verified Paper champion")
    candidate_id = str(entry.get("runtime_candidate_id") or "")
    specs = load_candidate_specs(root)
    if candidate_id not in specs:
        raise PaperPreviewError("active runtime candidate is missing")
    spec = specs[candidate_id]
    if candidate_id != "V69_PARENT" or spec.strategy != "V69":
        raise PaperPreviewError("single Paper runtime is pinned to the active V69 parent")
    built = build_candidate_ledgers(root, spec, use_common_cutoff=True)
    return spec, built


@lru_cache(maxsize=8)
def _candidate_base_cached(root_text: str, candidate_id: str, input_fingerprint: str) -> tuple[Any, dict[str, Any]]:
    """Build one registered candidate for an isolated operational replay.

    The default Paper runtime remains pinned to ``_strategy_base_cached`` and
    V69.  This adapter only exposes already-registered V104 candidates to the
    TEST_DATABASE_URL replay runner; it does not alter the active strategy.
    """
    root = Path(root_text)
    specs = load_candidate_specs(root)
    if candidate_id not in specs:
        raise PaperPreviewError(f"unknown replay candidate: {candidate_id}")
    spec = specs[candidate_id]
    return spec, build_candidate_ledgers(root, spec, use_common_cutoff=True)


@lru_cache(maxsize=4096)
def _build_strategy_preview_cached(
    root_text: str, as_of_text: str | None, candidate_id: str | None, input_fingerprint: str,
) -> dict[str, Any]:
    root = Path(root_text)
    replay_candidate_id = candidate_id
    if candidate_id is None:
        spec, built = _strategy_base_cached(root_text, input_fingerprint)
    else:
        spec, built = _candidate_base_cached(root_text, candidate_id, input_fingerprint)
    active = yaml.safe_load((root / "config/active_strategy.yaml").read_text(encoding="utf-8"))
    strategy_id = str(active["active_strategy_id"]) if candidate_id is None else str(candidate_id)
    candidate_id = spec.candidate_id
    ledger = built["ledger"].copy()
    ledger["date"] = pd.to_datetime(ledger["date"])
    latest = pd.Timestamp(ledger["date"].max())
    as_of = pd.Timestamp(as_of_text) if as_of_text else latest
    if as_of not in set(ledger["date"]):
        raise PaperPreviewError("Paper decision date is not a verified point-in-time session")
    target_row = ledger.loc[ledger["date"].eq(as_of)].iloc[0]
    selection = built["selection"].copy()
    selection["date"] = pd.to_datetime(selection["date"])
    selected_row = selection.loc[selection["date"].eq(as_of)].iloc[0]
    regime_row = built["regime"]["panel"].loc[as_of]

    manifest = root / "data/canonical/v84_market_manifest.csv"
    if not manifest.is_file():
        raise PaperPreviewError("canonical market manifest is missing")
    manifest_frame = pd.read_csv(manifest, dtype={"ticker": str})
    if manifest_frame.empty or pd.Timestamp(manifest_frame["end"].max()) < as_of:
        raise PaperPreviewError("canonical market manifest does not cover decision date")
    dataset_id = _dataset_id(str(root.resolve()))
    config_hash = _hash_files(root, CONFIG_FILES)
    strategy_build_hash = _hash_files(root, BUILD_FILES)
    input_hash = _digest(
        {
            "dataset_id": dataset_id,
            "as_of": as_of.date().isoformat(),
            "config_hash": config_hash,
            "kernel_input_hash": built["input_hash"],
            "candidate_id": candidate_id,
        }
    )
    weights = {
        str(symbol).zfill(6): float(weight)
        for symbol, weight in json.loads(str(target_row["target_weights_json"])).items()
    }
    market_open = built["market"]["open"].loc[as_of]
    adv20_d1 = built["market"]["adv20_d1"].loc[as_of]
    value_d1 = built["market"]["value"].loc[built["market"]["value"].index < as_of]
    prior_sessions = built["market"]["close"].index[built["market"]["close"].index < as_of]
    prior_session = pd.Timestamp(prior_sessions[-1]) if len(prior_sessions) else None
    prior_close = built["market"]["close"].loc[prior_session] if prior_session is not None else pd.Series(dtype=float)
    execution_open = built["market"]["open"].loc[as_of]
    initial_cfg = yaml.safe_load((root / "config/v85_operations.yaml").read_text(encoding="utf-8"))
    initial_capital = Decimal(str(initial_cfg["initial_capital_krw"]))
    targets: list[dict[str, Any]] = []
    for symbol, weight in sorted(weights.items()):
        price = market_open.get(symbol)
        reference = Decimal(str(price)) if pd.notna(price) and float(price) > 0 else None
        notional = initial_capital * Decimal(str(weight))
        quantity = (
            Decimal(math.floor(notional / reference))
            if reference is not None
            else Decimal("0")
        )
        targets.append(
            {
                "symbol": symbol,
                "target_weight": Decimal(str(weight)),
                "target_notional": notional,
                "reference_price": reference,
                "target_quantity": quantity,
                "adv20_d1_krw": (
                    Decimal(str(adv20_d1.get(symbol)))
                    if pd.notna(adv20_d1.get(symbol))
                    else None
                ),
                "calculation_status": "CALCULATED" if reference is not None else "BLOCKED",
                "reason": str(target_row.get("allocation_reason", "FIXED_PARENT_ALLOCATIONS")),
            }
        )
    selected = []
    for column in ("leader_ticker", "sleeve_ticker", "top_candidate_ticker"):
        if column in selected_row and pd.notna(selected_row.get(column)):
            selected.append(str(selected_row[column]).zfill(6))
            break
    receipt_body = {
        "status": "PASSED",
        "validator": "paper-decision-adapter/1",
        "evidence": {
            "dataset_id": dataset_id,
            "as_of": as_of.date().isoformat(),
            "input_hash": input_hash,
            "config_hash": config_hash,
            "strategy_build_hash": strategy_build_hash,
            "candidate_fingerprint": spec.fingerprint,
            "selected_candidates": selected,
            "target_hash": str(target_row["target_hash"]),
            "execution_targets_hash": _execution_targets_hash(targets),
            "decision_uses_same_day_close": bool(target_row["decision_uses_same_day_close"]),
        },
    }
    receipt = {**receipt_body, "receipt_hash": _digest(receipt_body)}
    decision_id = "DEC-" + _digest(
        {"strategy_id": strategy_id, "as_of": as_of.date().isoformat(), "input_hash": input_hash}
    )[:32]
    session_prefix = "PAPER" if replay_candidate_id is None else f"PAPER-{candidate_id}"
    return {
        "root": str(root),
        "session_id": f"{session_prefix}-{as_of.date().isoformat()}-{input_hash[:16]}",
        "decision_id": decision_id,
        "strategy_id": strategy_id,
        "candidate_id": candidate_id,
        "as_of": as_of,
        "dataset_id": dataset_id,
        "input_hash": input_hash,
        "config_hash": config_hash,
        "strategy_build_hash": strategy_build_hash,
        "candidate_fingerprint": spec.fingerprint,
        "target_hash": str(target_row["target_hash"]),
        "target_weights": weights,
        "regime": str(regime_row["regime_state"]),
        "selected_candidates": selected,
        "decision_status": "READY",
        "hold_reason": None,
        "decision_receipt": receipt,
        "targets": targets,
        # This is D-1 ADV calculated from the same adjusted daily market panel
        # as the target rows.  It is carried only for target-exit execution
        # intents, which deliberately have no positive-weight target row.
        "market_adv20_d1_krw": {
            str(symbol).zfill(6): Decimal(str(value))
            for symbol, value in adv20_d1.items()
            if pd.notna(value)
        },
        "market_adv20_status": {
            str(symbol).zfill(6): (
                "AVAILABLE" if pd.notna(adv20_d1.get(symbol))
                else "NOT_TRADABLE_WARMUP"
                if int(pd.to_numeric(value_d1.get(symbol), errors="coerce").notna().sum()) < 20
                else "DATA_INCOMPLETE"
            )
            for symbol in built["market"]["value"].columns
        },
        "allowed_symbols": sorted(
            {str(x).zfill(6) for x in built["universe"]["ticker"]} | set(weights)
        ),
        "market_data_status": "CURRENT_FOR_AS_OF",
        "broker_observation_status": "NOT_REQUESTED",
        "authority_status": "PREVIEW_ONLY",
        "runtime_mode": "MOCK",
        "initial_capital_krw": initial_capital,
        "initial_capital_source": INITIAL_CAPITAL_SOURCE,
        "execution_policy": spec.execution_policy,
        "created_at": datetime.now(timezone.utc),
        "_preopen_sizing": {
            "prior_session": prior_session.date().isoformat() if prior_session is not None else None,
            "prices": {
                str(symbol).zfill(6): Decimal(str(value))
                for symbol, value in prior_close.items()
                if pd.notna(value) and float(value) > 0
            },
        },
        "_execution_open_prices": {
            str(symbol).zfill(6): Decimal(str(value))
            for symbol, value in execution_open.items()
            if pd.notna(value) and float(value) > 0
        },
    }


def build_strategy_preview(
    root: Path | str,
    *,
    as_of: str | None = None,
    candidate_id: str | None = None,
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    root_text = str(root_path)
    input_fingerprint = _digest({
        "market_input_hash": _input_hash(root_path),
        "config_hash": _hash_files(root_path, CONFIG_FILES),
        "strategy_build_hash": _hash_files(root_path, BUILD_FILES),
        "dataset_id": _dataset_id(root_text),
    })
    return deepcopy(_build_strategy_preview_cached(root_text, as_of, candidate_id, input_fingerprint))


def build_candidate_strategy_preview(
    root: Path | str,
    candidate_id: str,
    *,
    as_of: str | None = None,
) -> dict[str, Any]:
    """Thin candidate adapter for TEST_DATABASE_URL operational replay only."""
    return build_strategy_preview(root, as_of=as_of, candidate_id=candidate_id)


def build_intent_previews(
    preview: dict[str, Any],
    account: dict[str, Any],
    *,
    position_reference_resolver: Any = None,
    rebalance_reference_prices: dict[str, Decimal | str | float] | None = None,
) -> list[dict[str, Any]]:
    if LIVE_BUILD_CAPABILITY or CURRENT_RELEASE_LIVE_AUTHORITY:
        raise PaperPreviewError("Live hardlock verification failed")
    _validate_receipt(preview)
    if not preview.get("selected_candidates"):
        fallback = preview.get("targets", [])
        if fallback and _unselected_target_exceeds_cap(preview):
            preview["decision_status"] = "HOLD_ONLY"
            preview["authority_status"] = "HOLD_ONLY"
            preview["hold_reason"] = (
                "NO_LEADER_CORE_FALLBACK_EXCEEDS_90_PERCENT_SINGLE_SYMBOL_CAP"
                if all(row.get("reason") == "NO_LEADER_CORE_FALLBACK" for row in fallback)
                else "NO_SELECTED_TARGET_EXCEEDS_90_PERCENT_SINGLE_SYMBOL_CAP"
            )
            return []
        # V79 may have no generic-trend sleeve selection while its V69 base
        # leader still produces a valid blended target. The signed target
        # ledger—not the sleeve-only selection field—determines whether that
        # allocation can be executed. Empty or malformed targets still fail
        # closed in the validation below.
    if account.get("paper_account_id") != PAPER_ACCOUNT_ID:
        raise PaperPreviewError("Paper DB state has an unknown account")
    if account.get("status") not in {"ACTIVE", "HOLD_ONLY", "BLOCKED"}:
        raise PaperPreviewError("Paper DB state is invalid")

    targets = preview.get("targets")
    if not isinstance(targets, list) or not targets:
        raise PaperPreviewError("target result is incomplete")
    total = sum(Decimal(str(row.get("target_weight", 0))) for row in targets)
    if abs(total - Decimal("1")) > Decimal("0.000000001"):
        raise PaperPreviewError("target weight contract violation")
    allowed = set(preview.get("allowed_symbols", []))
    prices: dict[str, Decimal] = {}
    for row in targets:
        symbol = str(row.get("symbol", ""))
        if symbol not in allowed:
            raise PaperPreviewError(f"unknown symbol in target: {symbol}")
        try:
            price = Decimal(str(row["reference_price"]))
        except Exception as exc:
            raise PaperPreviewError(f"reference price is missing for {symbol}") from exc
        if not price.is_finite() or price <= 0:
            raise PaperPreviewError(f"reference price is missing for {symbol}")
        weight = Decimal(str(row["target_weight"]))
        if weight < 0 or weight > Decimal("0.90"):
            raise PaperPreviewError("target weight contract violation")
        prices[symbol] = price

    positions = {
        str(symbol).zfill(6): Decimal(str(quantity))
        for symbol, quantity in account.get("positions", {}).items()
    }
    unknown_positions = sorted(set(positions) - allowed)
    if unknown_positions:
        raise PaperPreviewError(f"Paper DB state contains unknown symbol: {unknown_positions}")
    # A position can legitimately fall out of the current target list after a
    # rotation.  Keep the strategy target unchanged, but obtain its as-of
    # market price so the operational path can emit the required target=0 SELL
    # intent.  Missing data remains fail-closed.
    missing_position_prices = sorted(set(positions) - set(prices))
    for symbol in missing_position_prices:
        if position_reference_resolver is not None:
            try:
                price = Decimal(str(position_reference_resolver(symbol)))
                if not price.is_finite() or price <= 0:
                    raise ValueError("invalid replay reference price")
                prices[symbol] = price
                continue
            except Exception as exc:
                raise PaperPreviewError(f"reference price is missing for Paper positions: {missing_position_prices}") from exc
        root = Path(str(preview.get("root", ".")))
        frame_path = root / "data/toss_v19c_daily" / f"{symbol}_1d.csv"
        try:
            frame = pd.read_csv(frame_path)
            dates = pd.to_datetime(frame["timestamp"], errors="raise", utc=True)
            cutoff = pd.Timestamp(preview["as_of"], tz="UTC")
            frame = frame.loc[dates <= cutoff].sort_values("timestamp")
            if frame.empty:
                raise ValueError("no as-of row")
            price = Decimal(str(frame.iloc[-1]["close"]))
            if not price.is_finite() or price <= 0:
                raise ValueError("invalid as-of price")
            prices[symbol] = price
        except Exception as exc:
            raise PaperPreviewError(f"reference price is missing for Paper positions: {missing_position_prices}") from exc
    cash = Decimal(str(account["cash_krw"]))
    tracked = set(positions) | set(preview.get("target_weights", {}))
    gate_prices = dict(prices)
    if rebalance_reference_prices is not None:
        normalized_gate_prices = {str(symbol).zfill(6): Decimal(str(price)) for symbol, price in rebalance_reference_prices.items()}
        missing_gate_prices = sorted(tracked - set(normalized_gate_prices))
        if missing_gate_prices:
            raise PaperPreviewError(f"missing execution-time rebalance marks: {missing_gate_prices}")
        gate_prices.update(normalized_gate_prices)
    missing_gate_prices = sorted(set(positions) - set(gate_prices))
    if missing_gate_prices:
        raise PaperPreviewError(f"missing execution-time rebalance marks for Paper positions: {missing_gate_prices}")
    equity = cash + sum(positions[symbol] * gate_prices[symbol] for symbol in positions)
    if equity <= 0:
        raise PaperPreviewError("Paper equity is not positive")

    policy = v101._policy(Path(preview.get("root", ".")), preview["execution_policy"]) if preview.get("root") else None
    candidate_specs = load_candidate_specs(Path(preview["root"])) if preview.get("root") else {}
    candidate_spec = candidate_specs.get(str(preview.get("candidate_id", "")))
    if candidate_spec is None:
        raise PaperPreviewError("candidate execution policy is not registered")
    if policy is None:
        raise PaperPreviewError("registered V101 execution policy is unavailable")
    rebalance_band = Decimal(str(
        policy.v69_rebalance_band if candidate_spec.strategy == "V69" else policy.v79_rebalance_band
    ))
    target_weights = {
        str(symbol).zfill(6): Decimal(str(weight))
        for symbol, weight in preview.get("target_weights", {}).items()
    }
    max_abs_weight_drift = max((
        abs(
            positions.get(symbol, Decimal("0")) * gate_prices.get(symbol, prices.get(symbol, Decimal("0"))) / equity
            - target_weights.get(symbol, Decimal("0"))
        )
        for symbol in tracked
    ), default=Decimal("0"))
    target_changed = account.get("previous_target_hash") != preview.get("target_hash")
    pending = bool(account.get("execution_pending", False))
    should_execute = _rebalance_trigger(
        target_changed=target_changed,
        pending=pending,
        max_abs_weight_drift=max_abs_weight_drift,
        band=rebalance_band,
    )
    preview["execution_gate"] = {
        "policy_id": preview["execution_policy"],
        "rebalance_band": str(rebalance_band),
        "target_changed": target_changed,
        "pending": pending,
        "max_abs_weight_drift": str(max_abs_weight_drift),
        "triggered": should_execute,
    }
    if not should_execute:
        preview["decision_status"] = "NO_REBALANCE_WITHIN_REGISTERED_BAND"
        return []
    global_hold = (
        account["status"] != "ACTIVE"
        or preview.get("market_data_status") != "CURRENT_FOR_AS_OF"
        or preview.get("broker_observation_status") in {"FAILED", "UNKNOWN", "UNKNOWN_ORDER"}
    )
    intents: list[dict[str, Any]] = []
    buy_notional = Decimal("0")
    sell_notional = Decimal("0")
    for target in targets:
        symbol = target["symbol"]
        weight = Decimal(str(target["target_weight"]))
        price = prices[symbol]
        target_notional = Decimal(str(target["target_notional"]))
        target_quantity = Decimal(str(target["target_quantity"]))
        current = positions.get(symbol, Decimal("0"))
        delta = target_quantity - current
        target["target_notional"] = target_notional
        target["target_quantity"] = target_quantity
        target["calculation_status"] = "CALCULATED"
        if delta == 0:
            continue
        side = "BUY" if delta > 0 else "SELL"
        estimated = abs(delta) * price
        if side == "BUY":
            buy_notional += estimated
        else:
            sell_notional += estimated
        adv = target.get("adv20_d1_krw")
        risk_status = "PREVIEW_OK"
        authority = "HOLD_ONLY" if global_hold else "PREVIEW_ONLY"
        reason = str(target.get("reason") or "TARGET_DELTA")
        # Minimum notional depends on the executable price and the quantity
        # remaining after ADV/cash clipping. Defer that gate to the V101
        # execution planner; D-1 preview notional is diagnostic only.
        if adv is None or Decimal(str(adv)) <= 0:
            risk_status = "MISSING_OR_ZERO_D1_ADV"
            authority = "HOLD_ONLY"
        intent_id = "INT-" + _digest(
            {
                "session_id": preview["session_id"],
                "paper_account_id": PAPER_ACCOUNT_ID,
                "symbol": symbol,
                "side": side,
                "current_quantity": str(current),
                "target_quantity": str(target_quantity),
                "input_hash": preview["input_hash"],
            }
        )[:32]
        intents.append(
            {
                "intent_id": intent_id,
                "session_id": preview["session_id"],
                "paper_account_id": PAPER_ACCOUNT_ID,
                "symbol": symbol,
                "side": side,
                "current_quantity": current,
                "target_quantity": target_quantity,
                "delta_quantity": delta,
                "reference_price": price,
                "estimated_notional": estimated,
                "adv20_d1_krw": adv,
                "reason": reason,
                "risk_status": risk_status,
                "authority_status": authority,
                "created_at": datetime.now(timezone.utc),
                "input_hash": preview["input_hash"],
            }
        )
    target_symbols = {str(target["symbol"]).zfill(6) for target in targets}
    for symbol in sorted(set(positions) - target_symbols):
        current = positions[symbol]
        if current <= 0:
            continue
        price = prices[symbol]
        estimated = current * price
        sell_notional += estimated
        adv = preview.get("market_adv20_d1_krw", {}).get(symbol)
        intent_id = "INT-" + _digest(
            {
                "session_id": preview["session_id"], "paper_account_id": PAPER_ACCOUNT_ID,
                "symbol": symbol, "side": "SELL", "current_quantity": str(current),
                "target_quantity": "0", "input_hash": preview["input_hash"],
            }
        )[:32]
        intents.append(
            {
                "intent_id": intent_id, "session_id": preview["session_id"],
                "paper_account_id": PAPER_ACCOUNT_ID, "symbol": symbol, "side": "SELL",
                "current_quantity": current, "target_quantity": Decimal("0"),
                "delta_quantity": -current, "reference_price": price,
                "estimated_notional": estimated, "adv20_d1_krw": adv, "reason": "TARGET_EXIT",
                "risk_status": "MISSING_OR_ZERO_D1_ADV" if adv is None else "PREVIEW_OK",
                "authority_status": "HOLD_ONLY" if (global_hold or adv is None) else "PREVIEW_ONLY",
                "created_at": datetime.now(timezone.utc), "input_hash": preview["input_hash"],
            }
        )
    return intents


def _mark_stale_preview_hold(preview: dict[str, Any]) -> None:
    as_of = pd.Timestamp(preview["as_of"]).date()
    age_days = (datetime.now(timezone.utc).date() - as_of).days
    if age_days <= STALE_MARKET_INPUT_MAX_AGE_DAYS:
        return
    stale_key = _digest({"as_of": as_of.isoformat(), "input_hash": preview["input_hash"]})
    preview["session_id"] = f"PAPER-HOLD-{as_of.isoformat()}-{stale_key[:16]}"
    preview["decision_id"] = "DEC-HOLD-" + stale_key[:32]
    preview["market_data_status"] = "STALE"
    preview["hold_reason"] = f"STALE_MARKET_INPUT:{as_of.isoformat()}"


def run_paper_decision_preview(
    root: Path | str,
    *,
    database_url: str,
    mode: str,
) -> dict[str, Any]:
    if mode not in {"mock", "real-read-only"}:
        raise PaperPreviewError("mode must be mock or real-read-only")
    root = Path(root)
    initial_cfg = yaml.safe_load((root / "config/v85_operations.yaml").read_text(encoding="utf-8"))
    initial_capital = Decimal(str(initial_cfg["initial_capital_krw"]))
    initialize_paper_schema(database_url)
    ensure_paper_account(database_url, initial_capital, INITIAL_CAPITAL_SOURCE)
    snapshot = run_toss_snapshot(database_url=database_url, mode=mode)
    preview = build_strategy_preview(root)
    # The active-data updater establishes the verified common cutoff.  Calendar
    # age alone is not a data-integrity failure (weekends/holidays and provider
    # publication lag are valid); stale authority is set only by an explicit
    # missing or inconsistent input gate.
    preview["root"] = str(root)
    preview["runtime_mode"] = "MOCK" if mode == "mock" else "REAL_READ_ONLY"
    preview["broker_observation_status"] = snapshot.get("observation_status", snapshot["status"])
    account = load_paper_account(database_url)
    preopen = preview.pop("_preopen_sizing", None)
    execution_open_prices = preview.pop("_execution_open_prices", None)
    if not isinstance(preopen, dict) or not isinstance(execution_open_prices, dict):
        raise PaperPreviewError("pre-open sizing or executable D-open prices are missing")
    if not preopen.get("prior_session"):
        raise PaperPreviewError("pre-open sizing requires a prior completed session")
    sizing_prices = preopen["prices"]
    required_marks = {str(row["symbol"]).zfill(6) for row in preview.get("targets", [])}
    required_marks.update(str(symbol).zfill(6) for symbol in account.get("positions", {}))
    missing_marks = sorted(required_marks - set(sizing_prices))
    if missing_marks:
        raise PaperPreviewError(f"missing D-1 closing marks for Paper sizing: {missing_marks}")
    sizing_nav = Decimal(account["cash_krw"]) + sum(
        (Decimal(quantity) * Decimal(sizing_prices[str(symbol).zfill(6)])
         for symbol, quantity in account.get("positions", {}).items()),
        Decimal("0"),
    )
    preview = apply_replay_preopen_sizing(
        preview,
        prior_session=str(preopen["prior_session"]),
        sizing_prices=sizing_prices,
        sizing_nav_krw=sizing_nav,
        execution_contract_hash=PREOPEN_EXECUTION_CONTRACT_HASH,
        execution_contract_name=str(PREOPEN_EXECUTION_CONTRACT["name"]),
        execution_price_contract="D adjusted open",
    )
    intents = build_intent_previews(
        preview,
        account,
        position_reference_resolver=lambda symbol: sizing_prices[str(symbol).zfill(6)],
        rebalance_reference_prices=execution_open_prices,
    )
    references = {str(symbol).zfill(6): price for symbol, price in execution_open_prices.items()}
    for intent in intents:
        symbol = str(intent["symbol"]).zfill(6)
        if symbol not in execution_open_prices:
            raise PaperPreviewError(f"missing executable adjusted open for {symbol}")
        references[str(intent["intent_id"])] = execution_open_prices[symbol]
    statuses = {row["authority_status"] for row in intents}
    authority = (
        "HOLD_ONLY"
        if preview.get("authority_status") == "HOLD_ONLY"
        or "HOLD_ONLY" in statuses
        or preview["broker_observation_status"] in {"FAILED", "UNKNOWN", "UNKNOWN_ORDER"}
        else "PREVIEW_ONLY"
    )
    preview["authority_status"] = authority
    preview["decision_status"] = authority
    if authority != "PREVIEW_ONLY" and not preview.get("hold_reason"):
        preview["hold_reason"] = "CENTRAL_GATE_HOLD"
    outcome = save_paper_preview(database_url, preview, intents)
    summaries = latest_paper_summaries(database_url)
    return {
        "status": outcome,
        "mode": mode,
        "read_only_snapshot": snapshot,
        "paper_account": summaries["account"],
        "decision": summaries["decision"],
        "targets": summaries["targets"],
        "intent_previews": summaries["intents"],
        "execution_references": references,
        "runtime_health": summaries["health"],
        "authority_status": authority,
        "live_execution_allowed": False,
        "paper_assets_mutated": False,
        "broker_mutation_calls": 0,
    }
