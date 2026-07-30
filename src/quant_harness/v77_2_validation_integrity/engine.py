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

REPORT = "v77_2_validation_integrity"
SELECTION_COLUMNS = [
    "scenario", "allocation_policy", "rebalancing_policy",
    "development_return_pct", "development_sharpe", "development_mdd_pct", "development_order_count",
    "validation_return_pct", "validation_sharpe", "validation_mdd_pct", "validation_order_count",
    "negative_cash_days", "max_oracle_nav_error_krw",
]


def _load_local_config(root: Path) -> dict[str, Any]:
    return yaml.safe_load((root / "config/v77_2_validation_integrity.yaml").read_text(encoding="utf-8"))


def _slice_nav(nav: pd.Series, start: str, end: str, initial: float) -> tuple[pd.Series, float]:
    nav = nav.astype(float)
    sub = nav[(nav.index >= start) & (nav.index <= end)]
    if sub.empty:
        return sub, initial
    pos = nav.index.get_loc(sub.index[0])
    base = initial if pos == 0 else float(nav.iloc[pos - 1])
    rebased = sub / base * initial
    return rebased, base


def _slice_metrics(nav: pd.Series, start: str, end: str, initial: float) -> dict[str, float]:
    rebased, _ = _slice_nav(nav, start, end, initial)
    if rebased.empty:
        return {"return_pct": np.nan, "cagr_pct": np.nan, "sharpe": np.nan, "mdd_pct": np.nan, "ending_nav_krw": np.nan}
    return v69._metrics(rebased, initial)


def _slice_order_count(orders: pd.DataFrame, start: str, end: str) -> int:
    if orders.empty:
        return 0
    dates = pd.to_datetime(orders["date"])
    return int(dates.between(pd.Timestamp(start), pd.Timestamp(end)).sum())


def _selection_score(frame: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    return (
        float(weights["development_return"]) * frame["development_return_pct"]
        + float(weights["validation_return"]) * frame["validation_return_pct"]
        + float(weights["development_sharpe"]) * frame["development_sharpe"]
        + float(weights["validation_sharpe"]) * frame["validation_sharpe"]
        - float(weights["order_penalty"]) * (frame["development_order_count"] + frame["validation_order_count"])
    )


def select_candidate_from_isolated_columns(
    results: pd.DataFrame,
    *,
    baseline_name: str,
    selection_weights: dict[str, float],
    validation_floor_pp: float,
    mdd_tolerance_pp: float,
) -> tuple[str, pd.DataFrame]:
    missing = set(SELECTION_COLUMNS).difference(results.columns)
    if missing:
        raise ValueError(f"selection input is missing isolated columns: {sorted(missing)}")
    safe = results[SELECTION_COLUMNS].copy()
    baseline = safe.set_index("scenario").loc[baseline_name]
    safe["eligible_on_dev_validation"] = (
        safe["development_return_pct"].ge(float(baseline["development_return_pct"]))
        & safe["validation_return_pct"].ge(float(baseline["validation_return_pct"]) + validation_floor_pp)
        & safe["development_sharpe"].ge(float(baseline["development_sharpe"]))
        & safe["validation_sharpe"].ge(float(baseline["validation_sharpe"]))
        & safe["development_mdd_pct"].ge(float(baseline["development_mdd_pct"]) - mdd_tolerance_pp)
        & safe["validation_mdd_pct"].ge(float(baseline["validation_mdd_pct"]) - mdd_tolerance_pp)
        & safe["negative_cash_days"].eq(0)
        & safe["max_oracle_nav_error_krw"].le(0.01)
    )
    eligible = safe[safe["eligible_on_dev_validation"]].copy()
    if eligible.empty:
        return baseline_name, safe
    eligible["selection_score"] = _selection_score(eligible, selection_weights)
    complexity = {"EVENT_ONLY": 0, "BAND_10PP": 1, "BAND_5PP": 2, "MONTHLY_OR_CHANGE": 3, "DAILY_EXACT": 4}
    eligible["policy_complexity"] = eligible["rebalancing_policy"].map(complexity).fillna(9)
    selected = str(
        eligible.sort_values(
            ["selection_score", "validation_return_pct", "validation_order_count", "policy_complexity"],
            ascending=[False, False, True, True],
        ).iloc[0]["scenario"]
    )
    safe = safe.merge(
        eligible[["scenario", "selection_score", "policy_complexity"]], on="scenario", how="left"
    )
    return selected, safe


def _relative_bootstrap_period(
    a: pd.Series, b: pd.Series, start: str, end: str, *, samples: int, block_months: int
) -> dict[str, float]:
    aligned = pd.concat([a.rename("a"), b.rename("b")], axis=1).dropna().loc[start:end]
    monthly = aligned.resample("ME").last().pct_change(fill_method=None).dropna()
    relative = (1.0 + monthly["a"]) / (1.0 + monthly["b"]) - 1.0
    values = relative.to_numpy(float)
    if len(values) < block_months:
        return {"positive_probability": 0.0, "median_relative_return": np.nan, "months": int(len(values))}
    rng = np.random.default_rng(77201)
    outcomes: list[float] = []
    for _ in range(samples):
        draw: list[float] = []
        while len(draw) < len(values):
            start_pos = int(rng.integers(0, len(values) - block_months + 1))
            draw.extend(values[start_pos:start_pos + block_months])
        outcomes.append(float(np.prod(1.0 + np.asarray(draw[: len(values)])) - 1.0))
    arr = np.asarray(outcomes)
    return {
        "positive_probability": float(np.mean(arr > 0)),
        "median_relative_return": float(np.median(arr)),
        "months": int(len(values)),
    }


def _familywise_probability(raw_probability: float, family_size: int) -> float:
    # Bonferroni lower bound on confidence that at least one of m comparisons is not a false positive.
    return float(max(0.0, 1.0 - family_size * (1.0 - raw_probability)))


def _return_table(nav_map: dict[str, pd.Series], periods: dict[str, list[str]], initial: float) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for scenario, nav in nav_map.items():
        full = v69._metrics(nav, initial)
        row = {"scenario": scenario, **full}
        for name, (start, end) in periods.items():
            row[f"{name}_return_pct"] = _slice_metrics(nav, start, end, initial)["return_pct"]
        rows.append(row)
    return pd.DataFrame(rows)


def _annual_returns(nav_map: dict[str, pd.Series], initial: float) -> pd.DataFrame:
    rows = []
    for scenario, nav in nav_map.items():
        for year in sorted(set(nav.index.year)):
            start, end = f"{year}-01-01", f"{year}-12-31"
            rows.append({"scenario": scenario, "year": year, "return_pct": _slice_metrics(nav, start, end, initial)["return_pct"]})
    return pd.DataFrame(rows)


def _monthly_returns_2026(nav_map: dict[str, pd.Series], initial: float) -> pd.DataFrame:
    rows = []
    for scenario, nav in nav_map.items():
        for month in range(1, 13):
            start = pd.Timestamp(2026, month, 1)
            end = start + pd.offsets.MonthEnd(1)
            if start > nav.index.max():
                continue
            rows.append({"scenario": scenario, "month": start.strftime("%Y-%m"), "return_pct": _slice_metrics(nav, str(start.date()), str(end.date()), initial)["return_pct"]})
    return pd.DataFrame(rows)


def _dca_from_return_stream(nav: pd.Series, *, initial: float, monthly_contribution: float) -> pd.Series:
    daily = nav.astype(float).pct_change(fill_method=None).fillna(nav.iloc[0] / initial - 1.0)
    value = initial
    rows = []
    previous_month = None
    for date, ret in daily.items():
        month = (date.year, date.month)
        if previous_month is not None and month != previous_month:
            value += monthly_contribution
        value *= 1.0 + float(ret)
        rows.append(value)
        previous_month = month
    return pd.Series(rows, index=nav.index)


def run(root: Path | str) -> dict[str, Any]:
    root = Path(root)
    base_cfg = v77._load_config(root)
    local = _load_local_config(root)
    periods = local["periods"]
    market = v77.load_adjusted_market(root, base_cfg)
    v69_cfg = replace(
        v69._load_config(root),
        end_date=base_cfg.end_date,
        core_ticker=base_cfg.core_ticker,
        benchmark_ticker=base_cfg.benchmark_ticker,
    )
    universe = v69._load_universe(root, v69_cfg)
    features = v69.build_feature_panel(market["close"], market["value"], universe, v69_cfg)
    selection = v69.select_dynamic_leader(market["close"].index, universe, features, v69_cfg)

    rows: list[dict[str, Any]] = []
    accounts: dict[str, pd.DataFrame] = {}
    orders_map: dict[str, pd.DataFrame] = {}
    for allocation in base_cfg.allocation_candidates:
        for rebalance in base_cfg.rebalancing_candidates:
            scenario = f"{allocation}__{rebalance}"
            account, orders, audit = v77.execute(
                market["close"], market["open"], market["adv20_d1"], selection,
                base_cfg.core_ticker, base_cfg.initial_capital_krw, allocation, rebalance, base_cfg.base_execution,
            )
            nav = account.set_index("date")["nav_krw"]
            oracle = v77.independent_reconstruct(base_cfg.initial_capital_krw, market["close"], orders)
            merged = account[["date", "cash_krw", "nav_krw"]].merge(oracle, on="date", how="left")
            period_values: dict[str, float] = {}
            for name in ("development", "validation", "observed_only", "recent_1y"):
                start, end = periods[name]
                metric = _slice_metrics(nav, start, end, base_cfg.initial_capital_krw)
                prefix = "observed" if name == "observed_only" else name
                period_values.update({
                    f"{prefix}_return_pct": metric["return_pct"],
                    f"{prefix}_sharpe": metric["sharpe"],
                    f"{prefix}_mdd_pct": metric["mdd_pct"],
                    f"{prefix}_order_count": _slice_order_count(orders, start, end),
                })
            rows.append({
                "scenario": scenario,
                "allocation_policy": allocation,
                "rebalancing_policy": rebalance,
                **v69._metrics(nav, base_cfg.initial_capital_krw),
                **period_values,
                "order_count": int(len(orders)),
                "negative_cash_days": int(audit["negative_cash_days"]),
                "max_oracle_nav_error_krw": float((merged["nav_krw"] - merged["oracle_nav_krw"]).abs().max()),
            })
            accounts[scenario] = account
            orders_map[scenario] = orders
    results = pd.DataFrame(rows)
    baseline_name = str(local["baseline_scenario"])
    selected, safe_selection = select_candidate_from_isolated_columns(
        results,
        baseline_name=baseline_name,
        selection_weights=local["selection_weights"],
        validation_floor_pp=base_cfg.validation_floor_pp,
        mdd_tolerance_pp=base_cfg.mdd_tolerance_pp,
    )
    results = results.merge(
        safe_selection[["scenario", "eligible_on_dev_validation", "selection_score", "policy_complexity"]],
        on="scenario", how="left",
    )

    # Mutation proof: diagnostics and observed-only values can be arbitrarily changed without changing selection.
    mutated = results.copy()
    diagnostic_columns = [c for c in mutated.columns if c not in SELECTION_COLUMNS]
    for column in diagnostic_columns:
        if pd.api.types.is_numeric_dtype(mutated[column]):
            mutated[column] = np.arange(len(mutated), dtype=float) * 1_000_000.0
    mutated_selected, _ = select_candidate_from_isolated_columns(
        mutated,
        baseline_name=baseline_name,
        selection_weights=local["selection_weights"],
        validation_floor_pp=base_cfg.validation_floor_pp,
        mdd_tolerance_pp=base_cfg.mdd_tolerance_pp,
    )
    mutation_isolated = selected == mutated_selected

    selected_nav = accounts[selected].set_index("date")["nav_krw"]
    baseline_nav = accounts[baseline_name].set_index("date")["nav_krw"]
    samples = int(local["bootstrap"]["samples"])
    block_months = int(local["bootstrap"]["block_months"])
    val_start, val_end = periods["validation"]
    dev_start, dev_end = periods["development"]
    val_bootstrap = _relative_bootstrap_period(
        selected_nav, baseline_nav, val_start, val_end, samples=samples, block_months=block_months
    )
    dev_bootstrap = _relative_bootstrap_period(
        selected_nav, baseline_nav, dev_start, dev_end, samples=samples, block_months=block_months
    )
    family_size = int(local["multiple_testing"]["family_size"])
    familywise = _familywise_probability(val_bootstrap["positive_probability"], family_size)

    selected_allocation, selected_rebalance = selected.split("__", 1)
    stress_account, _, _ = v77.execute(
        market["close"], market["open"], market["adv20_d1"], selection,
        base_cfg.core_ticker, base_cfg.initial_capital_krw, selected_allocation, selected_rebalance,
        base_cfg.stress_execution,
    )
    stress_nav = stress_account.set_index("date")["nav_krw"]
    stress_validation = _slice_metrics(stress_nav, val_start, val_end, base_cfg.initial_capital_krw)
    baseline_validation = _slice_metrics(baseline_nav, val_start, val_end, base_cfg.initial_capital_krw)

    core_hold = v77._buy_hold(
        market["close"][base_cfg.core_ticker], market["open"][base_cfg.core_ticker],
        base_cfg.initial_capital_krw, base_cfg.base_execution,
    )
    semi_hold = v77._buy_hold(
        market["close"][base_cfg.semiconductor_benchmark_ticker], market["open"][base_cfg.semiconductor_benchmark_ticker],
        base_cfg.initial_capital_krw, base_cfg.base_execution,
    )
    kospi_close = market["close"][base_cfg.benchmark_ticker].dropna()
    kospi_nav = kospi_close / kospi_close.iloc[0] * base_cfg.initial_capital_krw
    nav_map = {
        selected: selected_nav,
        baseline_name: baseline_nav,
        "KODEX200_BUY_HOLD": core_hold,
        "SEMICONDUCTOR_ETF_BUY_HOLD": semi_hold,
        "KOSPI_INDEX": kospi_nav,
    }
    comparison_periods = {
        "development": periods["development"],
        "validation": periods["validation"],
        "observed": periods["observed_only"],
        "recent_1y": periods["recent_1y"],
    }
    comparison = _return_table(nav_map, comparison_periods, base_cfg.initial_capital_krw)
    annual = _annual_returns(nav_map, base_cfg.initial_capital_krw)
    monthly_2026 = _monthly_returns_2026(nav_map, base_cfg.initial_capital_krw)
    dca_rows = []
    for scenario, nav in nav_map.items():
        dca = _dca_from_return_stream(nav, initial=base_cfg.initial_capital_krw, monthly_contribution=300_000.0)
        contributions = base_cfg.initial_capital_krw + 300_000.0 * max(len(set(zip(dca.index.year, dca.index.month))) - 1, 0)
        dca_rows.append({
            "scenario": scenario,
            "monthly_contribution_krw": 300_000.0,
            "ending_value_krw": float(dca.iloc[-1]),
            "total_contributions_krw": float(contributions),
            "gain_on_contributions_pct": float((dca.iloc[-1] / contributions - 1.0) * 100.0),
            "method": "diagnostic_return_stream_dca_same_cashflow_for_all_scenarios",
        })
    dca = pd.DataFrame(dca_rows)

    raw_gate = float(local["multiple_testing"]["raw_probability_gate"])
    fw_gate = float(local["multiple_testing"]["familywise_probability_gate"])
    promotion = bool(
        mutation_isolated
        and val_bootstrap["positive_probability"] >= raw_gate
        and familywise >= fw_gate
        and stress_validation["return_pct"] >= baseline_validation["return_pct"]
    )
    gates = pd.DataFrame([
        {"gate": "SELECTION_COLUMNS_DEV_VALIDATION_ONLY", "passed": True, "detail": ",".join(SELECTION_COLUMNS)},
        {"gate": "OBSERVED_MUTATION_ISOLATION", "passed": mutation_isolated, "detail": f"selected={selected} mutated_selected={mutated_selected}"},
        {"gate": "VALIDATION_ONLY_BOOTSTRAP", "passed": val_bootstrap["positive_probability"] >= raw_gate, "detail": json.dumps(val_bootstrap)},
        {"gate": "MULTIPLE_TESTING_FAMILYWISE", "passed": familywise >= fw_gate, "detail": f"raw={val_bootstrap['positive_probability']:.4f} family_size={family_size} bonferroni_lower_bound={familywise:.4f}"},
        {"gate": "VALIDATION_STRESS_NONINFERIOR", "passed": stress_validation["return_pct"] >= baseline_validation["return_pct"], "detail": f"selected_stress={stress_validation['return_pct']:.2f} baseline={baseline_validation['return_pct']:.2f}"},
        {"gate": "AUTO_PROMOTION", "passed": promotion, "detail": "all selection-isolation, validation, familywise and stress gates required"},
        {"gate": "LIVE_BLOCKED", "passed": True, "detail": "research and shadow only"},
    ])

    out = root / "reports" / REPORT
    out.mkdir(parents=True, exist_ok=True)
    results.sort_values(["eligible_on_dev_validation", "selection_score"], ascending=[False, False]).to_csv(out / "v77_2_trials.csv", index=False)
    safe_selection.to_csv(out / "v77_2_selection_input_only.csv", index=False)
    comparison.to_csv(out / "v77_2_benchmark_comparison.csv", index=False)
    annual.to_csv(out / "v77_2_annual_returns.csv", index=False)
    monthly_2026.to_csv(out / "v77_2_2026_monthly_returns.csv", index=False)
    dca.to_csv(out / "v77_2_dca_comparison.csv", index=False)
    gates.to_csv(out / "v77_2_quality_gates.csv", index=False)
    accounts[selected].to_csv(out / "v77_2_selected_account.csv", index=False)
    orders_map[selected].to_csv(out / "v77_2_selected_orders.csv", index=False)
    pd.DataFrame([
        {"period": "development", **dev_bootstrap},
        {"period": "validation", **val_bootstrap, "familywise_positive_probability": familywise},
    ]).to_csv(out / "v77_2_bootstrap.csv", index=False)

    decision = {
        "status": "v77_2_validation_integrity_complete_live_blocked",
        "selected_shadow": selected,
        "baseline": baseline_name,
        "observed_mutation_isolated": mutation_isolated,
        "validation_bootstrap": val_bootstrap,
        "development_bootstrap": dev_bootstrap,
        "family_size": family_size,
        "familywise_positive_probability": familywise,
        "promotion_passed": promotion,
        "legacy_p2_p3_same_engine_comparison_available": False,
        "legacy_p2_p3_note": "The uploaded P2+P3 artifact is a calibrated historical NAV policy, not an executable signal definition under the corrected OHLC engine. It remains an archived reference rather than a falsely normalized rerun.",
        "live_allowed": False,
        "gates": gates.to_dict("records"),
    }
    (out / "v77_2_decision.json").write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# V77.2 Validation Integrity",
        "",
        f"- selected shadow: `{selected}`",
        f"- observed mutation isolation: `{mutation_isolated}`",
        f"- validation-only raw probability: `{val_bootstrap['positive_probability']:.4f}`",
        f"- Bonferroni familywise lower bound: `{familywise:.4f}`",
        f"- promotion: `{promotion}`",
        "",
        "## Benchmark comparison",
        "",
        comparison.to_markdown(index=False),
        "",
        "## Gates",
        "",
        gates.to_markdown(index=False),
    ]
    (out / "V77_2_KOREAN_SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")
    return decision
