"""Historical-only operational comparison for one fixed V79 sleeve challenger."""
from __future__ import annotations

from decimal import Decimal
from hashlib import sha256
import json
import math
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from quant_harness.daily_model_calendar_analysis import (
    END,
    START,
    _contribution,
    _ensure_schema,
    _read_replay_tables,
    _schema_url,
)
from quant_harness.historical_operational_replay import INITIAL_CAPITAL, run_historical_operational_replay
from quant_harness.v104_end_to_end_causal_challenger_audit.adapter import build_candidate_ledgers, load_candidate_specs


BASELINE = "V79_NO63_VOL_GUARD"
CHALLENGER = "V79_HIGH252_PROXIMITY_VOL_GUARD"
CANDIDATES = (BASELINE, CHALLENGER)
CONTRACT_PATH = "config/v79_high252_proximity_challenger.yaml"


def _json_default(value: Any) -> str:
    if isinstance(value, (pd.Timestamp, Decimal)):
        return str(value)
    raise TypeError(type(value).__name__)


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, default=_json_default) + "\n", encoding="utf-8")


def _contract(root: Path) -> tuple[dict[str, Any], str]:
    path = root / CONTRACT_PATH
    raw = path.read_bytes()
    import yaml
    return yaml.safe_load(raw), sha256(raw).hexdigest()


def _replay(root: Path, base_url: str, candidate_id: str, output: Path) -> dict[str, Any]:
    schema = f"v79_high252_{candidate_id.lower()}_20260731".replace("-", "_")
    _ensure_schema(base_url, schema)
    url = _schema_url(base_url, schema)
    # A timeout must not silently discard an already verified prefix of this
    # dedicated TEST-only replay.  The underlying historical runner remains
    # idempotent by date and will process only missing sessions on resume.
    import psycopg
    try:
        with psycopg.connect(url) as conn:
            existing_days = int(conn.execute("SELECT count(*) FROM paper_daily_nav").fetchone()[0])
    except psycopg.errors.UndefinedTable:
        existing_days = 0
    replay = run_historical_operational_replay(
        root, url, reset=existing_days == 0, candidate_id=candidate_id, start_date=START, end_date=END,
        output_dir=output / "replays" / candidate_id,
    )
    nav, trades = _read_replay_tables(url)
    return {"schema": schema, "resumed_existing_days": existing_days, "replay": replay, "nav": nav, "trades": trades}


def _filled(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return trades.copy()
    out = trades[trades["paper_fill_id"].notna()].copy()
    return out.drop_duplicates("paper_fill_id")


def _metrics(nav: pd.DataFrame, trades: pd.DataFrame) -> dict[str, Any]:
    values = nav["nav_krw"].astype(float)
    dates = pd.to_datetime(nav["date"])
    returns = values.pct_change().dropna()
    running = values.cummax()
    dd = values.div(running).sub(1.0)
    elapsed = max((dates.iloc[-1] - dates.iloc[0]).days, 1)
    final = float(values.iloc[-1])
    total_return = final / float(INITIAL_CAPITAL) - 1.0
    downside = returns[returns < 0]
    fills = _filled(trades)
    orders = trades.drop_duplicates("paper_order_id") if not trades.empty else trades
    turnover = float((fills["fill_quantity"].abs() * fills["fill_price"]).sum() / float(INITIAL_CAPITAL)) if not fills.empty else 0.0
    return {
        "start_nav_krw": float(values.iloc[0]), "final_nav_krw": final, "total_return": total_return,
        "cagr": (final / float(INITIAL_CAPITAL)) ** (365.25 / elapsed) - 1.0 if final > 0 else -1.0,
        "mdd": float(dd.min()),
        "sharpe": float(returns.mean() / returns.std(ddof=0) * math.sqrt(252)) if len(returns) and returns.std(ddof=0) else None,
        "sortino": float(returns.mean() / downside.std(ddof=0) * math.sqrt(252)) if len(downside) and downside.std(ddof=0) else None,
        "calmar": total_return / abs(float(dd.min())) if float(dd.min()) < 0 else None,
        "turnover": turnover, "order_count": int(len(orders)), "fill_count": int(len(fills)),
        "reject_count": int(orders[orders["status"].eq("REJECTED")]["paper_order_id"].nunique()) if not orders.empty else 0,
        "total_fee_krw": float(fills["fee"].sum()) if not fills.empty else 0.0,
        # paper_fill.slippage is the absolute per-share fill/reference price
        # difference. Convert it to KRW cost using the filled quantity.
        "total_slippage_krw": float((fills["slippage"] * fills["fill_quantity"].abs()).sum()) if not fills.empty else 0.0,
        "mean_cash_weight": float((nav["cash_krw"].astype(float) / values).mean()),
        "underwater_day_ratio": float((values < running).mean()),
    }


def _holding_stats(nav: pd.DataFrame, trades: pd.DataFrame) -> dict[str, Any]:
    fills = _filled(trades).sort_values(["date", "paper_order_id"])
    positions: dict[str, float] = {}
    opened: dict[str, pd.Timestamp] = {}
    spells: list[int] = []
    replacement_dates: set[pd.Timestamp] = set()
    for date, group in fills.groupby("date", sort=True):
        sides = set(group["side"])
        if {"BUY", "SELL"}.issubset(sides):
            replacement_dates.add(pd.Timestamp(date))
        for row in group.itertuples(index=False):
            symbol, before = str(row.symbol), positions.get(str(row.symbol), 0.0)
            delta = float(row.fill_quantity) if row.side == "BUY" else -float(row.fill_quantity)
            after = before + delta
            if before <= 0 < after:
                opened[symbol] = pd.Timestamp(date)
            if before > 0 and after <= 0 and symbol in opened:
                spells.append(int((pd.Timestamp(date) - opened.pop(symbol)).days))
            positions[symbol] = after
    last = pd.Timestamp(nav["date"].max())
    spells.extend(int((last - start).days) for start in opened.values())
    return {"average_holding_days": float(np.mean(spells)) if spells else 0.0, "holding_spells": len(spells), "etf_replacement_sessions": len(replacement_dates)}


def _calendar(nav: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    frame = nav.copy(); frame["date"] = pd.to_datetime(frame["date"])
    for year, group in frame.groupby(frame["date"].dt.year):
        rows.append({"period": str(year), "period_type": "PARTIAL" if year in (2021, 2026) else "FULL_YEAR", "return": float(group.nav_krw.iloc[-1] / group.nav_krw.iloc[0] - 1.0)})
    monthly = frame[frame.date.dt.year.eq(2026)].copy()
    out: list[dict[str, Any]] = []
    for month, group in monthly.groupby(monthly.date.dt.to_period("M")):
        out.append({"month": str(month), "return": float(group.nav_krw.iloc[-1] / group.nav_krw.iloc[0] - 1.0)})
    return pd.DataFrame(rows), pd.DataFrame(out)


def _selection_parity(root: Path) -> dict[str, Any]:
    specs = load_candidate_specs(root)
    left = build_candidate_ledgers(root, specs[BASELINE], use_common_cutoff=True)
    right = build_candidate_ledgers(root, specs[CHALLENGER], use_common_cutoff=True)
    ls = left["selection79"].set_index("date")["sleeve_ticker"]
    rs = right["selection79"].set_index("date")["sleeve_ticker"]
    ll = left["ledger"].set_index("date")["target_hash"]
    rl = right["ledger"].set_index("date")["target_hash"]
    dates = ls.index.intersection(rs.index)
    return {
        "comparable_dates": int(len(dates)),
        "selected_etf_match_ratio": float(ls.loc[dates].fillna("NONE").eq(rs.loc[dates].fillna("NONE")).mean()),
        "target_hash_match_ratio": float(ll.loc[dates].eq(rl.loc[dates]).mean()),
        "v69_base_leader_match_ratio": float(left["selection69"].set_index("date").loc[dates, "leader_ticker"].fillna("NONE").eq(right["selection69"].set_index("date").loc[dates, "leader_ticker"].fillna("NONE")).mean()),
        "regime_match_ratio": float(left["regime"]["risk_on"].loc[dates].eq(right["regime"]["risk_on"].loc[dates]).mean()),
    }


def _spread_bootstrap(root: Path, *, horizon: int, contract: dict[str, Any]) -> dict[str, Any]:
    specs = load_candidate_specs(root)
    built = build_candidate_ledgers(root, specs[CHALLENGER], use_common_cutoff=True)
    score = built["f79"]["high252_proximity"]
    eligible = built["f79"]["eligible"]
    close = built["market"]["close"][score.columns]
    forward = close.shift(-horizon).div(close).sub(1.0)
    rows: list[tuple[pd.Timestamp, float]] = []
    for date in score.index:
        q = pd.concat([score.loc[date], eligible.loc[date], forward.loc[date]], axis=1)
        q.columns = ["score", "eligible", "forward"]
        q = q[q["eligible"].astype(bool)].dropna()
        if len(q) >= 6:
            q = q.sort_values("score")
            rows.append((pd.Timestamp(date), float(q["forward"].iloc[-3:].mean() - q["forward"].iloc[:3].mean())))
    sampled = rows[::horizon]
    values = np.asarray([v for _, v in sampled], dtype=float)
    block = int(contract["research_measurement"]["moving_block_bootstrap_block_observations"])
    samples = int(contract["research_measurement"]["bootstrap_resamples"])
    rng = np.random.default_rng(20260805 + horizon)
    boot = []
    if len(values):
        for _ in range(samples):
            pieces: list[float] = []
            while len(pieces) < len(values):
                start = int(rng.integers(0, len(values)))
                pieces.extend(values[(start + np.arange(block)) % len(values)].tolist())
            boot.append(float(np.mean(pieces[:len(values)])))
    return {
        "horizon_days": horizon, "non_overlapping_observations": int(len(values)),
        "mean_top3_minus_bottom3_return": float(values.mean()) if len(values) else None,
        "bootstrap_ci_95": [float(np.quantile(boot, .025)), float(np.quantile(boot, .975))] if boot else None,
        "block_observations": block, "bootstrap_resamples": samples,
    }


def _stress_not_comparable() -> dict[str, Any]:
    """Do not substitute the direct V101 simulator for the Paper lifecycle.

    The requested stress result must retain Paper intent sizing, persistence,
    and rejection semantics.  No injectable 2x-cost Paper contract exists, so
    this runner fails closed instead of publishing a non-comparable number.
    """
    return {"status": "NOT_COMPARABLE_PAPER_2X_COST_CONTRACT_MISSING"}


def run(root: Path | str, *, output_dir: Path | str | None = None) -> dict[str, Any]:
    root = Path(root).resolve()
    out = Path(output_dir) if output_dir else root / "runtime/v79_high252_proximity_operational_replay"
    out.mkdir(parents=True, exist_ok=True)
    base_url = os.environ.get("TEST_DATABASE_URL")
    if not base_url:
        raise RuntimeError("TEST_DATABASE_URL is required")
    contract, contract_hash = _contract(root)
    specs = load_candidate_specs(root)
    if specs[CHALLENGER].strategy != "V79" or specs[CHALLENGER].sleeve_selection_policy != "V79_HIGH252_PROXIMITY":
        raise RuntimeError("challenger contract is not the fixed high252 sleeve replacement")
    replays = {candidate: _replay(root, base_url, candidate, out) for candidate in CANDIDATES}
    rows: list[dict[str, Any]] = []
    annual: list[pd.DataFrame] = []; monthly: list[pd.DataFrame] = []; contribution: list[pd.DataFrame] = []
    for candidate, result in replays.items():
        metric = {"candidate_id": candidate, **_metrics(result["nav"], result["trades"]), **_holding_stats(result["nav"], result["trades"])}
        metric["reconciliation_failures"] = int(result["replay"]["validation"]["reconciliation_failures"])
        rows.append(metric)
        a, m = _calendar(result["nav"]); a.insert(0, "candidate_id", candidate); m.insert(0, "candidate_id", candidate)
        annual.append(a); monthly.append(m); contribution.append(_contribution(root, result["nav"], result["trades"], candidate))
    metrics = pd.DataFrame(rows)
    for candidate in CANDIDATES:
        metrics.loc[metrics.candidate_id.eq(candidate), "stress_2x"] = json.dumps(_stress_not_comparable(), sort_keys=True)
    annual_frame = pd.concat(annual, ignore_index=True); monthly_frame = pd.concat(monthly, ignore_index=True)
    contribution_frame = pd.concat(contribution, ignore_index=True)
    parity = _selection_parity(root)
    spreads = [_spread_bootstrap(root, horizon=h, contract=contract) for h in (20, 60)]
    metrics.to_csv(out / "comparison_metrics.csv", index=False)
    annual_frame.to_csv(out / "annual_returns.csv", index=False)
    monthly_frame.to_csv(out / "monthly_returns_2026.csv", index=False)
    contribution_frame.to_csv(out / "contribution_by_etf.csv", index=False)
    summary = {
        "analysis_kind": "HISTORICAL_COMPARATIVE_OPERATIONAL_REPLAY_NOT_OUT_OF_SAMPLE",
        "period": {"start": START, "end": END, "initial_capital_krw": float(INITIAL_CAPITAL)},
        "baseline": BASELINE, "challenger": CHALLENGER, "contract": contract, "contract_sha256": contract_hash,
        "metrics": rows, "selection_target_parity": parity, "signal_spread": spreads,
        "reconciliation_passed": all(r["replay"]["validation"]["reconciliation_failures"] == 0 for r in replays.values()),
        "broker_mutation_calls": 0, "operating_database_touched": False, "reports_touched": False,
    }
    _write_json(out / "validation_summary.json", summary)
    return summary


__all__ = ["BASELINE", "CHALLENGER", "run"]
