"""Fail-closed robustness stage; it contains no execution or broker calls."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from quant_harness.alpha_research_factory import _append_jsonl, _canonical, _hash, _read_jsonl


SCHEMA_VERSION = "ALPHA_RESEARCH_ROBUSTNESS_V1"
PIT_LIMITATION = "ETF_UNIVERSE_PIT_LIMITED_OBSERVED_FIRST_BAR_PROXY"


def _artifact_hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _bucket_metrics(frame: pd.DataFrame, *, label: str, min_dates: int) -> tuple[pd.DataFrame, dict[str, int]]:
    rows: list[dict[str, Any]] = []
    reasons: Counter[str] = Counter()
    for (bucket, horizon), group in frame.groupby([label, "horizon_sessions"], dropna=False):
        daily = group.groupby("date", sort=True).apply(
            lambda x: x["signal"].rank().corr(x["future_return"].rank(), method="pearson"), include_groups=False
        ).dropna()
        if daily.shape[0] < min_dates:
            reasons["INSUFFICIENT_BUCKET_DATES"] += 1
            rows.append({"bucket_type": label, "bucket": str(bucket), "horizon_sessions": int(horizon), "dates": int(daily.shape[0]), "rank_ic": np.nan, "spread": np.nan, "passed_sample": False})
            continue
        spread_daily = group.groupby("date", sort=True).apply(
            lambda x: x.loc[x["signal"].nlargest(3).index, "future_return"].mean() - x.loc[x["signal"].nsmallest(3).index, "future_return"].mean(), include_groups=False
        )
        rows.append({"bucket_type": label, "bucket": str(bucket), "horizon_sessions": int(horizon), "dates": int(daily.shape[0]), "rank_ic": float(daily.mean()), "spread": float(spread_daily.mean()), "passed_sample": True})
    return pd.DataFrame(rows), dict(reasons)


def calculate_robustness(observations: pd.DataFrame, *, cfg: dict[str, Any]) -> dict[str, Any]:
    """Compute pre-specified robustness summaries from deterministic observations.

    Required observation columns are date, ticker, sector, risk_on,
    horizon_sessions, signal and future_return.  Signal is D-1 by contract;
    labels are research-only future outcomes.
    """
    required = {"date", "ticker", "sector", "risk_on", "horizon_sessions", "signal", "future_return"}
    missing = required.difference(observations.columns)
    if missing:
        raise ValueError(f"missing observation columns: {sorted(missing)}")
    data = observations.copy()
    data["date"] = pd.to_datetime(data["date"])
    data["year"] = data["date"].dt.year.astype(str)
    reasons: Counter[str] = Counter()
    invalid = data["signal"].isna() | data["future_return"].isna()
    reasons["MISSING_SIGNAL_OR_LABEL"] += int(invalid.sum())
    data = data.loc[~invalid].copy()
    min_dates = int(cfg["minimum_bucket_dates"])
    regime, regime_reasons = _bucket_metrics(data.assign(regime=np.where(data["risk_on"], "RISK_ON", "RISK_OFF")), label="regime", min_dates=min_dates)
    annual, annual_reasons = _bucket_metrics(data, label="year", min_dates=min_dates)
    sector, sector_reasons = _bucket_metrics(data, label="sector", min_dates=min_dates)
    reasons.update(regime_reasons); reasons.update(annual_reasons); reasons.update(sector_reasons)

    daily = data.groupby(["date", "horizon_sessions"], sort=True).apply(
        lambda x: pd.Series({
            "rank_ic": x["signal"].rank().corr(x["future_return"].rank(), method="pearson"),
            "spread": x.loc[x["signal"].nlargest(3).index, "future_return"].mean() - x.loc[x["signal"].nsmallest(3).index, "future_return"].mean(),
        }), include_groups=False
    ).reset_index()
    rolling_rows: list[dict[str, Any]] = []
    for horizon, part in daily.groupby("horizon_sessions", sort=True):
        series = part.sort_values("date")["rank_ic"]
        rolling = series.rolling(int(cfg["rolling_window_dates"]), min_periods=int(cfg["rolling_window_dates"])).mean().dropna()
        overall = float(series.mean()) if len(series) else np.nan
        if len(rolling) < int(cfg["minimum_rolling_windows"]):
            reasons["INSUFFICIENT_ROLLING_WINDOWS"] += 1
            agreement = np.nan
        else:
            agreement = float((np.sign(rolling) == np.sign(overall)).mean())
        rolling_rows.append({"horizon_sessions": int(horizon), "rolling_windows": int(len(rolling)), "overall_rank_ic": overall, "overall_spread": float(part["spread"].mean()) if len(part) else np.nan, "direction_agreement": agreement})
    rolling = pd.DataFrame(rolling_rows)

    # ETF contribution is the mean of cross-sectionally ranked signal times
    # the future return.  It is a diagnostic concentration measure, not alpha.
    data["signal_pct_rank"] = data.groupby(["date", "horizon_sessions"])["signal"].rank(pct=True)
    data["directional_contribution"] = data["signal_pct_rank"] * data["future_return"]
    etf = data.groupby(["ticker", "horizon_sessions"], sort=True).agg(dates=("date", "nunique"), directional_contribution=("directional_contribution", "mean")).reset_index()
    total_abs = etf.groupby("horizon_sessions")["directional_contribution"].transform(lambda x: x.abs().sum())
    etf["absolute_contribution_share"] = etf["directional_contribution"].abs().div(total_abs.where(total_abs.gt(0)))
    top_remove_rows: list[dict[str, Any]] = []
    for horizon, part in data.groupby("horizon_sessions", sort=True):
        base = float(daily.loc[daily["horizon_sessions"].eq(horizon), "rank_ic"].mean())
        for ticker in sorted(part["ticker"].unique()):
            reduced = part[part["ticker"].ne(ticker)]
            values = reduced.groupby("date").apply(lambda x: x["signal"].rank().corr(x["future_return"].rank(), method="pearson"), include_groups=False).dropna()
            top_remove_rows.append({"horizon_sessions": int(horizon), "removed_ticker": ticker, "rank_ic_without_ticker": float(values.mean()) if len(values) else np.nan, "delta_vs_all": float(values.mean() - base) if len(values) else np.nan})
    sensitivity = pd.DataFrame(top_remove_rows)
    return {"regime": regime, "annual": annual, "sector": sector, "rolling": rolling, "etf": etf, "top_etf_removal": sensitivity, "nan_reasons": dict(reasons), "source_data_end": str(data["date"].max().date()) if len(data) else None}


def evaluate_robustness(result: dict[str, Any], *, cfg: dict[str, Any]) -> str:
    buckets = pd.concat([result["regime"], result["annual"], result["sector"]], ignore_index=True)
    if buckets.empty or not buckets["passed_sample"].all():
        return "REJECTED_ROBUSTNESS"
    concentration = pd.concat([
        result["annual"].assign(weight=lambda x: x["spread"].abs()),
        result["sector"].assign(weight=lambda x: x["spread"].abs()),
    ], ignore_index=True)
    weights = concentration.groupby(["bucket_type", "horizon_sessions"])["weight"].transform("sum")
    # A bucket set with exactly zero spread has no signed performance to
    # concentrate.  Treat it as neutral rather than fabricating a 100% share.
    shares = concentration["weight"].div(weights.where(weights.gt(0))).fillna(0.0)
    concentration_ok = bool(shares.le(float(cfg["maximum_single_bucket_concentration"])).all())
    rolling = result["rolling"]
    rolling_ok = bool(rolling["direction_agreement"].notna().all() and rolling["direction_agreement"].ge(float(cfg["minimum_rolling_direction_agreement"])).all())
    directional_ok = (
        int(rolling["overall_rank_ic"].gt(0).sum()) >= int(cfg.get("minimum_horizons_with_positive_rank_ic", 1))
        and int(rolling["overall_spread"].gt(0).sum()) >= int(cfg.get("minimum_horizons_with_positive_spread", 1))
    )
    return "READY_FOR_EXECUTION_FEASIBILITY" if concentration_ok and rolling_ok and directional_ok else "REJECTED_ROBUSTNESS"


def _load_ready_diagnostic(path: Path) -> tuple[dict[str, Any], str]:
    if not path.exists():
        raise RuntimeError("BLOCKED_DIAGNOSTIC_NOT_RUN")
    payload = json.loads(path.read_text(encoding="utf-8"))
    expected = payload.get("diagnostic_artifact_hash")
    raw = dict(payload); raw.pop("diagnostic_artifact_hash", None)
    actual = _hash(raw)
    if expected and expected != actual:
        raise RuntimeError("BLOCKED_DIAGNOSTIC_HASH_MISMATCH")
    if payload.get("report", {}).get("attempt_status") != "READY_FOR_ROBUSTNESS":
        raise RuntimeError("BLOCKED_STAGE_DIAGNOSTIC_NOT_READY")
    return payload, actual


def _diagnostic_metadata(path: Path) -> dict[str, Any]:
    """Copy immutable diagnostic provenance into even a blocked receipt."""
    if not path.exists():
        return {
            "contract_hash": None, "data_hash": None, "diagnostic_artifact_hash": None,
            "calculation_version": None, "source_data_end": None, "last_labelable_date_by_horizon": {},
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    report = payload.get("report", {})
    labels: dict[str, str] = {}
    for row in payload.get("metrics", []):
        horizon = str(row.get("horizon_sessions"))
        date = str(row.get("date"))
        if horizon not in labels or date > labels[horizon]:
            labels[horizon] = date
    return {
        "contract_hash": report.get("contract_hash") or payload.get("contract_hash"),
        "data_hash": report.get("data_hash") or payload.get("data_hash"),
        "diagnostic_artifact_hash": _artifact_hash(path),
        "calculation_version": report.get("calculation_version"),
        "source_data_end": report.get("data_cutoff"),
        "last_labelable_date_by_horizon": labels,
    }


def run(root: Path | str, *, output_dir: Path | str | None = None) -> dict[str, Any]:
    """Record a fail-closed receipt for the real attempt; no robustness maths runs.

    The only approved current attempt is REJECTED_DIAGNOSTIC. Synthetic fixture
    tests call calculate_robustness/evaluate_robustness directly.
    """
    root = Path(root)
    out = Path(output_dir) if output_dir else root / "runtime/alpha_research_factory"
    cfg = yaml.safe_load((root / "config/alpha_research_factory_robustness.yaml").read_text(encoding="utf-8"))
    path = out / "diagnostics" / "REVERSAL_5D_metrics.json"
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    try:
        diagnostic, diagnostic_hash = _load_ready_diagnostic(path)
    except RuntimeError as exc:
        status = str(exc)
        report = {
            "status": "ALPHA_FACTORY_ROBUSTNESS_STAGE_VALID", "attempt_status": status,
            "receipt_schema_version": "ALPHA_RESEARCH_ROBUSTNESS_RECEIPT_V2",
            **_diagnostic_metadata(path), "pit_limitation": PIT_LIMITATION,
            "operational_replay_budget": {"used": 0, "limit": int(cfg["operational_replay_budget"])},
            "v101_called": False, "operational_replay_called": False, "broker_mutation_calls": 0,
        }
        registry, events = out / "robustness_registry.jsonl", out / "state_events.jsonl"
        key = _hash({"proposal_id": "REVERSAL_5D", "status": status, "stage": "ROBUSTNESS", "receipt_schema_version": report["receipt_schema_version"]})
        if not any(row.get("event_key") == key for row in _read_jsonl(registry)):
            _append_jsonl(registry, [{"event_key": key, "timestamp_utc": now, "proposal_id": "REVERSAL_5D", **report, "pit_limitation": PIT_LIMITATION}])
            _append_jsonl(events, [{"timestamp_utc": now, "attempt_id": "REVERSAL_5D", "from": "REJECTED_DIAGNOSTIC", "to": status, "reason": "ROBUSTNESS_ENTRY_GUARD"}])
        return report
    raise RuntimeError(f"BLOCKED_SYNTHETIC_ONLY_NO_REAL_READY_ATTEMPT diagnostic={diagnostic_hash}")
