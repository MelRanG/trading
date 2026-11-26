"""Isolated audit and single conditional prediction diagnostic of archived Kiwoom data."""
from collections import Counter, defaultdict
import io
import json
from pathlib import Path

import numpy as np
import pandas as pd

from experiments.task13_pth_to.preflight import REF, ROOT, RUNTIME, data_sources, daily_shares, digest

OLD = RUNTIME / "task13_pth_to/preflight.json"
PHASE = "KR_PTH_LAGGED_KIWOOM_MEAN_DAILY_TURNOVER"
MIN_NAMES = 25
MIN_MONTHS = 24


def required(condition, message):
    if not condition:
        raise ValueError(message)


def inventory():
    assets, source, snapshots, hashes, _ = data_sources()
    prior = json.loads(OLD.read_bytes())
    required(all(prior["source_sha256"][k] == v for k, v in hashes.items()), "official source hash changed")
    official = daily_shares(snapshots)
    quotes = {}
    for raw in snapshots:
        for row in json.loads(raw)["OutBlock_1"]:
            key = (pd.Timestamp(row["BAS_DD"]), row["ISU_CD"], row["MKT_NM"])
            quotes[key] = tuple(int(row[col]) for col in ("TDD_OPNPRC","TDD_HGPRC","TDD_LWPRC","TDD_CLSPRC"))

    broker = {}
    for name, sha in prior["source_sha256"].items():
        if not (name.startswith(str((REF/"task13_f1_r4/raw").relative_to(ROOT)))
                or name.startswith("runtime/task13_f1_r5/nominal/")):
            continue
        raw = (ROOT/name).read_bytes()
        required(digest(raw) == sha, f"broker source hash changed {name}")
        receipt = ROOT/Path(name).with_suffix(".receipt.json")
        if receipt.is_file():
            metadata = json.loads(receipt.read_bytes())
            required(metadata["sha256"] == sha and metadata["query"]["upd_stkpc_tp"] == "0",
                     f"receipt source mismatch {name}")
        page = json.loads(raw)
        for row in page["result_list"]:
            key = (pd.Timestamp(row["dt"]), page["stk_cd"])
            value = (int(row["trde_qty"]), float(row["trde_tern_rt"] or "nan"),
                     row["upd_stkpc_tp"], tuple(int(row[c]) for c in ("open_pric","high_pric","low_pric","cur_prc")))
            if not np.isfinite(value[1]):
                continue
            required(key not in broker or broker[key] == value, f"overlapping broker rows conflict {key}")
            broker[key] = value

    known_diffs = json.loads((RUNTIME/"task13_f1_r5/preflight.json").read_bytes())["volume_scope_differences"]
    known = {(pd.Timestamp(row["date"]), row["symbol"][:6]) for row in known_diffs}
    compared, mismatches, paired = Counter(), [], set()
    for (day, code, board), (shares, volume) in official.items():
        if (day,code) not in broker:
            continue
        qty, rate, flags, ohlc = broker[day,code]
        if qty == volume:
            required(abs(rate - 100*qty/shares) <= .005000001, "broader vendor rounding conflict")
            paired.add((day, code))
        else:
            mismatches.append(dict(date=str(day.date()),code=code,board=board,kiwoom=qty,krx=volume,
                action_flags=flags, ohlc_match=ohlc==quotes[day,code,board],
                vendor_own_qty_match=abs(rate-100*qty/shares)<=.005000001,
                official_qty_match=abs(rate-100*volume/shares)<=.005000001))
            compared[(day,code)] += 1
    required(len(paired)==680 and len(mismatches)==60 and set(compared)==known, "prior crosscheck changed")
    return [r for r in assets if r["market"]=="KR"], source, broker, set(compared), mismatches


def parse_frame(raw, columns=None):
    return pd.read_csv(io.BytesIO(raw),usecols=columns,parse_dates=["date"]).set_index("date")


def sample(assets, sources, broker, mismatches):
    grids = {}
    monthly = defaultdict(list)
    rejected = Counter()
    broker_codes = {code for _, code in broker}
    for asset in assets:
        symbol = asset["symbol"]
        code = symbol[:6]
        if code not in broker_codes:
            continue
        name = asset["calendar_key"]
        if name not in grids:
            grid = parse_frame(sources[asset["calendar_path"]],["date"]).index
            dates = pd.Series(grid,index=grid)
            grids[name] = grid, dates.groupby(grid.to_period("M")).agg(["first","last"])
        sessions, months = grids[name]
        bars = parse_frame(sources[asset["adjusted_path"]]).reindex(sessions)
        eligible = parse_frame(sources[asset["eligibility_path"]]).eligible.reindex(sessions).eq(True)
        price_ok = eligible & bars.close.gt(0) & np.isfinite(bars.close)
        open_ok = eligible & bars.open.gt(0) & np.isfinite(bars.open)
        for month in months.index[1:-2]:
            if month < pd.Period("2023-08",freq="M"):
                continue
            start,end = months.loc[month,["first","last"]]
            anchor = months.at[month-1,"last"]
            left = anchor - pd.Timedelta(weeks=52)
            start_open = months.at[month+1,"first"]
            next_open = months.at[month+2,"first"]
            window = sessions[(sessions>=start)&(sessions<=end)]
            if not price_ok.loc[left:end].all():
                rejected["r0_formation_or_52wk_mask"] += 1
                continue
            if not all((d,code) in broker and (d,code) not in mismatches for d in window):
                rejected["vendor_missing_or_scope_disputed"] += 1
                continue
            daily = [broker[d,code] for d in window]
            if any(qty<=0 or rate<0 or set(flags.split(","))-{"","4"} for qty,rate,flags,_ in daily):
                rejected["volume_or_noncash_action"] += 1
                continue
            if not (open_ok.at[start_open] and open_ok.at[next_open] and price_ok.loc[start_open:next_open].all()):
                rejected["horizon_mask"] += 1
                continue
            monthly[str(month)].append(asset["board"])
    coverage = {month:len(records) for month,records in sorted(monthly.items())}
    by_board = {month: dict(Counter(monthly[month])) for month in coverage}
    return coverage, by_board, rejected


def quality():
    assets, sources, broker, bad, rows = inventory()
    coverage, boards, excluded = sample(assets,sources,broker,bad)
    qualified = [m for m,n in coverage.items() if n>=MIN_NAMES]
    evidence = dict(
        hypothesis=PHASE, original_reproduction=False,
        mismatch_dates=dict(Counter(r["date"] for r in rows)),
        mismatch_by_board=dict(Counter(r["board"] for r in rows)),
        ohlc_matches=sum(r["ohlc_match"] for r in rows),
        positive_krx_minus_kiwoom=sum(r["krx"]>r["kiwoom"] for r in rows),
        mismatch_corporate_flags=dict(Counter(r["action_flags"] for r in rows)),
        mismatch_vendor_own_qty_reconciles=sum(r["vendor_own_qty_match"] for r in rows),
        mismatch_official_qty_reconciles=sum(r["official_qty_match"] for r in rows),
        excluded_symbol_months=dict(excluded), monthly_eligible_symbols=coverage, monthly_by_board=boards,
        qualifying_months=qualified, min_names=MIN_NAMES, min_months=MIN_MONTHS,
        quality_pass=len(qualified)>=MIN_MONTHS, mismatch_rows=rows,
        decision="EXPLORATORY_INCONCLUSIVE" if len(qualified)<MIN_MONTHS else "COVERAGE_PASS",
        future_return_evaluations=0,
        prior_preflight_sha256=digest(OLD.read_bytes()), code_sha256=digest(Path(__file__).read_bytes()))
    print(json.dumps(evidence,indent=2,allow_nan=False))


def main():
    quality()


if __name__ == "__main__":
    main()
