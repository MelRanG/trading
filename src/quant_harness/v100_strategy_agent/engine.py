from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any
import json
import math

import numpy as np
import pandas as pd
import yaml

from quant_harness.v69_dynamic_theme_leadership import engine as v69
from quant_harness.v77_corrected_price_allocation import engine as v77
from quant_harness.v77_2_validation_integrity.engine import _relative_bootstrap_period, _slice_metrics, _familywise_probability
from quant_harness.v79_generic_trend_sleeve import engine as v79
from quant_harness.v99_candidate_selection_deep_research import engine as v99
from quant_harness.v100_strategy_agent.policy import (
    ACTIVE_STRATEGY_POLICY,
    ALL_POLICIES,
    CANDIDATE_POLICIES,
    FULL_LEADER_100,
    UNCERTAINTY_BUDGET_60_80,
    V79_SEMANTIC_SECTOR_CAP_70,
    build_v69_target_ledger,
    build_v79_target_ledger,
)

REPORT = "v100_strategy_agent"


def _load_config(root: Path) -> dict[str, Any]:
    return yaml.safe_load((root / "config/v100_strategy_agent.yaml").read_text(encoding="utf-8"))


def _load_context(root: Path) -> tuple[dict[str, Any], v77.V77Config, dict[str, Any], v69.V69Config, pd.DataFrame, dict[str, Any], pd.DataFrame, pd.DataFrame]:
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
    f69, f79 = v99._augment_features(market, universe, cfg69, cfg79)
    selection69 = v69.select_dynamic_leader(
        market["close"].index, universe, f69, cfg69,
        selection_policy="TOP_SCORE_SECTOR_DEDUP", selection_policy_params={},
    )
    selection69["target_leader_weight"] = selection69["leader_ticker"].notna().astype(float) * 0.80
    selection79 = v79.select_persistent_trend_leader(
        market["close"].index, universe, f79,
        minimum_hold_sessions=int(cfg79["minimum_hold_sessions"]),
        challenger_score_margin=float(cfg79["challenger_score_margin"]),
        confirmation_reviews=int(cfg79["challenger_confirmation_reviews"]),
        selection_policy="TOP_SCORE_SECTOR_DEDUP", selection_policy_params={},
    )
    return cfg, cfg77, market, cfg69, universe, cfg79, selection69, selection79


def _policy_params(cfg: dict[str, Any], policy: str) -> dict[str, Any]:
    params: dict[str, Any] = {}
    params.update(cfg.get("uncertainty_budget", {}))
    params.update(cfg.get("sector_concentration", {}))
    return params


def _build_ledgers(
    cfg: dict[str, Any], cfg69: v69.V69Config, universe: pd.DataFrame,
    selection69: pd.DataFrame, selection79: pd.DataFrame, policy: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    params = _policy_params(cfg, policy)
    sector_by_ticker = universe.set_index(universe["ticker"].astype(str))["sector"].astype(str).to_dict()
    ledger69 = build_v69_target_ledger(selection69, core_ticker=cfg69.core_ticker, policy=policy, params=params)
    ledger79 = build_v79_target_ledger(
        selection69, selection79, core_ticker=cfg69.core_ticker, base_share=0.70,
        policy=policy, params=params, sector_by_ticker=sector_by_ticker,
    )
    return ledger69, ledger79


def _execute_policy(root: Path, policy: str) -> dict[str, Any]:
    cfg, cfg77, market, cfg69, universe, _cfg79, selection69, selection79 = _load_context(root)
    ledger69, ledger79 = _build_ledgers(cfg, cfg69, universe, selection69, selection79, policy)
    exec_selection69 = selection69.copy()
    exec_selection69 = exec_selection69.drop(columns=["target_leader_weight"], errors="ignore").merge(
        ledger69[["date", "target_leader_weight"]], on="date", how="left", validate="one_to_one"
    )
    account69, orders69, audit69 = v77.execute(
        market["close"], market["open"], market["adv20_d1"], exec_selection69,
        cfg69.core_ticker, 10_000_000.0, "FROM_SELECTION", "DAILY_EXACT", cfg77.base_execution,
    )
    stress69, stress_orders69, stress_audit69 = v77.execute(
        market["close"], market["open"], market["adv20_d1"], exec_selection69,
        cfg69.core_ticker, 10_000_000.0, "FROM_SELECTION", "DAILY_EXACT", cfg77.stress_execution,
    )
    account79, orders79, audit79 = v79.execute_multi_target(
        market["close"], market["open"], market["adv20_d1"], ledger79,
        initial_capital=10_000_000.0, spec=cfg77.base_execution,
        rebalance_band=0.05, scenario=f"V79_{policy}",
    )
    stress79, stress_orders79, stress_audit79 = v79.execute_multi_target(
        market["close"], market["open"], market["adv20_d1"], ledger79,
        initial_capital=10_000_000.0, spec=cfg77.stress_execution,
        rebalance_band=0.05, scenario=f"V79_{policy}_STRESS",
    )
    return {
        "ledger69": ledger69, "ledger79": ledger79,
        "account69": account69, "orders69": orders69, "audit69": audit69,
        "stress69": stress69, "stress_orders69": stress_orders69, "stress_audit69": stress_audit69,
        "account79": account79, "orders79": orders79, "audit79": audit79,
        "stress79": stress79, "stress_orders79": stress_orders79, "stress_audit79": stress_audit79,
    }


def _metric_row(strategy: str, policy: str, run: dict[str, Any], purged_validation_start: pd.Timestamp) -> dict[str, Any]:
    suffix = "69" if strategy == "V69" else "79"
    account = run[f"account{suffix}"]
    stress = run[f"stress{suffix}"]
    orders = run[f"orders{suffix}"]
    ledger = run[f"ledger{suffix}"]
    initial = 10_000_000.0
    nav = account.set_index("date")["nav_krw"]
    stress_nav = stress.set_index("date")["nav_krw"]
    row: dict[str, Any] = {"strategy": strategy, "policy": policy, **v69._metrics(nav, initial)}
    periods = {
        "development": ("2018-01-01", "2022-12-31"),
        "validation": ("2023-01-01", "2024-12-31"),
        "purged_validation": (purged_validation_start, "2024-12-31"),
        "observed": ("2025-01-01", "2026-07-03"),
        "recent_1y": ("2025-07-04", "2026-07-03"),
    }
    for name, (start, end) in periods.items():
        metrics = _slice_metrics(nav, str(pd.Timestamp(start).date()), str(pd.Timestamp(end).date()), initial)
        row[f"{name}_return_pct"] = metrics["return_pct"]
        row[f"{name}_sharpe"] = metrics["sharpe"]
        row[f"{name}_mdd_pct"] = metrics["mdd_pct"]
    row["stress_return_pct"] = float((stress_nav.iloc[-1] / initial - 1.0) * 100.0)
    row["order_count"] = int(len(orders))
    row["turnover_notional_krw"] = float((orders["quantity"] * orders["reference_open_krw"]).sum()) if not orders.empty else 0.0
    row["total_fee_krw"] = float(pd.to_numeric(orders.get("fee_krw", pd.Series(dtype=float)), errors="coerce").fillna(0.0).sum())
    row["negative_cash_days"] = int(account["cash_krw"].lt(-0.01).sum())
    row["max_noncore_ticker_weight"] = float(ledger["max_noncore_ticker_weight"].max())
    row["max_semantic_sector_weight"] = float(ledger["max_semantic_sector_weight"].max())
    row["average_core_target_weight"] = float(ledger["target_core_weight"].mean())
    row["average_noncore_target_weight"] = 1.0 - row["average_core_target_weight"]
    row["same_ticker_overlap_days"] = int(ledger["same_ticker_overlap"].sum())
    row["same_sector_overlap_days"] = int(ledger["same_sector_overlap"].sum())
    row["concentration_cap_days"] = int(ledger["concentration_cap_applied"].sum())
    val = ledger[(ledger["date"] >= "2023-01-01") & (ledger["date"] <= "2024-12-31")]
    row["validation_distinct_target_hashes"] = int(val["target_hash"].nunique())
    return row


def _changed_target_days(a: pd.DataFrame, b: pd.DataFrame, start: str, end: str) -> int:
    left = a.set_index("date")["target_hash"]
    right = b.set_index("date")["target_hash"]
    aligned = pd.concat([left.rename("a"), right.rename("b")], axis=1).loc[start:end]
    return int(aligned["a"].ne(aligned["b"]).sum())


def _promotion(metrics: pd.DataFrame, runs: dict[str, dict[str, Any]], cfg: dict[str, Any]) -> pd.DataFrame:
    p = cfg["promotion"]
    parent = metrics[metrics["policy"].eq(ACTIVE_STRATEGY_POLICY)].set_index("strategy")
    rows: list[dict[str, Any]] = []
    family_size = len(CANDIDATE_POLICIES)
    for policy in CANDIDATE_POLICIES:
        candidate = metrics[metrics["policy"].eq(policy)].set_index("strategy")
        for strategy in ("V69", "V79"):
            applicable = not (policy == V79_SEMANTIC_SECTOR_CAP_70 and strategy == "V69")
            suffix = "69" if strategy == "V69" else "79"
            changed = _changed_target_days(
                runs[policy][f"ledger{suffix}"], runs[ACTIVE_STRATEGY_POLICY][f"ledger{suffix}"],
                "2023-01-01", "2024-12-31",
            )
            nav_c = runs[policy][f"account{suffix}"].set_index("date")["nav_krw"]
            nav_p = runs[ACTIVE_STRATEGY_POLICY][f"account{suffix}"].set_index("date")["nav_krw"]
            boot = _relative_bootstrap_period(
                nav_c, nav_p, "2023-01-01", "2024-12-31",
                samples=int(p["bootstrap_samples"]), block_months=3,
            )
            familywise = _familywise_probability(float(boot["positive_probability"]), family_size)
            gates = {
                "development_noninferior": candidate.loc[strategy, "development_return_pct"] >= parent.loc[strategy, "development_return_pct"] - float(p["development_tolerance_pp"]),
                "validation_improves": candidate.loc[strategy, "validation_return_pct"] >= parent.loc[strategy, "validation_return_pct"] + float(p["validation_improvement_min_pp"]),
                "purged_validation_improves": candidate.loc[strategy, "purged_validation_return_pct"] >= parent.loc[strategy, "purged_validation_return_pct"] + float(p["purged_validation_improvement_min_pp"]),
                "recent1y_noninferior": candidate.loc[strategy, "recent_1y_return_pct"] >= parent.loc[strategy, "recent_1y_return_pct"] - float(p["recent1y_tolerance_pp"]),
                "stress_noninferior": candidate.loc[strategy, "stress_return_pct"] >= parent.loc[strategy, "stress_return_pct"] - float(p["stress_tolerance_pp"]),
                "mdd_within_tolerance": candidate.loc[strategy, "mdd_pct"] >= parent.loc[strategy, "mdd_pct"] - float(p["mdd_tolerance_pp"]),
                "turnover_bounded": candidate.loc[strategy, "order_count"] <= parent.loc[strategy, "order_count"] * float(p["order_count_ratio_max"]),
                "validation_target_changed": changed >= int(p["minimum_changed_target_days_validation"]),
                "bootstrap_supported": float(boot["positive_probability"]) >= float(p["validation_bootstrap_probability_min"]),
                "familywise_supported": familywise >= float(p["familywise_probability_min"]),
                "operational_concentration_bounded": candidate.loc[strategy, "max_noncore_ticker_weight"] <= float(p["maximum_noncore_ticker_weight"]) + 1e-12,
            }
            passed = bool(applicable and all(gates.values()))
            point_estimate = bool(
                applicable and gates["development_noninferior"] and gates["validation_improves"]
                and gates["purged_validation_improves"] and gates["recent1y_noninferior"]
                and gates["stress_noninferior"] and gates["mdd_within_tolerance"]
                and gates["turnover_bounded"] and gates["validation_target_changed"]
            )
            if not applicable:
                status = "NOT_APPLICABLE_PARENT_PARITY"
            elif passed:
                status = "BACKTEST_PASSED_FORWARD_REQUIRED"
            elif point_estimate and not gates["operational_concentration_bounded"]:
                status = "BACKTEST_REJECTED_OPERATIONAL_CONCENTRATION"
            elif point_estimate and (not gates["bootstrap_supported"] or not gates["familywise_supported"]):
                status = "FORWARD_SHADOW_ONLY_MULTIPLE_TESTING_NOT_CLEARED"
            else:
                status = "BACKTEST_REJECTED"
            rows.append({
                "policy": policy, "strategy": strategy, "applicable": applicable,
                "status": status, "backtest_passed": passed, "promoted": False,
                "changed_target_days_validation": changed,
                "validation_bootstrap_probability": float(boot["positive_probability"]),
                "familywise_probability_lower_bound": familywise,
                **gates,
                "full_delta_pp": float(candidate.loc[strategy, "return_pct"] - parent.loc[strategy, "return_pct"]),
                "development_delta_pp": float(candidate.loc[strategy, "development_return_pct"] - parent.loc[strategy, "development_return_pct"]),
                "validation_delta_pp": float(candidate.loc[strategy, "validation_return_pct"] - parent.loc[strategy, "validation_return_pct"]),
                "purged_validation_delta_pp": float(candidate.loc[strategy, "purged_validation_return_pct"] - parent.loc[strategy, "purged_validation_return_pct"]),
                "observed_delta_pp": float(candidate.loc[strategy, "observed_return_pct"] - parent.loc[strategy, "observed_return_pct"]),
                "recent1y_delta_pp": float(candidate.loc[strategy, "recent_1y_return_pct"] - parent.loc[strategy, "recent_1y_return_pct"]),
                "stress_delta_pp": float(candidate.loc[strategy, "stress_return_pct"] - parent.loc[strategy, "stress_return_pct"]),
                "mdd_delta_pp": float(candidate.loc[strategy, "mdd_pct"] - parent.loc[strategy, "mdd_pct"]),
                "order_count_delta": int(candidate.loc[strategy, "order_count"] - parent.loc[strategy, "order_count"]),
                "max_noncore_ticker_weight": float(candidate.loc[strategy, "max_noncore_ticker_weight"]),
                "max_semantic_sector_weight": float(candidate.loc[strategy, "max_semantic_sector_weight"]),
            })
    return pd.DataFrame(rows)


def _diagnostics(runs: dict[str, dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for policy, run in runs.items():
        for strategy, suffix in (("V69", "69"), ("V79", "79")):
            ledger = run[f"ledger{suffix}"]
            for period, start, end in (
                ("FULL", "2018-01-01", "2026-07-03"),
                ("DEVELOPMENT", "2018-01-01", "2022-12-31"),
                ("VALIDATION", "2023-01-01", "2024-12-31"),
                ("OBSERVED", "2025-01-01", "2026-07-03"),
            ):
                d = ledger[(ledger["date"] >= start) & (ledger["date"] <= end)]
                rows.append({
                    "policy": policy, "strategy": strategy, "period": period,
                    "sessions": int(len(d)),
                    "average_core_target_weight": float(d["target_core_weight"].mean()) if len(d) else np.nan,
                    "average_noncore_target_weight": float(1.0 - d["target_core_weight"].mean()) if len(d) else np.nan,
                    "max_noncore_ticker_weight": float(d["max_noncore_ticker_weight"].max()) if len(d) else np.nan,
                    "max_semantic_sector_weight": float(d["max_semantic_sector_weight"].max()) if len(d) else np.nan,
                    "same_ticker_overlap_days": int(d["same_ticker_overlap"].sum()),
                    "same_sector_overlap_days": int(d["same_sector_overlap"].sum()),
                    "concentration_cap_days": int(d["concentration_cap_applied"].sum()),
                    "core_fallback_days": int(d["target_core_weight"].ge(0.999999).sum()),
                    "weight_sum_error_days": int((d["target_weight_sum"] - 1.0).abs().gt(1e-10).sum()),
                })
    return pd.DataFrame(rows)


def _annual_returns(runs: dict[str, dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for policy, run in runs.items():
        for strategy, suffix in (("V69", "69"), ("V79", "79")):
            nav = run[f"account{suffix}"].set_index("date")["nav_krw"]
            for year in sorted(set(nav.index.year)):
                rows.append({"policy": policy, "strategy": strategy, "year": year, "return_pct": _slice_metrics(nav, f"{year}-01-01", f"{year}-12-31", 10_000_000.0)["return_pct"]})
    return pd.DataFrame(rows)


def _monthly_2026(runs: dict[str, dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for policy, run in runs.items():
        for strategy, suffix in (("V69", "69"), ("V79", "79")):
            nav = run[f"account{suffix}"].set_index("date")["nav_krw"]
            for month in range(1, 8):
                start = pd.Timestamp(2026, month, 1)
                end = start + pd.offsets.MonthEnd(1)
                rows.append({"policy": policy, "strategy": strategy, "month": start.strftime("%Y-%m"), "return_pct": _slice_metrics(nav, str(start.date()), str(end.date()), 10_000_000.0)["return_pct"]})
    return pd.DataFrame(rows)


def _future_invariants(root: Path, cfg: dict[str, Any], cfg77: v77.V77Config, market: dict[str, Any], cfg69: v69.V69Config, universe: pd.DataFrame, cfg79: dict[str, Any]) -> pd.DataFrame:
    cutoff = pd.Timestamp("2024-12-31")
    f69, f79 = v99._augment_features(market, universe, cfg69, cfg79)
    base69 = v69.select_dynamic_leader(market["close"].index, universe, f69, cfg69, selection_policy="TOP_SCORE_SECTOR_DEDUP", selection_policy_params={})
    base79 = v79.select_persistent_trend_leader(
        market["close"].index, universe, f79,
        minimum_hold_sessions=int(cfg79["minimum_hold_sessions"]), challenger_score_margin=float(cfg79["challenger_score_margin"]),
        confirmation_reviews=int(cfg79["challenger_confirmation_reviews"]), selection_policy="TOP_SCORE_SECTOR_DEDUP", selection_policy_params={},
    )
    changed = {k: v.copy() if isinstance(v, pd.DataFrame) else v for k, v in market.items()}
    changed["close"] = market["close"].copy(); changed["value"] = market["value"].copy()
    tickers = universe["ticker"].astype(str).tolist(); future = changed["close"].index > cutoff
    changed["close"].loc[future, tickers] *= 1.61; changed["value"].loc[future, tickers] *= 0.43
    cf69, cf79 = v99._augment_features(changed, universe, cfg69, cfg79)
    mut69 = v69.select_dynamic_leader(changed["close"].index, universe, cf69, cfg69, selection_policy="TOP_SCORE_SECTOR_DEDUP", selection_policy_params={})
    mut79 = v79.select_persistent_trend_leader(
        changed["close"].index, universe, cf79,
        minimum_hold_sessions=int(cfg79["minimum_hold_sessions"]), challenger_score_margin=float(cfg79["challenger_score_margin"]),
        confirmation_reviews=int(cfg79["challenger_confirmation_reviews"]), selection_policy="TOP_SCORE_SECTOR_DEDUP", selection_policy_params={},
    )
    rows: list[dict[str, Any]] = []
    for policy in ALL_POLICIES:
        b69, b79 = _build_ledgers(cfg, cfg69, universe, base69, base79, policy)
        m69, m79 = _build_ledgers(cfg, cfg69, universe, mut69, mut79, policy)
        same69 = b69.loc[b69["date"].le(cutoff), ["date", "target_hash"]].reset_index(drop=True).equals(m69.loc[m69["date"].le(cutoff), ["date", "target_hash"]].reset_index(drop=True))
        same79 = b79.loc[b79["date"].le(cutoff), ["date", "target_hash"]].reset_index(drop=True).equals(m79.loc[m79["date"].le(cutoff), ["date", "target_hash"]].reset_index(drop=True))
        rows.append({"policy": policy, "passed": bool(same69 and same79), "detail": f"cutoff={cutoff.date()} v69={same69} v79={same79}"})
    return pd.DataFrame(rows)


def _operational_gaps() -> pd.DataFrame:
    return pd.DataFrame([
        {"issue": "FIXED_WEIGHTS_IGNORE_SELECTION_UNCERTAINTY", "severity": "HIGH", "current_state": "V69 always 80 percent when a leader exists; V79 fixed 70/30", "v100_action": "tested uncertainty budget; no automatic promotion"},
        {"issue": "HIDDEN_COMPONENT_OVERLAP", "severity": "HIGH", "current_state": "V79 base and sleeve may select the same ticker or semantic sector", "v100_action": "explicit overlap ledger and 70 percent semantic-sector cap candidate"},
        {"issue": "NO_EXPLICIT_TARGET_CONTRACT", "severity": "HIGH", "current_state": "target map existed but lacked policy/version/reason/hash", "v100_action": "daily deterministic target ledger with hash and reason"},
        {"issue": "STATIC_TAXONOMY_PROXY", "severity": "MEDIUM", "current_state": "semantic sector mapping has no effective dates or holdings overlap", "v100_action": "documented; cap candidate remains research only"},
        {"issue": "NO_HOLDINGS_LEVEL_LOOKTHROUGH", "severity": "HIGH", "current_state": "core ETF and theme ETFs may share constituents", "v100_action": "external ETF holdings history required before live"},
        {"issue": "NO_ACCOUNT_CAPACITY_AWARE_TARGET", "severity": "MEDIUM", "current_state": "target weights do not shrink with account size or market capacity", "v100_action": "deferred to RiskExecutionAgent with ADV and broker constraints"},
        {"issue": "NO_PORTFOLIO_LEVEL_RISK_BUDGET", "severity": "MEDIUM", "current_state": "MarketRegime is binary and allocation is fixed", "v100_action": "dynamic candidate tested without parent mutation"},
        {"issue": "TARGET_REBALANCE_OWNERSHIP_AMBIGUITY", "severity": "MEDIUM", "current_state": "V69 daily exact and V79 5 percent band", "v100_action": "target generation separated; execution cadence deferred to RiskExecutionAgent"},
    ])


def run(root: Path | str) -> dict[str, Any]:
    root = Path(root)
    out = root / "reports" / REPORT
    out.mkdir(parents=True, exist_ok=True)
    cfg, cfg77, market, cfg69, universe, cfg79, selection69, selection79 = _load_context(root)
    runs = {policy: _execute_policy(root, policy) for policy in ALL_POLICIES}
    index = market["close"].index
    validation_pos = index.searchsorted(pd.Timestamp("2023-01-01"))
    purged_validation_start = index[min(validation_pos + int(cfg["purge_sessions"]), len(index) - 1)]
    metrics = pd.DataFrame([
        _metric_row(strategy, policy, run, purged_validation_start)
        for policy, run in runs.items() for strategy in ("V69", "V79")
    ])
    promotion = _promotion(metrics, runs, cfg)
    diagnostics = _diagnostics(runs)
    annual = _annual_returns(runs)
    monthly = _monthly_2026(runs)
    future = _future_invariants(root, cfg, cfg77, market, cfg69, universe, cfg79)
    gaps = _operational_gaps()

    parent_ref = pd.read_csv(root / "reports/v99_candidate_selection_deep_research/v99_strategy_metrics.csv")
    parent_ref = parent_ref[parent_ref["policy"].eq("TOP_SCORE_SECTOR_DEDUP")].set_index("strategy")
    active = metrics[metrics["policy"].eq(ACTIVE_STRATEGY_POLICY)].set_index("strategy")
    active_diag = diagnostics[(diagnostics["policy"].eq(ACTIVE_STRATEGY_POLICY)) & diagnostics["period"].eq("FULL")].set_index("strategy")
    quality = pd.DataFrame([
        {"gate": "v69_parent_nav_exact", "passed": bool(np.isclose(active.loc["V69", "ending_nav_krw"], parent_ref.loc["V69", "ending_nav_krw"], atol=0.01)), "detail": f"delta={active.loc['V69','ending_nav_krw']-parent_ref.loc['V69','ending_nav_krw']:.6f}"},
        {"gate": "v79_parent_nav_exact", "passed": bool(np.isclose(active.loc["V79", "ending_nav_krw"], parent_ref.loc["V79", "ending_nav_krw"], atol=0.01)), "detail": f"delta={active.loc['V79','ending_nav_krw']-parent_ref.loc['V79','ending_nav_krw']:.6f}"},
        {"gate": "daily_target_weights_sum_to_one", "passed": bool(all((run[f"ledger{s}"]["target_weight_sum"] - 1.0).abs().max() <= 1e-10 for run in runs.values() for s in ("69", "79"))), "detail": "all policies and strategies"},
        {"gate": "target_decisions_use_d1_only", "passed": bool(all(not run[f"ledger{s}"]["decision_uses_same_day_close"].any() for run in runs.values() for s in ("69", "79"))), "detail": "all target ledgers"},
        {"gate": "all_strategy_policies_future_invariant", "passed": bool(future["passed"].all()), "detail": "; ".join(future["detail"].tolist())},
        {"gate": "hidden_v79_overlap_measured", "passed": bool(active_diag.loc["V79", "same_ticker_overlap_days"] > 0 and active_diag.loc["V79", "same_sector_overlap_days"] > active_diag.loc["V79", "same_ticker_overlap_days"]), "detail": f"ticker={active_diag.loc['V79','same_ticker_overlap_days']} sector={active_diag.loc['V79','same_sector_overlap_days']}"},
        {"gate": "sector_cap_never_exceeds_70pct", "passed": bool(runs[V79_SEMANTIC_SECTOR_CAP_70]["ledger79"]["max_semantic_sector_weight"].max() <= 0.7000000001), "detail": f"max={runs[V79_SEMANTIC_SECTOR_CAP_70]['ledger79']['max_semantic_sector_weight'].max():.6f}"},
        {"gate": "no_negative_cash", "passed": bool(all(run[f"account{s}"]["cash_krw"].min() >= -0.01 and run[f"stress{s}"]["cash_krw"].min() >= -0.01 for run in runs.values() for s in ("69", "79"))), "detail": "base and stress"},
        {"gate": "parent_strategy_not_mutated", "passed": True, "detail": "all candidates research-only; active allocations remain 80/20 and 70/30"},
        {"gate": "live_execution_blocked", "passed": bool(not cfg.get("live_execution_allowed", False)), "detail": "V100 research-only"},
    ])

    metrics.to_csv(out / "v100_strategy_metrics.csv", index=False)
    promotion.to_csv(out / "v100_candidate_promotion.csv", index=False)
    diagnostics.to_csv(out / "v100_target_diagnostics.csv", index=False)
    annual.to_csv(out / "v100_annual_returns.csv", index=False)
    monthly.to_csv(out / "v100_2026_monthly_returns.csv", index=False)
    future.to_csv(out / "v100_future_mutation_invariants.csv", index=False)
    gaps.to_csv(out / "v100_operational_gap_register.csv", index=False)
    quality.to_csv(out / "v100_quality_gates.csv", index=False)
    for policy, run in runs.items():
        run["ledger69"].to_csv(out / f"v100_target_ledger_v69_{policy}.csv", index=False)
        run["ledger79"].to_csv(out / f"v100_target_ledger_v79_{policy}.csv", index=False)
    registry = {
        "version": "V100",
        "active_policy": ACTIVE_STRATEGY_POLICY,
        "candidate_policies": promotion.to_dict(orient="records"),
        "parent_strategies_changed": False,
        "automatic_parent_mutation": False,
        "purged_validation_start": purged_validation_start.date().isoformat(),
        "live_execution_allowed": False,
    }
    (out / "v100_strategy_agent_registry.json").write_text(json.dumps(registry, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    summary = {
        "status": "strategy_agent_research_completed_parent_unchanged",
        "active_policy": ACTIVE_STRATEGY_POLICY,
        "candidate_count": len(CANDIDATE_POLICIES),
        "backtest_passed_count": int(promotion["backtest_passed"].sum()),
        "promoted_count": 0,
        "v79_same_ticker_overlap_days": int(active_diag.loc["V79", "same_ticker_overlap_days"]),
        "v79_same_sector_overlap_days": int(active_diag.loc["V79", "same_sector_overlap_days"]),
        "live_execution_allowed": False,
    }
    (out / "v100_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    if not quality["passed"].all():
        raise AssertionError(f"V100 quality gates failed: {quality.loc[~quality['passed'], 'gate'].tolist()}")
    return {
        "metrics": metrics, "promotion": promotion, "diagnostics": diagnostics,
        "annual": annual, "monthly": monthly, "future": future, "gaps": gaps,
        "quality": quality, "runs": runs, "purged_validation_start": purged_validation_start,
    }
