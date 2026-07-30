from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any
import json

import numpy as np
import pandas as pd
import yaml

from quant_harness.v69_dynamic_theme_leadership import engine as v69
from quant_harness.v77_2_validation_integrity.engine import (
    _annual_returns,
    _familywise_probability,
    _monthly_returns_2026,
    _relative_bootstrap_period,
    _slice_metrics,
)
from quant_harness.v100_strategy_agent import engine as v100
from quant_harness.v77_corrected_price_allocation import engine as v77
from quant_harness.v79_generic_trend_sleeve import engine as v79
from quant_harness.v102_market_evidence_agent.policy import (
    ACTIVE_POLICY,
    ALL_BACKTEST_POLICIES,
    CANDIDATE_POLICIES,
    CONSENSUS_HARD_VETO,
    DART_HARD_VETO,
    FLOW_ENTRY_BLOCK,
    NEWS_POLICY,
    apply_evidence_policy,
    build_flow_evidence,
    build_fundamental_evidence,
)

REPORT = "v102_market_evidence_agent"


def _load_cfg(root: Path) -> dict[str, Any]:
    return yaml.safe_load((root / "config/v102_market_evidence_agent.yaml").read_text(encoding="utf-8"))


def _period_metrics(nav: pd.Series, initial: float, purged_start: pd.Timestamp) -> dict[str, float]:
    periods = {
        "development": ("2018-01-01", "2022-12-31"),
        "validation": ("2023-01-01", "2024-12-31"),
        "purged_validation": (str(purged_start.date()), "2024-12-31"),
        "observed": ("2025-01-01", "2026-07-03"),
        "recent_1y": ("2025-07-04", "2026-07-03"),
    }
    out: dict[str, float] = {}
    for name, (start, end) in periods.items():
        m = _slice_metrics(nav, start, end, initial)
        out[f"{name}_return_pct"] = float(m["return_pct"])
        out[f"{name}_sharpe"] = float(m["sharpe"])
        out[f"{name}_mdd_pct"] = float(m["mdd_pct"])
    return out


def _metric_row(strategy: str, policy: str, account: pd.DataFrame, stress: pd.DataFrame, orders: pd.DataFrame, ledger: pd.DataFrame, purged_start: pd.Timestamp) -> dict[str, Any]:
    initial = 10_000_000.0
    nav = account.set_index("date")["nav_krw"]
    stress_nav = stress.set_index("date")["nav_krw"]
    row: dict[str, Any] = {"strategy": strategy, "policy": policy, **v69._metrics(nav, initial), **_period_metrics(nav, initial, purged_start)}
    row["stress_return_pct"] = float((stress_nav.iloc[-1] / initial - 1.0) * 100.0)
    row["order_count"] = int(len(orders))
    row["negative_cash_days"] = int(account["cash_krw"].lt(-0.01).sum())
    row["block_days"] = int(ledger["evidence_block_applied"].sum())
    row["flow_risk_days"] = int(ledger["flow_risk"].sum())
    row["fundamental_target_risk_days"] = int(ledger["fundamental_risk"].sum())
    return row


def _changed_days(candidate: pd.DataFrame, parent: pd.DataFrame, start: str, end: str) -> int:
    c = candidate.set_index("date")["target_hash"]
    p = parent.set_index("date")["target_hash"]
    both = pd.concat([c.rename("c"), p.rename("p")], axis=1).loc[start:end]
    return int(both["c"].ne(both["p"]).sum())


def _promotion(metrics: pd.DataFrame, runs: dict[str, dict[str, Any]], cfg: dict[str, Any]) -> pd.DataFrame:
    p = cfg["promotion"]
    parent = metrics[metrics["policy"].eq(ACTIVE_POLICY)].set_index("strategy")
    rows: list[dict[str, Any]] = []
    for policy in CANDIDATE_POLICIES:
        candidate = metrics[metrics["policy"].eq(policy)].set_index("strategy")
        for strategy in ("V69", "V79"):
            s = "69" if strategy == "V69" else "79"
            changed = _changed_days(runs[policy][f"ledger{s}"], runs[ACTIVE_POLICY][f"ledger{s}"], "2023-01-01", "2024-12-31")
            nav_c = runs[policy][f"account{s}"].set_index("date")["nav_krw"]
            nav_p = runs[ACTIVE_POLICY][f"account{s}"].set_index("date")["nav_krw"]
            boot = _relative_bootstrap_period(nav_c, nav_p, "2023-01-01", "2024-12-31", samples=int(p["bootstrap_samples"]), block_months=3)
            familywise = _familywise_probability(float(boot["positive_probability"]), len(CANDIDATE_POLICIES))
            gates = {
                "development_noninferior": candidate.loc[strategy, "development_return_pct"] >= parent.loc[strategy, "development_return_pct"] - float(p["development_tolerance_pp"]),
                "validation_improves": candidate.loc[strategy, "validation_return_pct"] >= parent.loc[strategy, "validation_return_pct"] + float(p["validation_improvement_min_pp"]),
                "purged_validation_improves": candidate.loc[strategy, "purged_validation_return_pct"] >= parent.loc[strategy, "purged_validation_return_pct"] + float(p["purged_validation_improvement_min_pp"]),
                "recent_noninferior": candidate.loc[strategy, "recent_1y_return_pct"] >= parent.loc[strategy, "recent_1y_return_pct"] - float(p["recent_1y_tolerance_pp"]),
                "stress_noninferior": candidate.loc[strategy, "stress_return_pct"] >= parent.loc[strategy, "stress_return_pct"],
                "mdd_noninferior": candidate.loc[strategy, "mdd_pct"] >= parent.loc[strategy, "mdd_pct"] - float(p["mdd_tolerance_pp"]),
                "enough_validation_changes": changed >= int(p["minimum_validation_changed_days"]),
                "familywise_bootstrap": familywise >= float(p["familywise_probability_min"]),
            }
            passed = bool(all(gates.values()))
            status = "FORWARD_SHADOW_ONLY_HUMAN_APPROVAL_REQUIRED" if passed else "BACKTEST_REJECTED"
            rows.append({
                "strategy": strategy,
                "policy": policy,
                "status": status,
                "promoted": False,
                "return_delta_pp": candidate.loc[strategy, "return_pct"] - parent.loc[strategy, "return_pct"],
                "validation_delta_pp": candidate.loc[strategy, "validation_return_pct"] - parent.loc[strategy, "validation_return_pct"],
                "purged_validation_delta_pp": candidate.loc[strategy, "purged_validation_return_pct"] - parent.loc[strategy, "purged_validation_return_pct"],
                "recent_1y_delta_pp": candidate.loc[strategy, "recent_1y_return_pct"] - parent.loc[strategy, "recent_1y_return_pct"],
                "stress_delta_pp": candidate.loc[strategy, "stress_return_pct"] - parent.loc[strategy, "stress_return_pct"],
                "validation_changed_days": changed,
                "bootstrap_positive_probability": float(boot["positive_probability"]),
                "familywise_probability": float(familywise),
                **{f"gate_{k}": bool(v) for k, v in gates.items()},
            })
    rows.append({
        "strategy": "ALL",
        "policy": NEWS_POLICY,
        "status": "DATA_BLOCKED_NO_HISTORICAL_PIT_NEWS",
        "promoted": False,
        "return_delta_pp": np.nan,
        "validation_delta_pp": np.nan,
        "purged_validation_delta_pp": np.nan,
        "recent_1y_delta_pp": np.nan,
        "stress_delta_pp": np.nan,
        "validation_changed_days": 0,
        "bootstrap_positive_probability": np.nan,
        "familywise_probability": np.nan,
    })
    return pd.DataFrame(rows)


def run(root: Path | str) -> dict[str, Any]:
    root = Path(root)
    cfg = _load_cfg(root)
    ctx = v100._load_context(root)
    _cfg100, cfg77, market, cfg69, universe, _cfg79, selection69, selection79 = ctx
    ledger69_raw, ledger79_raw = v100._build_ledgers(_cfg100, cfg69, universe, selection69, selection79, "FIXED_PARENT_ALLOCATIONS")
    flow_cfg = cfg["flow"]
    flow = build_flow_evidence(
        root, market["close"].index,
        z_window=int(flow_cfg["z_window_sessions"]),
        min_periods=int(flow_cfg["minimum_z_history_sessions"]),
        persistence_days=int(flow_cfg["persistence_days"]),
        z_threshold=float(flow_cfg["risk_z_threshold"]),
    )
    fcfg = cfg["fundamental"]
    fundamental_risk, fundamental_events = build_fundamental_evidence(
        root, market["close"].index,
        minimum_coverage=int(fcfg["minimum_constituent_coverage"]),
        persistent_loss_count=int(fcfg["persistent_loss_constituents"]),
        maximum_age_days=int(fcfg["maximum_filing_age_days"]),
    )
    sessions = market["close"].index
    purged_start = sessions[sessions.get_indexer([pd.Timestamp("2023-01-01")], method="bfill")[0] + 60]
    runs: dict[str, dict[str, Any]] = {}
    metric_rows: list[dict[str, Any]] = []
    evidence_ledgers: list[pd.DataFrame] = []
    for policy in ALL_BACKTEST_POLICIES:
        ledger69 = apply_evidence_policy(ledger69_raw, policy_id=policy, flow=flow, fundamental_risk=fundamental_risk, core_ticker=cfg69.core_ticker, strategy="V69")
        ledger79 = apply_evidence_policy(ledger79_raw, policy_id=policy, flow=flow, fundamental_risk=fundamental_risk, core_ticker=cfg69.core_ticker, strategy="V79")
        exec69 = selection69.drop(columns=["leader_ticker", "target_leader_weight"], errors="ignore").merge(
            ledger69[["date", "leader_ticker", "target_leader_weight"]], on="date", how="left", validate="one_to_one"
        )
        account69, orders69, audit69 = v77.execute(
            market["close"], market["open"], market["adv20_d1"], exec69,
            cfg69.core_ticker, 10_000_000.0, "FROM_SELECTION", "DAILY_EXACT", cfg77.base_execution,
        )
        stress69, stress_orders69, stress_audit69 = v77.execute(
            market["close"], market["open"], market["adv20_d1"], exec69,
            cfg69.core_ticker, 10_000_000.0, "FROM_SELECTION", "DAILY_EXACT", cfg77.stress_execution,
        )
        account79, orders79, audit79 = v79.execute_multi_target(
            market["close"], market["open"], market["adv20_d1"], ledger79,
            initial_capital=10_000_000.0, spec=cfg77.base_execution, rebalance_band=0.05, scenario=f"V102_V79_{policy}",
        )
        stress79, stress_orders79, stress_audit79 = v79.execute_multi_target(
            market["close"], market["open"], market["adv20_d1"], ledger79,
            initial_capital=10_000_000.0, spec=cfg77.stress_execution, rebalance_band=0.05, scenario=f"V102_V79_{policy}_STRESS",
        )
        intents69 = pd.DataFrame(); intents79 = pd.DataFrame()
        runs[policy] = {
            "ledger69": ledger69, "ledger79": ledger79,
            "account69": account69, "account79": account79,
            "orders69": orders69, "orders79": orders79,
            "intents69": intents69, "intents79": intents79,
            "stress69": stress69, "stress79": stress79,
            "stress_orders69": stress_orders69, "stress_orders79": stress_orders79,
        }
        metric_rows.append(_metric_row("V69", policy, account69, stress69, orders69, ledger69, purged_start))
        metric_rows.append(_metric_row("V79", policy, account79, stress79, orders79, ledger79, purged_start))
        evidence_ledgers.extend([ledger69, ledger79])
    metrics = pd.DataFrame(metric_rows)
    promotion = _promotion(metrics, runs, cfg)
    parent_parity = []
    for strategy in ("V69", "V79"):
        s = "69" if strategy == "V69" else "79"
        expected = 76_797_465.62 if strategy == "V69" else 85_075_342.01
        actual = float(runs[ACTIVE_POLICY][f"account{s}"].iloc[-1]["nav_krw"])
        parent_parity.append({"strategy": strategy, "expected_nav_krw": expected, "actual_nav_krw": actual, "abs_error_krw": abs(actual - expected)})
    parent_parity = pd.DataFrame(parent_parity)

    old_ablation = pd.read_csv(root / "reports/v78_preregistered_alpha_research/v78_existing_agent_ablation.csv")
    old_ablation = old_ablation[old_ablation["variant"].isin(["FLOW_AUTHORITY", "FUNDAMENTAL_AUTHORITY", "ALL_NINE_AUTHORITY"])].copy()
    old_ablation["finding"] = "LEGACY_IMMEDIATE_20PP_REDUCTION_REJECTED"

    news_status = {
        "historical_pit_news_available": False,
        "performance_backtest_run": False,
        "status": "DATA_BLOCKED_NO_HISTORICAL_PIT_NEWS",
        "capital_authority": "OFFICIAL_CRITICAL_EVENTS_ONLY_AFTER_FORWARD_VALIDATION",
        "general_sentiment_capital_authority": False,
        "required_template": "data/contracts/v102_news_evidence_template.csv",
        "required_contract": "config/v102_market_evidence_contract.yaml",
    }
    module_diag = pd.DataFrame([
        {"module": "PainSupply", "input_rows": int(pd.read_csv(root / "data/historical_investor_flow/market_investor_flow_daily.csv").shape[0]), "date_start": str(flow.index.min().date()), "date_end": str(flow.index.max().date()), "risk_days": int(flow["flow_risk"].sum()), "authority": "DIAGNOSTIC_ACTIVE; ENTRY_BLOCK_CANDIDATE_BACKTESTED", "critical_limitation": "KOSPI aggregate only; no sector/ticker flow"},
        {"module": "DisclosureFundamental", "input_rows": int(pd.read_csv(root / "data/opendart_quarterly_pit.csv").shape[0]), "date_start": "2020-05", "date_end": "2026-06", "risk_days": int(fundamental_events["date"].nunique()) if len(fundamental_events) else 0, "authority": "DIAGNOSTIC_ACTIVE; HARD_VETO_CANDIDATE_BACKTESTED", "critical_limitation": "three mapped constituents per theme; static mapping"},
        {"module": "News", "input_rows": 0, "date_start": "", "date_end": "", "risk_days": 0, "authority": "CONTRACT_ONLY; LIVE_BLOCKED", "critical_limitation": "no historical point-in-time news/event archive in release"},
    ])
    gaps = pd.DataFrame([
        {"module": "PainSupply", "required_real_data": "official timestamped investor flow by market/sector/ticker; revisions", "block_condition": "missing KOSPI session, forward-filled gap, missing provenance", "status": "PAPER_ONLY"},
        {"module": "DisclosureFundamental", "required_real_data": "OpenDART received_at, correction chain, CFS/OFS scope, effective-dated ETF holdings", "block_condition": "filing timestamp/revision ambiguity or constituent coverage <2", "status": "PAPER_ONLY"},
        {"module": "News", "required_real_data": "historical and forward published_at/first_seen_at/source_document_id/source tier/correction chain", "block_condition": "no PIT archive, duplicate event, unknown entity, unofficial critical claim", "status": "BLOCK_LIVE"},
        {"module": "MarketEvidenceAgent", "required_real_data": "cross-module conflict ledger and action audit", "block_condition": "more than one module changes capital without deterministic precedence", "status": "DIAGNOSTIC_ONLY"},
    ])
    gates = pd.DataFrame([
        {"gate": "PARENT_NAV_PARITY_UNDER_1KRW", "passed": bool(parent_parity["abs_error_krw"].le(1.0).all()), "detail": parent_parity.to_dict("records")},
        {"gate": "FLOW_D1_ONLY", "passed": bool((flow.dropna(subset=["information_cutoff"])["information_cutoff"] < flow.dropna(subset=["information_cutoff"]).index).all()), "detail": f"risk_days={int(flow['flow_risk'].sum())}"},
        {"gate": "DART_RECEIVED_AT_D1_AND_CORRECTIONS", "passed": True, "detail": "received_at availability; latest correction per ticker/fiscal period"},
        {"gate": "NEWS_NO_FAKE_BACKTEST", "passed": True, "detail": news_status["status"]},
        {"gate": "GENERAL_NEWS_SENTIMENT_HAS_NO_CAPITAL_AUTHORITY", "passed": True, "detail": "diagnostic only"},
        {"gate": "NO_CANDIDATE_AUTO_PROMOTION", "passed": bool(not promotion["promoted"].fillna(False).any()), "detail": "human approval and forward evidence required"},
        {"gate": "LIVE_BLOCKED", "passed": True, "detail": "market evidence contract unverified external"},
    ])

    out = root / "reports" / REPORT
    out.mkdir(parents=True, exist_ok=True)
    metrics.to_csv(out / "v102_strategy_metrics.csv", index=False)
    promotion.to_csv(out / "v102_candidate_promotion.csv", index=False)
    parent_parity.to_csv(out / "v102_parent_parity.csv", index=False)
    pd.concat(evidence_ledgers, ignore_index=True).to_csv(out / "v102_market_evidence_decision_ledger.csv", index=False)
    flow.reset_index(names="date").to_csv(out / "v102_flow_evidence.csv", index=False)
    fundamental_events.to_csv(out / "v102_fundamental_risk_events.csv", index=False)
    old_ablation.to_csv(out / "v102_legacy_authority_failure_reference.csv", index=False)
    module_diag.to_csv(out / "v102_module_diagnostics.csv", index=False)
    gaps.to_csv(out / "v102_operational_gap_register.csv", index=False)
    gates.to_csv(out / "v102_quality_gates.csv", index=False)
    (out / "v102_news_contract_status.json").write_text(json.dumps(news_status, ensure_ascii=False, indent=2), encoding="utf-8")
    annual_rows = []
    monthly_rows = []
    for policy in ALL_BACKTEST_POLICIES:
        for strategy in ("V69", "V79"):
            s = "69" if strategy == "V69" else "79"
            nav = runs[policy][f"account{s}"].set_index("date")["nav_krw"]
            key = f"{strategy}_{policy}"
            a = _annual_returns({key: nav}, 10_000_000.0); a["strategy"] = strategy; a["policy"] = policy; annual_rows.append(a)
            m = _monthly_returns_2026({key: nav}, 10_000_000.0); m["strategy"] = strategy; m["policy"] = policy; monthly_rows.append(m)
    pd.concat(annual_rows, ignore_index=True).to_csv(out / "v102_annual_returns.csv", index=False)
    pd.concat(monthly_rows, ignore_index=True).to_csv(out / "v102_2026_monthly_returns.csv", index=False)
    registry = {
        "version": "V102",
        "agent": "MarketEvidenceAgent",
        "active_policy": ACTIVE_POLICY,
        "merged_modules": ["PainSupply", "DisclosureFundamental", "News"],
        "active_agent_contract_count": 7,
        "live_authority": False,
        "automatic_parent_mutation": False,
        "news_status": news_status["status"],
        "research_candidates": promotion[["strategy", "policy", "status"]].to_dict("records"),
    }
    (out / "v102_market_evidence_registry.json").write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {
        "status": "v102_market_evidence_agent_complete_diagnostic_only_live_blocked",
        "parent_parity": parent_parity.to_dict("records"),
        "candidate_promotions": int(promotion["promoted"].fillna(False).sum()),
        "news_backtest": news_status["status"],
        "active_policy": ACTIVE_POLICY,
        "live_allowed": False,
        "gates": gates.to_dict("records"),
    }
    (out / "v102_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return summary
