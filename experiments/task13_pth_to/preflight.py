"""Audit price and share-count coverage without constructing signals or labels."""
from collections import Counter, defaultdict
from hashlib import sha256
import io
import json
from pathlib import Path
import re
import tarfile

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "runtime"
REF = RUNTIME / "research_reference"
SNAPSHOT = re.compile(r"^krx_(?:[0-9]{8}_(?:KOSPI|KOSDAQ)|(?:KOSPI|KOSDAQ)_[0-9]{8})\.json$")
R0_ASSETS = REF / "task13_r0/native_manifest/assets.json"


def digest(data):
    return sha256(data).hexdigest()


def data_sources():
    reference = json.loads((REF / "index.json").read_bytes())
    inventory = Path(reference["archive_inventory"]).read_bytes()
    assert digest(inventory) == reference["archive_inventory_sha256"]
    inventory = json.loads(inventory)
    assets_data = R0_ASSETS.read_bytes()
    assert digest(assets_data) == inventory["runtime/task13_r0/native_manifest/assets.json"]["sha256"]
    assets = json.loads(assets_data)
    targets = {r[k] for r in assets for k in ("adjusted_path", "eligibility_path", "calendar_path")}
    quality_paths = {str(Path(r["adjusted_path"]).with_name("quality.json")) for r in assets}
    targets.update(quality_paths)
    targets.update(n for n in inventory if SNAPSHOT.match(Path(n).name))
    files, snapshots, hashes = {}, [], {}
    with tarfile.open(reference["archive"], "r|gz") as source:
        for entry in source:
            if entry.name not in targets:
                continue
            raw = source.extractfile(entry).read()
            assert digest(raw) == inventory[entry.name]["sha256"]
            if SNAPSHOT.match(Path(entry.name).name):
                snapshots.append(raw)
                hashes[entry.name] = digest(raw)
            else:
                files[entry.name] = raw
    found = set(files) | set(hashes)
    assert found == targets, sorted(targets - found)
    for base in (RUNTIME / "task13_f1_r2/raw", RUNTIME / "task13_f1_r5/reference",
                 RUNTIME / "task13_f1_r6/raw", REF / "task13_f1_r4"):
        for p in sorted(base.glob("krx_*.json")):
            if SNAPSHOT.match(p.name):
                raw = p.read_bytes()
                snapshots.append(raw)
                hashes[str(p.relative_to(ROOT))] = digest(raw)
    return assets, files, snapshots, hashes, inventory


def daily_shares(snapshots):
    rows = {}
    for raw in snapshots:
        for row in json.loads(raw)["OutBlock_1"]:
            if row.get("LIST_SHRS") and int(row["LIST_SHRS"]) > 0:
                key = (pd.Timestamp(row["BAS_DD"]), row["ISU_CD"], row["MKT_NM"])
                value = (int(row["LIST_SHRS"]), int(row["ACC_TRDVOL"]))
                if key in rows and rows[key] != value:
                    raise ValueError(f"official snapshot conflict: {key}")
                rows[key] = value
    return rows


def session_mask(assets, sources, shares):
    """Count coverage only. Use observed index calendars and conservative masks."""
    calendar = {r["calendar_key"]: pd.DatetimeIndex(pd.read_csv(
        io.BytesIO(sources[r["calendar_path"]]), usecols=["date"], parse_dates=["date"]).date)
        for r in assets}
    price_counts, endpoint_counts, all_days_counts = defaultdict(Counter), defaultdict(Counter), defaultdict(Counter)
    action_counts, literal_shares_columns = Counter(), Counter()
    for asset in assets:
        market, symbol = asset["market"], asset["symbol"]
        sessions = calendar[asset["calendar_key"]]
        price_data = sources[asset["adjusted_path"]]
        assert digest(price_data) == asset["adjusted_hash"]
        mask_data = sources[asset["eligibility_path"]]
        assert digest(mask_data) == asset["eligibility_hash"]
        bar = pd.read_csv(io.BytesIO(price_data), parse_dates=["date"]).set_index("date").reindex(sessions)
        assert bar.index.is_unique
        mask = pd.read_csv(io.BytesIO(mask_data), parse_dates=["date"]).set_index("date").eligible.reindex(sessions).eq(True)
        literal_shares_columns[market] += sum("share" in name.lower() for name in bar)
        positive = mask & np.isfinite(bar.close) & bar.close.gt(0)
        valid_turnover_input = mask & np.isfinite(bar.volume) & bar.volume.gt(0)
        valid_open = mask & np.isfinite(bar.open) & bar.open.gt(0)
        q = json.loads(sources[str(Path(asset["adjusted_path"]).with_name("quality.json"))])
        if q["actions"].get("splits"):
            action_counts[market] += 1
        months = pd.Series(sessions, index=sessions).groupby(sessions.to_period("M")).agg(["first", "last"])
        for month in months.index[1:-2]:
            end = months.at[month, "last"]
            if end.year not in range(2018, 2027):
                continue
            start = months.at[month, "first"]
            anchor = months.at[month-1, "last"]
            left = anchor - pd.Timedelta(weeks=52)
            if sessions[0] > left:
                continue
            if not positive.loc[left:end].all() or not valid_turnover_input.loc[start:end].all():
                continue
            if not all(valid_open.at[months.at[m, "first"]] for m in (month+1,month+2)):
                continue
            label = str(month)
            price_counts[market][label] += 1
            if market != "KR":
                continue
            code = symbol.split(".")[0]
            board = asset["board"]
            if (end, code, board) in shares:
                endpoint_counts[market][label] += 1
            if all((d, code, board) in shares for d in sessions[(sessions>=start)&(sessions<=end)]):
                all_days_counts[market][label] += 1
    return dict(price_only=dict(price_counts), endpoint_shares_overlap=dict(endpoint_counts),
                full_formation_month_daily_shares=dict(all_days_counts),
                R0_adjusted_share_columns=dict(literal_shares_columns),
                R0_symbols_with_split_records=dict(action_counts))


def kiwoom_audit(shares):
    daily = {}
    hashes = {}
    for base in (REF/"task13_f1_r4/raw", RUNTIME/"task13_f1_r5/nominal"):
        for p in sorted(base.glob("*.json")):
            raw = p.read_bytes()
            page = json.loads(raw)
            if "result_list" not in page or "stk_cd" not in page:
                continue
            hashes[str(p.relative_to(ROOT))] = digest(raw)
            for row in page["result_list"]:
                key = (pd.Timestamp(row["dt"]), page["stk_cd"])
                value = (int(row["trde_qty"]), row.get("trde_tern_rt"))
                if key in daily and daily[key] != value:
                    # Different retrievals overlap. Do not select one to manufacture a match.
                    daily[key] = None
                else:
                    daily[key] = value
    rows = {k:v for k,v in daily.items() if v is not None and v[1] not in ("",None)}
    numbers = Counter()
    for (day, code, _), (count, official_volume) in shares.items():
        if (day, code) in rows:
            number, pct = rows[day, code]
            numbers["official_pairs"] += 1
            if number != official_volume:
                numbers["different_volume"] += 1
                continue
            numbers["volume_matches"] += 1
            delta = abs(float(pct)-100*number/count)
            numbers["within_nearest_0.01_pct"] += delta <= .0050000001
            numbers["within_0.01_pct"] += delta < .0100000001
    return dict(symbols=len({code for _,code in rows}), days=len({day for day,_ in rows}),
                dated_rows_with_ratio=len(rows), disputed_overlap_rows=sum(v is None for v in daily.values()),
                first=str(min(d for d,_ in rows).date()),last=str(max(d for d,_ in rows).date()),
                crosscheck=dict(numbers)), hashes


def main():
    assets, sources, snapshots, hashes, inventory = data_sources()
    shares = daily_shares(snapshots)
    by_date = Counter(str(d.date()) for d,_,_ in shares)
    board_sets = defaultdict(set)
    for day, _, board in shares:
        board_sets[str(day.date())].add(board)
    by_board = {day: sorted(boards) for day, boards in board_sets.items()}
    coverage = session_mask(assets,sources,shares)
    ratio, vendor_hashes = kiwoom_audit(shares)
    h1 = {market: np.load(RUNTIME/f"task13_h1/{market}_panel.npz",allow_pickle=False).files
          for market in ("US","KR")}
    facts = {p.split("/")[1] for p in inventory if "companyfacts" in p.lower()}
    print(json.dumps(dict(
        data_status={"US":"PTH_TO_DATA_BLOCKED","KR":"PTH_TO_DATA_BLOCKED"},
        price_note="date/symbol/mask coverage only, no price ratios, future returns or signal ranking",
        assets_by_market=dict(Counter(a["market"] for a in assets)),
        coverage=coverage, official_share_snapshots_by_date=dict(sorted(by_date.items())),
        official_share_snapshots_markets=dict(sorted(by_board.items())),
        kiwoom_daily_ratio=ratio, H1_panel_schema=h1, archives_with_sec_facts=sorted(facts),
        source_sha256=hashes|vendor_hashes, prospective_evaluations=0),indent=2))


if __name__ == "__main__":
    main()
