"""Verify C3 lineage and freeze a complete-case H252 sample without evaluating returns."""
import hashlib
import json
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "runtime/task13_c4"
C3 = ROOT / "runtime/task13_c3"
R0 = ROOT / "runtime/task13_r0"
sys.path.insert(0, str(ROOT / "experiments/task13_c1"))
from factor import estimate_beta_sigma


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name, data):
    path = OUT / name
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")
    temp.replace(path)


def frame(path, columns):
    data = pd.read_csv(path, usecols=["date", *columns], index_col="date", parse_dates=True,
                       float_precision="round_trip")
    assert data.index.is_unique and data.index.is_monotonic_increasing, path
    return data.loc[:"2024-12-31"]


def mask(path, days):
    s = frame(path, ["eligible"]).eligible
    assert s.isin([True, False]).all(), path
    return s.reindex(days, fill_value=False).astype(bool)


def controls_at(prices, market, at):
    """MOM63 needs 64 observed closes including the anchor. No bridged returns."""
    i = prices.index.get_loc(at)
    if i < 126 or prices.iloc[i-63:i+1].isna().any():
        return None
    close = prices.iloc[:i+1]
    returns = close.pct_change(fill_method=None)
    beta, _, _ = estimate_beta_sigma(np.log(close).diff(), np.log(market.loc[:at]).diff())
    result = dict(REV5=1-close.iloc[-1]/close.iloc[-6],
                  MOM20=close.iloc[-1]/close.iloc[-21]-1,
                  MOM63=close.iloc[-1]/close.iloc[-64]-1,
                  LOWVOL20=-returns.iloc[-20:].std(ddof=1), beta=beta.iloc[-1])
    return {k: float(v) for k,v in result.items()} if np.isfinite(list(result.values())).all() else None


def gate(rows):
    counts = Counter(str(r["filed_year"]) for r in rows)
    return len({r["CIK"] for r in rows}) >= 40 and len(rows) >= 100 and sum(n >= 15 for n in counts.values()) >= 3


def positive(s):
    return s.notna() & np.isfinite(s) & s.gt(0)


def prepare():
    if (OUT / "execution.json").exists() or (OUT / "seal.json").exists():
        raise RuntimeError("C4 already sealed or reserved")
    manifest = read(C3 / "artifact_manifest.json")["files"]
    checked = {}
    for name, digest in manifest.items():
        assert sha(ROOT / name) == digest, name
        checked[name] = digest
    draft = read(C3 / "followup_contract_draft.json")
    assert sha(C3 / "financial_panel.json") == draft["input_panel"]["sha256"]
    assert draft["H"] == 252 and draft["direction"] == 1
    panel = read(C3 / "financial_panel.json")["rows"]
    csv = pd.read_csv(C3 / "financial_panel.csv", dtype=str, keep_default_na=False)
    assert all(csv[k].tolist() == [str(r[k]) for r in panel] for k in csv.columns)
    eligibility = {r["event_id"]:r for r in read(C3 / "label_availability.json")["rows"]}
    assert len(eligibility) == len(panel) == 163
    assets_path = R0 / "native_manifest/assets.json"
    assets = {a["symbol"]:a for a in read(assets_path) if a["market"] == "US"}
    market_dir = R0 / "accepted/US/^GSPC"
    inputs = dict(checked)
    for p in [assets_path, market_dir/"quote.csv", market_dir/"quality_mask.csv"]:
        inputs[str(p.relative_to(ROOT))] = sha(p)
    market_raw = frame(market_dir/"quote.csv", ["close"])
    days = market_raw.index
    assert (days.dayofweek < 5).all()
    market_ok = mask(market_dir/"quality_mask.csv", days)
    market = market_raw.close.where(market_ok & positive(market_raw.close))
    rows, excluded, seen = [], [], set()
    for symbol in sorted({e["symbol"] for e in panel}):
        asset = assets[symbol]
        company = read(C3 / "companies" / f"{symbol}.json")
        events = {e["event_id"]:e for e in company["events"]}
        files = {key: ROOT/asset[key] for key in ["adjusted_path", "eligibility_path"]}
        for key, hash_key in [("adjusted_path","adjusted_hash"),("eligibility_path","eligibility_hash")]:
            path = files[key]
            assert sha(path) == asset[hash_key], path
            inputs[str(path.relative_to(ROOT))] = asset[hash_key]
        basic_path = files["adjusted_path"].parent/"quality_mask.csv"
        inputs[str(basic_path.relative_to(ROOT))] = sha(basic_path)
        native, basic = mask(files["eligibility_path"], days), mask(basic_path, days)
        assert not (native & ~basic).any()
        quality = native & basic
        prices = frame(files["adjusted_path"], ["open","close"]).reindex(days)
        closes = prices.close.where(quality & positive(prices.close))
        for event in [e for e in panel if e["symbol"] == symbol]:
            eid, filed = event["event_id"], event["filed"]
            identity = event["CIK"], event["period_start"], event["period_end"]
            assert identity not in seen
            seen.add(identity)
            original = events[eid]
            assert all(original[k] == v for k,v in event.items() if k in original)
            assert company["company"]["CIK"] == original["CIK"] == event["CIK"]
            assert event["version"] == "FIRST_CURRENT_PERIOD_ORIGINAL_10K" or event["version"].startswith("FIRST_CURRENT_PERIOD_ORIGINAL_10K;")
            assert event["form"] == "10-K"
            assert event["period_start"] < event["period_end"] <= filed <= "2022-12-31"
            public = pd.Timestamp(event["public_available_upper_bound"])
            expected = pd.Timestamp(filed + "T23:59:59", tz=ZoneInfo("America/New_York"))
            assert public == expected
            assets_avg = (Decimal(event["Assets_start"]) + Decimal(event["Assets_end"]))/2
            assert assets_avg > 0 and assets_avg == Decimal(event["AverageAssets"])
            assert -(Decimal(event["NI"]) - Decimal(event["OperatingCashFlow"]))/assets_avg == Decimal(event["feature"])
            assert len(original["proofs"]) == 4
            for proof in original["proofs"]:
                f, v = proof["api_fact"], proof["original"]
                assert f["accession"] == eid and f["published"] == filed and f["currency"] == v["currency"] == "USD"
                assert int(v["entity_CIK"]) == int(event["CIK"]) and Decimal(f["value"]) == Decimal(v["value"])
                assert proof["original_source_hash"] == event["source"]["source_hash"]
            entry_pos = days.searchsorted(pd.Timestamp(filed), side="right")
            exit_pos = entry_pos+252
            anchor_pos = days.searchsorted(pd.Timestamp(filed), side="left")-1
            record = dict(event_id=eid,symbol=symbol,CIK=event["CIK"],filed=filed,
                          filed_year=int(filed[:4]), feature=float(event["feature"]),
                          sector_current=event["sector_current"],
                          entry=str(days[entry_pos].date()),exit=str(days[exit_pos].date()),
                          anchor=str(days[anchor_pos].date()))
            prior = eligibility[eid]
            assert prior["entry_session"] == record["entry"] and prior["exit_H252_session"] == record["exit"]
            assert prior["label_value"] is None
            reasons = list(prior["reason"])
            span = slice(entry_pos,exit_pos+1)
            if not quality.iloc[span].all() or not positive(prices.open.iloc[span]).all():
                reasons.append("STOCK_PATH_NOT_COMPLETE")
            if not market_ok.iloc[span].all():
                reasons.append("C3_INDEX_PATH_MASK")
            control = controls_at(closes, market, days[anchor_pos])
            if control is None:
                reasons.append("PRE_FILING_CONTROL_UNAVAILABLE")
            if reasons:
                excluded.append({**record,"reasons":reasons})
            else:
                rows.append({**record,**control})
    counts = Counter(str(r["filed_year"]) for r in rows)
    assert len({(r["CIK"],r["filed_year"]) for r in rows}) == len(rows), "Repeated issuer in same filing-year"
    state = "PREFLIGHT_PASS" if gate(rows) else "SAMPLE_INSUFFICIENT"
    write("sample.json", {"rows":rows,"exclusions":excluded})
    write("input_hashes.json",inputs)
    write("preflight.json",{"status":state,"firms":len({r["CIK"] for r in rows}),"events":len(rows),
          "years":dict(sorted(counts.items())),"excluded":len(excluded),
          "benchmark":"Stock adjusted H252 rank only. GSPC price index for pre-filing beta and inherited quality mask only.",
          "source":"C3 original proof records checked against panel and original manifest. No H252 returns computed.",
          "minimum":{"issuers":40,"events":100,"years_with_15":3}})
    print(state,len(rows),dict(counts))


if __name__ == "__main__":
    try:
        prepare()
    except Exception as exc:
        if not (OUT/"seal.json").exists() and not (OUT/"execution.json").exists():
            write("preflight_failure.json", {"status":"INVALID_INPUT","error":repr(exc)})
        raise
