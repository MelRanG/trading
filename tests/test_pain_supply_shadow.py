import pytest

from quant_harness.pain_supply_shadow import inspect_flow


def test_missing_flow_is_unknown_not_safe(tmp_path):
    result = inspect_flow(tmp_path / "absent.csv", required_source_date="2026-10-02")
    assert result["flow_risk"] is None and not result["metrics_executed"]
    assert result["capital_authority"] == "NONE"


def test_reconstructed_stale_flow_blocked_and_read_only(tmp_path):
    path = tmp_path / "flow.csv"
    path.write_text("as_of_date,market,foreign_net_buy_100m_krw,institution_net_buy_100m_krw,source_id,downloaded_at,data_status,provenance_hash\n"
                    "2026-07-03,KOSPI,1,2,NPAY,2026-07-04T00:00:00Z,historical_reconstructed,hash\n", encoding="utf-8")
    before = path.read_bytes()
    result = inspect_flow(path, required_source_date="2026-10-02")
    assert result["temporal_freshness"] == "STALE"
    assert "OFFICIAL_FORWARD_PIT_PROVENANCE_UNVERIFIED" in result["missing_dependencies"]
    assert result["flow_risk"] is None and path.read_bytes() == before


def test_status_label_alone_does_not_enable_flow(tmp_path):
    path = tmp_path / "flow.csv"
    path.write_text("as_of_date,market,foreign_net_buy_100m_krw,institution_net_buy_100m_krw,source_id,downloaded_at,data_status,provenance_hash\n"
                    "2026-10-02,KOSPI,1,2,claimed,2026-10-03T00:00:00Z,READY_FORWARD_PIT,hash\n", encoding="utf-8")
    result = inspect_flow(path, required_source_date="2026-10-02")
    assert result["temporal_freshness"] == "PASSED"
    assert result["status"] == "BLOCKED_PAIN_SUPPLY_DATA" and result["flow_risk"] is None


def test_unknown_source_date_fails_closed(tmp_path):
    with pytest.raises(ValueError):
        inspect_flow(tmp_path / "flow.csv", required_source_date="2026-10-02T09:00:00+09:00")
