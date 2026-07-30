from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Iterable

import numpy as np
import pandas as pd

ACTIVE_SELECTION_POLICY = "TOP_SCORE_SECTOR_DEDUP"
CROSS_HORIZON_CONSENSUS = "CROSS_HORIZON_CONSENSUS"
UNCERTAINTY_AWARE_ROTATION = "UNCERTAINTY_AWARE_ROTATION"
TREND_QUALITY_SCORE = "TREND_QUALITY_SCORE"
SECTOR_RESIDUAL_MOMENTUM = "SECTOR_RESIDUAL_MOMENTUM"
EXPECTED_VALUE_ROTATION = "EXPECTED_VALUE_ROTATION"

ABLATION_POLICIES = (
    "ABLATE_V69_SHORT_COMPONENT",
    "ABLATE_V69_MEDIUM_COMPONENT",
    "ABLATE_V69_LONG_FILTER",
    "ABLATE_V69_TREND_FILTER",
    "ABLATE_V79_63_COMPONENT",
    "ABLATE_V79_126_COMPONENT",
    "ABLATE_V79_252_COMPONENT",
    "ABLATE_V79_TREND_FILTER",
)

SUPPORTED_SELECTION_POLICIES = (
    ACTIVE_SELECTION_POLICY,
    CROSS_HORIZON_CONSENSUS,
    UNCERTAINTY_AWARE_ROTATION,
    TREND_QUALITY_SCORE,
    SECTOR_RESIDUAL_MOMENTUM,
    EXPECTED_VALUE_ROTATION,
    *ABLATION_POLICIES,
)

# Sector de-duplication is no longer a standalone agent. It is a deterministic
# sub-policy of CandidateSelectionAgent.
SECTOR_REPRESENTATION_POLICY = "STATIC_TOP_SCORE_EXPLICIT"


@dataclass
class _SectorState:
    current: str | None = None
    pending: str | None = None
    pending_count: int = 0


def taxonomy_hash(universe: pd.DataFrame) -> str:
    required = ["ticker", "sector"]
    frame = universe[required].copy()
    frame["ticker"] = frame["ticker"].astype(str)
    frame["sector"] = frame["sector"].astype(str)
    payload = frame.sort_values(required).to_csv(index=False).encode("utf-8")
    return sha256(payload).hexdigest()


def validate_taxonomy(universe: pd.DataFrame) -> dict[str, Any]:
    missing_columns = sorted({"ticker", "sector"}.difference(universe.columns))
    if missing_columns:
        raise ValueError(f"sector taxonomy missing columns: {missing_columns}")
    blank_sector = universe["sector"].isna() | universe["sector"].astype(str).str.strip().eq("")
    duplicate_ticker = universe["ticker"].astype(str).duplicated(keep=False)
    return {
        "taxonomy_hash": taxonomy_hash(universe),
        "ticker_count": int(len(universe)),
        "sector_count": int(universe["sector"].nunique(dropna=True)),
        "blank_sector_count": int(blank_sector.sum()),
        "duplicate_ticker_count": int(duplicate_ticker.sum()),
        "valid": bool(not blank_sector.any() and not duplicate_ticker.any()),
    }


def _safe_liquidity(liquidity: pd.Series, ticker: str) -> float:
    value = liquidity.get(ticker, np.nan)
    return float(value) if pd.notna(value) else 0.0


def _weighted_rank(frames: list[pd.DataFrame], weights: list[float]) -> pd.DataFrame:
    if len(frames) != len(weights) or not frames:
        raise ValueError("frames and weights must be non-empty and aligned")
    total = float(sum(weights))
    if total <= 0:
        raise ValueError("weights must sum to a positive number")
    normalized = [float(w) / total for w in weights]
    ranks = [frame.rank(axis=1, pct=True, method="average") for frame in frames]
    out = sum(weight * rank for weight, rank in zip(normalized, ranks))
    valid = sum(frame.notna().astype(int) for frame in frames).eq(len(frames))
    return out.where(valid)


def prepare_selection_features(
    features: dict[str, Any],
    *,
    family: str,
    policy: str = ACTIVE_SELECTION_POLICY,
    consensus_min_rank: float = 0.60,
    consensus_required_horizons: int = 2,
    dispersion_penalty: float = 0.20,
) -> dict[str, Any]:
    """Return the score and eligibility consumed by the selector.

    Source features are D-1 lagged by the parent strategy. Research policies
    change one component only: score, eligibility, or rotation gate.
    """
    if policy not in SUPPORTED_SELECTION_POLICIES:
        raise ValueError(f"unsupported candidate selection policy: {policy}")

    score = features["score"]
    eligible = features["eligible"]
    count = pd.DataFrame(np.nan, index=score.index, columns=score.columns)
    dispersion_frame = pd.DataFrame(np.nan, index=score.index, columns=score.columns)

    if policy == CROSS_HORIZON_CONSENSUS:
        if not 0.0 <= consensus_min_rank <= 1.0:
            raise ValueError("consensus_min_rank must be between 0 and 1")
        if consensus_required_horizons < 1 or consensus_required_horizons > 3:
            raise ValueError("consensus_required_horizons must be in [1,3]")
        if dispersion_penalty < 0:
            raise ValueError("dispersion_penalty must be non-negative")
        if family == "V69":
            horizon_frames = [features["rel_short"], features["rel_medium"], features["rel_long"]]
            weights = np.array([0.25, 0.50, 0.25], dtype=float)
        elif family == "V79":
            horizon_frames = [
                features["absolute_return_short"],
                features["absolute_return_medium"],
                features["absolute_return_long"],
            ]
            weights = np.array([0.25, 0.35, 0.40], dtype=float)
        else:
            raise ValueError(f"unsupported family: {family}")
        ranks = [frame.rank(axis=1, pct=True, method="average") for frame in horizon_frames]
        stacked = np.stack([frame.to_numpy(dtype=float) for frame in ranks], axis=2)
        weighted = np.nansum(stacked * weights.reshape(1, 1, -1), axis=2)
        valid_count = np.sum(np.isfinite(stacked), axis=2)
        weighted[valid_count < 3] = np.nan
        safe_count = np.maximum(valid_count, 1)
        mean = np.nansum(stacked, axis=2) / safe_count
        squared = np.nansum((stacked - mean[:, :, None]) ** 2, axis=2) / safe_count
        dispersion = np.sqrt(squared)
        dispersion[valid_count < 3] = np.nan
        consensus_count = np.sum(stacked >= consensus_min_rank, axis=2)
        score = pd.DataFrame(
            weighted - dispersion_penalty * dispersion,
            index=features["score"].index,
            columns=features["score"].columns,
        )
        count = pd.DataFrame(consensus_count, index=score.index, columns=score.columns)
        dispersion_frame = pd.DataFrame(dispersion, index=score.index, columns=score.columns)
        eligible = features["eligible"].astype(bool) & count.ge(consensus_required_horizons) & score.notna()

    elif policy == TREND_QUALITY_SCORE:
        score = features["trend_quality_score"]

    elif policy == SECTOR_RESIDUAL_MOMENTUM:
        score = features["sector_residual_score"]

    elif policy == "ABLATE_V69_SHORT_COMPONENT" and family == "V69":
        score = features["rel_medium"]
    elif policy == "ABLATE_V69_MEDIUM_COMPONENT" and family == "V69":
        score = features["rel_short"]
    elif policy == "ABLATE_V69_LONG_FILTER" and family == "V69":
        eligible = features["eligible_without_long_filter"]
    elif policy == "ABLATE_V69_TREND_FILTER" and family == "V69":
        eligible = features["eligible_without_trend_filter"]
    elif policy == "ABLATE_V79_63_COMPONENT" and family == "V79":
        score = _weighted_rank(
            [features["absolute_return_medium"], features["absolute_return_long"]], [0.35, 0.40]
        )
    elif policy == "ABLATE_V79_126_COMPONENT" and family == "V79":
        score = _weighted_rank(
            [features["absolute_return_short"], features["absolute_return_long"]], [0.25, 0.40]
        )
    elif policy == "ABLATE_V79_252_COMPONENT" and family == "V79":
        score = _weighted_rank(
            [features["absolute_return_short"], features["absolute_return_medium"]], [0.25, 0.35]
        )
    elif policy == "ABLATE_V79_TREND_FILTER" and family == "V79":
        eligible = features["eligible_without_trend_filter"]

    return {
        **features,
        "selection_score": score,
        "selection_eligible": eligible.fillna(False).astype(bool),
        "horizon_consensus_count": count,
        "horizon_dispersion": dispersion_frame,
    }


def build_sector_representative_panel(
    index: pd.DatetimeIndex,
    review_dates: Iterable[pd.Timestamp],
    universe: pd.DataFrame,
    score: pd.DataFrame,
    eligible: pd.DataFrame,
    liquidity: pd.DataFrame,
) -> pd.DataFrame:
    """Select one D-1 top-score representative per semantic sector."""
    audit = validate_taxonomy(universe)
    if not audit["valid"]:
        raise ValueError(f"invalid sector taxonomy: {audit}")
    review_set = set(pd.DatetimeIndex(review_dates))
    sector_groups = {
        str(sector): group["ticker"].astype(str).tolist()
        for sector, group in universe.groupby("sector", sort=True)
    }
    states = {sector: _SectorState() for sector in sector_groups}
    rows: list[dict[str, Any]] = []
    for pos, date in enumerate(index):
        if date not in review_set:
            continue
        day_score = score.loc[date]
        day_eligible = eligible.loc[date]
        day_liquidity = liquidity.loc[date]
        for sector, tickers in sector_groups.items():
            candidates = [
                ticker for ticker in tickers
                if bool(day_eligible.get(ticker, False)) and pd.notna(day_score.get(ticker, np.nan))
            ]
            state = states[sector]
            previous = state.current
            if not candidates:
                state.current = None
                rows.append({
                    "date": date,
                    "information_cutoff": index[pos - 1] if pos > 0 else pd.NaT,
                    "decision_uses_same_day_close": False,
                    "policy": SECTOR_REPRESENTATION_POLICY,
                    "sector": sector,
                    "representative_ticker": None,
                    "representative_score_d1": np.nan,
                    "representative_liquidity_d1": np.nan,
                    "raw_best_ticker": None,
                    "raw_best_score_d1": np.nan,
                    "score_gap_to_raw_best": np.nan,
                    "representative_changed": False,
                    "decision_reason": "NO_ELIGIBLE_SECTOR_MEMBER",
                    "eligible_member_count": 0,
                })
                continue
            chosen = max(candidates, key=lambda t: (float(day_score[t]), _safe_liquidity(day_liquidity, t)))
            chosen_score = float(day_score[chosen])
            state.current = chosen
            rows.append({
                "date": date,
                "information_cutoff": index[pos - 1] if pos > 0 else pd.NaT,
                "decision_uses_same_day_close": False,
                "policy": SECTOR_REPRESENTATION_POLICY,
                "sector": sector,
                "representative_ticker": chosen,
                "representative_score_d1": chosen_score,
                "representative_liquidity_d1": _safe_liquidity(day_liquidity, chosen),
                "raw_best_ticker": chosen,
                "raw_best_score_d1": chosen_score,
                "score_gap_to_raw_best": 0.0,
                "representative_changed": bool(previous is not None and previous != chosen),
                "decision_reason": "TOP_SCORE_SECTOR_REPRESENTATIVE",
                "eligible_member_count": len(candidates),
            })
    return pd.DataFrame(rows)


def ranked_representatives(panel: pd.DataFrame, date: pd.Timestamp) -> list[tuple[str, str, float, float]]:
    day = panel[panel["date"].eq(date) & panel["representative_ticker"].notna()]
    rows = [
        (
            str(row.representative_ticker),
            str(row.sector),
            float(row.representative_score_d1),
            float(row.representative_liquidity_d1),
        )
        for row in day.itertuples(index=False)
    ]
    rows.sort(key=lambda item: (item[2], item[3]), reverse=True)
    return rows


def score_distribution_diagnostics(ranked: list[tuple[str, str, float, float]]) -> dict[str, Any]:
    scores = np.array([row[2] for row in ranked], dtype=float)
    if len(scores) == 0:
        return {
            "top_ticker": None,
            "runner_up_ticker": None,
            "top_score": np.nan,
            "runner_up_score": np.nan,
            "top_gap": np.nan,
            "score_iqr": np.nan,
        }
    top = float(scores[0])
    runner = float(scores[1]) if len(scores) > 1 else np.nan
    return {
        "top_ticker": ranked[0][0],
        "runner_up_ticker": ranked[1][0] if len(ranked) > 1 else None,
        "top_score": top,
        "runner_up_score": runner,
        "top_gap": float(top - runner) if np.isfinite(runner) else np.nan,
        "score_iqr": float(np.nanpercentile(scores, 75) - np.nanpercentile(scores, 25)) if len(scores) >= 2 else 0.0,
    }


def effective_rotation_margin(
    ranked: list[tuple[str, str, float, float]],
    *,
    base_margin: float,
    policy: str,
    iqr_multiplier: float = 0.25,
) -> float:
    if policy not in SUPPORTED_SELECTION_POLICIES:
        raise ValueError(f"unsupported candidate selection policy: {policy}")
    if policy != UNCERTAINTY_AWARE_ROTATION:
        return float(base_margin)
    if iqr_multiplier < 0:
        raise ValueError("iqr_multiplier must be non-negative")
    diag = score_distribution_diagnostics(ranked)
    iqr = diag["score_iqr"]
    adaptive = 0.0 if not np.isfinite(iqr) else iqr_multiplier * iqr
    return float(max(base_margin, adaptive))


def expected_value_rotation_gate(
    date: pd.Timestamp,
    ranked: list[tuple[str, str, float, float]],
    current: str | None,
    *,
    policy: str,
    schedule: dict[str, dict[str, float]] | None = None,
    minimum_samples: int = 30,
    cost_buffer_return: float = 0.008,
) -> tuple[bool, float, int, str]:
    """Return a strictly walk-forward rotation decision.

    The schedule is built outside the selector using only 60-session-matured
    historical pair outcomes. Until enough samples exist, parent behaviour is
    preserved rather than inventing an early-period rule.
    """
    if policy != EXPECTED_VALUE_ROTATION:
        return True, np.nan, 0, "NOT_APPLICABLE"
    if current is None or not ranked or ranked[0][0] == current:
        return True, np.nan, 0, "NO_ROTATION_OPPORTUNITY"
    row = (schedule or {}).get(pd.Timestamp(date).date().isoformat())
    if not row:
        return True, np.nan, 0, "INSUFFICIENT_WALK_FORWARD_HISTORY_PARENT_FALLBACK"
    sample_count = int(row.get("sample_count", 0))
    if sample_count < int(minimum_samples):
        return True, np.nan, sample_count, "INSUFFICIENT_WALK_FORWARD_HISTORY_PARENT_FALLBACK"
    score_by_ticker = {ticker: score for ticker, _sector, score, _liq in ranked}
    if current not in score_by_ticker:
        return True, np.nan, sample_count, "CURRENT_NOT_RANKED_PARENT_FALLBACK"
    gap = float(score_by_ticker[ranked[0][0]] - score_by_ticker[current])
    scores = np.asarray([item[2] for item in ranked], dtype=float)
    iqr = float(np.nanpercentile(scores, 75) - np.nanpercentile(scores, 25)) if len(scores) >= 2 else 0.0
    normalized_gap = gap / max(iqr, 1e-6)
    predicted = (
        float(row.get("intercept", 0.0))
        + float(row.get("coef_gap", 0.0)) * gap
        + float(row.get("coef_normalized_gap", 0.0)) * normalized_gap
    )
    allowed = bool(predicted > float(cost_buffer_return))
    reason = "EXPECTED_VALUE_POSITIVE" if allowed else "EXPECTED_VALUE_BELOW_COST"
    return allowed, float(predicted), sample_count, reason
