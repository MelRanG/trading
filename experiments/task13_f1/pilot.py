"""Bounded read-only trial of the official KRX investor-by-security screen."""
from datetime import datetime, timezone
import hashlib
from http.cookiejar import CookieJar
import json
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "runtime/task13_f1"
SCREEN = "https://data.krx.co.kr/contents/MDC/MDI/outerLoader/index.cmd?screenId=MDCSTAT023"
QUERY = "https://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd"
PILOT = ("005930.KS", "005490.KS", "247540.KQ")
START = "20240401"
END = "20240430"


def main():
    assets = ROOT / "runtime/task13_r0/native_manifest/assets.json"
    plan = {
        "pilot": PILOT, "start": START, "end": END,
        "assets_sha256": hashlib.sha256(assets.read_bytes()).hexdigest(),
        "collection_cap_default": 80, "absolute_cap": 120,
        "pilot_max_data_requests": 6,
        "stop_on_access_control": True, "return_reads": 0,
    }
    with (OUT / "pilot_plan.json").open("x") as handle:
        json.dump(plan, handle, indent=2)
    universe = {asset["symbol"]: asset for asset in json.loads(assets.read_bytes())
                if asset["market"] == "KR" and asset["cohort"] == "CORE"}
    assert all(universe[symbol]["current_listing_verified"] for symbol in PILOT)
    opener = build_opener(HTTPCookieProcessor(CookieJar()))
    started = time.monotonic()
    cpu = time.process_time()

    def send(url, params=None, tag="screen"):
        payload = urlencode(params).encode() if params else None
        req = Request(url, data=payload, headers={"User-Agent": "Quant-Harness-Research/1.0"})
        when = datetime.now(timezone.utc).isoformat()
        status = None
        content_type = None
        raw = b""
        category = None
        try:
            try:
                resp = opener.open(req, timeout=15)
            except HTTPError as error:
                resp = error
            with resp:
                status = resp.code
                content_type = resp.headers.get("Content-Type")
                raw = resp.read(3_000_000)
        except (URLError, TimeoutError) as error:
            category = type(error).__name__

        sample = raw.strip().upper()
        if sample in {b"LOGOUT", b"LOGIN", b"UNAUTHORIZED", b"FORBIDDEN"} or status in {401, 403, 429}:
            category = "ACCESS_CONTROL_OR_RATE_LIMIT"
        rows = None
        if status == 200 and params and category is None:
            try:
                result = json.loads(raw)
                data = result.get("output") if isinstance(result, dict) else None
                rows = len(data) if isinstance(data, list) else None
                category = "RECEIVED_ROWS_NOT_VALIDATED" if rows else "EMPTY_OR_UNEXPECTED_SCHEMA"
            except (ValueError, UnicodeError):
                category = "NON_JSON"
        if category is None:
            category = "SCREEN_RESPONSE" if status == 200 and not params else "HTTP_ERROR"
        receipt = {
            "at_utc": when, "method": req.get_method(), "url": url, "request": params,
            "tag": tag, "http": status, "content_type": content_type,
            "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
            "rows": rows, "category": category,
        }
        if raw:
            with (OUT / f"{tag}.raw").open("xb") as handle:
                handle.write(raw)
        with (OUT / "requests.jsonl").open("a") as handle:
            handle.write(json.dumps(receipt) + "\n")
        print(tag, status, category, rows, flush=True)
        return receipt

    receipts = [send(SCREEN)]
    if receipts[0]["category"] == "SCREEN_RESPONSE":
        for symbol in PILOT:
            for basis, selector in (("net", 3), ("buy_total", 2)):
                time.sleep(1)
                params = {
                    "bld": "dbms/MDC/STAT/standard/MDCSTAT02302",
                    "strtDd": START, "endDd": END, "isuCd": universe[symbol]["isin"],
                    "inqTpCd": 2, "trdVolVal": 2, "askBid": selector, "money": 1,
                }
                receipt = send(QUERY, params, f"{symbol}_{basis}")
                receipts.append(receipt)
                if receipt["category"] != "RECEIVED_ROWS_NOT_VALIDATED":
                    break
            if receipts[-1]["category"] != "RECEIVED_ROWS_NOT_VALIDATED":
                break
    with (OUT / "pilot_result.json").open("x") as handle:
        json.dump({
            "requests": len(receipts), "status": receipts[-1]["category"],
            "source_row_count": sum(r["rows"] or 0 for r in receipts),
            "validated_rows": 0, "cpu_seconds": time.process_time() - cpu,
            "wall_seconds": time.monotonic() - started,
        }, handle, indent=2)


if __name__ == "__main__":
    main()
