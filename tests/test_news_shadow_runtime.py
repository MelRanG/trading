from datetime import date, datetime, timezone
import json

import pandas as pd
import pytest

from quant_harness.news_shadow_runtime import append_observations, collect_disclosures, evaluate_shadow_news
from quant_harness.v72_integration_ready.opendart import OpenDartClient


def client():
    def transport(request, timeout):
        assert request.get_method() == "GET"
        assert "list.json" in request.full_url and "corp_code=00126380" in request.full_url
        payload = {"status": "000", "total_page": 1, "list": [{"corp_code": "00126380", "stock_code": "005930",
                   "corp_name": "fixture", "report_nm": "fixture disclosure", "rcept_no": "20261002000001", "rcept_dt": "20261002"}]}
        return 200, {}, json.dumps(payload).encode()
    return OpenDartClient(api_key="fixture-key", transport=transport)


def observations():
    return collect_disclosures(client(), corp_code="00126380", stock_code="005930", start=date(2026, 10, 1),
                               end=date(2026, 10, 3), observed_at=datetime(2026, 10, 4, tzinfo=timezone.utc))


def event():
    return {"event_id": "1", "entity_ticker": "005930", "entity_name": "fixture", "published_at": "2026-10-01T01:00:00Z",
            "first_seen_at": "2026-10-01T01:01:00Z", "source_tier": "OFFICIAL_REGULATORY", "source_domain": "kind.krx.co.kr",
            "source_document_id": "doc", "event_type": "TRADING_SUSPENSION", "severity": "CRITICAL", "sentiment": "NEGATIVE",
            "title": "fixture", "url": "https://kind.krx.co.kr/fixture", "corrected_event_id": "", "ingestion_hash": "a" * 64,
            "correction_chain_verified": True}


def gate(row, **kwargs):
    return evaluate_shadow_news(pd.DataFrame([row]), cutoff=kwargs.get("cutoff", "2026-10-02T00:00:00+09:00"),
                                target_symbols=kwargs.get("targets", {"005930"}), trusted_domains={"kind.krx.co.kr"})


def test_official_collection_date_only_is_not_capital_evidence():
    result = observations()[0]
    assert result["published_at"] is None and result["timestamp_precision"] == "DATE_ONLY"
    assert result["capital_authority"] == "NONE"
    assert len(result["source_content_hash"]) == 64


def test_first_seen_preserved_dedup_and_revision_fail_closed(tmp_path):
    path = tmp_path / "news.jsonl"
    original = observations()
    assert append_observations(path, original)["appended"] == 1
    before = path.read_bytes()
    original[0]["first_seen_at"] = "2026-10-05T00:00:00Z"
    assert append_observations(path, original)["appended"] == 0
    assert path.read_bytes() == before
    original[0]["source_content_hash"] = "b" * 64
    with pytest.raises(ValueError, match="hash|revision"):
        append_observations(path, original)
    assert path.read_bytes() == before


def test_payload_and_existing_journal_tamper_are_not_silently_deduplicated(tmp_path):
    path = tmp_path / "news.jsonl"
    original = observations()
    append_observations(path, original)
    before = path.read_bytes()
    original[0]["title"] = "tampered"
    with pytest.raises(ValueError, match="hash mismatch"):
        append_observations(path, original)
    assert path.read_bytes() == before
    path.write_bytes(before.replace(b"fixture disclosure", b"tampered existing"))
    with pytest.raises(ValueError, match="hash mismatch"):
        append_observations(path, observations())


def test_official_critical_direct_target_changes_only_shadow_gate():
    result = gate(event())
    assert result["shadow_block_new_buy_symbols"] == ["005930"]
    assert result["capital_authority"] == "NONE"
    assert not result["target_mutation"] and not result["broker_mutation"]


def test_future_seen_and_stock_to_etf_mapping_never_leak():
    row = event()
    row["first_seen_at"] = "2026-10-03T00:00:00Z"
    assert gate(row)["shadow_block_new_buy_symbols"] == []
    assert gate(event(), targets={"069500"})["shadow_block_new_buy_symbols"] == []


@pytest.mark.parametrize("field,value", [("severity", "INFO"), ("event_type", "GENERAL_SENTIMENT"), ("source_tier", "LICENSED_MEDIA")])
def test_general_news_does_not_gain_capital_authority(field, value):
    row = event()
    row[field] = value
    assert gate(row)["shadow_block_new_buy_symbols"] == []


@pytest.mark.parametrize("field,value", [("published_at", "2026-10-01"), ("first_seen_at", None),
                                         ("ingestion_hash", ""), ("correction_chain_verified", False),
                                         ("url", "https://evil.example/fixture")])
def test_unknown_provenance_or_time_fails_closed(field, value):
    row = event()
    row[field] = value
    with pytest.raises(ValueError):
        gate(row)


def test_entity_mismatch_and_large_history_request_blocked():
    with pytest.raises(ValueError, match="entity"):
        collect_disclosures(client(), corp_code="00126380", stock_code="000660", start=date(2026, 10, 1),
                            end=date(2026, 10, 3), observed_at=datetime(2026, 10, 4, tzinfo=timezone.utc))
    with pytest.raises(ValueError, match="seven days"):
        collect_disclosures(client(), corp_code="00126380", stock_code="005930", start=date(2026, 9, 1),
                            end=date(2026, 10, 3), observed_at=datetime(2026, 10, 4, tzinfo=timezone.utc))


def test_corrections_are_resolved_as_of_not_from_future():
    first = event()
    corrected = {**event(), "event_id": "2", "source_document_id": "doc2", "corrected_event_id": "1", "severity": "INFO",
                 "published_at": "2026-10-02T01:00:00Z", "first_seen_at": "2026-10-02T01:01:00Z"}
    def evaluate(cutoff):
        return evaluate_shadow_news(pd.DataFrame([first, corrected]), cutoff=cutoff,
                                    target_symbols={"005930"}, trusted_domains={"kind.krx.co.kr"})
    assert evaluate("2026-10-01T23:00:00Z")["shadow_block_new_buy_symbols"] == ["005930"]
    assert evaluate("2026-10-02T23:00:00Z")["shadow_block_new_buy_symbols"] == []
    first["corrected_event_id"] = "2"
    with pytest.raises(ValueError, match="cyclic"):
        evaluate("2026-10-02T23:00:00Z")
