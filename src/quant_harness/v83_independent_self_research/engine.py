from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import inspect
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from quant_harness.v69_dynamic_theme_leadership import engine as v69
from quant_harness.v77_corrected_price_allocation import engine as v77
from quant_harness.v77_2_validation_integrity.engine import (
    _annual_returns,
    _monthly_returns_2026,
    _return_table,
    _slice_metrics,
)
from quant_harness.v78_preregistered_alpha_research.engine import build_baseline_features
from quant_harness.v79_generic_trend_sleeve import engine as v79
from quant_harness.v80_multi_indicator_confirmation import engine as v80

REPORT = "v83_independent_self_research"
CONTROL = "V69_FIXED80_DAILY_CORRECTED"
CHALLENGER = "V79_GENERIC_TREND_BASE70_SLEEVE30"


def _load_config(root: Path) -> dict[str, Any]:
    return yaml.safe_load((root / "config/v83_independent_self_research.yaml").read_text(encoding="utf-8"))


def _file_hash(path: Path) -> str:
    h = sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _weights_from_v69_selection(selection: pd.DataFrame, core: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in selection.itertuples(index=False):
        leader = str(row.leader_ticker) if pd.notna(row.leader_ticker) else None
        weight = float(row.target_leader_weight) if leader else 0.0
        weights = {core: 1.0 - weight}
        if leader:
            weights[leader] = weights.get(leader, 0.0) + weight
        rows.append({
            "date": pd.Timestamp(row.date),
            "information_cutoff": pd.Timestamp(row.information_cutoff) if pd.notna(row.information_cutoff) else pd.NaT,
            "decision_uses_same_day_close": False,
            "active_ticker": leader,
            "active_score_d1": float(row.leader_score_d1) if pd.notna(row.leader_score_d1) else np.nan,
            "decision_reason": str(row.decision_reason),
            "target_weights_json": json.dumps(weights, sort_keys=True),
            "target_weight_sum": float(sum(weights.values())),
        })
    return pd.DataFrame(rows)


def _v69_features_fast(close: pd.DataFrame, value: pd.DataFrame, universe: pd.DataFrame, cfg: v69.V69Config) -> dict[str, Any]:
    features = build_baseline_features(close, value, universe, cfg)
    features = dict(features)
    features["score"] = 0.70 * features["rel_short"] + 0.30 * features["rel_medium"]
    return features


def _v69_features_vol_adjusted(close: pd.DataFrame, value: pd.DataFrame, universe: pd.DataFrame, cfg: v69.V69Config) -> dict[str, Any]:
    features = build_baseline_features(close, value, universe, cfg)
    tickers = universe["ticker"].astype(str).tolist()
    vol = close[tickers].pct_change(fill_method=None).rolling(63, min_periods=40).std().shift(1) * math.sqrt(252)
    raw = (0.5 * features["rel_short"] + 0.5 * features["rel_medium"]) / vol.replace(0.0, np.nan)
    features = dict(features)
    features["score"] = raw.rank(axis=1, pct=True, method="average")
    return features


def _select_v69_exit_confirm(
    index: pd.DatetimeIndex,
    universe: pd.DataFrame,
    features: dict[str, Any],
    cfg: v69.V69Config,
    exit_confirmations: int = 2,
) -> pd.DataFrame:
    monthly, weekly = v69._review_dates(index)
    sector_by_ticker = universe.set_index("ticker")["sector"].to_dict()
    name_by_ticker = universe.set_index("ticker")["name"].to_dict()
    current: str | None = None
    pending: str | None = None
    pending_count = 0
    exit_count = 0
    rows: list[dict[str, Any]] = []
    for pos, date in enumerate(index):
        reason = "INTRA_REVIEW_HOLD"
        score = features["score"].loc[date]
        eligible = features["eligible"].loc[date]
        market_on = bool(features["benchmark_trend"].loc[date])
        if date in weekly and current is not None:
            current_ok = bool(eligible.get(current, False)) and pd.notna(score.get(current, np.nan))
            current_score = float(score[current]) if current_ok else -np.inf
            bad = (not current_ok) or current_score < cfg.weekly_exit_if_score_below
            exit_count = exit_count + 1 if bad else 0
            if exit_count >= exit_confirmations:
                current, pending, pending_count, exit_count = None, None, 0, 0
                reason = "CONFIRMED_WEEKLY_LEADER_DECAY_EXIT"
            elif bad:
                reason = "WEEKLY_EXIT_PENDING_CONFIRMATION"
        ranked: list[tuple[str, str, float, float]] = []
        if date in monthly:
            if not market_on:
                current, pending, pending_count, exit_count = None, None, 0, 0
                reason = "MARKET_TREND_OFF"
            else:
                for sector, group in universe.groupby("sector"):
                    candidates = [str(t) for t in group["ticker"] if bool(eligible.get(str(t), False)) and pd.notna(score.get(str(t), np.nan))]
                    if not candidates:
                        continue
                    best = max(candidates, key=lambda t: (float(score[t]), float(features["liquidity"].loc[date, t]) if pd.notna(features["liquidity"].loc[date, t]) else 0.0))
                    ranked.append((best, str(sector), float(score[best]), float(features["liquidity"].loc[date, best]) if pd.notna(features["liquidity"].loc[date, best]) else 0.0))
                ranked.sort(key=lambda x: (x[2], x[3]), reverse=True)
                challenger = ranked[0][0] if ranked else None
                if challenger is None:
                    current, pending, pending_count = None, None, 0
                    reason = "NO_ELIGIBLE_THEME"
                elif current is None:
                    current, pending, pending_count, exit_count = challenger, None, 0, 0
                    reason = "SELECT_NEW_LEADER"
                elif challenger == current:
                    pending, pending_count = None, 0
                    reason = "KEEP_CURRENT_LEADER"
                else:
                    current_score = float(score[current]) if pd.notna(score.get(current, np.nan)) else -np.inf
                    challenger_score = float(score[challenger])
                    if challenger_score > current_score + cfg.score_margin:
                        pending_count = pending_count + 1 if pending == challenger else 1
                        pending = challenger
                        if pending_count >= cfg.confirmation_reviews:
                            current, pending, pending_count, exit_count = challenger, None, 0, 0
                            reason = "CONFIRMED_LEADERSHIP_ROTATION"
                        else:
                            reason = "CHALLENGER_PENDING"
                    else:
                        pending, pending_count = None, 0
                        reason = "LEADERSHIP_MARGIN_NOT_MET"
        leader_score = float(score[current]) if current is not None and pd.notna(score.get(current, np.nan)) else np.nan
        rows.append({
            "date": date, "information_cutoff": index[pos - 1] if pos > 0 else pd.NaT,
            "decision_uses_same_day_close": False, "review_monthly": date in monthly, "review_weekly": date in weekly,
            "leader_ticker": current, "leader_name": name_by_ticker.get(current) if current else None,
            "leader_sector": sector_by_ticker.get(current) if current else None, "leader_score_d1": leader_score,
            "target_leader_weight": cfg.leader_weight if current else 0.0, "market_trend_on_d1": market_on,
            "decision_reason": reason, "pending_challenger": pending, "pending_confirmation_count": pending_count,
            "eligible_theme_count": int(sum(bool(v) for v in eligible.values)),
        })
    return pd.DataFrame(rows)


def _v79_features_vol_adjusted(
    close: pd.DataFrame,
    value: pd.DataFrame,
    universe: pd.DataFrame,
    cfg: dict[str, Any],
) -> dict[str, Any]:
    p = cfg["trend_sleeve"]
    tickers = universe["ticker"].astype(str).tolist()
    horizons = tuple(int(x) for x in p["horizons_days"])
    weights = tuple(float(x) for x in p["horizon_weights"])
    returns = [close[tickers].pct_change(h, fill_method=None) for h in horizons]
    vol = close[tickers].pct_change(fill_method=None).rolling(63, min_periods=40).std() * math.sqrt(252)
    risk_adjusted = [ret.div(vol.replace(0.0, np.nan)) for ret in returns]
    ranks = [frame.rank(axis=1, pct=True, method="average") for frame in risk_adjusted]
    score = sum(w * rank for w, rank in zip(weights, ranks))
    history = close[tickers].notna().cumsum()
    liquidity = value[tickers].rolling(20, min_periods=10).median()
    ma = close[tickers].rolling(int(p["trend_ma_days"]), min_periods=int(p["trend_ma_days"])).mean()
    eligible = (
        history.ge(int(p["minimum_history_days"]))
        & liquidity.ge(float(p["minimum_median_value_20d_krw"]))
        & returns[1].gt(0) & returns[2].gt(0) & close[tickers].gt(ma)
    )
    return {
        "score": score.shift(1), "eligible": eligible.shift(1, fill_value=False).astype(bool),
        "liquidity": liquidity.shift(1), "absolute_return_short": returns[0].shift(1),
        "absolute_return_medium": returns[1].shift(1), "absolute_return_long": returns[2].shift(1),
    }


def _select_v79_exit_confirm(
    index: pd.DatetimeIndex,
    universe: pd.DataFrame,
    features: dict[str, Any],
    *,
    minimum_hold_sessions: int,
    challenger_score_margin: float,
    confirmation_reviews: int,
    exit_confirmations: int = 2,
) -> pd.DataFrame:
    _, weekly = v69._review_dates(index)
    sector_by_ticker = universe.set_index("ticker")["sector"].to_dict()
    name_by_ticker = universe.set_index("ticker")["name"].to_dict()
    current: str | None = None
    holding = 0
    pending: str | None = None
    pending_count = 0
    exit_count = 0
    rows: list[dict[str, Any]] = []
    for pos, date in enumerate(index):
        score, eligible = features["score"].loc[date], features["eligible"].loc[date]
        reason = "INTRA_WEEK_HOLD"
        ranked: list[tuple[str, str, float, float]] = []
        if current:
            holding += 1
        if date in weekly:
            for sector, group in universe.groupby("sector"):
                candidates = [str(t) for t in group["ticker"] if bool(eligible.get(str(t), False)) and pd.notna(score.get(str(t), np.nan))]
                if not candidates:
                    continue
                best = max(candidates, key=lambda t: (float(score[t]), float(features["liquidity"].loc[date, t]) if pd.notna(features["liquidity"].loc[date, t]) else 0.0))
                ranked.append((best, str(sector), float(score[best]), float(features["liquidity"].loc[date, best]) if pd.notna(features["liquidity"].loc[date, best]) else 0.0))
            ranked.sort(key=lambda x: (x[2], x[3]), reverse=True)
            challenger = ranked[0][0] if ranked else None
            current_ok = bool(eligible.get(current, False)) if current else False
            if current and not current_ok:
                exit_count += 1
                if exit_count >= exit_confirmations:
                    current, holding, pending, pending_count, exit_count = None, 0, None, 0, 0
                    reason = "CONFIRMED_WEEKLY_HARD_TREND_EXIT"
                else:
                    reason = "WEEKLY_HARD_EXIT_PENDING_CONFIRMATION"
            else:
                exit_count = 0
            if challenger is None:
                if current is None:
                    reason = "NO_ELIGIBLE_GENERIC_TREND"
            elif current is None:
                current, holding, pending, pending_count, exit_count = challenger, 1, None, 0, 0
                reason = "SELECT_GENERIC_TREND_LEADER"
            elif challenger == current:
                pending, pending_count = None, 0
                reason = "KEEP_PERSISTENT_TREND_LEADER"
            elif holding < minimum_hold_sessions:
                pending, pending_count = None, 0
                reason = "MINIMUM_HOLD_NOT_SATISFIED"
            else:
                current_score = float(score[current]) if pd.notna(score.get(current, np.nan)) else -np.inf
                if float(score[challenger]) >= current_score + challenger_score_margin:
                    pending_count = pending_count + 1 if pending == challenger else 1
                    pending = challenger
                    if pending_count >= confirmation_reviews:
                        current, holding, pending, pending_count, exit_count = challenger, 1, None, 0, 0
                        reason = "CONFIRMED_GENERIC_TREND_ROTATION"
                    else:
                        reason = "GENERIC_CHALLENGER_PENDING"
                else:
                    pending, pending_count = None, 0
                    reason = "GENERIC_CHALLENGER_MARGIN_NOT_MET"
        current_score = float(score[current]) if current and pd.notna(score.get(current, np.nan)) else np.nan
        rows.append({
            "date": date, "information_cutoff": index[pos - 1] if pos > 0 else pd.NaT,
            "decision_uses_same_day_close": False, "review_weekly": date in weekly,
            "sleeve_ticker": current, "sleeve_name": name_by_ticker.get(current) if current else None,
            "sleeve_sector": sector_by_ticker.get(current) if current else None, "sleeve_score_d1": current_score,
            "holding_sessions": holding if current else 0, "decision_reason": reason,
            "pending_challenger": pending, "pending_confirmation_count": pending_count,
            "eligible_sector_count": len(ranked),
        })
    return pd.DataFrame(rows)


def _build_v79_strength_targets(
    base_selection: pd.DataFrame,
    sleeve_selection: pd.DataFrame,
    market: dict[str, Any],
    cfg79: dict[str, Any],
    core: str,
) -> pd.DataFrame:
    base = base_selection.set_index("date")
    sleeve = sleeve_selection.set_index("date")
    indicator_cfg = yaml.safe_load((Path(cfg79["_root"]) / "config/v80_multi_indicator_confirmation.yaml").read_text(encoding="utf-8"))
    indicators = v80.build_indicator_library(market["close"], market["high"], market["low"], market["volume"], cfg=indicator_cfg)
    score_series = sleeve_selection.set_index("date")["sleeve_score_d1"]
    percentile = v77._expanding_percentile(score_series)
    rows: list[dict[str, Any]] = []
    for date in base.index:
        leader = str(base.loc[date, "leader_ticker"]) if pd.notna(base.loc[date, "leader_ticker"]) else None
        leader_weight = float(base.loc[date, "target_leader_weight"]) if leader else 0.0
        st = str(sleeve.loc[date, "sleeve_ticker"]) if pd.notna(sleeve.loc[date, "sleeve_ticker"]) else None
        pct = float(percentile.loc[date]) if pd.notna(percentile.loc[date]) else 0.5
        extreme = False
        if st and st in indicators["atr_extreme"].columns:
            extreme = bool(indicators["atr_extreme"].loc[date, st] or indicators["bollinger_extreme"].loc[date, st])
        sleeve_weight = 0.15 if extreme or pct < 0.40 else (0.45 if pct >= 0.75 else 0.30)
        if st is None:
            sleeve_weight = 0.0
        base_share = 1.0 - sleeve_weight
        weights: dict[str, float] = {core: base_share * (1.0 - leader_weight)}
        if leader:
            weights[leader] = weights.get(leader, 0.0) + base_share * leader_weight
        if st:
            weights[st] = weights.get(st, 0.0) + sleeve_weight
        else:
            weights[core] = weights.get(core, 0.0) + (1.0 - sum(weights.values()))
        rows.append({
            "date": date,
            "information_cutoff": min(base.loc[date, "information_cutoff"], sleeve.loc[date, "information_cutoff"]),
            "decision_uses_same_day_close": False, "active_ticker": st, "active_score_d1": float(sleeve.loc[date, "sleeve_score_d1"]) if pd.notna(sleeve.loc[date, "sleeve_score_d1"]) else np.nan,
            "decision_reason": "SELF_SIGNAL_STRENGTH_WEIGHT", "target_weights_json": json.dumps(weights, sort_keys=True),
            "target_weight_sum": float(sum(weights.values())), "dynamic_sleeve_weight": sleeve_weight,
        })
    return pd.DataFrame(rows)


def _normalise_target_columns(frame: pd.DataFrame, active_col: str, score_col: str, reason_col: str) -> pd.DataFrame:
    out = frame.copy()
    out["active_ticker"] = out[active_col]
    out["active_score_d1"] = out[score_col]
    out["decision_reason"] = out[reason_col]
    return out


def _build_all_targets(root: Path, market: dict[str, Any], cfg77: v77.V77Config) -> tuple[dict[str, pd.DataFrame], dict[str, dict[str, Any]]]:
    cfg79 = yaml.safe_load((root / "config/v79_generic_trend_sleeve.yaml").read_text(encoding="utf-8"))
    cfg79["_root"] = str(root)
    v69_cfg = replace(v69._load_config(root), end_date=cfg77.end_date, core_ticker=cfg77.core_ticker, benchmark_ticker=cfg77.benchmark_ticker, leader_weight=0.80)
    universe = v69._load_universe(root, v69_cfg)
    index = market["close"].index

    f_base = build_baseline_features(market["close"], market["value"], universe, v69_cfg)
    f_fast = _v69_features_fast(market["close"], market["value"], universe, v69_cfg)
    f_vol = _v69_features_vol_adjusted(market["close"], market["value"], universe, v69_cfg)
    s_v69_base = v69.select_dynamic_leader(index, universe, f_base, v69_cfg)
    s_v69_fast = v69.select_dynamic_leader(index, universe, f_fast, v69_cfg)
    s_v69_vol = v69.select_dynamic_leader(index, universe, f_vol, v69_cfg)
    s_v69_exit = _select_v69_exit_confirm(index, universe, f_base, v69_cfg, 2)
    for frame in (s_v69_base, s_v69_fast, s_v69_vol, s_v69_exit):
        frame["target_leader_weight"] = frame["leader_ticker"].notna().astype(float) * 0.80

    p = cfg79["trend_sleeve"]
    sf_base = v79.build_generic_trend_features(
        market["close"], market["value"], universe,
        horizons=tuple(int(x) for x in p["horizons_days"]), horizon_weights=tuple(float(x) for x in p["horizon_weights"]),
        trend_ma_days=int(p["trend_ma_days"]), minimum_history_days=int(p["minimum_history_days"]),
        minimum_median_value_20d_krw=float(p["minimum_median_value_20d_krw"]),
    )
    sf_vol = _v79_features_vol_adjusted(market["close"], market["value"], universe, cfg79)
    ss_base = v79.select_persistent_trend_leader(index, universe, sf_base, minimum_hold_sessions=int(p["minimum_hold_sessions"]), challenger_score_margin=float(p["challenger_score_margin"]), confirmation_reviews=int(p["challenger_confirmation_reviews"]))
    ss_fast = v79.select_persistent_trend_leader(index, universe, sf_base, minimum_hold_sessions=10, challenger_score_margin=0.05, confirmation_reviews=1)
    ss_vol = v79.select_persistent_trend_leader(index, universe, sf_vol, minimum_hold_sessions=int(p["minimum_hold_sessions"]), challenger_score_margin=float(p["challenger_score_margin"]), confirmation_reviews=int(p["challenger_confirmation_reviews"]))
    ss_exit = _select_v79_exit_confirm(index, universe, sf_base, minimum_hold_sessions=int(p["minimum_hold_sessions"]), challenger_score_margin=float(p["challenger_score_margin"]), confirmation_reviews=int(p["challenger_confirmation_reviews"]), exit_confirmations=2)

    targets = {
        "V69_PARENT": _weights_from_v69_selection(s_v69_base, cfg77.core_ticker),
        "V69_FAST_ALPHA": _weights_from_v69_selection(s_v69_fast, cfg77.core_ticker),
        "V69_VOL_ADJUSTED_ALPHA": _weights_from_v69_selection(s_v69_vol, cfg77.core_ticker),
        "V69_EXIT_CONFIRM_2": _weights_from_v69_selection(s_v69_exit, cfg77.core_ticker),
    }
    # Avoid rebuilding base ledger repeatedly and attach the sleeve diagnostics explicitly.
    def blend(selection: pd.DataFrame) -> pd.DataFrame:
        frame = v79.build_blended_target_ledger(s_v69_base, selection, core_ticker=cfg77.core_ticker, base_share=0.70)
        frame["active_ticker"] = selection["sleeve_ticker"].values
        frame["active_score_d1"] = selection["sleeve_score_d1"].values
        frame["decision_reason"] = selection["decision_reason"].values
        return frame
    targets["V79_PARENT"] = blend(ss_base)
    targets["V79_FAST_ROTATION"] = blend(ss_fast)
    targets["V79_VOL_ADJUSTED_TREND"] = blend(ss_vol)
    targets["V79_EXIT_CONFIRM_2"] = blend(ss_exit)
    targets["V79_SIGNAL_STRENGTH_WEIGHT"] = _build_v79_strength_targets(s_v69_base, ss_base, market, cfg79, cfg77.core_ticker)

    selections = {
        "V69_PARENT": {"selection": s_v69_base, "features": f_base, "family": "V69"},
        "V69_FAST_ALPHA": {"selection": s_v69_fast, "features": f_fast, "family": "V69"},
        "V69_VOL_ADJUSTED_ALPHA": {"selection": s_v69_vol, "features": f_vol, "family": "V69"},
        "V69_EXIT_CONFIRM_2": {"selection": s_v69_exit, "features": f_base, "family": "V69"},
        "V79_PARENT": {"selection": ss_base, "features": sf_base, "family": "V79"},
        "V79_FAST_ROTATION": {"selection": ss_fast, "features": sf_base, "family": "V79"},
        "V79_VOL_ADJUSTED_TREND": {"selection": ss_vol, "features": sf_vol, "family": "V79"},
        "V79_EXIT_CONFIRM_2": {"selection": ss_exit, "features": sf_base, "family": "V79"},
        "V79_SIGNAL_STRENGTH_WEIGHT": {"selection": ss_base, "features": sf_base, "family": "V79"},
    }
    return targets, selections


def _ranked_two(date: pd.Timestamp, universe: pd.DataFrame, features: dict[str, Any]) -> tuple[str | None, str | None]:
    score, eligible = features["score"].loc[date], features["eligible"].loc[date]
    ranked: list[tuple[str, float, float]] = []
    for _, group in universe.groupby("sector"):
        candidates = [str(t) for t in group["ticker"] if bool(eligible.get(str(t), False)) and pd.notna(score.get(str(t), np.nan))]
        if not candidates:
            continue
        best = max(candidates, key=lambda t: (float(score[t]), float(features["liquidity"].loc[date, t]) if pd.notna(features["liquidity"].loc[date, t]) else 0.0))
        ranked.append((best, float(score[best]), float(features["liquidity"].loc[date, best]) if pd.notna(features["liquidity"].loc[date, best]) else 0.0))
    ranked.sort(key=lambda x: (x[1], x[2]), reverse=True)
    return (ranked[0][0] if ranked else None, ranked[1][0] if len(ranked) > 1 else None)


def _own_event_outcomes(
    scenario: str,
    selection: pd.DataFrame,
    features: dict[str, Any],
    universe: pd.DataFrame,
    market: dict[str, Any],
    core: str,
    horizon: int = 60,
) -> pd.DataFrame:
    active_col = "leader_ticker" if "leader_ticker" in selection.columns else "sleeve_ticker"
    rows: list[dict[str, Any]] = []
    dates = market["close"].index
    pos_map = {d: i for i, d in enumerate(dates)}
    prior: str | None = None
    for row in selection.itertuples(index=False):
        date = pd.Timestamp(row.date)
        current_raw = getattr(row, active_col)
        current = str(current_raw) if pd.notna(current_raw) else None
        if current == prior:
            continue
        event_type = "ENTRY" if prior is None and current else ("EXIT" if prior and current is None else "ROTATION")
        pos = pos_map[date]
        if pos + horizon >= len(dates):
            prior = current
            continue
        _, runner = _ranked_two(date, universe, features)
        start = pos
        end = pos + horizon
        def ret(ticker: str | None) -> float:
            if not ticker or ticker not in market["open"].columns:
                return np.nan
            entry, finish = market["open"].iloc[start].get(ticker, np.nan), market["close"].iloc[end].get(ticker, np.nan)
            return float(finish / entry - 1.0) if pd.notna(entry) and pd.notna(finish) and float(entry) > 0 else np.nan
        chosen_ret, core_ret, runner_ret, old_ret = ret(current), ret(core), ret(runner), ret(prior)
        delayed_ret = np.nan
        if current and start + 5 < end:
            e = market["open"].iloc[start + 5].get(current, np.nan)
            f = market["close"].iloc[end].get(current, np.nan)
            delayed_ret = float(f / e - 1.0) if pd.notna(e) and pd.notna(f) and float(e) > 0 else np.nan
        path = market["close"].iloc[start:end + 1]
        mae = np.nan
        if current and current in path.columns and pd.notna(market["open"].iloc[start].get(current, np.nan)):
            mae = float(path[current].min() / market["open"].iloc[start][current] - 1.0)
        rows.append({
            "scenario": scenario, "family": "V69" if scenario.startswith("V69") else "V79", "event_type": event_type,
            "decision_date": date, "horizon_end_date": dates[end], "old_ticker": prior, "chosen_ticker": current,
            "runner_up_ticker": runner, "chosen_return": chosen_ret, "core_return": core_ret,
            "runner_up_return": runner_ret, "old_ticker_return": old_ret, "delayed_5d_return": delayed_ret, "mae": mae,
            "selection_edge": runner_ret - chosen_ret if np.isfinite(runner_ret) and np.isfinite(chosen_ret) else np.nan,
            "entry_delay_edge": chosen_ret - delayed_ret if np.isfinite(chosen_ret) and np.isfinite(delayed_ret) else np.nan,
            "exit_edge": old_ret - core_ret if event_type in {"EXIT", "ROTATION"} and np.isfinite(old_ret) and np.isfinite(core_ret) else np.nan,
            "broad_rally_undercapture": bool(np.isfinite(core_ret) and core_ret >= 0.10 and (not np.isfinite(chosen_ret) or chosen_ret <= core_ret - 0.05)),
            "volatility_pain": bool(np.isfinite(mae) and mae <= -0.10),
        })
        prior = current
    return pd.DataFrame(rows)


def _issue_table(evidence: pd.DataFrame, minimum_events: int) -> pd.DataFrame:
    if evidence.empty or len(evidence) < minimum_events:
        return pd.DataFrame(columns=["issue", "rate", "severity", "score", "events"])
    def issue(name: str, mask: pd.Series, severity: pd.Series) -> dict[str, Any]:
        valid = severity.replace([np.inf, -np.inf], np.nan).dropna()
        return {"issue": name, "rate": float(mask.fillna(False).mean()), "severity": float(valid.clip(lower=0).mean()) if len(valid) else 0.0, "events": len(evidence)}
    rows = [
        issue("selection_error", evidence["selection_edge"].gt(0.05), evidence["selection_edge"]),
        issue("late_entry", evidence["entry_delay_edge"].lt(-0.03), -evidence["entry_delay_edge"]),
        issue("early_exit", evidence["exit_edge"].gt(0.05), evidence["exit_edge"]),
        issue("broad_rally_undercapture", evidence["broad_rally_undercapture"].astype(bool), (evidence["core_return"] - evidence["chosen_return"]).where(evidence["broad_rally_undercapture"])),
        issue("volatility_pain", evidence["volatility_pain"].astype(bool), -evidence["mae"]),
    ]
    out = pd.DataFrame(rows)
    out["score"] = out["rate"] + 4.0 * out["severity"].clip(upper=0.25)
    return out.sort_values(["score", "severity"], ascending=False).reset_index(drop=True)


def _proposal_for_fold(
    family: str,
    active: str,
    outcome_map: dict[str, pd.DataFrame],
    index: pd.DatetimeIndex,
    test_start: pd.Timestamp,
    cfg: dict[str, Any],
) -> tuple[str, str, pd.DataFrame, pd.Timestamp]:
    start_pos = int(index.searchsorted(test_start))
    cutoff_pos = max(start_pos - int(cfg["feedback"]["purge_sessions"]) - 1, 0)
    cutoff = index[cutoff_pos]
    window_pos = max(cutoff_pos - int(cfg["feedback"]["rolling_evidence_sessions"]), 0)
    window_start = index[window_pos]
    evidence = outcome_map[active]
    evidence = evidence[(pd.to_datetime(evidence["horizon_end_date"]) <= cutoff) & (pd.to_datetime(evidence["decision_date"]) >= window_start)].copy()
    issues = _issue_table(evidence, int(cfg["feedback"]["minimum_matured_events"]))
    if issues.empty:
        return active, "INSUFFICIENT_MATURED_SELF_TRADES", issues, cutoff
    best = issues.iloc[0]
    if float(best["rate"]) < float(cfg["feedback"]["issue_minimum_rate"]) and float(best["severity"]) < float(cfg["feedback"]["issue_minimum_severity"]):
        return active, "NO_DOMINANT_SELF_ERROR", issues, cutoff
    mapping = cfg["families"][family]["candidates"]
    candidate = str(mapping.get(str(best["issue"]), active))
    return candidate, str(best["issue"]), issues, cutoff


def _execute_target(
    market: dict[str, Any], target: pd.DataFrame, cfg77: v77.V77Config, scenario: str, *, stress: bool = False,
    start: pd.Timestamp | None = None, end: pd.Timestamp | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    mask = pd.Series(True, index=market["close"].index)
    if start is not None:
        mask &= market["close"].index >= start
    if end is not None:
        mask &= market["close"].index <= end
    idx = market["close"].index[mask]
    spec = cfg77.stress_execution if stress else cfg77.base_execution
    rebalance_band = 0.0 if "V69" in scenario else 0.05
    account, orders, audit = v79.execute_multi_target(
        market["close"].loc[idx], market["open"].loc[idx], market["adv20_d1"].loc[idx],
        target.set_index("date").loc[idx].reset_index(), initial_capital=cfg77.initial_capital_krw,
        spec=spec, rebalance_band=rebalance_band, scenario=scenario,
    )
    return account, orders, audit


def _period_fold_metrics(account: pd.DataFrame, initial: float) -> dict[str, float]:
    nav = account.set_index("date")["nav_krw"]
    return _slice_metrics(nav, str(nav.index.min().date()), str(nav.index.max().date()), initial)


def _walk_forward_family(
    family: str,
    target_map: dict[str, pd.DataFrame],
    outcome_map: dict[str, pd.DataFrame],
    market: dict[str, Any], cfg77: v77.V77Config, cfg: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    parent = str(cfg["families"][family]["parent"])
    active = parent
    active_by_year: dict[int, str] = {}
    rows: list[dict[str, Any]] = []
    issue_rows: list[dict[str, Any]] = []
    years = [int(y) for y in cfg["walk_forward"]["test_years"]]
    idx = market["close"].index
    for year in years:
        test_dates = idx[idx.year == year]
        if len(test_dates) == 0:
            continue
        start, end = test_dates.min(), test_dates.max()
        active_by_year[year] = active
        candidate, reason, issues, cutoff = _proposal_for_fold(family, active, outcome_map, idx, start, cfg)
        for r in issues.to_dict("records"):
            issue_rows.append({"family": family, "test_year": year, "active_strategy": active, "candidate": candidate, "evidence_cutoff": cutoff, **r})
        active_account, active_orders, _ = _execute_target(market, target_map[active], cfg77, f"{family}_{year}_ACTIVE", start=start, end=end)
        active_stress, _, _ = _execute_target(market, target_map[active], cfg77, f"{family}_{year}_ACTIVE_STRESS", stress=True, start=start, end=end)
        if candidate == active:
            cand_account, cand_orders, cand_stress = active_account, active_orders, active_stress
        else:
            cand_account, cand_orders, _ = _execute_target(market, target_map[candidate], cfg77, f"{family}_{year}_CANDIDATE", start=start, end=end)
            cand_stress, _, _ = _execute_target(market, target_map[candidate], cfg77, f"{family}_{year}_CANDIDATE_STRESS", stress=True, start=start, end=end)
        am, cm = _period_fold_metrics(active_account, cfg77.initial_capital_krw), _period_fold_metrics(cand_account, cfg77.initial_capital_krw)
        asm, csm = _period_fold_metrics(active_stress, cfg77.initial_capital_krw), _period_fold_metrics(cand_stress, cfg77.initial_capital_krw)
        promoted = bool(
            candidate != active
            and cm["return_pct"] - am["return_pct"] >= float(cfg["walk_forward"]["promotion_return_delta_pp"])
            and cm["mdd_pct"] >= am["mdd_pct"] - float(cfg["walk_forward"]["promotion_mdd_tolerance_pp"])
            and csm["return_pct"] - asm["return_pct"] >= float(cfg["walk_forward"]["promotion_stress_return_delta_pp"])
        )
        rows.append({
            "family": family, "test_year": year, "test_start": start, "test_end": end, "evidence_cutoff": cutoff,
            "active_strategy": active, "proposed_candidate": candidate, "proposal_reason": reason,
            "active_return_pct": am["return_pct"], "candidate_return_pct": cm["return_pct"],
            "return_delta_pp": cm["return_pct"] - am["return_pct"], "active_mdd_pct": am["mdd_pct"], "candidate_mdd_pct": cm["mdd_pct"],
            "active_stress_return_pct": asm["return_pct"], "candidate_stress_return_pct": csm["return_pct"],
            "stress_delta_pp": csm["return_pct"] - asm["return_pct"], "active_orders": len(active_orders), "candidate_orders": len(cand_orders),
            "promoted_for_next_fold": promoted, "next_active_strategy": candidate if promoted else active,
        })
        if promoted:
            active = candidate
    # Construct the truly causal active target: a promotion from year Y is only effective in Y+1.
    stitched = target_map[parent].copy().set_index("date")
    for year, scenario in active_by_year.items():
        mask = stitched.index.year == year
        source = target_map[scenario].set_index("date")
        stitched.loc[mask, source.columns] = source.loc[stitched.index[mask], source.columns]
    stitched = stitched.reset_index()
    return pd.DataFrame(rows), pd.DataFrame(issue_rows), stitched


def _data_contract(root: Path, market: dict[str, Any], target_map: dict[str, pd.DataFrame], cfg77: v77.V77Config) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    universe = market["universe"]
    rows.append({"gate": "UNIVERSE_TICKERS_UNIQUE", "passed": not universe["ticker"].duplicated().any(), "detail": f"tickers={len(universe)}"})
    rows.append({"gate": "ADJUSTED_SOURCE_TAG_ONLY", "passed": bool(market["source_audit"]["source"].eq(cfg77.required_source_tag).all()), "detail": cfg77.required_source_tag})
    oc_max = pd.DataFrame(np.maximum(market["open"].to_numpy(float), market["close"].to_numpy(float)), index=market["open"].index, columns=market["open"].columns)
    oc_min = pd.DataFrame(np.minimum(market["open"].to_numpy(float), market["close"].to_numpy(float)), index=market["open"].index, columns=market["open"].columns)
    invalid_ohlc = ((market["high"] < oc_max) | (market["low"] > oc_min)).sum().sum()
    rows.append({"gate": "OHLC_RELATION_VALID", "passed": int(invalid_ohlc) == 0, "detail": f"invalid={int(invalid_ohlc)}"})
    rows.append({"gate": "CORE_OPEN_CLOSE_COMPLETE", "passed": not market["open"][cfg77.core_ticker].isna().any() and not market["close"][cfg77.core_ticker].isna().any(), "detail": cfg77.core_ticker})
    target_sum = max(float((frame["target_weight_sum"] - 1.0).abs().max()) for frame in target_map.values())
    rows.append({"gate": "ALL_TARGETS_SUM_TO_ONE", "passed": target_sum <= 1e-12, "detail": f"max_error={target_sum}"})
    hashes = {str(p.relative_to(root)): _file_hash(p) for p in sorted((root / cfg77.etf_source).glob("*_1d.csv"))}
    rows.append({"gate": "DATA_FINGERPRINT_WRITTEN", "passed": len(hashes) == len(universe), "detail": json.dumps(hashes, sort_keys=True)})
    return pd.DataFrame(rows)


def _target_signature(frame: pd.DataFrame) -> pd.Series:
    return frame.set_index("date")["target_weights_json"].astype(str)


def _rebuild_on_market(root: Path, market: dict[str, Any], cfg77: v77.V77Config) -> dict[str, pd.DataFrame]:
    targets, _ = _build_all_targets(root, market, cfg77)
    return targets


def _robustness_gates(root: Path, market: dict[str, Any], cfg77: v77.V77Config, target_map: dict[str, pd.DataFrame], adaptive_targets: dict[str, pd.DataFrame], cfg: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    cutoff = pd.Timestamp("2024-12-31")
    mutated = {k: (v.copy() if isinstance(v, pd.DataFrame) else v) for k, v in market.items()}
    for key in ("open", "high", "low", "close"):
        mutated[key] = market[key].copy()
        mutated[key].loc[mutated[key].index > cutoff] *= 1.50
    mutated["value"] = mutated["close"] * mutated["volume"]
    mutated["adv20_d1"] = mutated["value"].rolling(20, min_periods=10).median().shift(1)
    future_targets = _rebuild_on_market(root, mutated, cfg77)
    future_equal = True
    for name in target_map:
        a, b = _target_signature(target_map[name]), _target_signature(future_targets[name])
        common = a.index[a.index <= cutoff]
        future_equal &= bool(a.loc[common].equals(b.loc[common]))
    rows.append({"gate": "FUTURE_MUTATION_DOES_NOT_CHANGE_PAST_TARGETS", "passed": future_equal, "detail": str(cutoff.date())})

    scaled = {k: (v.copy() if isinstance(v, pd.DataFrame) else v) for k, v in market.items()}
    cols = [c for c in market["close"].columns if c != cfg77.benchmark_ticker]
    factors = pd.Series({c: 0.75 + (int(sha256(c.encode()).hexdigest()[:6], 16) % 1000) / 1000.0 for c in cols})
    for key in ("open", "high", "low", "close"):
        scaled[key] = market[key].copy()
        scaled[key].loc[:, cols] = scaled[key][cols].mul(factors, axis=1)
    scaled["volume"] = market["volume"].copy()
    scaled["volume"].loc[:, cols] = scaled["volume"][cols].div(factors, axis=1)
    scaled["value"] = scaled["close"] * scaled["volume"]
    scaled["adv20_d1"] = scaled["value"].rolling(20, min_periods=10).median().shift(1)
    scaled_targets = _rebuild_on_market(root, scaled, cfg77)
    scale_target_equal = all(_target_signature(target_map[name]).equals(_target_signature(scaled_targets[name])) for name in target_map)
    rows.append({"gate": "PRICE_VOLUME_SCALE_INVARIANT_TARGETS", "passed": scale_target_equal, "detail": f"tickers={len(cols)}"})

    noise_bps = float(cfg["robustness"]["small_noise_bps"])
    noisy = {k: (v.copy() if isinstance(v, pd.DataFrame) else v) for k, v in market.items()}
    row_phase = np.arange(len(market["close"]))[:, None]
    col_phase = np.arange(len(market["close"].columns))[None, :]
    noise = 1.0 + np.sin(row_phase * 0.73 + col_phase * 1.17) * noise_bps / 10000.0
    for key in ("open", "high", "low", "close"):
        noisy[key] = pd.DataFrame(market[key].to_numpy(float) * noise, index=market[key].index, columns=market[key].columns)
    noisy["volume"] = pd.DataFrame(market["volume"].to_numpy(float) / noise, index=market["volume"].index, columns=market["volume"].columns)
    noisy["value"] = noisy["close"] * noisy["volume"]
    noisy["adv20_d1"] = noisy["value"].rolling(20, min_periods=10).median().shift(1)
    noisy_targets = _rebuild_on_market(root, noisy, cfg77)
    agreements = []
    for name in target_map:
        a, b = _target_signature(target_map[name]), _target_signature(noisy_targets[name])
        agreements.append(float((a == b).mean()))
    min_agreement = min(agreements)
    rows.append({"gate": "SMALL_VENDOR_NOISE_TARGET_STABILITY", "passed": min_agreement >= float(cfg["robustness"]["small_noise_target_agreement_min"]), "detail": f"min_agreement={min_agreement:.6f}"})

    for family, target in adaptive_targets.items():
        base_account, _, _ = _execute_target(market, target, cfg77, family + "_BASE")
        noisy_account, _, _ = _execute_target(noisy, target, cfg77, family + "_NOISY")
        b = _period_fold_metrics(base_account, cfg77.initial_capital_krw)["return_pct"]
        n = _period_fold_metrics(noisy_account, cfg77.initial_capital_krw)["return_pct"]
        diff = abs(n - b)
        rows.append({"gate": f"{family}_SMALL_NOISE_RETURN_STABILITY", "passed": diff <= float(cfg["robustness"]["small_noise_return_tolerance_pp"]), "detail": f"delta_pp={diff:.6f}"})
    return pd.DataFrame(rows)


def _genericity_audit() -> dict[str, Any]:
    source = inspect.getsource(_v69_features_fast) + inspect.getsource(_v69_features_vol_adjusted) + inspect.getsource(_v79_features_vol_adjusted) + inspect.getsource(_build_v79_strength_targets)
    forbidden = ["semiconductor", "battery_ev", "091160", "091230", "471990"]
    hits = [x for x in forbidden if x.lower() in source.lower()]
    return {"passed": not hits, "hits": hits}


def run(root: Path | str) -> dict[str, Any]:
    root = Path(root)
    out = root / "reports" / REPORT
    out.mkdir(parents=True, exist_ok=True)
    cfg = _load_config(root)
    cfg77 = replace(v77._load_config(root), end_date=str(cfg["data_end"]))
    market = v77.load_adjusted_market(root, cfg77)
    targets, selections = _build_all_targets(root, market, cfg77)
    v69_cfg = replace(v69._load_config(root), end_date=cfg77.end_date, core_ticker=cfg77.core_ticker, benchmark_ticker=cfg77.benchmark_ticker, leader_weight=0.80)
    universe = v69._load_universe(root, v69_cfg)

    outcomes = {
        name: _own_event_outcomes(name, info["selection"], info["features"], universe, market, cfg77.core_ticker, int(cfg["feedback"]["outcome_horizon"]))
        for name, info in selections.items()
    }
    fold_frames, issue_frames, adaptive_targets = [], [], {}
    for family in ("V69", "V79"):
        folds, issues, stitched = _walk_forward_family(family, targets, outcomes, market, cfg77, cfg)
        fold_frames.append(folds)
        issue_frames.append(issues)
        adaptive_targets[family] = stitched

    folds = pd.concat(fold_frames, ignore_index=True)
    issues = pd.concat(issue_frames, ignore_index=True) if issue_frames else pd.DataFrame()

    accounts: dict[str, pd.DataFrame] = {}
    orders: dict[str, pd.DataFrame] = {}
    audits: dict[str, dict[str, Any]] = {}
    for name, target in targets.items():
        account, order, audit = _execute_target(market, target, cfg77, name)
        accounts[name], orders[name], audits[name] = account, order, audit
    for family, target in adaptive_targets.items():
        name = f"V83_{family}_INDEPENDENT_SELF_RESEARCH"
        account, order, audit = _execute_target(market, target, cfg77, name)
        accounts[name], orders[name], audits[name] = account, order, audit

    nav_map = {name: frame.set_index("date")["nav_krw"] for name, frame in accounts.items()}
    periods = {
        "development": cfg["periods"]["development"],
        "walk_forward": cfg["periods"]["walk_forward"],
        "recent_1y": cfg["periods"]["recent_1y"],
    }
    metrics = _return_table(nav_map, periods, cfg77.initial_capital_krw)
    metrics["order_count"] = metrics["scenario"].map({k: len(v) for k, v in orders.items()}).astype(int)
    metrics["negative_cash_days"] = metrics["scenario"].map({k: v["negative_cash_days"] for k, v in audits.items()}).astype(int)
    for period_name, (start, end) in periods.items():
        metrics[f"{period_name}_sharpe"] = metrics["scenario"].map({name: _slice_metrics(nav, start, end, cfg77.initial_capital_krw)["sharpe"] for name, nav in nav_map.items()})
        metrics[f"{period_name}_mdd_pct"] = metrics["scenario"].map({name: _slice_metrics(nav, start, end, cfg77.initial_capital_krw)["mdd_pct"] for name, nav in nav_map.items()})

    contract = _data_contract(root, market, targets, cfg77)
    robustness = _robustness_gates(root, market, cfg77, targets, adaptive_targets, cfg)
    generic = _genericity_audit()
    prior_metrics = pd.read_csv(root / "reports/v79_generic_trend_sleeve/v79_all_strategy_metrics.csv").set_index("scenario")
    current_metrics = metrics.set_index("scenario")
    v69_lineage_delta = float(current_metrics.loc["V69_PARENT", "return_pct"] - prior_metrics.loc[CONTROL, "return_pct"])
    v79_lineage_delta = float(current_metrics.loc["V79_PARENT", "return_pct"] - prior_metrics.loc[CHALLENGER, "return_pct"])
    lineage_ok = abs(v69_lineage_delta) <= 0.50 and abs(v79_lineage_delta) <= 0.01
    no_cross_family = all(not ((row.family == "V69" and str(row.proposed_candidate).startswith("V79")) or (row.family == "V79" and str(row.proposed_candidate).startswith("V69"))) for row in folds.itertuples())
    delayed = True
    for family in ("V69", "V79"):
        f = folds[folds["family"].eq(family)].sort_values("test_year")
        for i in range(1, len(f)):
            expected = f.iloc[i - 1]["next_active_strategy"]
            delayed &= str(f.iloc[i]["active_strategy"]) == str(expected)
    quality = pd.concat([
        contract,
        robustness,
        pd.DataFrame([
            {"gate": "PARENT_LINEAGE_REPRODUCED", "passed": lineage_ok, "detail": f"v69_delta_pp={v69_lineage_delta:.6f};v79_delta_pp={v79_lineage_delta:.6f}"},
            {"gate": "V69_AND_V79_FEEDBACK_ARE_INDEPENDENT", "passed": no_cross_family, "detail": "proposal generation only reads same-family own outcomes"},
            {"gate": "ONE_FOLD_DELAYED_PROMOTION", "passed": delayed, "detail": "candidate result in year Y can only affect active strategy from year Y+1"},
            {"gate": "PURGED_MATURED_OUTCOME_ONLY", "passed": bool((pd.to_datetime(folds["evidence_cutoff"]) < pd.to_datetime(folds["test_start"])).all()), "detail": f"purge={cfg['feedback']['purge_sessions']} sessions"},
            {"gate": "NO_THEME_OR_TICKER_SPECIFIC_RULE", "passed": generic["passed"], "detail": json.dumps(generic)},
            {"gate": "NO_NEGATIVE_CASH", "passed": all(v["negative_cash_days"] == 0 for v in audits.values()), "detail": f"strategies={len(audits)}"},
            {"gate": "LIVE_EXECUTION_BLOCKED", "passed": cfg["live_execution_allowed"] is False, "detail": "research and paper shadow only"},
        ])
    ], ignore_index=True)

    for name, frame in targets.items():
        frame.to_csv(out / f"v83_target_{name.lower()}.csv", index=False)
    for family, frame in adaptive_targets.items():
        frame.to_csv(out / f"v83_adaptive_target_{family.lower()}.csv", index=False)
    for name, frame in outcomes.items():
        frame.to_csv(out / f"v83_own_outcomes_{name.lower()}.csv", index=False)
    metrics.sort_values("return_pct", ascending=False).to_csv(out / "v83_strategy_metrics.csv", index=False)
    folds.to_csv(out / "v83_walk_forward_proposals_and_promotions.csv", index=False)
    issues.to_csv(out / "v83_self_issue_scores.csv", index=False)
    quality.to_csv(out / "v83_quality_gates.csv", index=False)
    _annual_returns(nav_map, cfg77.initial_capital_krw).to_csv(out / "v83_annual_returns.csv", index=False)
    _monthly_returns_2026(nav_map, cfg77.initial_capital_krw).to_csv(out / "v83_2026_monthly_returns.csv", index=False)
    market["source_audit"].to_csv(out / "v83_data_source_audit.csv", index=False)

    parent_rows = metrics[metrics["scenario"].isin(["V69_PARENT", "V79_PARENT", "V83_V69_INDEPENDENT_SELF_RESEARCH", "V83_V79_INDEPENDENT_SELF_RESEARCH"])].copy()
    decision = {
        "status": "v83_independent_self_research_backtest_complete_live_blocked",
        "quality_gates_passed": bool(quality["passed"].all()),
        "official_champion_unchanged": CONTROL,
        "official_challenger_unchanged": CHALLENGER,
        "automatic_registry_change": False,
        "live_allowed": False,
    }
    (out / "v83_decision.json").write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = [
        "# V83 독립 자기연구형 FeedbackAgent", "",
        "- V69는 V69 자신의 거래만 분석한다.",
        "- V79는 V79 자신의 거래만 분석한다.",
        "- 다른 전략의 최근 성과를 보고 알파를 복제하지 않는다.",
        "- 오류 유형은 고정 후보 라이브러리의 한 가지 변경안으로만 연결된다.",
        "- 후보는 다음 연도 Shadow에서 검증되고, 승격되어도 그 다음 연도부터 적용된다.", "",
        "## 핵심 성과", "", parent_rows.to_markdown(index=False), "",
        "## Walk-forward 제안 및 승격", "", folds.to_markdown(index=False), "",
        "## 품질 게이트", "", quality.to_markdown(index=False),
    ]
    (out / "V83_KOREAN_SUMMARY.md").write_text("\n".join(summary), encoding="utf-8")
    return decision
