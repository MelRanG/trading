from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping
import json

import numpy as np
import pandas as pd

from quant_harness.v69_dynamic_theme_leadership import engine as v69

ACTIVE_POLICY = "MARKET_EVIDENCE_DIAGNOSTIC_ONLY"
FLOW_ENTRY_BLOCK = "FLOW_ENTRY_BLOCK_PERSISTENT_5D"
DART_HARD_VETO = "DART_HARD_VETO_PERSISTENT_LOSS"
CONSENSUS_HARD_VETO = "FLOW_DART_CONSENSUS_HARD_VETO"
NEWS_POLICY = "NEWS_OFFICIAL_SEVERE_EVENT_VETO"
CANDIDATE_POLICIES = [FLOW_ENTRY_BLOCK, DART_HARD_VETO, CONSENSUS_HARD_VETO]
ALL_BACKTEST_POLICIES = [ACTIVE_POLICY, *CANDIDATE_POLICIES]

OFFICIAL_NEWS_TIERS = {"OFFICIAL_REGULATORY", "PRIMARY_COMPANY"}
HARD_VETO_EVENT_TYPES = {
    "TRADING_SUSPENSION",
    "DELISTING_OR_MANAGEMENT_DESIGNATION",
    "BANKRUPTCY_OR_RESTRUCTURING",
    "ACCOUNTING_VIOLATION",
    "FRAUD_OR_EMBEZZLEMENT",
    "LICENSE_OR_REGULATORY_SHUTDOWN",
}
NEWS_SOURCE_TIERS = OFFICIAL_NEWS_TIERS | {"LICENSED_MEDIA", "AGGREGATOR", "SOCIAL"}
NEWS_SEVERITIES = {"INFO", "WATCH", "MATERIAL", "CRITICAL"}
NEWS_SENTIMENTS = {"NEGATIVE", "NEUTRAL", "POSITIVE", "MIXED", "UNKNOWN"}


@dataclass(frozen=True)
class EvidencePolicy:
    policy_id: str
    blocks_on_flow: bool = False
    blocks_on_fundamental: bool = False
    requires_consensus: bool = False


POLICIES = {
    ACTIVE_POLICY: EvidencePolicy(ACTIVE_POLICY),
    FLOW_ENTRY_BLOCK: EvidencePolicy(FLOW_ENTRY_BLOCK, blocks_on_flow=True),
    DART_HARD_VETO: EvidencePolicy(DART_HARD_VETO, blocks_on_fundamental=True),
    CONSENSUS_HARD_VETO: EvidencePolicy(
        CONSENSUS_HARD_VETO,
        blocks_on_flow=True,
        blocks_on_fundamental=True,
        requires_consensus=True,
    ),
}


def _target_hash(weights: Mapping[str, float]) -> str:
    payload = json.dumps(dict(sorted((str(k).zfill(6), round(float(v), 12)) for k, v in weights.items())), separators=(",", ":"))
    return sha256(payload.encode()).hexdigest()


def _parse_targets(raw: Any) -> dict[str, float]:
    if isinstance(raw, dict):
        values = raw
    else:
        values = json.loads(str(raw))
    clean = {str(k).zfill(6): float(v) for k, v in values.items() if float(v) > 1e-12}
    total = sum(clean.values())
    if not np.isclose(total, 1.0, atol=1e-9):
        raise ValueError(f"invalid target sum {total}")
    return clean


def build_flow_evidence(root: Path, index: pd.DatetimeIndex, *, z_window: int = 252, min_periods: int = 60, persistence_days: int = 5, z_threshold: float = -1.5) -> pd.DataFrame:
    path = root / "data/historical_investor_flow/market_investor_flow_daily.csv"
    frame = pd.read_csv(path, low_memory=False)
    frame = frame[frame["market"].astype(str).eq("KOSPI")].copy()
    frame["date"] = pd.to_datetime(frame["as_of_date"], errors="coerce").dt.normalize()
    frame = frame.dropna(subset=["date"]).sort_values("date").drop_duplicates("date", keep="last").set_index("date")
    foreign = pd.to_numeric(frame["foreign_net_buy_100m_krw"], errors="coerce").reindex(index)
    institution = pd.to_numeric(frame["institution_net_buy_100m_krw"], errors="coerce").reindex(index)
    source_present = foreign.notna() & institution.notna()
    foreign_5d = foreign.rolling(persistence_days, min_periods=persistence_days).sum()
    institution_5d = institution.rolling(persistence_days, min_periods=persistence_days).sum()
    combined_5d = foreign_5d + institution_5d
    mean = combined_5d.rolling(z_window, min_periods=min_periods).mean()
    std = combined_5d.rolling(z_window, min_periods=min_periods).std(ddof=0).replace(0.0, np.nan)
    z = (combined_5d - mean) / std
    prior_session = pd.Series(index, index=index).shift(1)
    source_dates = pd.Series(index.where(source_present), index=index).shift(1)
    out = pd.DataFrame(index=index)
    out["flow_source_date_d1"] = source_dates
    out["flow_foreign_5d_d1"] = foreign_5d.shift(1)
    out["flow_institution_5d_d1"] = institution_5d.shift(1)
    out["flow_combined_5d_d1"] = combined_5d.shift(1)
    out["flow_combined_z252_d1"] = z.shift(1)
    out["flow_data_current"] = source_dates.eq(prior_session).fillna(False)
    out["flow_risk"] = (
        out["flow_data_current"]
        & out["flow_combined_z252_d1"].le(float(z_threshold))
        & out["flow_foreign_5d_d1"].lt(0.0)
        & out["flow_institution_5d_d1"].lt(0.0)
    ).fillna(False)
    out["information_cutoff"] = prior_session
    return out


def _prepare_dart(root: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    mapping = pd.read_csv(root / "data/agent_ready_v62_16/agent_etf_to_stock_mapping_v62_16.csv", dtype=str)
    mapping["etf_symbol"] = mapping["etf_symbol"].map(v69._normalise_ticker)
    mapping["stock_symbol"] = mapping["stock_symbol"].map(v69._normalise_ticker)
    mapping = mapping.dropna(subset=["etf_symbol", "stock_symbol"]).drop_duplicates(["etf_symbol", "stock_symbol"])
    dart = pd.read_csv(root / "data/opendart_quarterly_pit.csv", dtype={"ticker": str, "corp_code": str, "rcept_no": str})
    dart["ticker"] = dart["ticker"].map(v69._normalise_ticker)
    dart["received_at_utc"] = pd.to_datetime(dart["received_at"], utc=True, errors="coerce")
    dart["available_date"] = dart["received_at_utc"].dt.tz_convert("Asia/Seoul").dt.tz_localize(None).dt.normalize()
    dart["quarterly_net_income"] = pd.to_numeric(dart["quarterly_net_income"], errors="coerce")
    dart["total_assets"] = pd.to_numeric(dart["total_assets"], errors="coerce")
    dart["business_year"] = pd.to_numeric(dart["business_year"], errors="coerce").astype("Int64")
    dart["fiscal_quarter"] = pd.to_numeric(dart["fiscal_quarter"], errors="coerce").astype("Int64")
    dart = dart.dropna(subset=["ticker", "available_date", "business_year", "fiscal_quarter", "quarterly_net_income"])
    return mapping, dart


def build_fundamental_evidence(root: Path, index: pd.DatetimeIndex, *, minimum_coverage: int = 2, persistent_loss_count: int = 2, maximum_age_days: int = 220) -> tuple[pd.DataFrame, pd.DataFrame]:
    mapping, dart = _prepare_dart(root)
    etfs = sorted(mapping["etf_symbol"].unique())
    risk = pd.DataFrame(False, index=index, columns=etfs, dtype=bool)
    rows: list[dict[str, Any]] = []
    stock_map = {etf: sorted(g["stock_symbol"].unique()) for etf, g in mapping.groupby("etf_symbol")}
    filings = dart.sort_values(["available_date", "ticker", "business_year", "fiscal_quarter", "rcept_no"]).to_dict("records")
    pointer = 0
    # Current point-in-time version for each fiscal period; later corrections overwrite earlier versions.
    period_state: dict[str, dict[tuple[int, int], dict[str, Any]]] = {}
    for date in index:
        cutoff = pd.Timestamp(date) - pd.Timedelta(days=1)
        while pointer < len(filings) and pd.Timestamp(filings[pointer]["available_date"]) <= cutoff:
            event = filings[pointer]
            ticker = str(event["ticker"])
            key = (int(event["business_year"]), int(event["fiscal_quarter"]))
            period_state.setdefault(ticker, {})[key] = event
            pointer += 1
        stock_state: dict[str, dict[str, Any]] = {}
        for ticker, periods in period_state.items():
            latest = [periods[k] for k in sorted(periods)[-2:]]
            latest_date = max(pd.Timestamp(x["available_date"]) for x in latest)
            age = int((cutoff - latest_date).days)
            covered = len(latest) >= 2 and age <= maximum_age_days
            stock_state[ticker] = {
                "covered": covered,
                "persistent_loss": covered and all(float(x["quarterly_net_income"]) < 0.0 for x in latest),
                "latest_negative": covered and float(latest[-1]["quarterly_net_income"]) < 0.0,
                "age": age,
            }
        for etf in etfs:
            valid = [stock_state[t] for t in stock_map[etf] if t in stock_state and stock_state[t]["covered"]]
            cov = len(valid)
            losses = sum(bool(x["persistent_loss"]) for x in valid)
            latest_neg = sum(bool(x["latest_negative"]) for x in valid)
            age = max((float(x["age"]) for x in valid), default=np.nan)
            flag = cov >= minimum_coverage and losses >= persistent_loss_count
            risk.loc[date, etf] = flag
            if flag:
                rows.append({
                    "date": date,
                    "etf_ticker": etf,
                    "coverage": cov,
                    "persistent_loss_count": losses,
                    "latest_negative_count": latest_neg,
                    "maximum_constituent_filing_age_days": age,
                    "fundamental_risk": True,
                    "information_cutoff": cutoff,
                })
    return risk, pd.DataFrame(rows)

def validate_news_events(frame: pd.DataFrame) -> pd.DataFrame:
    required = [
        "event_id", "entity_ticker", "entity_name", "published_at", "first_seen_at",
        "source_tier", "source_domain", "source_document_id", "event_type", "severity",
        "sentiment", "title", "url", "corrected_event_id", "ingestion_hash",
    ]
    missing = [c for c in required if c not in frame.columns]
    if missing:
        raise ValueError(f"missing news fields: {missing}")
    out = frame.copy()
    out["entity_ticker"] = out["entity_ticker"].fillna("").astype(str).map(lambda x: x.zfill(6) if x else "")
    out["published_at"] = pd.to_datetime(out["published_at"], utc=True, errors="coerce")
    out["first_seen_at"] = pd.to_datetime(out["first_seen_at"], utc=True, errors="coerce")
    if out[["published_at", "first_seen_at"]].isna().any().any():
        raise ValueError("invalid news timestamps")
    if (out["first_seen_at"] < out["published_at"]).any():
        raise ValueError("first_seen_at cannot precede published_at")
    if not set(out["source_tier"]).issubset(NEWS_SOURCE_TIERS):
        raise ValueError("unknown source_tier")
    if not set(out["severity"]).issubset(NEWS_SEVERITIES):
        raise ValueError("unknown severity")
    if not set(out["sentiment"]).issubset(NEWS_SENTIMENTS):
        raise ValueError("unknown sentiment")
    if out["event_id"].astype(str).duplicated().any():
        raise ValueError("duplicate event_id")
    out["canonical_event_key"] = out.apply(
        lambda r: sha256(
            "|".join([
                str(r["entity_ticker"]), str(r["event_type"]), str(r["source_document_id"]),
                r["published_at"].floor("h").isoformat(),
            ]).encode()
        ).hexdigest(), axis=1,
    )
    out["capital_action"] = np.where(
        out["source_tier"].isin(OFFICIAL_NEWS_TIERS)
        & out["event_type"].isin(HARD_VETO_EVENT_TYPES)
        & out["severity"].eq("CRITICAL"),
        "HARD_VETO",
        "DIAGNOSTIC_ONLY",
    )
    return out.sort_values(["first_seen_at", "event_id"]).reset_index(drop=True)


def _fundamental_risk_for_targets(date: pd.Timestamp, raw_targets: dict[str, float], risk_matrix: pd.DataFrame, core_ticker: str) -> tuple[bool, list[str]]:
    risky: list[str] = []
    if date not in risk_matrix.index:
        return False, risky
    for ticker, weight in raw_targets.items():
        if ticker == core_ticker or weight <= 1e-12:
            continue
        if ticker in risk_matrix.columns and bool(risk_matrix.loc[date, ticker]):
            risky.append(ticker)
    return bool(risky), risky

def apply_evidence_policy(
    ledger: pd.DataFrame,
    *,
    policy_id: str,
    flow: pd.DataFrame,
    fundamental_risk: pd.DataFrame,
    core_ticker: str,
    strategy: str,
) -> pd.DataFrame:
    policy = POLICIES[policy_id]
    rows: list[dict[str, Any]] = []
    previous_effective = {str(core_ticker).zfill(6): 1.0}
    for source in ledger.sort_values("date").to_dict("records"):
        date = pd.Timestamp(source["date"])
        raw_targets = _parse_targets(source["target_weights_json"])
        raw_noncore = {t: w for t, w in raw_targets.items() if t != str(core_ticker).zfill(6)}
        prev_noncore = {t: w for t, w in previous_effective.items() if t != str(core_ticker).zfill(6)}
        raw_noncore_sum = sum(raw_noncore.values())
        prev_noncore_sum = sum(prev_noncore.values())
        rotation_or_increase = raw_noncore != prev_noncore and raw_noncore_sum >= prev_noncore_sum - 1e-12 and raw_noncore_sum > 1e-12
        flow_risk = bool(flow.loc[date, "flow_risk"]) if date in flow.index else False
        fundamental_flag, risky_tickers = _fundamental_risk_for_targets(
            date, raw_targets, fundamental_risk, str(core_ticker).zfill(6)
        )
        hard_veto = fundamental_flag and policy.blocks_on_fundamental and (flow_risk if policy.requires_consensus else True)
        flow_entry_block = rotation_or_increase and flow_risk and policy.blocks_on_flow and not policy.requires_consensus
        if hard_veto:
            effective = dict(raw_targets)
            core = str(core_ticker).zfill(6)
            moved = 0.0
            for ticker in risky_tickers:
                moved += effective.pop(ticker, 0.0)
            effective[core] = effective.get(core, 0.0) + moved
            block = moved > 1e-12
            reason = "HARD_VETO_FLOW_AND_DART" if policy.requires_consensus else "HARD_VETO_DART"
        elif flow_entry_block:
            effective = dict(previous_effective)
            block = True
            reason = "ENTRY_BLOCKED_FLOW"
        else:
            effective = raw_targets
            block = False
            reason = "DIAGNOSTIC_ONLY" if policy_id == ACTIVE_POLICY else "PASS"
        record = dict(source)
        record.update({
            "market_evidence_policy": policy_id,
            "raw_target_weights_json": json.dumps(raw_targets, sort_keys=True),
            "target_weights_json": json.dumps(effective, sort_keys=True),
            "target_hash": _target_hash(effective),
            "flow_risk": flow_risk,
            "flow_z_d1": float(flow.loc[date, "flow_combined_z252_d1"]) if date in flow.index and pd.notna(flow.loc[date, "flow_combined_z252_d1"]) else np.nan,
            "fundamental_risk": fundamental_flag,
            "fundamental_risk_tickers": "+".join(risky_tickers),
            "entry_rotation_or_increase": rotation_or_increase,
            "evidence_block_applied": block,
            "evidence_action_reason": reason,
            "raw_noncore_target_weight": raw_noncore_sum,
            "effective_noncore_target_weight": sum(w for t, w in effective.items() if t != str(core_ticker).zfill(6)),
            "strategy": strategy,
        })
        if strategy == "V69":
            leader = next((t for t in effective if t != str(core_ticker).zfill(6)), None)
            record["leader_ticker"] = leader
            record["target_leader_weight"] = float(effective.get(leader, 0.0)) if leader else 0.0
            record["target_core_weight"] = float(effective.get(str(core_ticker).zfill(6), 0.0))
        else:
            record["target_core_weight"] = float(effective.get(str(core_ticker).zfill(6), 0.0))
        rows.append(record)
        previous_effective = effective
    return pd.DataFrame(rows)
