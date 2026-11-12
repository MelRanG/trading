"""Keyless, forward-only Google RSS observations, never authoritative events.

Query terms are topic filters, NOT a PIT constituent mapping or sentiment alpha.
Only feed metadata is retained; article bodies/redirect targets are not fetched.
"""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from hashlib import sha256
from pathlib import Path
import json
import os
import unicodedata
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

from quant_harness.news_shadow_runtime import append_observations, digest, source_body

KST = ZoneInfo("Asia/Seoul")
MAX_BYTES = 2_000_000


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("feed redirects disabled")


def feed_url(query: str) -> str:
    if not query.strip() or len(query) > 200:
        raise ValueError("explicit bounded topic query required")
    return "https://news.google.com/rss/search?" + urlencode(
        {"q": query, "hl": "ko", "gl": "KR", "ceid": "KR:ko"})


def fetch_feed(query: str) -> tuple[bytes, datetime]:
    request = Request(feed_url(query), headers={"User-Agent": "StockAgent-ShadowRSS/1.0"}, method="GET")
    with build_opener(NoRedirect()).open(request, timeout=20) as response:
        if urlsplit(response.url).hostname != "news.google.com" or urlsplit(response.url).scheme != "https":
            raise ValueError("unexpected feed redirect")
        raw = response.read(MAX_BYTES + 1)
    # Available no earlier than the completed response.
    return raw, datetime.now(timezone.utc)


def parse_feed(raw: bytes, *, observed_at: datetime, include_terms: list[str]) -> dict:
    if observed_at.tzinfo is None or not include_terms or any(not term.strip() for term in include_terms):
        raise ValueError("aware observation time and explicit relevance terms required")
    if len(raw) > MAX_BYTES:
        raise ValueError("unsupported RSS document")
    try:
        decoded = raw.decode("utf-8-sig")
        if "\x00" in decoded or "<!DOCTYPE" in decoded.upper() or "<!ENTITY" in decoded.upper():
            raise ValueError("unsupported RSS document")
        tree = ElementTree.fromstring(decoded)
    except (UnicodeError, ElementTree.ParseError) as exc:
        raise ValueError("invalid RSS XML") from exc
    channel = tree.find("channel")
    if tree.tag != "rss" or channel is None:
        raise ValueError("RSS channel missing")
    normalize = lambda text: unicodedata.normalize("NFKC", text).casefold()
    terms = [normalize(term.strip()) for term in include_terms]
    counts = {"items": 0, "irrelevant": 0, "invalid": 0, "outside_today": 0, "future": 0}
    observations = []
    today = observed_at.astimezone(KST).date()
    for item in channel.findall("item"):
        counts["items"] += 1
        title = (item.findtext("title") or "").strip()
        url = (item.findtext("link") or "").strip()
        source = item.find("source")
        publisher = source.text.strip() if source is not None and source.text else ""
        source_url = source.get("url", "") if source is not None else ""
        identity = (item.findtext("guid") or url).strip()
        try:
            published = parsedate_to_datetime(item.findtext("pubDate") or "")
            if published.tzinfo is None or not title or not identity or not publisher:
                raise ValueError("unknown metadata")
            if urlsplit(url).scheme != "https" or urlsplit(url).hostname != "news.google.com":
                raise ValueError("invalid feed link")
            if urlsplit(source_url).scheme not in {"http", "https"} or not urlsplit(source_url).hostname:
                raise ValueError("publisher URL missing")
        except (ValueError, TypeError, OverflowError):
            counts["invalid"] += 1
            continue
        published = published.astimezone(timezone.utc)
        if published > observed_at:
            counts["future"] += 1
            continue
        if published.astimezone(KST).date() != today:
            counts["outside_today"] += 1
            continue
        matches = [term for term in terms if term in normalize(title)]
        if not matches:
            counts["irrelevant"] += 1
            continue
        body = {"source": "GOOGLE_NEWS_RSS", "corp_code": "", "entity_ticker": "",
                "source_document_id": sha256(identity.encode()).hexdigest(),
                "receipt_date": today.isoformat(), "title": title, "url": url}
        row = {**body,
            "published_at": published.isoformat(), "first_seen_at": observed_at.astimezone(timezone.utc).isoformat(),
            "available_at": observed_at.astimezone(timezone.utc).isoformat(),
            "publication_time_verified": False, "source_tier": "AGGREGATOR",
            "publisher": publisher, "publisher_url": source_url, "matched_terms": matches,
            "feed_sha256": sha256(raw).hexdigest(), "correction_chain_verified": False,
            "capital_authority": "NONE", "status": "FORWARD_SHADOW_DIAGNOSTIC_ONLY",
            "entity_mapping_status": "UNVERIFIED_NO_ETF_CONSTITUENT_MAPPING"}
        row["source_content_hash"] = digest(source_body(row))
        observations.append(row)
    return {"observations": observations, "filter_counts": counts,
            "observed_at": observed_at.isoformat(), "include_terms": include_terms}


def store_feed(directory: Path, *, raw: bytes, parsed: dict, query: str) -> dict:
    """Raw preserved by checksum; existing append-only content revision gate reused.

    V87 candle normalization is deliberately NOT applied to news or trading data.
    """
    directory.mkdir(parents=True, exist_ok=True)
    if parse_feed(raw, observed_at=datetime.fromisoformat(parsed["observed_at"]),
                  include_terms=parsed["include_terms"]) != parsed:
        raise ValueError("raw/parsed metadata mismatch")
    raw_hash = sha256(raw).hexdigest()
    raw_path = directory / f"{raw_hash}.xml"
    if raw_path.exists():
        if raw_path.read_bytes() != raw:
            raise ValueError("raw archive hash mismatch")
    else:
        with raw_path.open("xb") as handle:
            handle.write(raw)
    query_hash = sha256(query.encode()).hexdigest()
    stored = append_observations(directory / f"rss_{query_hash}.jsonl", parsed["observations"])
    receipt = {"query": query, "query_hash": query_hash, "raw_sha256": raw_hash,
               "observed_at": parsed["observed_at"], "include_terms": parsed["include_terms"],
               "filter_counts": parsed["filter_counts"], "accepted_items": len(parsed["observations"]),
               "appended": stored["appended"], "capital_authority": "NONE"}
    identity_keys = ("query", "raw_sha256", "observed_at", "include_terms")
    receipt["collection_id"] = digest({key: receipt[key] for key in identity_keys})
    receipt["receipt_hash"] = digest(receipt)
    # Persist even an empty result; it is NOT evidence that no relevant news exists.
    lock = directory / "collection_log.lock"
    descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        log = directory / "collection_log.jsonl"
        existing = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()] if log.exists() else []
        for entry in existing:
            if entry["receipt_hash"] != digest({key: value for key, value in entry.items() if key != "receipt_hash"}):
                raise ValueError("collection receipt tamper")
        existing_ids = {digest({key: entry[key] for key in identity_keys}) for entry in existing}
        if receipt["collection_id"] not in existing_ids:
            with log.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(receipt, ensure_ascii=False, sort_keys=True) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
    finally:
        os.close(descriptor)
        lock.unlink()
    return {**stored, "raw_sha256": raw_hash, "query_hash": query_hash,
            "filter_counts": parsed["filter_counts"], "capital_authority": "NONE"}


def visible_observations(rows: list[dict], *, cutoff: datetime) -> list[dict]:
    if cutoff.tzinfo is None:
        raise ValueError("aware cutoff required")
    return [row for row in rows
            if datetime.fromisoformat(row["published_at"]) <= cutoff
            and datetime.fromisoformat(row["first_seen_at"]) <= cutoff]
