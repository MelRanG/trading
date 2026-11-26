"""One preregistered H20 prediction test, independent of execution paths."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

import numpy as np
import pandas as pd

from experiments.task13_h1.prepare_inputs import OUT as H1, ROOT, sha, write_json
from experiments.task14.stats_eval import block_mean, corr, holm

HERE = Path(__file__).resolve().parent
OUT = ROOT / "runtime/task13_conditional_distance"
MARKETS = ("US", "KR")
STATES = {"UP": 1, "REBOUND": 1, "DOWN": -1, "CRASH": -1, "SIDEWAYS": 0, "TRANSITION": 0}
BASE = ["REV5", "MOM20", "MOM63", "D", "T", "VOL20", "H1"]
COLUMNS = BASE + ["D_squared", "interaction"]
FIRST = {"fit": "2023-04-03", "eval": "2024-01-01"}
LAST = {"fit": "2023-12-31", "eval": "2024-12-31"}


def features(close):
    logs = np.log(close)
    ret = logs.diff()
    vol = ret.rolling(20).std(ddof=0)
    distance = np.log(close / close.rolling(20).mean()) / (np.sqrt(20) * vol.where(vol.gt(0)))
    path = ret.abs().rolling(63).sum().shift(20)
    trend = (logs.shift(20) - logs.shift(83)) / path.where(path.gt(0))
    return {
        "REV5": 1 - close / close.shift(5),
        "MOM20": close / close.shift(20) - 1,
        "MOM63": close / close.shift(63) - 1,
        "D": distance,
        "T": trend,
        "VOL20": vol,
    }


def data(market):
    with np.load(H1 / f"{market}_panel.npz") as panel, np.load(H1 / f"{market}_features.npz") as old:
        dates = pd.DatetimeIndex(panel["dates"])
        names = panel["symbols"]
        op, close = (pd.DataFrame(panel[key], index=dates, columns=names) for key in ["open", "close"])
        state = pd.Series(panel["regime"], index=dates)
        h1 = pd.DataFrame(old["score"], index=dates, columns=names)
    assert dates.is_unique and dates.is_monotonic_increasing and close.columns.is_unique
    raw = features(close)
    cut = len(dates) // 2
    prefix = features(close.iloc[:cut])
    perturbed = close.copy()
    perturbed.iloc[cut:] *= 1 + np.arange(len(close) - cut)[:, None] / len(close)
    amended = features(perturbed)
    for name in raw:
        pd.testing.assert_frame_equal(raw[name].iloc[:cut], prefix[name])
        pd.testing.assert_frame_equal(raw[name].iloc[:cut], amended[name].iloc[:cut])
    raw["H1"] = h1
    asof = state.map(STATES)
    valid = close.notna().rolling(84).sum().eq(84)
    for frame in raw.values():
        valid &= np.isfinite(frame)
    valid.loc[asof.isna()] = False
    ranked = {k: f.where(valid).rank(axis=1, pct=True) for k, f in raw.items()}
    centered = {k: f.sub(f.mean(axis=1), axis=0) for k, f in ranked.items()}
    centered["D_squared"] = centered["D"] ** 2
    centered["interaction"] = centered["D"] * raw["T"].add(asof, axis=0) / 2
    label_ready = valid.copy()
    good_open = np.isfinite(op) & op.gt(0)
    for lag in range(1, 22):
        label_ready &= good_open.shift(-lag, fill_value=False)
    exit_date = dates.to_series().shift(-21)
    pairs = {}
    calendars = {}
    for key in FIRST:
        end_valid = exit_date.lt("2024-01-01") if key == "fit" else exit_date.le(LAST[key])
        calendar = dates[(dates >= FIRST[key]) & (dates <= LAST[key]) & end_valid]
        calendar_mask = label_ready.loc[calendar]
        pairs[key] = calendar_mask.loc[calendar_mask.sum(axis=1).ge(50)]
        calendars[key] = calendar
    return op, raw, centered, ranked, state, pairs, calendars


def verified_inputs():
    receipt = json.loads((H1 / "input_receipt.json").read_bytes())
    gate = json.loads((H1 / "feature_gate.json").read_bytes())
    assert sha(H1 / "input_receipt.json") == gate["inputs_sha256"]
    paths = [H1 / n for n in ("input_receipt.json", "feature_gate.json", "research_contract.json")]
    assert sha(paths[-1]) == gate["contract_sha256"]
    for market in MARKETS:
        panel = H1 / f"{market}_panel.npz"
        derived = H1 / f"{market}_features.npz"
        assert sha(panel) == receipt["checks"][market]["panel_sha256"]
        assert sha(derived) == gate["members"][market]["sha256"]
        paths.extend([panel, derived])
    paths.extend([HERE / "contract.json", Path(__file__).resolve(),
                  ROOT / "experiments/task14/stats_eval.py", ROOT / "experiments/task13_h1/prepare_inputs.py"])
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in paths}


def snapshot(datasets, fingerprints):
    notes = {}
    for market, (_, _, _, _, states, pairs, _) in datasets.items():
        notes[market] = {}
        for key, mask in pairs.items():
            notes[market][key] = {
                "days": len(mask), "rows": int(mask.sum().sum()), "names": int(mask.any().sum()),
                "first": str(mask.index.min().date()), "last": str(mask.index.max().date()),
                "states": states.reindex(mask.index).value_counts().to_dict(),
                "mask_sha256": sha256(
                    pd.util.hash_pandas_object(mask, index=True).to_numpy().tobytes()
                ).hexdigest(),
            }
    ready = all(v["fit"]["days"] >= 80 and v["eval"]["days"] >= 100 for v in notes.values())
    return {"hashes": fingerprints, "markets": notes, "eligible": ready, "future_returns_computed": False}


def day_sample(dt, mask, design, labels):
    names = mask.index[mask]
    x = np.column_stack([design[k].loc[dt, names].to_numpy() for k in COLUMNS])
    y = labels.loc[dt, names]
    rank_y = y.rank(pct=True)
    return x - x.mean(axis=0), rank_y.to_numpy() - rank_y.mean(), y


def fit(mask, design, labels):
    rows, response = [], []
    for day, members in mask.iterrows():
        x, y, _ = day_sample(day, members, design, labels)
        w = np.sqrt(len(x))
        rows.append(x / w)
        response.append(y / w)
    X, Y = np.concatenate(rows), np.concatenate(response)
    base, _, r0, _ = np.linalg.lstsq(X[:, :-1], Y, rcond=None)
    full, _, r1, _ = np.linalg.lstsq(X, Y, rcond=None)
    assert r0 == len(base) and r1 == len(full)
    return base, full


def tail(score, actual):
    q = len(actual) // 5
    rank = pd.Series(score, index=actual.index)
    top = actual[rank.rank(ascending=False) <= q]
    bottom = actual[rank.rank() <= q]
    return float(top.mean()), float(top.mean() - bottom.mean())


def market_test(market, dataset):
    op, raw, design, ranks, state, pairs, calendars = dataset
    labels = op.shift(-21) / op.shift(-1) - 1
    base, full = fit(pairs["fit"], design, labels)
    records, group_records = [], []
    contributions = pd.Series(0., index=op.columns)
    for dt, mask in pairs["eval"].iterrows():
        x, y, actual = day_sample(dt, mask, design, labels)
        a, b = x[:, :-1] @ base, x @ full
        rec = {"date": dt, "state": state.at[dt], "names": len(y), "mean_H20": actual.mean()}
        scores = {k: ranks[k].loc[dt, actual.index].to_numpy() for k in BASE}
        scores.update(additive=a, conditional=b)
        for k, score in scores.items():
            rec[k + "_RankIC"] = corr(score, y, rank=True)
            rec[k + "_top"], rec[k + "_spread"] = tail(score, actual)
        rec["delta"] = rec["conditional_RankIC"] - rec["additive_RankIC"]
        rec["top_lift"] = rec["conditional_top"] - rec["additive_top"]
        contributions.loc[actual.index] += ((a-y)**2 - (b-y)**2) / len(y) / len(pairs["eval"])
        d = ranks["D"].loc[dt, actual.index]
        positive = raw["T"].loc[dt, actual.index].gt(0)
        for sign, trend in [("positive", positive), ("nonpositive", ~positive)]:
            for band, side in [("low", d.le(.2)), ("high", d.gt(.8))]:
                group = actual[trend & side]
                if len(group):
                    group_records.append((dt, rec["state"], sign, band, len(group), group.mean(), group.median()))
        records.append(rec)
    daily = pd.DataFrame(records).set_index("date")
    daily.to_csv(OUT / f"{market}_daily.csv")
    groups = pd.DataFrame(group_records, columns=["date", "state", "trend", "band", "names", "mean_H20", "median_H20"])
    groups.to_csv(OUT / f"{market}_state_tails.csv", index=False)
    uncertainty = block_mean(daily.delta.reindex(calendars["eval"]), 42, samples=5000, seed=131420)
    order = contributions.abs().sort_values(ascending=False).index
    contributions.loc[order].rename("rank_MSE_lift").to_csv(OUT / f"{market}_name_contributions.csv")
    halves = daily.groupby(np.where(daily.index.month <= 6, "H1", "H2")).delta.mean()
    states = daily.groupby("state")[["delta", "mean_H20", "top_lift"]].agg(["count", "mean"])
    return {
        "primary": uncertainty,
        "base_coefficients": dict(zip(COLUMNS[:-1], base)),
        "conditional_coefficients": dict(zip(COLUMNS, full)),
        "baseline_stats": daily.filter(regex=r"_(RankIC|top|spread)$").mean().to_dict(),
        "distance_MOM20_avg_corr": float(np.mean([
            corr(ranks["D"].loc[dt, m], ranks["MOM20"].loc[dt, m], rank=True)
            for dt, m in pairs["eval"].iterrows()
        ])),
        "half_delta": halves.to_dict(), "state_summary": json.loads(states.to_json(orient="split")),
        "top_lift": float(daily.top_lift.mean()),
        "MSE_lift": float(contributions.sum()),
        "MSE_lift_excluding_largest_five_contributions": float(contributions.loc[order[5:]].sum()),
        "largest_5_absolute_name_contributions": contributions.loc[order[:5]].to_dict(),
    }


def classify(result, adjusted):
    stats = result["primary"]
    result["holm_two_markets"] = adjusted
    result["bonferroni45_lower_bound_evidence_scope"] = min(1., 45 * stats["p_positive"])
    candidate = (result["conditional_coefficients"]["interaction"] > 0 and
                 len(result["half_delta"]) == 2 and min(result["half_delta"].values()) > 0 and
                 stats["CI95"][0] > 0 and adjusted < .05 and
                 result["bonferroni45_lower_bound_evidence_scope"] < .05 and result["top_lift"] > 0 and
                 result["MSE_lift_excluding_largest_five_contributions"] > 0)
    if candidate:
        return "INCREMENTAL_SIGNAL_CANDIDATE"
    if stats["mean"] <= 0 and result["top_lift"] <= 0:
        return "NO_INCREMENTAL_SIGNAL"
    return "INCONCLUSIVE"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["seal", "evaluate"])
    phase = parser.parse_args().phase
    if phase == "evaluate" and (OUT / "reservation.json").exists():
        raise SystemExit("Label evaluation already reserved")
    fingerprints = verified_inputs()
    datasets = {m: data(m) for m in MARKETS}
    snap = snapshot(datasets, fingerprints)
    if phase == "seal":
        write_json(OUT / "seal.json", {"utc": datetime.now(timezone.utc).isoformat(), **snap})
        print(json.dumps(snap["markets"], indent=2))
        return
    sealed = json.loads((OUT / "seal.json").read_bytes())
    assert all(sealed[k] == v for k, v in snap.items())
    if not sealed["eligible"]:
        raise SystemExit("DATA_BLOCKED: preregistered sample minimum")
    write_json(OUT / "reservation.json", {"utc": datetime.now(timezone.utc).isoformat(),
               "seal_sha256": sha(OUT / "seal.json"), "max_evaluation_runs": 1})
    results = {m: market_test(m, datasets[m]) for m in MARKETS}
    adjusted = holm([results[m]["primary"]["p_positive"] for m in MARKETS])
    for m, p in zip(MARKETS, adjusted):
        results[m]["decision"] = classify(results[m], p)
    individual = {r["decision"] for r in results.values()}
    overall = next((d for d in ("INCREMENTAL_SIGNAL_CANDIDATE", "INCONCLUSIVE", "NO_INCREMENTAL_SIGNAL")
                    if d in individual))
    write_json(OUT / "result.json", {"decision": overall, "markets": results,
               "alpha": "ALPHA_NOT_VALIDATED", "portfolio_runs": 0, "task15": "GATED"})
    print({m: (r["decision"], r["primary"]) for m, r in results.items()})


if __name__ == "__main__":
    main()
