"""Narrow evidence gate for the existing daily operational replay."""
from __future__ import annotations

from collections import Counter
from decimal import Decimal
import json
from pathlib import Path
from typing import Any

import pandas as pd

from quant_harness.model_validation_gate import (
    _cost_terms, _dec, _load_prices, _load_replay, _previews, _target_meta,
)
from quant_harness.v77_corrected_price_allocation import engine as v77


MODE = "BASE_OPERATIONAL_REPLAY_VALIDATION"
INITIAL_CAPITAL = Decimal("10000000")


def _hashes(root: Path) -> dict[str, str]:
    frozen = json.loads((root / "reports/v89_forward_governance/frozen_trial_registry.json").read_text(encoding="utf-8"))
    return frozen["hashes"]


def _rejects(root: Path, trades: pd.DataFrame, previews: dict[str, dict[str, Any]]) -> pd.DataFrame:
    """Reconstruct only existing execution checks, in the actual SELL-first order."""
    spec = v77._load_config(root).base_execution
    cash = INITIAL_CAPITAL
    positions: dict[str, Decimal] = {}
    rows: list[dict[str, Any]] = []
    for ds, group in trades.groupby("replay_date", sort=True):
        preview = previews[ds]
        target = _target_meta(preview)
        ordered = group.assign(_side=group["side"].map({"SELL": 0, "BUY": 1})).sort_values(["_side", "symbol"])
        for _, order in ordered.iterrows():
            symbol, side = str(order["symbol"]).zfill(6), str(order["side"])
            meta = target.get(symbol)
            qty, ref = _dec(order["requested_quantity"]), _dec(order["reference_price"])
            status = str(order["status"])
            adv = _dec((meta or {}).get("adv20_d1_krw", preview.get("market_adv20_d1_krw", {}).get(symbol)))
            reason = "FILLED" if status == "FILLED" else "UNEXPLAINED"
            if status == "REJECTED":
                if qty * ref < Decimal("100000"):
                    reason = "MINIMUM_NOTIONAL"
                elif adv <= 0:
                    reason = str(preview.get("market_adv20_status", {}).get(symbol, "DATA_INCOMPLETE"))
                else:
                    fill, fee, _ = _cost_terms(qty, ref, adv, spec, side)
                    if side == "BUY" and cash < qty * fill + fee:
                        reason = "INSUFFICIENT_CASH"
                    elif side == "SELL" and positions.get(symbol, Decimal("0")) < qty:
                        reason = "INSUFFICIENT_POSITION"
            rows.append({"date": ds, "symbol": symbol, "side": side, "status": status, "reason": reason})
            if status == "FILLED":
                cash += _dec(order["cash_delta"])
                positions[symbol] = positions.get(symbol, Decimal("0")) + _dec(order["quantity_delta"])
                if not positions[symbol]:
                    positions.pop(symbol, None)
    return pd.DataFrame(rows)


def run_base_operational_replay_validation(root: Path | str, *, output_dir: Path | str | None = None) -> dict[str, Any]:
    root = Path(root).resolve()
    out = Path(output_dir) if output_dir else root / "runtime/base_operational_replay_validation"
    out.mkdir(parents=True, exist_ok=True)
    prior_path = root / "runtime/model_validation_gate/validation_summary.json"
    prior = json.loads(prior_path.read_text(encoding="utf-8")) if prior_path.exists() else {}
    from quant_harness.model_validation_gate import run_model_validation_gate
    current = run_model_validation_gate(root)
    nav, trades = _load_replay(root)
    previews = _previews(root, sorted(nav["as_of"].tolist()))
    rejects = _rejects(root, trades, previews)
    rejection_counts = rejects[rejects["status"].eq("REJECTED")]["reason"].value_counts().rename_axis("reason").reset_index(name="count")
    execution = current["execution"]["funnel_reason_counts"]
    legacy_v90 = pd.read_csv(root / "reports/v90_trade_attribution/v90_regime_d1.csv", dtype=str)
    legacy_counts = legacy_v90["regime_d1"].value_counts().to_dict()
    regime = current["regime"]
    unexplained = int((rejects["reason"] == "UNEXPLAINED").sum())
    if regime["semantic_parity"] < 1 or current["candidate_target_parity"]["candidate_parity"] < 1 or current["candidate_target_parity"]["target_parity"] < 1:
        decision = "BLOCKED_BY_REGIME_CONTRACT"
    elif int((rejection_counts["reason"] == "DATA_INCOMPLETE").mul(rejection_counts["count"]).sum()) if len(rejection_counts) else 0:
        decision = "BLOCKED_BY_ADV_DATA"
    elif unexplained:
        decision = "BLOCKED_BY_REBALANCE_EXECUTION"
    elif abs(Decimal(current["cost_recalculation"]["fee_difference"])) > Decimal("0.01"):
        decision = "BLOCKED_BY_METRIC_ACCOUNTING"
    else:
        decision = "BASE_OPERATIONAL_REPLAY_VALID"
    before = prior.get("execution", {}).get("funnel_reason_counts", {})
    comparison = pd.DataFrame([
        {"metric": "semantic_regime_parity", "before": prior.get("regime", {}).get("semantic_parity"), "after": regime["semantic_parity"]},
        {"metric": "orders", "before": prior.get("execution", {}).get("order_count"), "after": current["execution"]["order_count"]},
        {"metric": "fills", "before": prior.get("execution", {}).get("fill_count"), "after": current["execution"]["fill_count"]},
        {"metric": "rejected", "before": before.get("REJECTED"), "after": execution.get("REJECTED")},
        {"metric": "final_nav_krw", "before": prior.get("accounting", {}).get("final_nav"), "after": current["accounting"]["final_nav"]},
        {"metric": "calmar", "before": prior.get("risk", {}).get("strategy_calmar"), "after": current["risk"]["strategy_calmar"]},
    ])
    regime_rows = pd.read_csv(root / "runtime/model_validation_gate/regime_parity.csv")
    replay_summary = json.loads((root / "runtime/historical_operational_replay/replay_summary.json").read_text(encoding="utf-8"))
    average_nav = sum((_dec(x) for x in nav["nav_krw"]), Decimal("0")) / Decimal(len(nav))
    standard_turnover = Decimal(current["cost_recalculation"]["total_fill_notional"]) / average_nav
    legacy_by_date = legacy_v90.rename(columns={"regime_d1": "legacy_v90_regime"})
    regime_rows = regime_rows.merge(legacy_by_date, on="date", how="left")
    legacy_normalization = {"RANGE_RISK": "RISK_OFF", "SHOCK_RISK": "RISK_OFF", "NARROW_BULL": "RISK_ON", "BROAD_BULL": "RISK_ON"}
    regime_rows["legacy_v90_normalized"] = regime_rows["legacy_v90_regime"].map(legacy_normalization)
    regime_rows["legacy_v90_classification"] = regime_rows.apply(
        lambda row: "DIFFERENT_REGIME_VERSION_NOT_COMPARABLE"
        if pd.notna(row["legacy_v90_regime"]) and row["legacy_v90_normalized"] != row["runtime_regime"]
        else "LEGACY_LABEL_ONLY_OR_NO_DIFFERENCE",
        axis=1,
    )
    summary = {
        "mode": MODE,
        "decision": decision,
        "approved_regime_source_of_truth": {
            "active_strategy": "config/active_strategy.yaml",
            "frozen_registry": "reports/v89_forward_governance/frozen_trial_registry.json",
            "policy": "D1_MA120_EXPLICIT",
            "baseline": regime["baseline"],
            "frozen_hashes": _hashes(root),
        },
        "legacy_331_day_result": {"source": "reports/v90_trade_attribution/v90_regime_d1.csv", "classification": "DIFFERENT_REGIME_VERSION_NOT_COMPARABLE", "legacy_enum_counts": legacy_counts},
        "regime": regime,
        "execution_rejections": {str(r["reason"]): int(r["count"]) for _, r in rejection_counts.iterrows()},
        "unexplained_rejections": unexplained,
        "execution": current["execution"],
        "exposure": current["exposure"],
        "performance": {"base": current["base"], "calmar": current["risk"]["strategy_calmar"], "turnover_legacy_initial_capital": replay_summary["metrics"]["turnover"], "turnover_standard_filled_notional_over_average_nav": str(standard_turnover)},
        "costs": current["cost_recalculation"],
        "broker_mutation_calls": 0,
        "operating_database_touched": False,
    }
    regime_rows.to_csv(out / "regime_mismatch.csv", index=False)
    rejection_counts.to_csv(out / "execution_rejection_summary.csv", index=False)
    comparison.to_csv(out / "before_after_comparison.csv", index=False)
    (out / "validation_summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8")
    (out / "validation.log").write_text(json.dumps({"decision": decision, "broker_mutation_calls": 0, "unexplained_rejections": unexplained}, indent=2) + "\n", encoding="utf-8")
    return summary


__all__ = ["MODE", "run_base_operational_replay_validation"]
