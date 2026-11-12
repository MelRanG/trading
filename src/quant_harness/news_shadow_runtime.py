"""Forward-only official disclosure intake and existing severe-event shadow gate.

This module cannot mutate strategy targets, Paper accounts or broker orders.
OpenDART list records have receipt dates, not exact publication timestamps:
they remain diagnostics and are never silently promoted to capital evidence.
"""
from __future__ import annotations

from datetime import datetime, timezone, date
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import pandas as pd

from quant_harness.v72_integration_ready.opendart import OpenDartClient
from quant_harness.v102_market_evidence_agent.policy import validate_news_events

SOURCE_BODY_KEYS = ("source", "corp_code", "entity_ticker", "source_document_id", "receipt_date", "title", "url")


def source_body(row: dict) -> dict:
    keys = SOURCE_BODY_KEYS
    if row["source"] == "GOOGLE_NEWS_RSS":
        keys += ("published_at", "publisher", "publisher_url")
    return {key: row[key] for key in keys}


def digest(value: dict) -> str:
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def collect_disclosures(client: OpenDartClient, *, corp_code: str, stock_code: str,
                        start: date, end: date, observed_at: datetime) -> list[dict]:
    if not re.fullmatch(r"\d{8}", corp_code) or not re.fullmatch(r"\d{6}", stock_code):
        raise ValueError("explicit corporation and listed stock codes required")
    if observed_at.tzinfo is None or start > end or (end - start).days >= 7 or end > observed_at.astimezone(ZoneInfo("Asia/Seoul")).date():
        raise ValueError("forward intake requires an aware timestamp and at most seven days")
    result = []
    # Company-scoped official search, not whole-market/all-news scraping.
    for item in client.search_disclosures(corp_code=corp_code, start_date=start, end_date=end):
        if item.corp_code != corp_code or item.stock_code != stock_code:
            raise ValueError("official entity does not match requested scope")
        if not re.fullmatch(r"\d{14}", item.receipt_no):
            raise ValueError("invalid official document identity")
        receipt_date = datetime.strptime(item.receipt_date, "%Y%m%d").date()
        if not start <= receipt_date <= end:
            raise ValueError("official response outside requested range")
        body = {"source": "OPENDART", "corp_code": corp_code, "entity_ticker": stock_code,
                "source_document_id": item.receipt_no, "receipt_date": receipt_date.isoformat(),
                "title": item.report_name, "url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={item.receipt_no}"}
        result.append({**body, "source_content_hash": digest(body), "first_seen_at": observed_at.astimezone(timezone.utc).isoformat(),
                       "published_at": None, "timestamp_precision": "DATE_ONLY",
                       "correction_chain_verified": False, "capital_authority": "NONE",
                       "status": "DIAGNOSTIC_ONLY_PUBLICATION_TIME_UNVERIFIED"})
    return result


def append_observations(path: Path, observations: list[dict]) -> dict:
    """Preserve first-seen and raw content; changed same-document content fails closed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_suffix(".lock")
    descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        existing = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []
        for row in [*existing, *observations]:
            if row["source_content_hash"] != digest(source_body(row)):
                raise ValueError("source content hash mismatch; original retained")
        indexed = {row["source_document_id"]: row for row in existing}
        if len(indexed) != len(existing):
            raise ValueError("duplicate journal document")
        pending = []
        for row in observations:
            identity = row["source_document_id"]
            prior = indexed.get(identity)
            if prior:
                if prior["source_content_hash"] != row["source_content_hash"]:
                    raise ValueError("official content revision requires review; original retained")
                continue
            pending.append(row)
            indexed[identity] = row
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            for row in pending:
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return {"appended": len(pending), "total": len(indexed), "capital_authority": "NONE"}
    finally:
        os.close(descriptor)
        lock.unlink()


def evaluate_shadow_news(frame: pd.DataFrame, *, cutoff: str, target_symbols: set[str],
                         trusted_domains: set[str]) -> dict:
    """Evaluate the pre-existing official critical-event rule, never execute it.

    No implicit stock-to-ETF mapping: an event must name the target entity itself.
    Missing exact timestamps, provenance or correction verification fails closed.
    """
    instant = pd.Timestamp(cutoff)
    if instant.tzinfo is None:
        raise ValueError("explicit timezone required for decision cutoff")
    if frame.empty:
        return {"status": "NO_VERIFIED_NEWS", "shadow_block_new_buy_symbols": [], "capital_authority": "NONE"}
    for column in ("published_at", "first_seen_at"):
        if any(pd.Timestamp(value).tzinfo is None for value in frame[column]):
            raise ValueError("exact timezone-aware news timestamps required")
    if "correction_chain_verified" not in frame or not frame["correction_chain_verified"].map(lambda value: value is True).all():
        raise ValueError("correction chain is unverified")
    checked = validate_news_events(frame)
    if not checked["ingestion_hash"].astype(str).str.fullmatch(r"[0-9a-f]{64}").all():
        raise ValueError("provenance hash missing")
    identities = set(checked.event_id.astype(str))
    parents = {str(row.event_id): str(row.corrected_event_id) for row in checked.itertuples()
               if pd.notna(row.corrected_event_id) and str(row.corrected_event_id)}
    for identity in parents:
        cursor, visited = identity, set()
        while cursor in parents:
            if cursor in visited or parents[cursor] not in identities:
                raise ValueError("unknown or cyclic correction chain")
            visited.add(cursor)
            cursor = parents[cursor]
    visible = checked[(checked.published_at <= instant) & (checked.first_seen_at <= instant)]
    superseded = {parents[str(identity)] for identity in visible.event_id if str(identity) in parents}
    visible = visible[~visible.event_id.astype(str).isin(superseded)].drop_duplicates("canonical_event_key", keep="last")
    blocked = set()
    for row in visible.to_dict("records"):
        parsed = urlsplit(row["url"])
        if parsed.scheme != "https" or parsed.hostname != row["source_domain"] or parsed.hostname not in trusted_domains:
            raise ValueError("untrusted official-source claim")
        if row["entity_ticker"] in target_symbols and row["capital_action"] == "HARD_VETO":
            blocked.add(row["entity_ticker"])
    return {"status": "SHADOW_VETO" if blocked else "SHADOW_DIAGNOSTIC_ONLY", "visible_events": len(visible),
            "shadow_block_new_buy_symbols": sorted(blocked), "capital_authority": "NONE",
            "policy": "NEWS_OFFICIAL_SEVERE_EVENT_VETO", "target_mutation": False, "broker_mutation": False}
