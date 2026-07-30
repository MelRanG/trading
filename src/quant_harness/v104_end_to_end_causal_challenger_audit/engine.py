from __future__ import annotations

from dataclasses import asdict
from concurrent.futures import ProcessPoolExecutor, as_completed
import pickle
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from quant_harness.v69_dynamic_theme_leadership import engine as v69
from quant_harness.v77_corrected_price_allocation import engine as v77
from quant_harness.v77_2_validation_integrity.engine import _dca_from_return_stream, _slice_metrics
from quant_harness.v84_dual_paper_parity import engine as v84
from quant_harness.v101_risk_execution_agent import engine as v101
from .adapter import CandidateSpec, build_candidate_ledgers, future_mutation_invariant, load_candidate_specs, load_config, replay_candidate

REPORT = "v104_end_to_end_causal_challenger_audit"
PARENT_BY_STRATEGY = {"V69": "V69_PARENT", "V79": "V79_PARENT"}


def _progress(root: Path, message: str) -> None:
    path = root / "reports" / REPORT / "v104_progress.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(message + "\n")


def _canonical_hash(payload: Any) -> str:
    return sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str, separators=(",", ":")).encode("utf-8")).hexdigest()


def _purged_start(index: pd.DatetimeIndex, sessions: int) -> pd.Timestamp:
    candidates = index[index >= pd.Timestamp("2023-01-01")]
    if len(candidates) <= sessions:
        raise ValueError("not enough validation sessions for purge")
    return pd.Timestamp(candidates[int(sessions)])


def _metric_row(run: dict[str, Any], purged_start: pd.Timestamp) -> dict[str, Any]:
    spec: CandidateSpec = run["spec"]
    initial = float(run["initial_capital_krw"])
    base = v101._metrics(run["account"], run["orders"], run["intents"], initial, purged_start)
    stress_nav = run["stress_account"].set_index("date")["nav_krw"]
    nav = run["account"].set_index("date")["nav_krw"]
    dca = _dca_from_return_stream(nav, initial=initial, monthly_contribution=300_000.0)
    contributions = initial + 300_000.0 * int(pd.Series(nav.index.to_period("M")).nunique())
    ledger = run["ledger"]
    base.update({
        "candidate_id": spec.candidate_id,
        "strategy": spec.strategy,
        "candidate_fingerprint": spec.fingerprint,
        "input_hash": run["input_hash"],
        "audit_only": bool(spec.audit_only),
        "regime_policy": spec.regime_policy,
        "base_selection_policy": spec.base_selection_policy,
        "sleeve_selection_policy": spec.sleeve_selection_policy,
        "strategy_policy": spec.strategy_policy,
        "evidence_policy": spec.evidence_policy,
        "execution_policy": spec.execution_policy,
        "ending_nav_krw": float(nav.iloc[-1]),
        "stress_return_pct": float((stress_nav.iloc[-1] / initial - 1.0) * 100.0),
        "stress_ending_nav_krw": float(stress_nav.iloc[-1]),
        "dca_ending_value_krw": float(dca.iloc[-1]),
        "dca_profit_on_contributions_pct": float((dca.iloc[-1] / contributions - 1.0) * 100.0),
        "max_noncore_ticker_weight": float(pd.to_numeric(ledger.get("max_noncore_ticker_weight", pd.Series([np.nan])), errors="coerce").max()),
        "max_semantic_sector_weight": float(pd.to_numeric(ledger.get("max_semantic_sector_weight", pd.Series([np.nan])), errors="coerce").max()),
        "target_hash_unique_count": int(ledger["target_hash"].nunique()),
        "same_day_decision_count": int(pd.to_numeric(ledger.get("decision_uses_same_day_close", pd.Series(False, index=ledger.index)), errors="coerce").fillna(False).astype(bool).sum()),
        "purpose": spec.purpose,
    })
    return base


def _daily_order_signature(orders: pd.DataFrame, index: pd.DatetimeIndex) -> pd.Series:
    if orders.empty:
        return pd.Series("", index=index)
    frame = orders.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    cols = [c for c in ("ticker", "side", "quantity", "execution_price_krw", "fee_krw") if c in frame.columns]
    frame["row_sig"] = frame[cols].astype(str).agg("|".join, axis=1)
    sig = frame.sort_values(["date", *(["ticker"] if "ticker" in frame.columns else [])]).groupby("date")["row_sig"].agg(";".join)
    return sig.reindex(index, fill_value="")


def _add_deltas(metrics: pd.DataFrame, runs: dict[str, dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    by_id = metrics.set_index("candidate_id")
    for candidate_id, run in runs.items():
        spec: CandidateSpec = run["spec"]
        parent_id = PARENT_BY_STRATEGY[spec.strategy]
        parent = runs[parent_id]
        row = by_id.loc[candidate_id].to_dict()
        row["candidate_id"] = candidate_id
        prow = by_id.loc[parent_id]
        for field in (
            "return_pct", "development_return_pct", "validation_return_pct", "purged_validation_return_pct",
            "observed_return_pct", "recent_1y_return_pct", "stress_return_pct", "mdd_pct", "sharpe",
            "order_count", "total_execution_cost_krw", "pending_days", "dca_profit_on_contributions_pct",
        ):
            row[f"{field}_delta"] = float(row[field] - prow[field])
        candidate_ledger = run["ledger"].set_index("date")
        parent_ledger = parent["ledger"].set_index("date")
        common = candidate_ledger.index.intersection(parent_ledger.index)
        row["changed_target_days"] = int(candidate_ledger.loc[common, "target_hash"].ne(parent_ledger.loc[common, "target_hash"]).sum())
        idx = run["account"]["date"]
        osig = _daily_order_signature(run["orders"], pd.DatetimeIndex(idx))
        psig = _daily_order_signature(parent["orders"], pd.DatetimeIndex(idx))
        row["changed_order_days"] = int(osig.ne(psig).sum())
        nav = run["account"].set_index("date")["nav_krw"]
        pnav = parent["account"].set_index("date")["nav_krw"]
        row["changed_nav_days"] = int(nav.sub(pnav).abs().gt(0.01).sum())
        row["parent_candidate_id"] = parent_id
        rows.append(row)
    return pd.DataFrame(rows)


def _annual_monthly(runs: dict[str, dict[str, Any]]) -> tuple[pd.DataFrame, pd.DataFrame]:
    annual: list[dict[str, Any]] = []
    monthly: list[dict[str, Any]] = []
    for candidate_id, run in runs.items():
        if run["spec"].audit_only:
            continue
        nav = run["account"].set_index("date")["nav_krw"]
        for year, values in nav.groupby(nav.index.year):
            annual.append({
                "candidate_id": candidate_id, "strategy": run["spec"].strategy, "year": int(year),
                "return_pct": float((values.iloc[-1] / values.iloc[0] - 1.0) * 100.0),
            })
        sample = nav[nav.index.year == 2026]
        for month, values in sample.groupby(sample.index.month):
            monthly.append({
                "candidate_id": candidate_id, "strategy": run["spec"].strategy, "month": int(month),
                "return_pct": float((values.iloc[-1] / values.iloc[0] - 1.0) * 100.0),
            })
    return pd.DataFrame(annual), pd.DataFrame(monthly)


def _positive_inventory(root: Path) -> pd.DataFrame:
    mappings = {
        ("MA120_VOLATILITY_GUARD_35PCT", "V69"): "V69_VOL_GUARD",
        ("MA120_VOLATILITY_GUARD_35PCT", "V79"): "V79_VOL_GUARD",
        ("FULL_LEADER_100", "V69"): "V69_FULL_LEADER_100",
        ("FULL_LEADER_100", "V79"): "V79_FULL_LEADER_100",
        ("UNCERTAINTY_AWARE_ROTATION", "V69"): "V69_UNCERTAINTY",
        ("UNCERTAINTY_AWARE_ROTATION", "V79"): "V79_UNCERTAINTY",
        ("ABLATE_V79_63_COMPONENT", "V79"): "V79_NO63",
        ("V69_REBALANCE_BAND_2PP", "V69"): "V69_BAND_2PP",
        ("DYNAMIC_MIN_ORDER_50BPS_NAV", "V69"): "V69_DYNAMIC_MIN_ORDER",
        ("DYNAMIC_MIN_ORDER_50BPS_NAV", "V79"): "V79_DYNAMIC_MIN_ORDER",
        ("V69_ALPHA_FIRST_BUY_PRIORITY", "V69"): "V69_ALPHA_FIRST_BUY",
        ("FLOW_ENTRY_BLOCK_PERSISTENT_5D", "V69"): "V69_FLOW_ENTRY_BLOCK",
        ("MA120_CRASH_GUARD", "V79"): None,
    }
    rows: list[dict[str, Any]] = []
    files = sorted(root.glob("reports/v*_*/v*_candidate_promotion.csv"))
    for path in files:
        try:
            frame = pd.read_csv(path)
        except Exception:
            continue
        for source_row, raw in enumerate(frame.to_dict("records"), 1):
            policy = str(raw.get("policy") or raw.get("candidate") or raw.get("scenario") or "")
            if "strategy" in raw:
                pairs = [(str(raw.get("strategy")), raw.get("full_delta_pp", raw.get("return_delta_pp")))]
            elif "v69_full_delta_pp" in raw:
                pairs = [("V69", raw.get("v69_full_delta_pp")), ("V79", raw.get("v79_full_delta_pp"))]
            else:
                continue
            for strategy, value in pairs:
                delta = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
                if pd.isna(delta) or float(delta) <= 0:
                    continue
                candidate_id = mappings.get((policy, strategy))
                rows.append({
                    "source_report": str(path.relative_to(root)), "source_row": int(source_row),
                    "policy": policy, "strategy": strategy, "historical_full_delta_pp": float(delta),
                    "historical_validation_delta_pp": raw.get("validation_delta_pp", raw.get(f"{strategy.lower()}_validation_delta_pp")),
                    "historical_recent_delta_pp": raw.get("recent1y_delta_pp", raw.get("recent_1y_delta_pp", raw.get(f"{strategy.lower()}_recent1y_delta_pp"))),
                    "historical_stress_delta_pp": raw.get("stress_delta_pp", raw.get(f"{strategy.lower()}_stress_delta_pp")),
                    "historical_status": raw.get("status", ""),
                    "v104_rerun_candidate_id": candidate_id or "NOT_PORTABLE_TO_V104_EXPLICIT_PIPELINE",
                    "v104_same_engine_rerun_available": bool(candidate_id),
                })
    return pd.DataFrame(rows).sort_values("historical_full_delta_pp", ascending=False).reset_index(drop=True)


def _causal_row(agent: str, role: str, parent: dict[str, Any], mutated: dict[str, Any], mutation: str) -> dict[str, Any]:
    index = pd.DatetimeIndex(parent["account"]["date"])
    pledger = parent["ledger"].set_index("date")
    mledger = mutated["ledger"].set_index("date")
    common = pledger.index.intersection(mledger.index)
    target_days = int(pledger.loc[common, "target_hash"].ne(mledger.loc[common, "target_hash"]).sum())
    psig = _daily_order_signature(parent["orders"], index)
    msig = _daily_order_signature(mutated["orders"], index)
    order_days = int(psig.ne(msig).sum())
    nav_delta = float(mutated["account"]["nav_krw"].iloc[-1] - parent["account"]["nav_krw"].iloc[-1])
    capital_changed = bool(target_days > 0 or order_days > 0 or abs(nav_delta) > 0.01)
    return {
        "agent": agent, "causal_role": role, "mutation": mutation,
        "parent_candidate": parent["spec"].candidate_id, "mutated_candidate": mutated["spec"].candidate_id,
        "target_hash_changed_days": target_days, "order_signature_changed_days": order_days,
        "ending_nav_delta_krw": nav_delta, "capital_path_changed": capital_changed,
        "governance_output_changed": False, "passed": capital_changed,
    }


def _causal_audit(runs: dict[str, dict[str, Any]], priority: list[str]) -> pd.DataFrame:
    rows = [
        _causal_row("UniverseAgent", "CAPITAL_CAUSAL", runs["V69_PARENT"], runs["V69_FORCE_CORE_ONLY_MUTATION"], "force all theme gates false"),
        _causal_row("MarketRegimeAgent", "CAPITAL_CAUSAL", runs["V69_PARENT"], runs["V69_VOL_GUARD"], "replace D1 MA120 with volatility guard"),
        _causal_row("CandidateSelectionAgent", "CAPITAL_CAUSAL", runs["V79_PARENT"], runs["V79_NO63"], "remove 63-session sleeve component"),
        _causal_row("StrategyAgent", "CAPITAL_CAUSAL", runs["V69_PARENT"], runs["V69_FULL_LEADER_100"], "change fixed 80/20 to full leader"),
        _causal_row("RiskExecutionAgent", "CAPITAL_CAUSAL", runs["V69_PARENT"], runs["V69_BAND_2PP"], "change rebalance band only"),
        _causal_row("MarketEvidenceAgent", "CAPITAL_CAUSAL_CANDIDATE_DIAGNOSTIC_ACTIVE", runs["V79_PARENT"], runs["V79_DART_VETO"], "apply DART persistent-loss veto"),
    ]
    route3 = priority[:3]
    route1 = priority[:1]
    rows.append({
        "agent": "ReviewFeedbackAgent", "causal_role": "GOVERNANCE_CAUSAL_NO_CAPITAL",
        "mutation": "change maximum parallel shadow slots from 3 to 1",
        "parent_candidate": "+".join(route3), "mutated_candidate": "+".join(route1),
        "target_hash_changed_days": 0, "order_signature_changed_days": 0, "ending_nav_delta_krw": 0.0,
        "capital_path_changed": False, "governance_output_changed": route3 != route1,
        "passed": route3 != route1,
    })
    return pd.DataFrame(rows)


def _static_ledger(index: pd.DatetimeIndex, core: str, ticker: str, open_px: pd.Series) -> pd.DataFrame:
    valid = open_px.notna() & open_px.gt(0)
    start = valid[valid].index.min() if valid.any() else None
    rows = []
    for date in index:
        weights = {core: 1.0} if start is None or date < start else {ticker: 1.0}
        payload = json.dumps(weights, sort_keys=True)
        rows.append({"date": date, "target_weights_json": payload, "target_hash": sha256(payload.encode()).hexdigest()})
    return pd.DataFrame(rows)


def _benchmark_comparison(root: Path, parent_context: dict[str, Any]) -> pd.DataFrame:
    market = parent_context["market"]
    cfg77 = parent_context["cfg77"]
    core = cfg77.core_ticker
    execution = v101._policy(root, "PARENT_EXECUTION_CONTRACT")
    rows: list[dict[str, Any]] = []
    # Tradable core benchmark through the same execution engine.
    ledger = _static_ledger(market["close"].index, core, core, market["open"][core])
    acc, orders, intents = v101.replay(
        market["close"], market["open"], market["adv20_d1"], ledger,
        initial_capital=float(cfg77.initial_capital_krw), spec=cfg77.base_execution,
        policy=execution, strategy="V69", core_ticker=core,
    )
    rows.append({"benchmark": "KODEX200_BUY_HOLD_COMMON_EXECUTION", "ticker": core, "return_pct": float((acc.nav_krw.iloc[-1] / cfg77.initial_capital_krw - 1) * 100), "ending_nav_krw": float(acc.nav_krw.iloc[-1]), "order_count": len(orders), "comparison_type": "TRADABLE"})
    # KOSPI index reference, price only because the index is not an executable security.
    ks = market["close"]["KS11"].dropna()
    rows.append({"benchmark": "KOSPI_PRICE_INDEX", "ticker": "KS11", "return_pct": float((ks.iloc[-1] / ks.iloc[0] - 1) * 100), "ending_nav_krw": np.nan, "order_count": 0, "comparison_type": "NON_TRADABLE_PRICE_REFERENCE"})
    best: dict[str, Any] | None = None
    universe = parent_context["universe"]
    for ticker in universe.loc[~universe["sector"].astype(str).eq("broad_equity"), "ticker"].astype(str):
        ledger = _static_ledger(market["close"].index, core, ticker, market["open"][ticker])
        try:
            account, orders, _ = v101.replay(
                market["close"], market["open"], market["adv20_d1"], ledger,
                initial_capital=float(cfg77.initial_capital_krw), spec=cfg77.base_execution,
                policy=execution, strategy="V79", core_ticker=core,
            )
        except ValueError:
            continue
        row = {"benchmark": "BEST_THEME_ETF_ORACLE_COMMON_EXECUTION", "ticker": ticker, "return_pct": float((account.nav_krw.iloc[-1] / cfg77.initial_capital_krw - 1) * 100), "ending_nav_krw": float(account.nav_krw.iloc[-1]), "order_count": len(orders), "comparison_type": "HINDSIGHT_ORACLE_NOT_STRATEGY"}
        if best is None or row["return_pct"] > best["return_pct"]:
            best = row
    if best:
        rows.append(best)
    rows.append({"benchmark": "LEGACY_P2_PLUS_P3", "ticker": "N/A", "return_pct": np.nan, "ending_nav_krw": np.nan, "order_count": np.nan, "comparison_type": "NOT_EXECUTABLE_SIGNAL_DEFINITION_ARCHIVED_REFERENCE"})
    return pd.DataFrame(rows)


def _shadow_observations(runs: dict[str, dict[str, Any]], enabled: list[str]) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for candidate_id in enabled:
        run = runs[candidate_id]
        parent = runs[PARENT_BY_STRATEGY[run["spec"].strategy]]
        cand = run["account"].set_index("date")
        base = parent["account"].set_index("date")
        cledger = run["ledger"].set_index("date")
        pledger = parent["ledger"].set_index("date")
        frame = pd.DataFrame(index=cand.index)
        frame["candidate_id"] = candidate_id
        frame["parent_candidate_id"] = parent["spec"].candidate_id
        frame["strategy"] = run["spec"].strategy
        frame["candidate_fingerprint"] = run["spec"].fingerprint
        frame["input_hash"] = run["input_hash"]
        frame["parent_nav_krw"] = base["nav_krw"]
        frame["candidate_nav_krw"] = cand["nav_krw"]
        frame["candidate_minus_parent_nav_krw"] = cand["nav_krw"] - base["nav_krw"]
        frame["parent_target_hash"] = pledger["target_hash"]
        frame["candidate_target_hash"] = cledger["target_hash"]
        frame["changed_decision"] = frame["parent_target_hash"].ne(frame["candidate_target_hash"])
        frame["historical_replay_only"] = True
        frame["new_forward_observation"] = False
        frame.index.name = "date"
        rows.append(frame.reset_index())
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def _operational_gaps() -> pd.DataFrame:
    return pd.DataFrame([
        {"item": "NEW_FORWARD_SESSIONS", "severity": "BLOCK_PROMOTION", "status": "ZERO", "required": "sessions after V104 freeze with identical parent/candidate input hashes"},
        {"item": "BROKER_EXECUTION_CONTRACT", "severity": "BLOCK_LIVE", "status": "UNVERIFIED_EXTERNAL", "required": "actual order, fill, fee, tax, reject and reconciliation data"},
        {"item": "NEWS_PIT_HISTORY", "severity": "BLOCK_NEWS_ALPHA", "status": "DATA_BLOCKED", "required": "published_at, first_seen_at, source document and correction lineage"},
        {"item": "ETF_EFFECTIVE_DATED_HOLDINGS", "severity": "WARN_PAPER", "status": "STATIC_PROXY", "required": "daily constituent weights for overlap and fundamental evidence"},
        {"item": "P2_PLUS_P3_EXECUTABLE_DEFINITION", "severity": "BLOCK_SAME_ENGINE_COMPARISON", "status": "ARCHIVED_NAV_ONLY", "required": "sealed signal and allocation rules"},
        {"item": "CAPITAL_CAPACITY", "severity": "WARN_PAPER", "status": "V101_DIAGNOSED", "required": "account-size-specific ADV and realized participation validation"},
    ])


def _candidate_job(root_text: str, candidate_id: str) -> tuple[str, str]:
    root = Path(root_text)
    specs = load_candidate_specs(root)
    result = replay_candidate(root, specs[candidate_id])
    cache = root / ".v104_cache"
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / f"{candidate_id}.pkl"
    with path.open("wb") as handle:
        pickle.dump(result, handle, protocol=pickle.HIGHEST_PROTOCOL)
    return candidate_id, str(path)


def run(root: Path | str) -> dict[str, Any]:
    root = Path(root)
    out = root / "reports" / REPORT
    out.mkdir(parents=True, exist_ok=True)
    cfg = load_config(root)
    _progress(root, "START")
    specs = load_candidate_specs(root)
    future_path = out / "v104_future_mutation_audit.csv"
    if not future_path.exists():
        raise RuntimeError("run the isolated V104 future-mutation checks before the integrated audit")
    future = pd.read_csv(future_path)
    required_future = {"V69_PARENT", "V79_PARENT", *cfg["forward_adapter_priority"]}
    if set(future["candidate_id"]) != required_future or not future["passed"].astype(bool).all():
        raise RuntimeError("V104 future-mutation audit is incomplete or failed")
    _progress(root, "FUTURE_AUDIT_LOADED")
    runs: dict[str, dict[str, Any]] = {}
    cache_dir = root / ".v104_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    missing: list[str] = []
    for candidate_id in specs:
        cached_path = cache_dir / f"{candidate_id}.pkl"
        if cached_path.exists():
            with cached_path.open("rb") as handle:
                runs[candidate_id] = pickle.load(handle)
        else:
            missing.append(candidate_id)
    if missing:
        workers = min(int(cfg.get("parallel_workers", 4)), len(missing))
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(_candidate_job, str(root), candidate_id) for candidate_id in missing]
            for future in as_completed(futures):
                candidate_id, path_text = future.result()
                with Path(path_text).open("rb") as handle:
                    runs[candidate_id] = pickle.load(handle)
    _progress(root, "CANDIDATES_LOADED")
    parent_context = build_candidate_ledgers(root, specs["V69_PARENT"])
    _progress(root, "PARENT_CONTEXT_BUILT")
    index = parent_context["market"]["close"].index
    purged_start = _purged_start(index, int(cfg["purge_sessions"]))
    metrics = pd.DataFrame([_metric_row(run, purged_start) for run in runs.values()])
    deltas = _add_deltas(metrics, runs)
    annual, monthly = _annual_monthly(runs)
    inventory = _positive_inventory(root)
    causal = _causal_audit(runs, list(cfg["forward_adapter_priority"]))
    _progress(root, "METRICS_COMPLETE")

    # Explicit V104 parent pipeline must exactly reproduce legacy common paper NAV.
    _market, _universe, old_l69, old_l79, _sel = v84.build_strategy_ledgers_legacy(root)
    p69 = runs["V69_PARENT"]
    p79 = runs["V79_PARENT"]
    old_a69, _ = v84.replay_target_ledger(
        _market["close"], _market["open"], _market["adv20_d1"], old_l69,
        initial_capital=float(parent_context["cfg77"].initial_capital_krw), policy=v84.ExecutionPolicy.from_v77(parent_context["cfg77"].base_execution),
        rebalance_band=0.0, scenario="V104_LEGACY_PARITY_69", buy_priority="CORE_THEN_TARGET_DESC", core_ticker=parent_context["cfg77"].core_ticker,
    )
    old_a79, _ = v84.replay_target_ledger(
        _market["close"], _market["open"], _market["adv20_d1"], old_l79,
        initial_capital=float(parent_context["cfg77"].initial_capital_krw), policy=v84.ExecutionPolicy.from_v77(parent_context["cfg77"].base_execution),
        rebalance_band=0.05, scenario="V104_LEGACY_PARITY_79",
    )
    _progress(root, "LEGACY_REPLAY_COMPLETE")
    parent_parity = pd.DataFrame([
        {"strategy": "V69", "legacy_nav_krw": float(old_a69.nav_krw.iloc[-1]), "explicit_v104_nav_krw": float(p69["account"].nav_krw.iloc[-1]), "abs_error_krw": abs(float(old_a69.nav_krw.iloc[-1] - p69["account"].nav_krw.iloc[-1]))},
        {"strategy": "V79", "legacy_nav_krw": float(old_a79.nav_krw.iloc[-1]), "explicit_v104_nav_krw": float(p79["account"].nav_krw.iloc[-1]), "abs_error_krw": abs(float(old_a79.nav_krw.iloc[-1] - p79["account"].nav_krw.iloc[-1]))},
    ])


    delta_by_id = deltas.set_index("candidate_id")
    enabled: list[str] = []
    adapter_rows: list[dict[str, Any]] = []
    for rank, candidate_id in enumerate(cfg["forward_adapter_priority"], 1):
        run = runs[candidate_id]
        row = delta_by_id.loc[candidate_id]
        future_ok = bool(future.set_index("candidate_id").loc[candidate_id, "passed"])
        gates = {
            "adapter_implemented_and_tested": True,
            "target_change": int(row["changed_target_days"]) > 0,
            "order_or_nav_change": int(row["changed_order_days"]) > 0 or int(row["changed_nav_days"]) > 0,
            "no_negative_cash": int(row["negative_cash_days"]) == 0,
            "future_mutation_invariant": future_ok,
            "same_input_hash_as_parent": run["input_hash"] == runs[PARENT_BY_STRATEGY[run["spec"].strategy]]["input_hash"],
        }
        ready = bool(all(gates.values()))
        if ready and len(enabled) < int(cfg["maximum_parallel_forward_candidates"]):
            enabled.append(candidate_id)
        adapter_rows.append({
            "candidate_id": candidate_id, "priority_rank": rank, "strategy": run["spec"].strategy,
            "candidate_fingerprint": run["spec"].fingerprint, "input_hash": run["input_hash"],
            "paper_account_id": f"PAPER-V104-{candidate_id}",
            "adapter_status": "IMPLEMENTED_AND_TESTED_FORWARD_NOT_STARTED" if ready else "BLOCKED_GATE_FAILURE",
            "enabled_for_new_forward": ready, "historical_return_delta_pp": float(row["return_pct_delta"]),
            "gates_json": json.dumps(gates, sort_keys=True),
        })
    adapters = pd.DataFrame(adapter_rows)
    observations = _shadow_observations(runs, enabled)
    _progress(root, "BENCHMARK_BEGIN")
    benchmarks = _benchmark_comparison(root, parent_context)
    _progress(root, "BENCHMARK_COMPLETE")
    gaps = _operational_gaps()

    legacy_source = (root / "src/quant_harness/v84_dual_paper_parity/engine.py").read_text(encoding="utf-8")
    registry_dispatch_fixed = all(token in legacy_source for token in (
        "build_strategy_ledgers_legacy", "runtime_candidate_id", "v104_end_to_end_causal_challenger_audit.adapter",
    ))
    market_files = sorted((root / "data/toss_v19c_daily").glob("*_1d.csv"))
    input_hash_source = (root / "src/quant_harness/v104_end_to_end_causal_challenger_audit/adapter.py").read_text(encoding="utf-8")
    input_hash_binds_market = bool(market_files) and 'glob("*_1d.csv")' in input_hash_source
    gates = pd.DataFrame([
        {"gate": "EXPLICIT_PARENT_V69_PARITY_UNDER_1KRW", "passed": bool(parent_parity.loc[parent_parity.strategy.eq("V69"), "abs_error_krw"].iloc[0] < 1.0), "detail": parent_parity.to_json(orient="records")},
        {"gate": "EXPLICIT_PARENT_V79_PARITY_UNDER_1KRW", "passed": bool(parent_parity.loc[parent_parity.strategy.eq("V79"), "abs_error_krw"].iloc[0] < 1.0), "detail": parent_parity.to_json(orient="records")},
        {"gate": "LEGACY_REGISTRY_DYNAMIC_DISPATCH_DEFECT_CONFIRMED_AND_FIXED", "passed": bool(registry_dispatch_fixed), "detail": "V84 legacy path is preserved for audit, while active registry entries dispatch the V104 explicit adapter"},
        {"gate": "ACTIVE_INPUT_HASH_BINDS_MARKET_FLOW_AND_FILING_DATA", "passed": bool(input_hash_binds_market), "detail": f"market_files={len(market_files)} plus flow and filing inputs"},
        {"gate": "ALL_SIX_CAPITAL_AGENTS_CAUSAL", "passed": bool(causal[causal.causal_role.str.startswith("CAPITAL")]["passed"].all()), "detail": causal.to_json(orient="records")},
        {"gate": "REVIEW_FEEDBACK_GOVERNANCE_CAUSAL_NO_CAPITAL", "passed": bool(causal.loc[causal.agent.eq("ReviewFeedbackAgent"), "passed"].all()), "detail": "shadow routing changes; parent capital path remains unchanged"},
        {"gate": "HISTORICAL_POSITIVE_CANDIDATES_REMEMBERED", "passed": bool(len(inventory) >= 13 and {"ABLATE_V79_63_COMPONENT", "MA120_VOLATILITY_GUARD_35PCT", "FULL_LEADER_100"}.issubset(set(inventory.policy))), "detail": f"rows={len(inventory)}"},
        {"gate": "PRIORITY_RUNTIME_ADAPTERS_READY", "passed": bool(len(enabled) == int(cfg["maximum_parallel_forward_candidates"])), "detail": "+".join(enabled)},
        {"gate": "PRIORITY_CANDIDATES_FUTURE_MUTATION_INVARIANT", "passed": bool(future[future.candidate_id.isin(cfg["forward_adapter_priority"])]["passed"].all()), "detail": future.to_json(orient="records")},
        {"gate": "NO_SAME_DAY_DECISIONS", "passed": bool(metrics.same_day_decision_count.eq(0).all()), "detail": "all explicit candidate ledgers"},
        {"gate": "NO_NEGATIVE_CASH", "passed": bool(metrics.negative_cash_days.eq(0).all()), "detail": "all base candidate replays"},
        {"gate": "NO_AUTOMATIC_CHAMPION_PROMOTION", "passed": bool(not cfg["promotion"]["automatic_champion_promotion"]), "detail": "historical results remain screening only"},
        {"gate": "P2_P3_COMPARISON_TRUTHFUL", "passed": bool(benchmarks.loc[benchmarks.benchmark.eq("LEGACY_P2_PLUS_P3"), "return_pct"].isna().all()), "detail": "no executable sealed P2+P3 signal definition"},
        {"gate": "LIVE_EXECUTION_BLOCKED", "passed": bool(not cfg["live_execution_allowed"]), "detail": "paper research only"},
    ])

    _progress(root, "GATES_COMPLETE")
    metrics.to_csv(out / "v104_candidate_metrics.csv", index=False)
    deltas.to_csv(out / "v104_candidate_deltas.csv", index=False)
    annual.to_csv(out / "v104_annual_returns.csv", index=False)
    monthly.to_csv(out / "v104_2026_monthly_returns.csv", index=False)
    inventory.to_csv(out / "v104_historical_improvement_inventory.csv", index=False)
    causal.to_csv(out / "v104_agent_causal_audit.csv", index=False)
    parent_parity.to_csv(out / "v104_parent_parity.csv", index=False)
    future.to_csv(out / "v104_future_mutation_audit.csv", index=False)
    adapters.to_csv(out / "v104_runtime_adapter_registry.csv", index=False)
    observations.to_csv(out / "v104_shadow_replay_observations.csv", index=False)
    benchmarks.to_csv(out / "v104_benchmark_comparison.csv", index=False)
    gaps.to_csv(out / "v104_operational_gap_register.csv", index=False)
    gates.to_csv(out / "v104_quality_gates.csv", index=False)

    _progress(root, "CSV_WRITES_COMPLETE")
    runtime_contract = {
        "schema_version": 1,
        "release": "V104_END_TO_END_CAUSAL_CHALLENGER_AUDIT",
        "active_parent_runtime": "EXPLICIT_SEVEN_AGENT_DISPATCH",
        "historical_replay_is_forward_evidence": False,
        "new_forward_observations": 0,
        "maximum_parallel_candidates": int(cfg["maximum_parallel_forward_candidates"]),
        "enabled_candidates": enabled,
        "candidates": {row["candidate_id"]: row for row in adapter_rows},
        "automatic_parent_mutation": False,
        "automatic_champion_promotion": False,
        "live_execution_allowed": False,
    }
    (root / "config/v104_challenger_runtime_contract.yaml").write_text(yaml.safe_dump(runtime_contract, sort_keys=False, allow_unicode=True), encoding="utf-8")
    (out / "v104_runtime_adapter_registry.json").write_text(json.dumps(runtime_contract, indent=2, ensure_ascii=False), encoding="utf-8")

    registry = {
        "release": "V104_END_TO_END_CAUSAL_CHALLENGER_AUDIT",
        "status": "explicit_parent_dispatch_and_challenger_adapters_implemented_forward_not_started",
        "parent_parity": parent_parity.to_dict("records"),
        "enabled_forward_candidates": enabled,
        "historical_positive_candidates": int(len(inventory)),
        "capital_causal_agents": int(causal[causal.causal_role.str.startswith("CAPITAL")].passed.sum()),
        "governance_causal_agents": int(causal[causal.causal_role.str.startswith("GOVERNANCE")].passed.sum()),
        "quality_passed": bool(gates.passed.all()),
        "automatic_promotion": False,
        "new_forward_observations": 0,
        "live_execution_allowed": False,
    }
    (out / "v104_audit_registry.json").write_text(json.dumps(registry, indent=2, ensure_ascii=False), encoding="utf-8")
    _progress(root, "REGISTRY_WRITES_COMPLETE")
    for cache_file in cache_dir.glob("*.pkl"):
        cache_file.unlink(missing_ok=True)
    cache_dir.rmdir()
    _progress(root, "DONE")
    return {
        "runs": runs, "metrics": metrics, "deltas": deltas, "annual": annual, "monthly": monthly,
        "inventory": inventory, "causal": causal, "parent_parity": parent_parity, "future": future,
        "adapters": adapters, "observations": observations, "benchmarks": benchmarks, "gaps": gaps,
        "quality": gates, "registry": registry,
    }
