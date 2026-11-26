"""Single D0 feature-only probe on R0 training closes, with mask-only future coverage."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import time

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "runtime/task13_d0"
R0 = ROOT / "runtime/task13_r0"
CONTROLS = ["formation", "REV5", "MOM20", "MOM63", "LOWVOL20",
            "negative_downside_variance_share20", "high252_proximity"]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def feature_frame(close):
    daily = close.pct_change(fill_method=None)
    formed = daily.shift(20)
    square = daily ** 2
    return pd.DataFrame({
        "score": np.sign(formed).rolling(126,min_periods=126).mean(),
        "formation": close.shift(20)/close.shift(146)-1,
        "REV5": 1-close/close.shift(5),
        "MOM20": close/close.shift(20)-1,
        "MOM63": close/close.shift(63)-1,
        "LOWVOL20": -daily.rolling(20,min_periods=20).std(),
        "negative_downside_variance_share20": -square.where(daily.lt(0),0).where(daily.notna()).rolling(20).sum()/square.rolling(20).sum(),
        "high252_proximity": close/close.rolling(252,min_periods=252).max()-1,
    })


def mask(path, days):
    col = pd.read_csv(path, usecols=["date","eligible"],index_col="date",parse_dates=True).eligible
    assert col.index.is_unique and col.isin([True, False]).all()
    return col.reindex(days,fill_value=False).astype(bool)


def train_close(path, dates):
    rows = []
    with path.open() as f:
        header = f.readline().strip().split(",")
        d, c = header.index("date"), header.index("close")
        for line in f:
            fields = line.strip().split(",")
            if fields[d] > "2022-12-31":
                break
            rows.append((pd.Timestamp(fields[d]),float(fields[c])))
    series = pd.DataFrame(rows,columns=["date","close"]).set_index("date").close.astype(float)
    assert series.index.is_unique and series.index.is_monotonic_increasing
    return series.reindex(dates)


def main():
    start = time.process_time()
    plan = OUT/"screen_plan.json"
    source = R0/"native_manifest/assets.json"
    calendar = R0/"accepted/US/^GSPC/quote.csv"
    market_mask = calendar.parent/"quality_mask.csv"
    days = pd.DatetimeIndex(pd.read_csv(calendar,usecols=["date"]).date).sort_values()
    assert days.is_unique
    dates = days[days <= "2022-12-31"]
    pilot = pd.Series(dates,index=dates).groupby(dates.to_period("Q")).max()
    pilot = pd.DatetimeIndex(pilot[pilot >= "2018-01-01"])
    all_assets = json.loads(source.read_text())
    assets = [a for a in all_assets if a["market"]=="US" and a["cohort"]=="CORE"]
    assert len(assets)==176 and len({a["symbol"] for a in assets})==176
    inputs = {str(p.relative_to(ROOT)):digest(p) for p in [plan,source,calendar,market_mask]}
    market_ok = mask(market_mask,days)
    schedule = days[(days >= "2023-04-03") & (days <= "2024-12-31")][::21]
    ceiling = Counter()
    collected = []
    identities = Counter()
    for a in assets:
        path = ROOT/a["adjusted_path"]
        ep = ROOT/a["eligibility_path"]
        quality_path = path.parent/"quality.json"
        quality = json.loads(quality_path.read_text())
        mask_path = path.parent/"quality_mask.csv"
        meta = quality["meta"]
        assert meta["symbol"] == a["symbol"] and meta["currency"]=="USD" and meta["instrumentType"]=="EQUITY"
        for p, expected in [(path,a["adjusted_hash"]),(ep,a["eligibility_hash"]),
                            (mask_path,quality["output_hashes"]["quality_mask.csv"]),(quality_path,None)]:
            h = digest(p)
            assert expected is None or h == expected,p
            inputs[str(p.relative_to(ROOT))] = h
        identities[meta["exchangeName"]] += 1
        native,basic=mask(ep,days),mask(mask_path,days)
        assert not (native & ~basic).any(),a["symbol"]
        valid = native & basic
        close = train_close(path,dates).where(valid.loc[dates])
        eligible = close.where(close.gt(0)&np.isfinite(close))
        scores = feature_frame(eligible).loc[pilot].replace([np.inf,-np.inf],np.nan).dropna()
        scores = scores[scores.formation.gt(0)].assign(symbol=a["symbol"])
        collected.append(scores)
        for t in schedule:
            i = days.get_loc(t)
            path_days = days[i+1:i+22]
            if len(path_days)==21 and path_days[-1] <= pd.Timestamp("2024-12-31"):
                if valid.iloc[i-251:i+22].all() and market_ok.loc[path_days].all():
                    ceiling[str(t.date())] += 1
    per_date = []
    passing_names=set()
    for t, rows in pd.concat(collected).groupby(level=0):
        result = {"date":str(t.date()),"names":len(rows)}
        if len(rows)>=50:
            passing_names.update(rows.symbol)
            ranked = rows[["score",*CONTROLS]].rank()
            signal = ranked.score.to_numpy()
            design = np.column_stack((np.ones(len(rows)),ranked[CONTROLS].to_numpy()))
            coeff,_,rank,_ = np.linalg.lstsq(design,signal,rcond=None)
            if rank != design.shape[1] or np.var(signal)==0:
                raise ValueError(f"Degenerate pilot date {t}")
            result["rank_overlap"] = ranked.corr().score[CONTROLS].to_dict()
            result["residual_fraction"] = float(np.var(signal-design@coeff)/np.var(signal))
        per_date.append(result)
    passed = [d for d in per_date if "rank_overlap" in d]
    overlap = pd.DataFrame([d["rank_overlap"] for d in passed]).mean().to_dict()
    fraction = float(np.median([d["residual_fraction"] for d in passed])) if passed else None
    contract_rows = json.loads((ROOT/"runtime/task13_b1/contract_events.json").read_text())
    result = {"plan_sha":digest(plan),"code_sha":digest(Path(__file__)),"inputs":inputs,
              "quarterly_pilot":per_date,"passing_dates":len(passed),"passing_issuers":len(passing_names),
              "mean_rank_overlap":overlap,"median_residual_rank_variance_fraction":fraction,
              "observed_schedule_mask_ceiling":{str(d.date()):ceiling[str(d.date())] for d in schedule},
              "dates_ceiling_ge50":sum(n>=50 for n in ceiling.values()),
              "provider_exchange_counts":dict(identities),"historical_identity":"R0 surviving issuers, native lower bounds and primary masks retained. No complete historical ticker/listing/action tape or PIT cross-listing guarantee.",
              "B1_contract_file_sha":digest(ROOT/"runtime/task13_b1/contract_events.json"),
              "B1_contract_counts":{k:len(v) for k,v in contract_rows.items() if isinstance(v,list)},
              "feature_gate":bool(len(passed)>=12 and len(passing_names)>=50 and overlap and max(map(abs,overlap.values()))<.90 and fraction>=.10),
              "CPU_seconds":time.process_time()-start,"wire_requests":0,"new_H20_values":0}
    (OUT/"precheck.json").write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    print({k:v for k,v in result.items() if k not in {"inputs","quarterly_pilot","observed_schedule_mask_ceiling"}})


if __name__=="__main__":
    main()
