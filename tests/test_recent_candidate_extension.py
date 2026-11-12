from __future__ import annotations

from pathlib import Path

from quant_harness.recent_candidate_extension import CANDIDATES, market_coverage, schema_url


ROOT = Path(__file__).resolve().parents[1]


def test_extension_is_limited_to_the_two_approved_candidates():
    assert CANDIDATES == ("V69_PARENT", "V79_NO63_VOL_GUARD")


def test_market_coverage_reports_the_actual_common_cutoff():
    coverage = market_coverage(ROOT)
    assert coverage["symbols"] == 26
    assert coverage["etf_cutoff"] == min(
        end for symbol, end in coverage["end_by_symbol"].items() if symbol != "KS11"
    )
    assert coverage["ks11_cutoff"] == coverage["end_by_symbol"]["KS11"]
    assert coverage["common_cutoff"] == min(
        coverage["etf_cutoff"], coverage["ks11_cutoff"]
    )


def test_schema_url_isolated_search_path_is_encoded():
    url = schema_url("postgresql://localhost/db", "recent_ext_v69_parent")
    assert "search_path%3Drecent_ext_v69_parent" in url
