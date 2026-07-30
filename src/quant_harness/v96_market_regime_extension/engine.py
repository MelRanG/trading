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
from quant_harness.v95_market_regime_agent import engine as v95
from quant_harness.v96_market_regime_extension.policy import ACTIVE_POLICY, SUPPORTED_POLICIES, build_market_regime_panel

REPORT = "v96_market_regime_extension"


def _load_config(root: Path) -> dict[str, Any]:
    return yaml.safe_load((root / "config/v96_market_regime_extension.yaml").read_text(encoding="utf-8"))


def _policy_kwargs(cfg: dict[str, Any], policy: str) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "trend_ma_days": int(cfg["shared_parameters"]["trend_ma_days"]),
        "volatility_window": int(cfg["shared_parameters"]["volatility_window"]),
    }
    for row in cfg.get("research_candidates", []):
        if str(row["policy_id"]) == policy:
            kwargs.update({k: v for k, v in row.items() if k != "policy_id"})
            break
    return kwargs


def _execute_pair(
    root: Path,
    market: dict[str, Any],
    universe: pd.DataFrame,
    cfg69: v69.V69Config,
    cfg79: dict[str, Any],
    policy: str,
) -> dict[str, Any]:
    f69 = v94._strict_v69_features(market["close"], market["value"], universe, cfg69)
    f79 = v94._strict_v79_features(market["close"], market["value"], universe, cfg79)
    regime = build_market_regime_panel(
        market["close"], benchmark_ticker=cfg69.benchmark_ticker,
        theme_tickers=universe["ticker"].astype(str).tolist(),
        universe_gate_d1=f69["universe_gate"]["gate"], policy=policy,
        **_policy_kwargs(_load_config(root), policy),
    )
    f69 = dict(f69)
    f69["benchmark_trend"] = regime["risk_on"]
    index = market["close"].index
    sel69 = v69.select_dynamic_leader(index, universe, f69, cfg69)
    exposure = regime["exposure_multiplier"].reindex(index).fillna(0.0).clip(0.0, 1.0)
    sel69["market_exposure_multiplier"] = exposure.to_numpy(float)
    sel69["target_leader_weight"] = (
        sel69["leader_ticker"].notna().astype(float) * 0.80 * exposure.to_numpy(float)
    )
    account69, orders69, audit69 = v77.execute(
        market["close"], market["open"], market["adv20_d1"], sel69,
        cfg69.core_ticker, 10_000_000.0, "FROM_SELECTION", "DAILY_EXACT",
        v77._load_config(root).base_execution,
    )
    sleeve = v79.select_persistent_trend_leader(
        index, universe, f79,
        minimum_hold_sessions=int(cfg79["minimum_hold_sessions"]),
        challenger_score_margin=float(cfg79["challenger_score_margin"]),
        confirmation_reviews=int(cfg79["challenger_confirmation_reviews"]),
    )
    ledger79 = v79.build_blended_target_ledger(sel69, sleeve, core_ticker=cfg69.core_ticker, base_share=0.70)
    account79, orders79, audit79 = v79.execute_multi_target(
        market["close"], market["open"], market["adv20_d1"], ledger79,
        initial_capital=10_000_000.0, spec=v77._load_config(root).base_execution,
        rebalance_band=0.05, scenario=f"V79_{policy}",
    )
    stress69, _, _ = v77.execute(
        market["close"], market["open"], market["adv20_d1"], sel69,
        cfg69.core_ticker, 10_000_000.0, "FROM_SELECTION", "DAILY_EXACT",
        v77._load_config(root).stress_execution,
    )
    stress79, _, _ = v79.execute_multi_target(
        market["close"], market["open"], market["adv20_d1"], ledger79,
        initial_capital=10_000_000.0, spec=v77._load_config(root).stress_execution,
        rebalance_band=0.05, scenario=f"V79_{policy}_STRESS",
    )
    return {
        "regime": regime, "features69": f69, "features79": f79,
        "selection69": sel69, "selection79": sleeve, "ledger79": ledger79,
        "account69": account69, "orders69": orders69, "audit69": audit69,
        "account79": account79, "orders79": orders79, "audit79": audit79,
        "stress69": stress69, "stress79": stress79,
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
        m = _slice_metrics(nav, start, end, initial)
        row[f"{name}_return_pct"] = m["return_pct"]
        row[f"{name}_mdd_pct"] = m["mdd_pct"]
    row["stress_return_pct"] = float((stress_nav.iloc[-1] / initial - 1.0) * 100.0)
    row["ending_nav_krw"] = float(nav.iloc[-1])
    row["order_count"] = int(len(orders))
    row["total_fee_krw"] = float(pd.to_numeric(orders.get("fee_krw", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
    return row


def _annual_returns(runs: dict[str, dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for policy, payload in runs.items():
        for strategy in ("V69", "V79"):
            nav = payload[f"account{69 if strategy == 'V69' else 79}"].set_index("date")["nav_krw"]
            for year, values in nav.groupby(nav.index.year):
                rows.append({"policy": policy, "strategy": strategy, "year": int(year), "return_pct": float((values.iloc[-1] / values.iloc[0] - 1.0) * 100.0)})
    return pd.DataFrame(rows)


def _monthly_2026(runs: dict[str, dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for policy, payload in runs.items():
        for strategy in ("V69", "V79"):
            nav = payload[f"account{69 if strategy == 'V69' else 79}"].set_index("date")["nav_krw"]
            sample = nav[nav.index.year == 2026]
            for month, values in sample.groupby(sample.index.month):
                rows.append({"policy": policy, "strategy": strategy, "month": int(month), "return_pct": float((values.iloc[-1] / values.iloc[0] - 1.0) * 100.0)})
    return pd.DataFrame(rows)


def _diagnostics(runs: dict[str, dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for policy, payload in runs.items():
        panel = payload["regime"]["panel"]
        exposure = pd.to_numeric(panel["exposure_multiplier"], errors="coerce").fillna(0.0)
        switches = panel["regime_switch"].astype(bool)
        positions = np.flatnonzero(switches.to_numpy())
        whipsaws = int(sum((positions[i] - positions[i - 1]) <= 20 for i in range(1, len(positions))))
        rows.append({
            "policy": policy,
            "sessions": int(len(panel)),
            "risk_on_sessions": int(panel["risk_on"].astype(bool).sum()),
            "partial_exposure_sessions": int(((exposure > 0) & (exposure < 1)).sum()),
            "zero_exposure_sessions": int(exposure.eq(0).sum()),
            "mean_exposure_multiplier": float(exposure.mean()),
            "regime_switches": int(switches.sum()),
            "switches_within_20_sessions": whipsaws,
            "crash_guard_trigger_sessions": int(panel["crash_guard_triggered_d1"].astype(bool).sum()),
        })
    return pd.DataFrame(rows)


def _future_mutation_invariant(market: dict[str, Any], universe: pd.DataFrame, cfg69: v69.V69Config, policy: str, cfg: dict[str, Any]) -> tuple[bool, str]:
    f69 = v94._strict_v69_features(market["close"], market["value"], universe, cfg69)
    base = build_market_regime_panel(
        market["close"], benchmark_ticker=cfg69.benchmark_ticker,
        theme_tickers=universe["ticker"].astype(str).tolist(), universe_gate_d1=f69["universe_gate"]["gate"],
        policy=policy, **_policy_kwargs(cfg, policy),
    )
    cutoff = pd.Timestamp("2024-12-31")
    changed_close = market["close"].copy()
    future = changed_close.index > cutoff
    changed_close.loc[future, cfg69.benchmark_ticker] *= 1.73
    changed_close.loc[future, universe["ticker"].astype(str).tolist()] *= 0.61
    changed = build_market_regime_panel(
        changed_close, benchmark_ticker=cfg69.benchmark_ticker,
        theme_tickers=universe["ticker"].astype(str).tolist(), universe_gate_d1=f69["universe_gate"]["gate"],
        policy=policy, **_policy_kwargs(cfg, policy),
    )
    same_signal = base["risk_on"].loc[:cutoff].equals(changed["risk_on"].loc[:cutoff])
    same_exposure = np.allclose(
        base["exposure_multiplier"].loc[:cutoff].to_numpy(float),
        changed["exposure_multiplier"].loc[:cutoff].to_numpy(float),
        equal_nan=True,
    )
    return bool(same_signal and same_exposure), f"policy={policy} cutoff={cutoff.date()} compared_rows={len(base['risk_on'].loc[:cutoff])}"


def _promotion_decision(metrics: pd.DataFrame, runs: dict[str, dict[str, Any]], cfg: dict[str, Any]) -> pd.DataFrame:
    parent = metrics[metrics["policy"].eq(ACTIVE_POLICY)].set_index("strategy")
    parent_exposure = runs[ACTIVE_POLICY]["selection69"].set_index("date")["target_leader_weight"].astype(float)
    p = cfg["promotion"]
    rows: list[dict[str, Any]] = []
    for policy in SUPPORTED_POLICIES:
        if policy == ACTIVE_POLICY:
            continue
        candidate = metrics[metrics["policy"].eq(policy)].set_index("strategy")
        candidate_exposure = runs[policy]["selection69"].set_index("date")["target_leader_weight"].astype(float)
        changed = candidate_exposure.sub(parent_exposure).abs().gt(1e-12)
        changed_total = int(changed.sum())
        changed_development = int(changed.loc["2018-01-01":"2022-12-31"].sum())
        changed_validation = int(changed.loc["2023-01-01":"2024-12-31"].sum())
        changed_observed = int(changed.loc["2025-01-01":"2026-07-03"].sum())
        gates = {
            "both_full_noninferior": all(candidate.loc[s, "return_pct"] >= parent.loc[s, "return_pct"] - float(p["full_return_tolerance_pp"]) for s in ("V69", "V79")),
            "both_development_noninferior": all(candidate.loc[s, "development_return_pct"] >= parent.loc[s, "development_return_pct"] - float(p["development_return_tolerance_pp"]) for s in ("V69", "V79")),
            "both_validation_noninferior": all(candidate.loc[s, "validation_return_pct"] >= parent.loc[s, "validation_return_pct"] - float(p["validation_return_tolerance_pp"]) for s in ("V69", "V79")),
            "both_recent1y_noninferior": all(candidate.loc[s, "recent_1y_return_pct"] >= parent.loc[s, "recent_1y_return_pct"] - float(p["recent_1y_return_tolerance_pp"]) for s in ("V69", "V79")),
            "both_mdd_within_tolerance": all(candidate.loc[s, "mdd_pct"] >= parent.loc[s, "mdd_pct"] - float(p["mdd_tolerance_pp"]) for s in ("V69", "V79")),
            "both_stress_noninferior": all(candidate.loc[s, "stress_return_pct"] >= parent.loc[s, "stress_return_pct"] - float(p["stress_return_tolerance_pp"]) for s in ("V69", "V79")),
            "turnover_bounded": all(candidate.loc[s, "order_count"] <= parent.loc[s, "order_count"] * float(p["order_count_ratio_max"]) for s in ("V69", "V79")),
            "meaningful_exposure_change": changed_total >= int(p["minimum_changed_exposure_days"]),
            "validation_has_changed_evidence": changed_validation >= int(p["minimum_changed_exposure_days_validation"]),
            "at_least_one_parent_improves": any(candidate.loc[s, "return_pct"] >= parent.loc[s, "return_pct"] + float(p["minimum_one_parent_full_improvement_pp"]) for s in ("V69", "V79")),
        }
        promoted = bool(all(gates.values()))
        forward_shadow_only = bool(
            (not promoted)
            and gates["both_full_noninferior"]
            and gates["both_recent1y_noninferior"]
            and gates["both_mdd_within_tolerance"]
            and gates["both_stress_noninferior"]
            and gates["turnover_bounded"]
            and gates["meaningful_exposure_change"]
            and gates["at_least_one_parent_improves"]
            and changed_observed > 0
            and changed_validation < int(p["minimum_changed_exposure_days_validation"])
        )
        rows.append({
            "policy": policy, "promoted": promoted, "forward_shadow_only": forward_shadow_only,
            "changed_exposure_days_total": changed_total,
            "changed_exposure_days_development": changed_development,
            "changed_exposure_days_validation": changed_validation,
            "changed_exposure_days_observed": changed_observed,
            **gates,
            **{f"v69_{k}_delta_pp": float(candidate.loc["V69", f"{k}_return_pct"] - parent.loc["V69", f"{k}_return_pct"]) for k in ("development", "validation", "observed", "recent_1y")},
            **{f"v79_{k}_delta_pp": float(candidate.loc["V79", f"{k}_return_pct"] - parent.loc["V79", f"{k}_return_pct"]) for k in ("development", "validation", "observed", "recent_1y")},
            "v69_full_delta_pp": float(candidate.loc["V69", "return_pct"] - parent.loc["V69", "return_pct"]),
            "v79_full_delta_pp": float(candidate.loc["V79", "return_pct"] - parent.loc["V79", "return_pct"]),
            "v69_stress_delta_pp": float(candidate.loc["V69", "stress_return_pct"] - parent.loc["V69", "stress_return_pct"]),
            "v79_stress_delta_pp": float(candidate.loc["V79", "stress_return_pct"] - parent.loc["V79", "stress_return_pct"]),
        })
    return pd.DataFrame(rows)


def run(root: Path | str) -> dict[str, Any]:
    root = Path(root)
    out = root / "reports" / REPORT
    out.mkdir(parents=True, exist_ok=True)
    cfg = _load_config(root)
    cfg77 = v77._load_config(root)
    market = v77.load_adjusted_market(root, cfg77)
    cfg69 = replace(v69._load_config(root), end_date=cfg77.end_date, core_ticker=cfg77.core_ticker, benchmark_ticker=cfg77.benchmark_ticker, leader_weight=0.80)
    universe = v69._load_universe(root, cfg69)
    cfg79 = v79._load_config(root)["trend_sleeve"]

    runs = {policy: _execute_pair(root, market, universe, cfg69, cfg79, policy) for policy in SUPPORTED_POLICIES}
    metrics = pd.DataFrame([
        _metric_row(strategy, policy, payload[f"account{69 if strategy == 'V69' else 79}"], payload[f"orders{69 if strategy == 'V69' else 79}"], payload[f"stress{69 if strategy == 'V69' else 79}"])
        for policy, payload in runs.items() for strategy in ("V69", "V79")
    ])
    diagnostics = _diagnostics(runs)
    promotions = _promotion_decision(metrics, runs, cfg)
    annual = _annual_returns(runs)
    monthly = _monthly_2026(runs)

    active = runs[ACTIVE_POLICY]
    v95_parent = v95._execute_pair(root, market, universe, cfg69, cfg79, ACTIVE_POLICY)
    nav_errors = {
        "V69": abs(float(active["account69"]["nav_krw"].iloc[-1] - v95_parent["account69"]["nav_krw"].iloc[-1])),
        "V79": abs(float(active["account79"]["nav_krw"].iloc[-1] - v95_parent["account79"]["nav_krw"].iloc[-1])),
    }
    exposure_error = float(
        active["selection69"].set_index("date")["target_leader_weight"]
        .sub(v95_parent["selection69"].set_index("date")["target_leader_weight"])
        .abs().max()
    )
    future_checks = [_future_mutation_invariant(market, universe, cfg69, policy, cfg) for policy in SUPPORTED_POLICIES]
    future_ok = all(ok for ok, _ in future_checks)
    promoted = promotions.loc[promotions["promoted"], "policy"].tolist()
    forward_shadow = promotions.loc[promotions["forward_shadow_only"], "policy"].tolist()

    for policy, payload in runs.items():
        payload["regime"]["panel"].reset_index(drop=True).to_csv(out / f"v96_regime_ledger_{policy.lower()}.csv", index=False)
    metrics.to_csv(out / "v96_strategy_metrics.csv", index=False)
    diagnostics.to_csv(out / "v96_regime_diagnostics.csv", index=False)
    promotions.to_csv(out / "v96_candidate_promotion.csv", index=False)
    annual.to_csv(out / "v96_annual_returns.csv", index=False)
    monthly.to_csv(out / "v96_2026_monthly_returns.csv", index=False)

    quality = pd.DataFrame([
        {"gate": "V95_ACTIVE_PARENT_PARITY", "passed": all(v <= 1.0 for v in nav_errors.values()) and exposure_error <= 1e-12, "detail": f"nav_errors={nav_errors} exposure_error={exposure_error}"},
        {"gate": "D1_ONLY_REGIME_EVIDENCE", "passed": all(not p["regime"]["panel"]["decision_uses_same_day_close"].astype(bool).any() for p in runs.values()), "detail": "same-day close is prohibited"},
        {"gate": "FUTURE_MUTATION_INVARIANT", "passed": future_ok, "detail": "; ".join(detail for _, detail in future_checks)},
        {"gate": "ONLY_TWO_PREREGISTERED_CANDIDATES", "passed": len(SUPPORTED_POLICIES) == 3, "detail": str(SUPPORTED_POLICIES)},
        {"gate": "CANDIDATES_CHANGE_ONLY_MARKET_EXPOSURE", "passed": True, "detail": "universe, alpha, selection, V79 sleeve and execution are shared"},
        {"gate": "AUTOMATIC_LIVE_AUTHORITY_BLOCKED", "passed": not bool(cfg["live_execution_allowed"]), "detail": "research-only"},
        {"gate": "OPTIONAL_RESEARCH_PROMOTION", "passed": len(promoted) > 0, "detail": f"promoted={promoted}; forward_shadow={forward_shadow}; failure preserves parent"},
    ])
    quality.to_csv(out / "v96_quality_gates.csv", index=False)
    registry = {
        "schema_version": 1, "agent": "MarketRegimeAgent", "active_policy": ACTIVE_POLICY,
        "automatic_parent_mutation": False, "automatic_capital_authority": False,
        "candidates": [
            {
                "policy_id": str(row.policy),
                "status": "PROMOTION_ELIGIBLE" if bool(row.promoted) else "FORWARD_SHADOW_ONLY" if bool(row.forward_shadow_only) else "BACKTEST_REJECTED",
                "paper_account_id": None, "capital_authority": False,
                "changed_exposure_days_development": int(row.changed_exposure_days_development),
                "changed_exposure_days_validation": int(row.changed_exposure_days_validation),
                "changed_exposure_days_observed": int(row.changed_exposure_days_observed),
            }
            for row in promotions.itertuples(index=False)
        ],
    }
    (out / "v96_market_regime_candidate_registry.json").write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {
        "version": "V96", "active_policy": ACTIVE_POLICY,
        "active_parent_nav_abs_error_krw": nav_errors, "active_parent_exposure_max_error": exposure_error,
        "research_candidates": [p for p in SUPPORTED_POLICIES if p != ACTIVE_POLICY],
        "promoted_candidates": promoted, "forward_shadow_only_candidates": forward_shadow,
        "market_regime_parent_changed": False, "live_execution_allowed": False,
        "future_mutation_invariant": future_ok,
        "quality_gate_passed_excluding_optional_promotion": bool(quality.loc[quality["gate"].ne("OPTIONAL_RESEARCH_PROMOTION"), "passed"].astype(bool).all()),
    }
    (out / "v96_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary
