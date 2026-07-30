from __future__ import annotations

from hashlib import sha256
from typing import Any
import json

import numpy as np
import pandas as pd

ACTIVE_STRATEGY_POLICY = "FIXED_PARENT_ALLOCATIONS"
FULL_LEADER_100 = "FULL_LEADER_100"
UNCERTAINTY_BUDGET_60_80 = "UNCERTAINTY_BUDGET_60_80"
V79_SEMANTIC_SECTOR_CAP_70 = "V79_SEMANTIC_SECTOR_CAP_70"
CANDIDATE_POLICIES = (FULL_LEADER_100, UNCERTAINTY_BUDGET_60_80, V79_SEMANTIC_SECTOR_CAP_70)
ALL_POLICIES = (ACTIVE_STRATEGY_POLICY, *CANDIDATE_POLICIES)


def _target_hash(weights: dict[str, float]) -> str:
    payload = json.dumps({str(k): round(float(v), 12) for k, v in sorted(weights.items())}, separators=(",", ":"), sort_keys=True)
    return sha256(payload.encode("utf-8")).hexdigest()


def _confidence(row: pd.Series, *, full_confidence_normalized_gap: float) -> tuple[float, float]:
    gap = pd.to_numeric(pd.Series([row.get("top_runner_gap_d1")]), errors="coerce").iloc[0]
    iqr = pd.to_numeric(pd.Series([row.get("candidate_score_iqr_d1")]), errors="coerce").iloc[0]
    if not np.isfinite(gap) or not np.isfinite(iqr) or float(iqr) <= 1e-12:
        return 0.0, np.nan
    normalized = float(gap) / max(float(iqr), 1e-12)
    confidence = float(np.clip(normalized / max(float(full_confidence_normalized_gap), 1e-12), 0.0, 1.0))
    return confidence, normalized


def _normalise(weights: dict[str, float], core_ticker: str) -> dict[str, float]:
    clean = {str(k): max(0.0, float(v)) for k, v in weights.items() if float(v) > 1e-12}
    total = float(sum(clean.values()))
    if total <= 0:
        return {str(core_ticker): 1.0}
    if not np.isclose(total, 1.0, atol=1e-12):
        clean[str(core_ticker)] = clean.get(str(core_ticker), 0.0) + (1.0 - total)
    return {k: float(v) for k, v in clean.items() if v > 1e-12}


def build_v69_target_ledger(selection: pd.DataFrame, *, core_ticker: str, policy: str, params: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, row in selection.iterrows():
        leader = str(row["leader_ticker"]) if pd.notna(row.get("leader_ticker")) else None
        confidence, normalized_gap = _confidence(row, full_confidence_normalized_gap=float(params.get("full_confidence_normalized_gap", 1.0)))
        if not leader:
            leader_weight = 0.0
            reason = "NO_LEADER_CORE_FALLBACK"
        elif policy == FULL_LEADER_100:
            leader_weight = 1.0
            reason = "FULL_LEADER_100"
        elif policy == UNCERTAINTY_BUDGET_60_80:
            low = float(params.get("minimum_base_leader_weight", 0.60))
            high = float(params.get("maximum_base_leader_weight", 0.80))
            leader_weight = low + (high - low) * confidence
            reason = "UNCERTAINTY_BUDGET"
        else:
            leader_weight = 0.80
            reason = "FIXED_PARENT_80_20"
        weights = _normalise({core_ticker: 1.0 - leader_weight, **({leader: leader_weight} if leader else {})}, core_ticker)
        rows.append({
            "date": pd.Timestamp(row["date"]),
            "information_cutoff": row.get("information_cutoff"),
            "decision_uses_same_day_close": False,
            "strategy_policy": policy,
            "leader_ticker": leader,
            "leader_confidence_d1": confidence,
            "leader_normalized_gap_d1": normalized_gap,
            "target_leader_weight": leader_weight,
            "target_core_weight": weights.get(core_ticker, 0.0),
            "target_weights_json": json.dumps(weights, sort_keys=True),
            "target_weight_sum": sum(weights.values()),
            "max_noncore_ticker_weight": max((v for k, v in weights.items() if k != core_ticker), default=0.0),
            "max_semantic_sector_weight": max((v for k, v in weights.items() if k != core_ticker), default=0.0),
            "same_ticker_overlap": False,
            "same_sector_overlap": False,
            "concentration_cap_applied": False,
            "allocation_reason": reason,
            "target_hash": _target_hash(weights),
        })
    return pd.DataFrame(rows)


def build_v79_target_ledger(
    base_selection: pd.DataFrame,
    sleeve_selection: pd.DataFrame,
    *, core_ticker: str, base_share: float, policy: str, params: dict[str, Any], sector_by_ticker: dict[str, str],
) -> pd.DataFrame:
    base = base_selection.set_index("date")
    sleeve = sleeve_selection.set_index("date")
    sleeve_share = 1.0 - float(base_share)
    rows: list[dict[str, Any]] = []
    for date in base.index:
        brow = base.loc[date]
        srow = sleeve.loc[date]
        base_leader = str(brow["leader_ticker"]) if pd.notna(brow.get("leader_ticker")) else None
        sleeve_ticker = str(srow["sleeve_ticker"]) if pd.notna(srow.get("sleeve_ticker")) else None
        base_conf, base_norm = _confidence(brow, full_confidence_normalized_gap=float(params.get("full_confidence_normalized_gap", 1.0)))
        sleeve_conf, sleeve_norm = _confidence(srow, full_confidence_normalized_gap=float(params.get("full_confidence_normalized_gap", 1.0)))
        if policy == FULL_LEADER_100:
            base_leader_weight = 1.0 if base_leader else 0.0
            deployed_sleeve_share = sleeve_share if sleeve_ticker else 0.0
            reason = "FULL_BASE_LEADER_100"
        elif policy == UNCERTAINTY_BUDGET_60_80:
            low = float(params.get("minimum_base_leader_weight", 0.60))
            high = float(params.get("maximum_base_leader_weight", 0.80))
            base_leader_weight = (low + (high - low) * base_conf) if base_leader else 0.0
            min_fraction = float(params.get("minimum_sleeve_deployment_fraction", 0.50))
            deployed_sleeve_share = sleeve_share * (min_fraction + (1.0 - min_fraction) * sleeve_conf) if sleeve_ticker else 0.0
            reason = "UNCERTAINTY_BUDGET"
        else:
            base_leader_weight = 0.80 if base_leader else 0.0
            deployed_sleeve_share = sleeve_share if sleeve_ticker else 0.0
            reason = "FIXED_PARENT_70_30"
        weights: dict[str, float] = {core_ticker: base_share * (1.0 - base_leader_weight)}
        if base_leader:
            weights[base_leader] = weights.get(base_leader, 0.0) + base_share * base_leader_weight
        else:
            weights[core_ticker] += base_share * base_leader_weight
        if sleeve_ticker:
            weights[sleeve_ticker] = weights.get(sleeve_ticker, 0.0) + deployed_sleeve_share
        weights[core_ticker] += sleeve_share - deployed_sleeve_share
        same_ticker = bool(base_leader and sleeve_ticker and base_leader == sleeve_ticker)
        same_sector = bool(base_leader and sleeve_ticker and sector_by_ticker.get(base_leader) == sector_by_ticker.get(sleeve_ticker))
        cap_applied = False
        if policy == V79_SEMANTIC_SECTOR_CAP_70:
            cap = float(params.get("maximum_v79_semantic_sector_weight", 0.70))
            sectors: dict[str, list[str]] = {}
            for ticker in list(weights):
                if ticker == core_ticker:
                    continue
                sectors.setdefault(sector_by_ticker.get(ticker, "UNKNOWN"), []).append(ticker)
            for members in sectors.values():
                sector_total = sum(weights.get(t, 0.0) for t in members)
                if sector_total > cap + 1e-12:
                    scale = cap / sector_total
                    excess = sector_total - cap
                    for ticker in members:
                        weights[ticker] *= scale
                    weights[core_ticker] = weights.get(core_ticker, 0.0) + excess
                    cap_applied = True
            reason = "SEMANTIC_SECTOR_CAP_70" if cap_applied else "PARENT_NO_CAP_NEEDED"
        weights = _normalise(weights, core_ticker)
        by_sector: dict[str, float] = {}
        for ticker, weight in weights.items():
            if ticker != core_ticker:
                sector = sector_by_ticker.get(ticker, "UNKNOWN")
                by_sector[sector] = by_sector.get(sector, 0.0) + weight
        info_values = [brow.get("information_cutoff"), srow.get("information_cutoff")]
        info_values = [pd.Timestamp(v) for v in info_values if pd.notna(v)]
        rows.append({
            "date": pd.Timestamp(date),
            "information_cutoff": min(info_values) if info_values else pd.NaT,
            "decision_uses_same_day_close": False,
            "strategy_policy": policy,
            "base_share": float(base_share),
            "trend_sleeve_share": sleeve_share,
            "base_leader_ticker": base_leader,
            "trend_sleeve_ticker": sleeve_ticker,
            "base_leader_confidence_d1": base_conf,
            "base_leader_normalized_gap_d1": base_norm,
            "sleeve_confidence_d1": sleeve_conf,
            "sleeve_normalized_gap_d1": sleeve_norm,
            "base_leader_component_weight": base_share * base_leader_weight,
            "deployed_sleeve_weight": deployed_sleeve_share,
            "target_core_weight": weights.get(core_ticker, 0.0),
            "target_weights_json": json.dumps(weights, sort_keys=True),
            "target_weight_sum": sum(weights.values()),
            "max_noncore_ticker_weight": max((v for k, v in weights.items() if k != core_ticker), default=0.0),
            "max_semantic_sector_weight": max(by_sector.values(), default=0.0),
            "same_ticker_overlap": same_ticker,
            "same_sector_overlap": same_sector,
            "concentration_cap_applied": cap_applied,
            "allocation_reason": reason,
            "target_hash": _target_hash(weights),
        })
    return pd.DataFrame(rows)
