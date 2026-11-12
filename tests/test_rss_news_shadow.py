from datetime import datetime, timezone
import json

import pytest

from quant_harness.rss_news_shadow import NoRedirect, feed_url, parse_feed, store_feed, visible_observations

NOW = datetime(2026, 10, 5, 6, tzinfo=timezone.utc)


def xml(title="반도체 뉴스", published="Mon, 05 Oct 2026 05:00:00 GMT"):
    return (f'<rss><channel><item><title>{title}</title><link>https://news.google.com/rss/articles/test</link>'
            f'<guid>id1</guid><pubDate>{published}</pubDate><source url="https://example.com">Test</source>'
            '</item></channel></rss>').encode()


def parse(raw=None, now=NOW):
    return parse_feed(raw or xml(), observed_at=now, include_terms=["반도체"])


def test_keyless_query_is_scoped_and_encoded():
    url = feed_url("반도체 ETF when:1d")
    assert url.startswith("https://news.google.com/rss/search?")
    assert "key" not in url and "when%3A1d" in url


def test_current_day_observation_does_not_gain_capital_authority():
    row = parse()["observations"][0]
    assert row["source_tier"] == "AGGREGATOR" and row["capital_authority"] == "NONE"
    assert row["first_seen_at"] == NOW.isoformat()
    assert not row["publication_time_verified"] and row["entity_ticker"] == ""


@pytest.mark.parametrize("published,bucket", [("Sun, 04 Oct 2026 05:00:00 GMT", "outside_today"),
                                               ("Mon, 05 Oct 2026 07:00:00 GMT", "future"), ("bad", "invalid")])
def test_old_future_or_unknown_timestamps_not_promoted(published, bucket):
    result = parse(xml(published=published))
    assert result["observations"] == [] and result["filter_counts"][bucket] == 1


def test_topic_filter_and_kst_date_boundary():
    assert parse(xml("다른 주제"))["filter_counts"]["irrelevant"] == 1
    # October 4 UTC is October 5 in KST.
    assert len(parse(xml(published="Sun, 04 Oct 2026 16:00:00 GMT"))["observations"]) == 1


def test_first_seen_blocks_historical_leakage():
    rows = parse()["observations"]
    assert visible_observations(rows, cutoff=datetime(2026, 10, 5, 5, 30, tzinfo=timezone.utc)) == []
    assert len(visible_observations(rows, cutoff=NOW)) == 1


def test_raw_preservation_idempotency_first_seen_and_revision_gate(tmp_path):
    assert store_feed(tmp_path, raw=xml(), parsed=parse(), query="topic")["appended"] == 1
    later = parse(now=datetime(2026, 10, 5, 7, tzinfo=timezone.utc))
    assert store_feed(tmp_path, raw=xml(), parsed=later, query="topic")["appended"] == 0
    row = json.loads(next(tmp_path.glob("rss_*.jsonl")).read_text(encoding="utf-8"))
    assert row["first_seen_at"] == NOW.isoformat()
    assert next(tmp_path.glob("*.xml")).read_bytes() == xml()
    changed = xml("반도체 수정 뉴스")
    with pytest.raises(ValueError, match="revision"):
        store_feed(tmp_path, raw=changed, parsed=parse(changed), query="topic")


@pytest.mark.parametrize("raw", [b"<!DOCTYPE rss><rss><channel/></rss>", b"<html/>", b"<rss>"])
def test_invalid_feed_fail_closed(raw):
    with pytest.raises(ValueError):
        parse(raw)


def test_redirect_rejected_before_second_get():
    with pytest.raises(ValueError, match="redirect"):
        NoRedirect().redirect_request(None, None, 302, "", {}, "https://evil.example")


def test_published_time_revision_and_raw_parsed_tamper_fail_closed(tmp_path):
    store_feed(tmp_path, raw=xml(), parsed=parse(), query="topic")
    changed = xml(published="Mon, 05 Oct 2026 05:01:00 GMT")
    with pytest.raises(ValueError, match="revision"):
        store_feed(tmp_path, raw=changed, parsed=parse(changed), query="topic")
    altered = parse()
    altered["observations"][0]["publisher"] = "tampered"
    with pytest.raises(ValueError, match="metadata mismatch"):
        store_feed(tmp_path, raw=xml(), parsed=altered, query="topic")


def test_empty_current_day_result_preserves_collection_receipt(tmp_path):
    raw = xml(published="Sun, 04 Oct 2026 05:00:00 GMT")
    store_feed(tmp_path, raw=raw, parsed=parse(raw), query="topic")
    receipt = json.loads((tmp_path / "collection_log.jsonl").read_text(encoding="utf-8"))
    assert receipt["observed_at"] == NOW.isoformat()
    assert receipt["accepted_items"] == 0 and receipt["filter_counts"]["outside_today"] == 1


def test_same_observation_receipt_is_idempotent_even_when_appended_changes(tmp_path):
    first = store_feed(tmp_path, raw=xml(), parsed=parse(), query="topic")
    second = store_feed(tmp_path, raw=xml(), parsed=parse(), query="topic")
    assert first["appended"] == 1 and second["appended"] == 0
    receipts = (tmp_path / "collection_log.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(receipts) == 1 and json.loads(receipts[0])["appended"] == 1
