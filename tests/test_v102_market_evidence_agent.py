from pathlib import Path

import pandas as pd
import pytest

from quant_harness.v100_strategy_agent import engine as v100
from quant_harness.v102_market_evidence_agent.policy import (
    ACTIVE_POLICY,
    NEWS_POLICY,
    build_flow_evidence,
    build_fundamental_evidence,
    validate_news_events,
)

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports/v102_market_evidence_agent"


def test_v102_parent_parity_and_live_blocked():
    parity = pd.read_csv(REPORT / "v102_parent_parity.csv")
    gates = pd.read_csv(REPORT / "v102_quality_gates.csv")
    promotion = pd.read_csv(REPORT / "v102_candidate_promotion.csv")
    assert parity["abs_error_krw"].le(1.0).all()
    assert gates["passed"].all()
    assert not promotion["promoted"].fillna(False).any()
    news = promotion[promotion["policy"].eq(NEWS_POLICY)].iloc[0]
    assert news["status"] == "DATA_BLOCKED_NO_HISTORICAL_PIT_NEWS"


def test_flow_signal_is_d1_and_future_mutation_invariant(tmp_path):
    _cfg, _cfg77, market, *_ = v100._load_context(ROOT)
    index = market["close"].index
    original = build_flow_evidence(ROOT, index)
    clone = tmp_path / "project"
    clone.mkdir()
    (clone / "data/historical_investor_flow").mkdir(parents=True)
    src = pd.read_csv(ROOT / "data/historical_investor_flow/market_investor_flow_daily.csv")
    mask = pd.to_datetime(src["as_of_date"]) >= pd.Timestamp("2025-01-01")
    src.loc[mask, "foreign_net_buy_100m_krw"] = 99999999
    src.loc[mask, "institution_net_buy_100m_krw"] = -99999999
    src.to_csv(clone / "data/historical_investor_flow/market_investor_flow_daily.csv", index=False)
    changed = build_flow_evidence(clone, index)
    pd.testing.assert_series_equal(original.loc[:"2024-12-31", "flow_risk"], changed.loc[:"2024-12-31", "flow_risk"])
    valid = original.dropna(subset=["information_cutoff"])
    assert (valid["information_cutoff"] < valid.index).all()


def test_dart_uses_received_at_and_future_mutation_does_not_change_past(tmp_path):
    _cfg, _cfg77, market, *_ = v100._load_context(ROOT)
    index = market["close"].index
    original, _ = build_fundamental_evidence(ROOT, index)
    clone = tmp_path / "project"
    (clone / "data/agent_ready_v62_16").mkdir(parents=True)
    (clone / "data").mkdir(exist_ok=True)
    mapping = pd.read_csv(ROOT / "data/agent_ready_v62_16/agent_etf_to_stock_mapping_v62_16.csv")
    mapping.to_csv(clone / "data/agent_ready_v62_16/agent_etf_to_stock_mapping_v62_16.csv", index=False)
    dart = pd.read_csv(ROOT / "data/opendart_quarterly_pit.csv", dtype={"ticker": str})
    future = pd.to_datetime(dart["received_at"], utc=True) >= pd.Timestamp("2025-01-01", tz="UTC")
    dart.loc[future, "quarterly_net_income"] = -9.99e15
    dart.to_csv(clone / "data/opendart_quarterly_pit.csv", index=False)
    changed, _ = build_fundamental_evidence(clone, index)
    pd.testing.assert_frame_equal(original.loc[:"2024-12-31"], changed.loc[:"2024-12-31"])


def test_news_contract_only_official_critical_event_has_veto():
    frame = pd.DataFrame([
        {
            "event_id": "E1", "entity_ticker": "660", "entity_name": "A",
            "published_at": "2026-07-01T08:00:00Z", "first_seen_at": "2026-07-01T08:01:00Z",
            "source_tier": "OFFICIAL_REGULATORY", "source_domain": "kind.krx.co.kr",
            "source_document_id": "KIND-1", "event_type": "TRADING_SUSPENSION",
            "severity": "CRITICAL", "sentiment": "NEGATIVE", "title": "suspension",
            "url": "https://kind.krx.co.kr/example", "corrected_event_id": "", "ingestion_hash": "abc",
        },
        {
            "event_id": "E2", "entity_ticker": "660", "entity_name": "A",
            "published_at": "2026-07-01T08:00:00Z", "first_seen_at": "2026-07-01T08:02:00Z",
            "source_tier": "LICENSED_MEDIA", "source_domain": "media.example",
            "source_document_id": "N-1", "event_type": "TRADING_SUSPENSION",
            "severity": "CRITICAL", "sentiment": "NEGATIVE", "title": "reported suspension",
            "url": "https://media.example/n1", "corrected_event_id": "", "ingestion_hash": "def",
        },
    ])
    result = validate_news_events(frame)
    assert result.loc[result.event_id.eq("E1"), "capital_action"].iloc[0] == "HARD_VETO"
    assert result.loc[result.event_id.eq("E2"), "capital_action"].iloc[0] == "DIAGNOSTIC_ONLY"
    bad = frame.iloc[[0]].copy()
    bad["first_seen_at"] = "2026-07-01T07:59:00Z"
    with pytest.raises(ValueError):
        validate_news_events(bad)


def test_v102_merged_contract_and_real_data_guide():
    registry = (ROOT / "reports/v102_market_evidence_agent/v102_market_evidence_registry.json").read_text(encoding="utf-8")
    checklist = (ROOT / "docs/REAL_DATA_EXECUTION_CHECKLIST.md").read_text(encoding="utf-8")
    contract = (ROOT / "config/v102_market_evidence_contract.yaml").read_text(encoding="utf-8")
    assert '"active_agent_contract_count": 7' in registry
    assert "v102_news_evidence_template.csv" in checklist
    assert "UNVERIFIED_EXTERNAL" in contract
    assert ACTIVE_POLICY in registry
