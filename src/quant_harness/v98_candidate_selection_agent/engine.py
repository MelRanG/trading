from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any
import json

import numpy as np
import pandas as pd
import yaml

from quant_harness.v69_dynamic_theme_leadership import engine as v69
from quant_harness.v77_corrected_price_allocation import engine as v77
from quant_harness.v77_2_validation_integrity.engine import _slice_metrics
from quant_harness.v79_generic_trend_sleeve import engine as v79
from quant_harness.v94_universe_agent import engine as v94
from quant_harness.v98_candidate_selection_agent.policy import (
    ACTIVE_SELECTION_POLICY,
    CROSS_HORIZON_CONSENSUS,
    UNCERTAINTY_AWARE_ROTATION,
    build_sector_representative_panel,
    prepare_selection_features,
    taxonomy_hash,
    validate_taxonomy,
)

REPORT = "v98_candidate_selection_agent"
V98_SELECTION_POLICIES = (ACTIVE_SELECTION_POLICY, CROSS_HORIZON_CONSENSUS, UNCERTAINTY_AWARE_ROTATION)


def _load_config(root: Path) -> dict[str, Any]:
    return yaml.safe_load((root / "config/v98_candidate_selection_agent.yaml").read_text(encoding="utf-8"))


def _policy_params(cfg: dict[str, Any], policy: str) -> dict[str, Any]:
    for row in cfg.get("research_candidates", []):
        if row["policy_id"] == policy:
            return {k: v for k, v in row.items() if k != "policy_id"}
    return {}


def _execute_pair(
    root: Path,
    market: dict[str, Any],
    universe: pd.DataFrame,
    cfg69: v69.V69Config,
    cfg79: dict[str, Any],
    policy: str,
    params: dict[str, Any],
) -> dict[str, Any]:
    f69 = v94._strict_v69_features(market["close"], market["value"], universe, cfg69)
    f79 = v94._strict_v79_features(market["close"], market["value"], universe, cfg79)
    index = market["close"].index
    monthly, weekly = v69._review_dates(index)

    sf69 = prepare_selection_features(f69, family="V69", policy=policy, **{
        k: v for k, v in params.items() if k in {"consensus_min_rank", "consensus_required_horizons", "dispersion_penalty"}
    })
    sf79 = prepare_selection_features(f79, family="V79", policy=policy, **{
        k: v for k, v in params.items() if k in {"consensus_min_rank", "consensus_required_horizons", "dispersion_penalty"}
    })
    sector69 = build_sector_representative_panel(
        index, monthly, universe, sf69["selection_score"], sf69["selection_eligible"], sf69["liquidity"]
    )
    sector79 = build_sector_representative_panel(
        index, weekly, universe, sf79["selection_score"], sf79["selection_eligible"], sf79["liquidity"]
    )

    sel69 = v69.select_dynamic_leader(
        index, universe, f69, cfg69, selection_policy=policy, selection_policy_params=params,
    )
    sel69["target_leader_weight"] = sel69["leader_ticker"].notna().astype(float) * 0.80
    cfg77 = v77._load_config(root)
    account69, orders69, audit69 = v77.execute(
        market["close"], market["open"], market["adv20_d1"], sel69,
        cfg69.core_ticker, 10_000_000.0, "FROM_SELECTION", "DAILY_EXACT", cfg77.base_execution,
    )
    stress69, _, _ = v77.execute(
        market["close"], market["open"], market["adv20_d1"], sel69,
        cfg69.core_ticker, 10_000_000.0, "FROM_SELECTION", "DAILY_EXACT", cfg77.stress_execution,
    )

    sleeve = v79.select_persistent_trend_leader(
        index, universe, f79,
        minimum_hold_sessions=int(cfg79["minimum_hold_sessions"]),
        challenger_score_margin=float(cfg79["challenger_score_margin"]),
        confirmation_reviews=int(cfg79["challenger_confirmation_reviews"]),
        selection_policy=policy,
        selection_policy_params=params,
    )
    ledger79 = v79.build_blended_target_ledger(sel69, sleeve, core_ticker=cfg69.core_ticker, base_share=0.70)
    account79, orders79, audit79 = v79.execute_multi_target(
        market["close"], market["open"], market["adv20_d1"], ledger79,
        initial_capital=10_000_000.0, spec=cfg77.base_execution,
        rebalance_band=0.05, scenario=f"V79_{policy}",
    )
    stress79, _, _ = v79.execute_multi_target(
        market["close"], market["open"], market["adv20_d1"], ledger79,
        initial_capital=10_000_000.0, spec=cfg77.stress_execution,
        rebalance_band=0.05, scenario=f"V79_{policy}_STRESS",
    )
    return {
        "features69": f69, "features79": f79,
        "selection_features69": sf69, "selection_features79": sf79,
        "sector69": sector69, "sector79": sector79,
        "selection69": sel69, "selection79": sleeve, "ledger79": ledger79,
        "account69": account69, "orders69": orders69, "audit69": audit69, "stress69": stress69,
        "account79": account79, "orders79": orders79, "audit79": audit79, "stress79": stress79,
    }


def _metric_row(strategy: str, policy: str, account: pd.DataFrame, orders: pd.DataFrame, stress: pd.DataFrame) -> dict[str, Any]:
    initial = 10_000_000.0
    nav = account.set_index("date")["nav_krw"]
    stress_nav = stress.set_index("date")["nav_krw"]
    row: dict[str, Any] = {"strategy": strategy, "policy": policy, **v69._metrics(nav, initial)}
    for name, (start, end) in {
        "development": ("2018-01-01", "2022-12-31"),
        "validation": ("2023-01-01", "2024-12-31"),
        "observed": ("2025-01-01", "2026-07-03"),
        "recent_1y": ("2025-07-04", "2026-07-03"),
    }.items():
        metrics = _slice_metrics(nav, start, end, initial)
        row[f"{name}_return_pct"] = metrics["return_pct"]
        row[f"{name}_mdd_pct"] = metrics["mdd_pct"]
    row["stress_return_pct"] = float((stress_nav.iloc[-1] / initial - 1.0) * 100.0)
    row["ending_nav_krw"] = float(nav.iloc[-1])
    row["order_count"] = int(len(orders))
    row["total_fee_krw"] = float(pd.to_numeric(orders.get("fee_krw", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
    return row


def _annual_returns(runs: dict[str, dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for policy, payload in runs.items():
        for strategy, key in (("V69", "account69"), ("V79", "account79")):
            nav = payload[key].set_index("date")["nav_krw"]
            for year, values in nav.groupby(nav.index.year):
                rows.append({
                    "policy": policy, "strategy": strategy, "year": int(year),
                    "return_pct": float((values.iloc[-1] / values.iloc[0] - 1.0) * 100.0),
                })
    return pd.DataFrame(rows)


def _monthly_2026(runs: dict[str, dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for policy, payload in runs.items():
        for strategy, key in (("V69", "account69"), ("V79", "account79")):
            nav = payload[key].set_index("date")["nav_krw"]
            sample = nav[nav.index.year == 2026]
            for month, values in sample.groupby(sample.index.month):
                rows.append({
                    "policy": policy, "strategy": strategy, "month": int(month),
                    "return_pct": float((values.iloc[-1] / values.iloc[0] - 1.0) * 100.0),
                })
    return pd.DataFrame(rows)


def _fwd_return(close: pd.DataFrame, date: pd.Timestamp, ticker: Any, horizon: int) -> float:
    if ticker is None or pd.isna(ticker) or str(ticker) not in close.columns:
        return np.nan
    pos = close.index.get_indexer([date])[0]
    if pos < 0 or pos + horizon >= len(close):
        return np.nan
    a = close.iloc[pos][str(ticker)]
    b = close.iloc[pos + horizon][str(ticker)]
    if pd.isna(a) or pd.isna(b) or float(a) <= 0:
        return np.nan
    return float(b / a - 1.0)


def _decision_quality(runs: dict[str, dict[str, Any]], close: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for policy, payload in runs.items():
        for strategy, key, ticker_col, review_col in (
            ("V69", "selection69", "leader_ticker", "review_monthly"),
            ("V79", "selection79", "sleeve_ticker", "review_weekly"),
        ):
            selection = payload[key].copy()
            reviews = selection[selection[review_col].astype(bool)].copy()
            reviews["previous_selected"] = reviews[ticker_col].shift(1)
            for horizon in (20, 60):
                selected_ret = reviews.apply(lambda r: _fwd_return(close, r["date"], r[ticker_col], horizon), axis=1)
                runner_ret = reviews.apply(lambda r: _fwd_return(close, r["date"], r.get("runner_up_ticker"), horizon), axis=1)
                old_ret = reviews.apply(lambda r: _fwd_return(close, r["date"], r.get("previous_selected"), horizon), axis=1)
                valid_runner = selected_ret.notna() & runner_ret.notna()
                changed = reviews[ticker_col].fillna("").ne(reviews["previous_selected"].fillna(""))
                valid_old = selected_ret.notna() & old_ret.notna() & changed
                rows.append({
                    "policy": policy,
                    "strategy": strategy,
                    "horizon_days": horizon,
                    "review_count": int(len(reviews)),
                    "selection_changed_reviews": int(changed.sum()),
                    "mature_selected_runner_events": int(valid_runner.sum()),
                    "selected_minus_runner_mean_pp": float((selected_ret[valid_runner] - runner_ret[valid_runner]).mean() * 100.0) if valid_runner.any() else np.nan,
                    "selected_beats_runner_rate": float((selected_ret[valid_runner] > runner_ret[valid_runner]).mean()) if valid_runner.any() else np.nan,
                    "mature_rotation_events": int(valid_old.sum()),
                    "selected_minus_old_mean_pp": float((selected_ret[valid_old] - old_ret[valid_old]).mean() * 100.0) if valid_old.any() else np.nan,
                    "selected_beats_old_rate": float((selected_ret[valid_old] > old_ret[valid_old]).mean()) if valid_old.any() else np.nan,
                    "median_top_runner_gap": float(pd.to_numeric(reviews["top_runner_gap_d1"], errors="coerce").median()),
                    "median_effective_rotation_margin": float(pd.to_numeric(reviews["effective_rotation_margin_d1"], errors="coerce").median()),
                })
    return pd.DataFrame(rows)


def _future_mutation_invariant(
    market: dict[str, Any], universe: pd.DataFrame, cfg69: v69.V69Config, cfg79: dict[str, Any],
    policy: str, params: dict[str, Any],
) -> tuple[bool, str]:
    cutoff = pd.Timestamp("2024-12-31")
    f69 = v94._strict_v69_features(market["close"], market["value"], universe, cfg69)
    f79 = v94._strict_v79_features(market["close"], market["value"], universe, cfg79)
    base69 = v69.select_dynamic_leader(market["close"].index, universe, f69, cfg69, selection_policy=policy, selection_policy_params=params)
    base79 = v79.select_persistent_trend_leader(
        market["close"].index, universe, f79,
        minimum_hold_sessions=int(cfg79["minimum_hold_sessions"]),
        challenger_score_margin=float(cfg79["challenger_score_margin"]),
        confirmation_reviews=int(cfg79["challenger_confirmation_reviews"]),
        selection_policy=policy, selection_policy_params=params,
    )
    changed_close = market["close"].copy()
    changed_value = market["value"].copy()
    future = changed_close.index > cutoff
    tickers = universe["ticker"].astype(str).tolist()
    changed_close.loc[future, tickers] *= 1.83
    changed_value.loc[future, tickers] *= 0.43
    cf69 = v94._strict_v69_features(changed_close, changed_value, universe, cfg69)
    cf79 = v94._strict_v79_features(changed_close, changed_value, universe, cfg79)
    changed69 = v69.select_dynamic_leader(changed_close.index, universe, cf69, cfg69, selection_policy=policy, selection_policy_params=params)
    changed79 = v79.select_persistent_trend_leader(
        changed_close.index, universe, cf79,
        minimum_hold_sessions=int(cfg79["minimum_hold_sessions"]),
        challenger_score_margin=float(cfg79["challenger_score_margin"]),
        confirmation_reviews=int(cfg79["challenger_confirmation_reviews"]),
        selection_policy=policy, selection_policy_params=params,
    )
    c69 = ["date", "leader_ticker", "decision_reason"]
    c79 = ["date", "sleeve_ticker", "decision_reason"]
    same69 = base69.loc[base69["date"].le(cutoff), c69].reset_index(drop=True).equals(changed69.loc[changed69["date"].le(cutoff), c69].reset_index(drop=True))
    same79 = base79.loc[base79["date"].le(cutoff), c79].reset_index(drop=True).equals(changed79.loc[changed79["date"].le(cutoff), c79].reset_index(drop=True))
    return bool(same69 and same79), f"policy={policy} cutoff={cutoff.date()}"


def _promotion_decision(
    metrics: pd.DataFrame,
    quality: pd.DataFrame,
    runs: dict[str, dict[str, Any]],
    cfg: dict[str, Any],
) -> pd.DataFrame:
    parent = metrics[metrics["policy"].eq(ACTIVE_SELECTION_POLICY)].set_index("strategy")
    qparent = quality[quality["policy"].eq(ACTIVE_SELECTION_POLICY)].set_index(["strategy", "horizon_days"])
    p = cfg["promotion"]
    rows: list[dict[str, Any]] = []
    for policy in V98_SELECTION_POLICIES:
        if policy == ACTIVE_SELECTION_POLICY:
            continue
        candidate = metrics[metrics["policy"].eq(policy)].set_index("strategy")
        qcand = quality[quality["policy"].eq(policy)].set_index(["strategy", "horizon_days"])
        family_pass: dict[str, bool] = {}
        for strategy, ticker_col, selection_key, review_col in (
            ("V69", "leader_ticker", "selection69", "review_monthly"),
            ("V79", "sleeve_ticker", "selection79", "review_weekly"),
        ):
            base_sel = runs[ACTIVE_SELECTION_POLICY][selection_key]
            cand_sel = runs[policy][selection_key]
            validation = base_sel["date"].between(pd.Timestamp("2023-01-01"), pd.Timestamp("2024-12-31")) & base_sel[review_col].astype(bool)
            changed_validation = int(
                cand_sel.loc[validation, ticker_col].fillna("").reset_index(drop=True).ne(
                    base_sel.loc[validation, ticker_col].fillna("").reset_index(drop=True)
                ).sum()
            )
            gates = {
                "development_noninferior": candidate.loc[strategy, "development_return_pct"] >= parent.loc[strategy, "development_return_pct"] - float(p["development_return_tolerance_pp"]),
                "validation_improves": candidate.loc[strategy, "validation_return_pct"] >= parent.loc[strategy, "validation_return_pct"] + float(p["validation_improvement_min_pp"]),
                "recent1y_noninferior": candidate.loc[strategy, "recent_1y_return_pct"] >= parent.loc[strategy, "recent_1y_return_pct"] - float(p["recent_1y_return_tolerance_pp"]),
                "stress_noninferior": candidate.loc[strategy, "stress_return_pct"] >= parent.loc[strategy, "stress_return_pct"] - float(p["stress_return_tolerance_pp"]),
                "mdd_within_tolerance": candidate.loc[strategy, "mdd_pct"] >= parent.loc[strategy, "mdd_pct"] - float(p["mdd_tolerance_pp"]),
                "turnover_bounded": candidate.loc[strategy, "order_count"] <= parent.loc[strategy, "order_count"] * float(p["order_count_ratio_max"]),
                "validation_has_changed_evidence": changed_validation >= int(p["minimum_changed_reviews_validation"]),
                "selection_edge_20d_noninferior": qcand.loc[(strategy, 20), "selected_minus_runner_mean_pp"] >= qparent.loc[(strategy, 20), "selected_minus_runner_mean_pp"] - float(p["selection_edge_20d_tolerance_pp"]),
                "selection_edge_60d_noninferior": qcand.loc[(strategy, 60), "selected_minus_runner_mean_pp"] >= qparent.loc[(strategy, 60), "selected_minus_runner_mean_pp"] - float(p["selection_edge_60d_tolerance_pp"]),
            }
            passed = bool(all(gates.values()))
            observed_supported = (
                candidate.loc[strategy, "return_pct"] > parent.loc[strategy, "return_pct"]
                and candidate.loc[strategy, "observed_return_pct"] > parent.loc[strategy, "observed_return_pct"]
                and candidate.loc[strategy, "recent_1y_return_pct"] > parent.loc[strategy, "recent_1y_return_pct"]
                and candidate.loc[strategy, "stress_return_pct"] > parent.loc[strategy, "stress_return_pct"]
                and candidate.loc[strategy, "mdd_pct"] >= parent.loc[strategy, "mdd_pct"] - float(p["mdd_tolerance_pp"])
            )
            forward_shadow_only = bool(not passed and observed_supported and changed_validation < int(p["minimum_changed_reviews_validation"]))
            family_pass[strategy] = passed
            rows.append({
                "policy": policy, "strategy": strategy, "promoted": passed,
                "forward_shadow_only": forward_shadow_only,
                "status": "PROMOTED" if passed else ("FORWARD_SHADOW_ONLY" if forward_shadow_only else "BACKTEST_REJECTED"),
                "changed_reviews_validation": changed_validation,
                **gates,
                "full_delta_pp": float(candidate.loc[strategy, "return_pct"] - parent.loc[strategy, "return_pct"]),
                "development_delta_pp": float(candidate.loc[strategy, "development_return_pct"] - parent.loc[strategy, "development_return_pct"]),
                "validation_delta_pp": float(candidate.loc[strategy, "validation_return_pct"] - parent.loc[strategy, "validation_return_pct"]),
                "observed_delta_pp": float(candidate.loc[strategy, "observed_return_pct"] - parent.loc[strategy, "observed_return_pct"]),
                "recent1y_delta_pp": float(candidate.loc[strategy, "recent_1y_return_pct"] - parent.loc[strategy, "recent_1y_return_pct"]),
                "stress_delta_pp": float(candidate.loc[strategy, "stress_return_pct"] - parent.loc[strategy, "stress_return_pct"]),
                "mdd_delta_pp": float(candidate.loc[strategy, "mdd_pct"] - parent.loc[strategy, "mdd_pct"]),
                "order_count_delta": int(candidate.loc[strategy, "order_count"] - parent.loc[strategy, "order_count"]),
            })
    return pd.DataFrame(rows)


def run(root: Path | str) -> dict[str, Any]:
    root = Path(root)
    out = root / "reports" / REPORT
    out.mkdir(parents=True, exist_ok=True)
    cfg = _load_config(root)
    cfg77 = v77._load_config(root)
    market = v77.load_adjusted_market(root, cfg77)
    cfg69 = replace(
        v69._load_config(root), end_date=cfg77.end_date,
        core_ticker=cfg77.core_ticker, benchmark_ticker=cfg77.benchmark_ticker,
        leader_weight=0.80,
    )
    universe = v69._load_universe(root, cfg69)
    cfg79 = v79._load_config(root)["trend_sleeve"]
    taxonomy = validate_taxonomy(universe)

    runs = {
        policy: _execute_pair(root, market, universe, cfg69, cfg79, policy, _policy_params(cfg, policy))
        for policy in V98_SELECTION_POLICIES
    }
    metrics = pd.DataFrame([
        _metric_row(strategy, policy, payload[f"account{69 if strategy == 'V69' else 79}"], payload[f"orders{69 if strategy == 'V69' else 79}"], payload[f"stress{69 if strategy == 'V69' else 79}"])
        for policy, payload in runs.items() for strategy in ("V69", "V79")
    ])
    annual = _annual_returns(runs)
    monthly = _monthly_2026(runs)
    decision_quality = _decision_quality(runs, market["close"])
    promotion = _promotion_decision(metrics, decision_quality, runs, cfg)

    parent_reference = pd.read_csv(root / "reports/v96_market_regime_extension/v96_strategy_metrics.csv")
    parent_reference = parent_reference[parent_reference["policy"].eq("D1_MA120_EXPLICIT")].set_index("strategy")
    active = metrics[metrics["policy"].eq(ACTIVE_SELECTION_POLICY)].set_index("strategy")
    invariants = []
    for policy in V98_SELECTION_POLICIES:
        ok, detail = _future_mutation_invariant(market, universe, cfg69, cfg79, policy, _policy_params(cfg, policy))
        invariants.append({"policy": policy, "passed": ok, "detail": detail})
    invariant_df = pd.DataFrame(invariants)

    quality_rows = [
        {"gate": "taxonomy_valid_after_merge", "passed": bool(taxonomy["valid"]), "detail": json.dumps(taxonomy, sort_keys=True)},
        {"gate": "sector_theme_agent_merged_into_candidate_selection", "passed": True, "detail": "sector de-duplication is a deterministic CandidateSelection sub-policy"},
        {"gate": "active_v69_parent_nav_exact", "passed": bool(np.isclose(active.loc["V69", "ending_nav_krw"], parent_reference.loc["V69", "ending_nav_krw"], atol=0.01)), "detail": f"delta={active.loc['V69','ending_nav_krw']-parent_reference.loc['V69','ending_nav_krw']:.6f}"},
        {"gate": "active_v79_parent_nav_exact", "passed": bool(np.isclose(active.loc["V79", "ending_nav_krw"], parent_reference.loc["V79", "ending_nav_krw"], atol=0.01)), "detail": f"delta={active.loc['V79','ending_nav_krw']-parent_reference.loc['V79','ending_nav_krw']:.6f}"},
        {"gate": "all_policies_future_mutation_invariant", "passed": bool(invariant_df["passed"].all()), "detail": "; ".join(invariant_df["detail"].tolist())},
        {"gate": "all_information_cutoffs_d1", "passed": bool(all(not payload["selection69"]["decision_uses_same_day_close"].any() and not payload["selection79"]["decision_uses_same_day_close"].any() for payload in runs.values())), "detail": "selection ledgers"},
        {"gate": "no_negative_cash_v69", "passed": bool(all(payload["account69"]["cash_krw"].min() >= -0.01 for payload in runs.values())), "detail": "all policies"},
        {"gate": "no_negative_cash_v79", "passed": bool(all(payload["account79"]["cash_krw"].min() >= -0.01 for payload in runs.values())), "detail": "all policies"},
        {"gate": "live_execution_blocked", "passed": bool(not cfg.get("live_execution_allowed", False)), "detail": "research only"},
    ]
    quality = pd.DataFrame(quality_rows)

    metrics.to_csv(out / "v98_strategy_metrics.csv", index=False)
    annual.to_csv(out / "v98_annual_returns.csv", index=False)
    monthly.to_csv(out / "v98_2026_monthly_returns.csv", index=False)
    decision_quality.to_csv(out / "v98_decision_quality.csv", index=False)
    promotion.to_csv(out / "v98_candidate_promotion.csv", index=False)
    invariant_df.to_csv(out / "v98_future_mutation_invariants.csv", index=False)
    quality.to_csv(out / "v98_quality_gates.csv", index=False)
    pd.DataFrame([taxonomy]).to_csv(out / "v98_taxonomy_audit.csv", index=False)
    for policy, payload in runs.items():
        payload["selection69"].to_csv(out / f"v98_selection_v69_{policy}.csv", index=False)
        payload["selection79"].to_csv(out / f"v98_selection_v79_{policy}.csv", index=False)

    registry = {
        "version": "V98",
        "active_policy": ACTIVE_SELECTION_POLICY,
        "sector_representation_policy": "STATIC_TOP_SCORE_EXPLICIT",
        "sector_theme_agent_merged": True,
        "taxonomy_hash": taxonomy_hash(universe),
        "candidates": promotion.to_dict(orient="records"),
        "parent_strategies_changed": bool(promotion["promoted"].any()),
        "automatic_parent_mutation": False,
        "live_execution_allowed": False,
    }
    (out / "v98_candidate_selection_registry.json").write_text(
        json.dumps(registry, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )

    if not quality["passed"].all():
        failed = quality.loc[~quality["passed"], "gate"].tolist()
        raise AssertionError(f"V98 quality gates failed: {failed}")
    return {
        "metrics": metrics,
        "annual": annual,
        "monthly": monthly,
        "decision_quality": decision_quality,
        "promotion": promotion,
        "quality": quality,
        "taxonomy": taxonomy,
        "runs": runs,
    }
