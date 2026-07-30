from __future__ import annotations

import json
import math
import sqlite3
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd
import yaml

from quant_harness.v69_dynamic_theme_leadership import engine as v69
from quant_harness.v77_corrected_price_allocation import engine as v77
from quant_harness.v78_preregistered_alpha_research.engine import build_baseline_features
from quant_harness.v79_generic_trend_sleeve import engine as v79
from quant_harness.v100_strategy_agent.policy import ACTIVE_STRATEGY_POLICY, build_v69_target_ledger, build_v79_target_ledger
from quant_harness.v101_risk_execution_agent.policy import ACTIVE_RISK_EXECUTION_POLICY
from quant_harness.v102_market_evidence_agent.policy import ACTIVE_POLICY as ACTIVE_MARKET_EVIDENCE_POLICY, build_flow_evidence, build_fundamental_evidence, apply_evidence_policy

REPORT = "v84_dual_paper_parity"


@dataclass(frozen=True)
class ExecutionPolicy:
    buy_fee_bps: float
    sell_fee_bps: float
    half_spread_bps: float
    impact_bps_at_1pct_adv: float
    max_impact_bps: float
    max_participation_of_d1_adv: float
    minimum_order_notional_krw: float

    @classmethod
    def from_v77(cls, spec: v77.ExecutionSpec) -> "ExecutionPolicy":
        return cls(**asdict(spec))

    def as_v77(self) -> v77.ExecutionSpec:
        return v77.ExecutionSpec(**asdict(self))


@dataclass
class PortfolioState:
    cash: float
    quantities: dict[str, int] = field(default_factory=dict)
    pending: bool = False
    prior_signature: str | None = None


@dataclass(frozen=True)
class Fill:
    ticker: str
    side: str
    quantity: int
    reference_open_krw: float
    execution_price_krw: float
    fee_krw: float
    impact_bps: float
    adv20_d1_krw: float
    participation_of_d1_adv: float


def _signature(weights: Mapping[str, float]) -> str:
    return sha256(json.dumps(dict(sorted(weights.items())), separators=(",", ":")).encode()).hexdigest()


def _normalise_targets(weights: Mapping[str, float]) -> dict[str, float]:
    clean = {str(k).zfill(6): float(v) for k, v in weights.items() if float(v) > 1e-12}
    total = sum(clean.values())
    if not clean or not np.isclose(total, 1.0, atol=1e-9):
        raise ValueError(f"target weights must sum to one; total={total}")
    return clean


def execute_target_map(
    state: PortfolioState,
    *,
    targets: Mapping[str, float],
    open_prices: Mapping[str, float],
    adv20_d1: Mapping[str, float],
    policy: ExecutionPolicy,
    rebalance_band: float,
    buy_priority: str = "DEFICIT_DESC",
    core_ticker: str | None = None,
) -> tuple[PortfolioState, list[Fill], dict[str, Any]]:
    """Apply one session using the same sell-first/participation/impact math as backtests."""
    targets = _normalise_targets(targets)
    tracked = set(state.quantities) | set(targets)
    missing = sorted(t for t in tracked if t not in open_prices or not np.isfinite(open_prices[t]) or open_prices[t] <= 0)
    if missing:
        raise ValueError(f"missing executable adjusted open: {missing}")
    nav_open = state.cash + sum(q * float(open_prices[t]) for t, q in state.quantities.items())
    actual = {t: state.quantities.get(t, 0) * float(open_prices[t]) / nav_open for t in tracked} if nav_open > 0 else {}
    max_drift = max((abs(actual.get(t, 0.0) - targets.get(t, 0.0)) for t in tracked), default=0.0)
    sig = _signature(targets)
    trigger = bool(state.pending or sig != state.prior_signature or max_drift >= rebalance_band)
    quantities = dict(state.quantities)
    cash = float(state.cash)
    pending = False
    fills: list[Fill] = []
    participation_limited = 0
    if trigger:
        desired = {t: int(math.floor(nav_open * w / float(open_prices[t]))) for t, w in targets.items()}
        for ticker in quantities:
            desired.setdefault(ticker, 0)
        # sell first
        for ticker in sorted(quantities):
            delta = quantities.get(ticker, 0) - desired.get(ticker, 0)
            if delta <= 0:
                continue
            raw = float(open_prices[ticker]); adv = float(adv20_d1.get(ticker, np.nan))
            cap = int(math.floor(adv * policy.max_participation_of_d1_adv / raw)) if np.isfinite(adv) and adv > 0 else 0
            qty = min(delta, cap)
            if qty < delta:
                pending = True; participation_limited += 1
            if qty <= 0 or qty * raw < policy.minimum_order_notional_krw:
                pending = pending or delta > 0; continue
            notional = qty * raw
            impact = v77._impact_bps(notional, adv, policy.as_v77())
            px = raw * (1.0 - (policy.half_spread_bps + impact) / 10000.0)
            fee = qty * px * policy.sell_fee_bps / 10000.0
            cash += qty * px - fee
            quantities[ticker] = quantities.get(ticker, 0) - qty
            fills.append(Fill(ticker, "SELL", qty, raw, px, fee, impact, adv, notional / adv if np.isfinite(adv) and adv > 0 else np.nan))
        # buy by deficit then target weight, same deterministic order as V79
        if buy_priority == "CORE_THEN_TARGET_DESC":
            if not core_ticker:
                raise ValueError("core_ticker is required for CORE_THEN_TARGET_DESC")
            buy_order = [core_ticker] + [t for t in sorted(targets, key=lambda x: (targets[x], x), reverse=True) if t != core_ticker]
        elif buy_priority == "DEFICIT_DESC":
            buy_order = sorted(targets, key=lambda t: (desired.get(t, 0) - quantities.get(t, 0), targets[t], t), reverse=True)
        else:
            raise ValueError(f"unknown buy priority {buy_priority}")
        for ticker in buy_order:
            delta = desired.get(ticker, 0) - quantities.get(ticker, 0)
            if delta <= 0:
                continue
            raw = float(open_prices[ticker]); adv = float(adv20_d1.get(ticker, np.nan))
            cap = int(math.floor(adv * policy.max_participation_of_d1_adv / raw)) if np.isfinite(adv) and adv > 0 else 0
            qty = min(delta, cap)
            if qty < delta:
                pending = True; participation_limited += 1
            if qty <= 0 or qty * raw < policy.minimum_order_notional_krw:
                pending = pending or delta > 0; continue
            requested = qty
            qty, impact, px, fee, participation = v77._buy_fill_terms(
                cash=cash, max_quantity=requested, raw_open=raw, adv=adv, spec=policy.as_v77()
            )
            if qty < requested:
                pending = True
            if qty <= 0 or qty * raw < policy.minimum_order_notional_krw:
                pending = True; continue
            cash -= qty * px + fee
            quantities[ticker] = quantities.get(ticker, 0) + qty
            fills.append(Fill(ticker, "BUY", qty, raw, px, fee, impact, adv, participation))
    next_state = PortfolioState(cash=cash, quantities=quantities, pending=pending, prior_signature=sig)
    return next_state, fills, {"triggered": trigger, "max_abs_weight_drift_open": max_drift, "participation_limited_orders": participation_limited, "risk_execution_policy": ACTIVE_RISK_EXECUTION_POLICY}


def replay_target_ledger(
    close: pd.DataFrame,
    open_px: pd.DataFrame,
    adv20_d1: pd.DataFrame,
    ledger: pd.DataFrame,
    *,
    initial_capital: float,
    policy: ExecutionPolicy,
    rebalance_band: float,
    scenario: str,
    buy_priority: str = "DEFICIT_DESC",
    core_ticker: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    indexed = ledger.set_index("date").reindex(close.index)
    state = PortfolioState(initial_capital)
    daily: list[dict[str, Any]] = []
    orders: list[dict[str, Any]] = []
    for date in close.index:
        raw = indexed.loc[date, "target_weights_json"]
        targets = raw if isinstance(raw, dict) else json.loads(str(raw))
        relevant = set(state.quantities) | set(targets)
        opens = {t: float(open_px.loc[date, t]) for t in relevant}
        adv = {t: float(adv20_d1.loc[date, t]) if t in adv20_d1.columns else np.nan for t in relevant}
        state, fills, audit = execute_target_map(state, targets=targets, open_prices=opens, adv20_d1=adv, policy=policy, rebalance_band=rebalance_band, buy_priority=buy_priority, core_ticker=core_ticker)
        for fill in fills:
            orders.append({"date": date, "scenario": scenario, **asdict(fill)})
        nav = state.cash + sum(q * float(close.loc[date, t]) for t, q in state.quantities.items())
        daily.append({
            "date": date, "scenario": scenario, "cash_krw": state.cash, "nav_krw": nav,
            "target_weights_json": json.dumps(targets, sort_keys=True),
            "holdings_json": json.dumps({k: v for k, v in state.quantities.items() if v}, sort_keys=True),
            "pending_execution": state.pending, **audit,
        })
    return pd.DataFrame(daily), pd.DataFrame(orders)


def build_strategy_ledgers_legacy(root: Path) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    cfg77 = v77._load_config(root)
    market = v77.load_adjusted_market(root, cfg77)
    v69_cfg = replace(v69._load_config(root), end_date=cfg77.end_date, core_ticker=cfg77.core_ticker, benchmark_ticker=cfg77.benchmark_ticker, leader_weight=0.80)
    universe = v69._load_universe(root, v69_cfg)
    base_features = build_baseline_features(market["close"], market["value"], universe, v69_cfg)
    base_selection = v69.select_dynamic_leader(market["close"].index, universe, base_features, v69_cfg)
    base_selection["target_leader_weight"] = base_selection["leader_ticker"].notna().astype(float) * 0.80
    strategy_params = {
        "minimum_base_leader_weight": 0.60,
        "maximum_base_leader_weight": 0.80,
        "full_confidence_normalized_gap": 1.0,
        "minimum_sleeve_deployment_fraction": 0.50,
        "maximum_v79_semantic_sector_weight": 0.70,
    }
    v69_ledger = build_v69_target_ledger(
        base_selection, core_ticker=cfg77.core_ticker,
        policy=ACTIVE_STRATEGY_POLICY, params=strategy_params,
    )

    cfg79 = v79._load_config(root); sleeve_cfg = cfg79["trend_sleeve"]
    sleeve_features = v79.build_generic_trend_features(
        market["close"], market["value"], universe,
        horizons=tuple(int(x) for x in sleeve_cfg["horizons_days"]),
        horizon_weights=tuple(float(x) for x in sleeve_cfg["horizon_weights"]),
        trend_ma_days=int(sleeve_cfg["trend_ma_days"]), minimum_history_days=int(sleeve_cfg["minimum_history_days"]),
        minimum_median_value_20d_krw=float(sleeve_cfg["minimum_median_value_20d_krw"]),
    )
    sleeve_selection = v79.select_persistent_trend_leader(
        market["close"].index, universe, sleeve_features,
        minimum_hold_sessions=int(sleeve_cfg["minimum_hold_sessions"]),
        challenger_score_margin=float(sleeve_cfg["challenger_score_margin"]),
        confirmation_reviews=int(sleeve_cfg["challenger_confirmation_reviews"]),
    )
    sector_by_ticker = universe.set_index(universe["ticker"].astype(str))["sector"].astype(str).to_dict()
    v79_ledger = build_v79_target_ledger(
        base_selection, sleeve_selection, core_ticker=cfg77.core_ticker, base_share=0.70,
        policy=ACTIVE_STRATEGY_POLICY, params=strategy_params, sector_by_ticker=sector_by_ticker,
    )
    flow = build_flow_evidence(root, market["close"].index)
    fundamental_risk, _ = build_fundamental_evidence(root, market["close"].index)
    v69_ledger = apply_evidence_policy(
        v69_ledger, policy_id=ACTIVE_MARKET_EVIDENCE_POLICY, flow=flow,
        fundamental_risk=fundamental_risk, core_ticker=cfg77.core_ticker, strategy="V69",
    )
    v79_ledger = apply_evidence_policy(
        v79_ledger, policy_id=ACTIVE_MARKET_EVIDENCE_POLICY, flow=flow,
        fundamental_risk=fundamental_risk, core_ticker=cfg77.core_ticker, strategy="V79",
    )
    return market, universe, v69_ledger, v79_ledger, base_selection


def build_strategy_ledgers(root: Path) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Resolve the active parent ledgers from the strategy registry.

    V84 historically treated the registry as descriptive metadata and called its
    embedded baseline functions directly.  V104 makes the registry executable:
    when both parent entries name the V104 adapter and a runtime candidate id,
    the exact seven-agent candidate contract is dispatched.  A legacy fallback
    remains only for old release replay and parity audits.
    """
    registry_path = root / "config/strategy_registry_v84.yaml"
    if not registry_path.exists():
        return build_strategy_ledgers_legacy(root)
    registry = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    strategies = {str(row.get("strategy_id")): row for row in registry.get("strategies", [])}
    v69_entry = strategies.get("v69_fixed80_daily_control", {})
    v79_entry = strategies.get("v79_core70_generic_trend30", {})
    adapter_module = "quant_harness.v104_end_to_end_causal_challenger_audit.adapter"
    if (
        v69_entry.get("engine") == adapter_module
        and v79_entry.get("engine") == adapter_module
        and v69_entry.get("runtime_candidate_id")
        and v79_entry.get("runtime_candidate_id")
    ):
        # Lazy import prevents a module import cycle during V104's legacy parity audit.
        from quant_harness.v104_end_to_end_causal_challenger_audit.adapter import (
            build_candidate_ledgers,
            load_candidate_specs,
        )

        specs = load_candidate_specs(root)
        v69_id = str(v69_entry["runtime_candidate_id"])
        v79_id = str(v79_entry["runtime_candidate_id"])
        if v69_id not in specs or v79_id not in specs:
            raise ValueError(f"registry runtime candidate missing from V104 config: {v69_id}, {v79_id}")
        built69 = build_candidate_ledgers(root, specs[v69_id])
        built79 = build_candidate_ledgers(root, specs[v79_id])
        if built69["input_hash"] != built79["input_hash"]:
            raise ValueError("active parent strategies were built from different input hashes")
        return (
            built69["market"],
            built69["universe"],
            built69["ledger"],
            built79["ledger"],
            built69["selection69"],
        )
    return build_strategy_ledgers_legacy(root)


def build_canonical_market(root: Path, market: dict[str, Any], universe: pd.DataFrame) -> tuple[Path, Path, pd.DataFrame]:
    target = root / "data/canonical/v84_market_bars.csv"
    manifest_path = root / "data/canonical/v84_market_manifest.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for ticker in universe["ticker"].astype(str):
        for date in market["close"].index:
            if pd.isna(market["close"].loc[date, ticker]):
                continue
            rows.append({
                "date": date.date().isoformat(), "ticker": ticker,
                "open": market["open"].loc[date, ticker], "high": market["high"].loc[date, ticker],
                "low": market["low"].loc[date, ticker], "close": market["close"].loc[date, ticker],
                "volume": market["volume"].loc[date, ticker], "value_approx": market["value"].loc[date, ticker],
                "source": "toss_openapi_1d_adjusted", "price_scale": "ADJUSTED_OHLC",
            })
    frame = pd.DataFrame(rows)
    frame.to_csv(target, index=False)
    manifest = frame.groupby("ticker").agg(rows=("date", "size"), start=("date", "min"), end=("date", "max"), source=("source", "first")).reset_index()
    manifest["sha256"] = manifest["ticker"].map(lambda t: sha256((root / f"data/toss_v19c_daily/{t}_1d.csv").read_bytes()).hexdigest())
    manifest.to_csv(manifest_path, index=False)
    return target, manifest_path, frame


class DualPaperStore:
    def __init__(self, path: Path):
        self.path = path; path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as conn:
            conn.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS accounts(strategy_id TEXT PRIMARY KEY,cash REAL NOT NULL,quantities_json TEXT NOT NULL,pending INTEGER NOT NULL,prior_signature TEXT);
            CREATE TABLE IF NOT EXISTS sessions(strategy_id TEXT NOT NULL,session TEXT NOT NULL,nav REAL NOT NULL,cash REAL NOT NULL,holdings_json TEXT NOT NULL,plan_hash TEXT NOT NULL,PRIMARY KEY(strategy_id,session));
            CREATE TABLE IF NOT EXISTS fills(strategy_id TEXT NOT NULL,session TEXT NOT NULL,ticker TEXT NOT NULL,side TEXT NOT NULL,quantity INTEGER NOT NULL,reference_open REAL NOT NULL,execution_price REAL NOT NULL,fee REAL NOT NULL,impact_bps REAL NOT NULL,participation REAL,PRIMARY KEY(strategy_id,session,ticker,side));
            """)
    def load(self, strategy_id: str, initial_cash: float) -> PortfolioState:
        with sqlite3.connect(self.path) as conn:
            row = conn.execute("SELECT cash,quantities_json,pending,prior_signature FROM accounts WHERE strategy_id=?", (strategy_id,)).fetchone()
        return PortfolioState(initial_cash) if row is None else PortfolioState(float(row[0]), json.loads(row[1]), bool(row[2]), row[3])
    def commit(self, strategy_id: str, session: str, state: PortfolioState, nav: float, fills: list[Fill], plan_hash: str) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute("SELECT plan_hash FROM sessions WHERE strategy_id=? AND session=?", (strategy_id, session)).fetchone()
            if existing:
                if existing[0] != plan_hash: raise ValueError("idempotency conflict for dual-paper session")
                return
            conn.execute("INSERT INTO sessions VALUES(?,?,?,?,?,?)", (strategy_id, session, nav, state.cash, json.dumps(state.quantities, sort_keys=True), plan_hash))
            for f in fills:
                conn.execute("INSERT INTO fills VALUES(?,?,?,?,?,?,?,?,?,?)", (strategy_id, session, f.ticker, f.side, f.quantity, f.reference_open_krw, f.execution_price_krw, f.fee_krw, f.impact_bps, f.participation_of_d1_adv))
            conn.execute("INSERT INTO accounts VALUES(?,?,?,?,?) ON CONFLICT(strategy_id) DO UPDATE SET cash=excluded.cash,quantities_json=excluded.quantities_json,pending=excluded.pending,prior_signature=excluded.prior_signature", (strategy_id, state.cash, json.dumps(state.quantities, sort_keys=True), int(state.pending), state.prior_signature))


def run(root: Path | str) -> dict[str, Any]:
    root = Path(root); out = root / "reports" / REPORT; out.mkdir(parents=True, exist_ok=True)
    market, universe, ledger69, ledger79, _ = build_strategy_ledgers(root)
    cfg77 = v77._load_config(root); policy = ExecutionPolicy.from_v77(cfg77.base_execution)
    acc69, ord69 = replay_target_ledger(market["close"], market["open"], market["adv20_d1"], ledger69, initial_capital=cfg77.initial_capital_krw, policy=policy, rebalance_band=0.0, scenario="V69_DUAL_PAPER_PARITY", buy_priority="CORE_THEN_TARGET_DESC", core_ticker=cfg77.core_ticker)
    acc79, ord79 = replay_target_ledger(market["close"], market["open"], market["adv20_d1"], ledger79, initial_capital=cfg77.initial_capital_krw, policy=policy, rebalance_band=0.05, scenario="V79_DUAL_PAPER_PARITY")
    # Compare with official historical engines.
    official69, _, _ = v77.execute(market["close"], market["open"], market["adv20_d1"],
        pd.DataFrame({"date": ledger69["date"], "leader_ticker": [next((k for k,v in json.loads(x).items() if k != cfg77.core_ticker and v > 0.5), None) for x in ledger69["target_weights_json"]],
                      "review_monthly": True, "information_cutoff": pd.to_datetime(ledger69["date"]).shift(1)}), cfg77.core_ticker, cfg77.initial_capital_krw, "FIXED_80", "DAILY_EXACT", cfg77.base_execution)
    official79, _, _ = v79.execute_multi_target(market["close"], market["open"], market["adv20_d1"], ledger79, initial_capital=cfg77.initial_capital_krw, spec=cfg77.base_execution, rebalance_band=0.05, scenario="OFFICIAL79")
    parity = pd.DataFrame([
        {"strategy_id":"v69_fixed80_daily_control","official_final_nav":float(official69.nav_krw.iloc[-1]),"common_final_nav":float(acc69.nav_krw.iloc[-1]),"abs_error_krw":abs(float(official69.nav_krw.iloc[-1]-acc69.nav_krw.iloc[-1]))},
        {"strategy_id":"v79_core70_generic_trend30","official_final_nav":float(official79.nav_krw.iloc[-1]),"common_final_nav":float(acc79.nav_krw.iloc[-1]),"abs_error_krw":abs(float(official79.nav_krw.iloc[-1]-acc79.nav_krw.iloc[-1]))},
    ])
    canonical, manifest, frame = build_canonical_market(root, market, universe)
    config_gates = {
        "v69_weight_single_source": float(yaml.safe_load((root/"config/v69_dynamic_theme_leadership.yaml").read_text())["leadership"]["leader_weight"]) == 0.8,
        "canonical_unique": not frame.duplicated(["date","ticker"]).any(),
        "canonical_adjusted_only": set(frame.source) == {"toss_openapi_1d_adjusted"},
        "v69_parity_under_1krw": float(parity.loc[parity.strategy_id.str.startswith("v69"),"abs_error_krw"].iloc[0]) < 1.0,
        "v79_parity_under_1krw": float(parity.loc[parity.strategy_id.str.startswith("v79"),"abs_error_krw"].iloc[0]) < 1.0,
        "live_blocked": True,
    }
    parity.to_csv(out/"execution_parity.csv", index=False)
    acc69.to_csv(out/"v69_dual_paper_account.csv", index=False); acc79.to_csv(out/"v79_dual_paper_account.csv", index=False)
    pd.concat([ord69, ord79], ignore_index=True).to_csv(out/"dual_paper_fills.csv", index=False)
    pd.DataFrame([{"gate":k,"passed":v} for k,v in config_gates.items()]).to_csv(out/"quality_gates.csv", index=False)
    summary = {"status":"v84_dual_paper_execution_parity_complete_live_blocked","gates":config_gates,"parity":parity.to_dict("records"),"canonical_market":str(canonical.relative_to(root)),"canonical_manifest":str(manifest.relative_to(root)),"live_execution_allowed":False}
    (out/"summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
