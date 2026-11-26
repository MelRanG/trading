"""Bounded offline verification of original archived quarterly EPS disclosures."""
from datetime import datetime
from decimal import Decimal
import gzip
import json
from pathlib import Path
import re
import tarfile

from dateutil.parser import parse
from lxml import html

from experiments.task13_h1.prepare_inputs import ROOT, sha

B2 = "runtime/task13_b2/"
BENCH = "runtime/task13_r0/accepted/US/^GSPC/"
ARCHIVE = ROOT / "runtime/research_reference/index.json"
DART = ("runtime/task13_b0/result_summary.json", "runtime/task13_b0/validation.json",
        "runtime/task13_b1/KR_collection.json")
DATE_TEXT = re.compile(r"(?:[A-Za-z]+\.?\s+\d{1,2}(?:,\s*|\s+)20\d{2}|\d{1,2}/\d{1,2}/20\d{2})")
QUARTER = re.compile(r"\b(?:three\s+months|quarter)\s+ended\b", re.I)
MONTH_DAY = re.compile(r"[A-Za-z]+\.?\s+\d{1,2}\b")
YEAR = re.compile(r"20\d{2}")
EPS = re.compile(r"(?:earnings|income|loss|net\s+loss).*?per\s+(?:common\s+|ordinary\s+)?share|\bEPS\b", re.I)
NUMBER = re.compile(r"\(?[-−+]?\d+\.\d{1,4}\)?")


def archived():
    pointer = json.loads(ARCHIVE.read_bytes())
    inventory_file = Path(pointer["archive_inventory"])
    assert sha(inventory_file) == pointer["archive_inventory_sha256"]
    inventory = json.loads(inventory_file.read_bytes())
    pack = Path(pointer["archive"])
    assert sha(pack) == pointer["archive_sha256"]
    paths = {
        p for p in inventory
        if p.startswith(B2 + "collection/") and p.endswith(".json")
    } | set(DART) | {BENCH + "quote.csv", BENCH + "quality_mask.csv"}
    from hashlib import sha256

    data, hashes = {}, {}
    def extract(binary, targets):
        remaining = set(targets)
        with tarfile.open(pack, "r|gz") as f:
            for member in f:
                if member.name not in remaining:
                    continue
                raw = f.extractfile(member).read()
                digest = sha256(raw).hexdigest()
                assert digest == inventory[member.name]["sha256"], member.name
                data[member.name] = raw if binary else json.loads(raw)
                hashes[member.name] = digest
                remaining.remove(member.name)
                if not remaining:
                    break
        assert not remaining, remaining

    extract(False, paths - {BENCH + "quote.csv", BENCH + "quality_mask.csv"})
    companies = {p.split("/")[-1][:-5]: v for p, v in data.items()
                 if p.startswith(B2 + "collection/") and p.endswith(".json") and "targets" in v}
    receipts = []
    for symbol, company in companies.items():
        targets = company["targets"]
        assert [e["filing"] for e in targets] == data[B2 + f"collection/{symbol}.target_seal.json"]["target_filings"]
        receipts.extend([company.get("submissions", {}), *company.get("history", [])])
        for event in targets:
            receipts.append(event["source"])
            if event.get("primary_source"):
                receipts.append(event["primary_source"])
    extract(True, {r["storage_path"] for r in receipts if r.get("status") == "SAVED"} |
            {BENCH + "quote.csv", BENCH + "quality_mask.csv"})
    return companies, data, hashes


def body(receipt, archive):
    from hashlib import sha256
    path = receipt["storage_path"]
    raw = gzip.decompress(archive[path]) if path.endswith(".gz") else archive[path]
    assert sha256(raw).hexdigest() == receipt["source_hash"], path
    return raw


def exhibit(event, archive):
    source = body(event["source"], archive)
    if event.get("source_kind") == "EXHIBIT_HTML":
        official = html.fromstring(body(event["primary_source"], archive))
        hrefs = official.xpath("//a/@href")
        filename = event["exhibit_filename"]
        if filename not in hrefs or filename.split("/")[-1] != event["source"]["url"].split("/")[-1]:
            return None
        return source
    docs = re.findall(rb"<DOCUMENT>(.*?)</DOCUMENT>", source, re.I | re.S)
    exhibits = [d for d in docs if re.search(rb"(?m)^<TYPE>EX-99(?:\.1)?\s*$", d)]
    if len(exhibits) == 1:
        matches = re.findall(rb"<TEXT>(.*?)</TEXT>", exhibits[0], re.I | re.S)
        if len(matches) == 1:
            return matches[0]
    return None


def texts(row):
    pieces = (" ".join(c.text_content().replace("\u200b", "").split()) for c in row.xpath("./td|./th"))
    return [p for p in pieces if p]


def periods(rows, filed_day):
    headers = [(i, cells) for i, cells in enumerate(rows[:14]) if cells and QUARTER.search(cells[0])]
    for i, cells in headers:
        dates = DATE_TEXT.findall(" ".join(cells))
        if len(dates) < 2 and i+1 < len(rows):
            dates = DATE_TEXT.findall(" ".join(rows[i+1]))
        if len(dates) < 2:
            quarter_md = MONTH_DAY.findall(cells[0])
            date_row = rows[i+1] if i+1 < len(rows) else []
            month_days = MONTH_DAY.findall(" ".join(date_row))[:2]
            for j in (i+1, i+2):
                if j >= len(rows):
                    break
                years = [x for x in rows[j] if YEAR.fullmatch(x)][:2]
                if len(years) != 2:
                    continue
                md = quarter_md*2 if len(quarter_md) == 1 else month_days
                if len(md) == 2:
                    dates = [f"{d}, {y}" for d, y in zip(md, years)]
                break
        if len(dates) >= 2:
            try:
                current, prior = (parse(re.sub(r",\s*", ", ", x), default=datetime(1900, 1, 1)).date()
                                   for x in dates[:2])
            except ValueError:
                continue
            if 350 <= (current-prior).days <= 380 and 0 <= (filed_day-current).days <= 95:
                return current, prior, i
    return None


def amount(text):
    x = text.replace("$", "").replace("−", "-").strip()
    if NUMBER.fullmatch(x) is None or (x.startswith("(") != x.endswith(")")):
        return None
    return -Decimal(x[1:-1]) if x.startswith("(") else Decimal(x)


def eps_pairs(raw, filed_day):
    tree = html.fromstring(raw.decode("utf-8", "replace"))
    pairs = {}
    for table in tree.xpath("//table[not(.//table)]"):
        nodes = table.xpath(".//tr")
        rows = [texts(node) for node in nodes]
        found = periods(rows, filed_day)
        if not found:
            continue
        current, prior, head = found
        # Only consolidated statement-like tables with independent GAAP line items.
        row_labels = [x[0].lower() for x in rows if len(x) > 2]
        if not (any(re.fullmatch(r"(?:net |total |net operating )?(?:sales|revenues?)", x) for x in row_labels)
                and any(re.match(r"(?:net (?:income|earnings|loss)|operating (?:income|profit))", x) and not EPS.search(x)
                        for x in row_labels)
                and not re.search(r"non.gaap|reconciliation|adjusted|pro forma", " ".join(" ".join(r) for r in rows[:head]), re.I)):
            continue
        for pos, cells in enumerate(rows[head+1:], head+1):
            if not cells:
                continue
            label = cells[0]
            specific = EPS.search(label) and re.search(r"diluted", label, re.I)
            lines_above = [r[0] for r in rows[max(head, pos-3):pos] if r]
            subsection = bool(re.fullmatch(r"diluted(?:\s*\([a-z0-9]+\))?", label, re.I)
                              and any(EPS.search(x) for x in lines_above))
            if not (specific or subsection) or re.search(r"adjust|core|continuing|discontinued|pro forma|weighted|shares|%|guidance", label, re.I):
                continue
            normalized = [x for x in cells[1:] if x not in ("$", "US$", "USD")]
            if len(normalized) < 2:
                continue
            a, b = map(amount, normalized[:2])
            if a is None or b is None:
                continue
            # Percentage interleaving is invalid. Successive amount columns must form a comparable pair.
            if any(x.endswith("%") for x in normalized[:2]) or not (a or b):
                continue
            key = current.isoformat(), prior.isoformat(), str(a.normalize()), str(b.normalize())
            pairs[key] = {"row_xpath": tree.getroottree().getpath(nodes[pos]), "row_cells": cells,
                          "quarter_heading": rows[head], "following_headers": rows[head+1:head+3]}
    return pairs


def submission_records(company, archive):
    found = {}
    for m in [company.get("submissions", {}), *company.get("history", [])]:
        if m.get("status") != "SAVED":
            continue
        raw = json.loads(body(m, archive))
        if "filings" in raw:
            assert int(raw["cik"]) == int(company["cik"])
            rows = raw["filings"]["recent"]
        else:
            rows = raw
        for i, acc in enumerate(rows["accessionNumber"]):
            found[acc] = {k: v[i] for k, v in rows.items() if isinstance(v, list) and len(v) == len(rows["accessionNumber"])}
    return found
