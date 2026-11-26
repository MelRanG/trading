"""Single-market event research with sealed timestamp, masks and H20 splits."""
import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
from io import BytesIO
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from experiments.task13_earnings_strength.source import (
    ARCHIVE, BENCH, DART, archived, eps_pairs, exhibit, submission_records,
)
from experiments.task13_h1.prepare_inputs import OUT as H1, ROOT, sha, write_json
from experiments.task14.stats_eval import corr

HERE = Path(__file__).resolve().parent
OUT = ROOT / "runtime/task13_earnings_strength"
SPLIT = pd.Timestamp("2024-01-01")
END = pd.Timestamp("2024-12-31")
NY = ZoneInfo("America/New_York")
CONTROLS = ["MOM20", "RS63", "REV5", "VOL20", "REACTION"]
PLAN = HERE / "contract.json"


def price_frames(storage):
    receipt = json.loads((H1 / "input_receipt.json").read_bytes())
    gate = json.loads((H1 / "feature_gate.json").read_bytes())
    assert sha(H1 / "input_receipt.json") == gate["inputs_sha256"]
    p = H1 / "US_panel.npz"
    assert sha(p) == receipt["checks"]["US"]["panel_sha256"]
    with np.load(p) as data:
        dates = pd.DatetimeIndex(data["dates"])
        symbols = data["symbols"]
        close, op = (pd.DataFrame(data[k], index=dates, columns=symbols) for k in ("close", "open"))
    assert dates.is_unique and dates.is_monotonic_increasing and close.columns.is_unique
    def get(k):
        return pd.read_csv(BytesIO(storage[BENCH + k + ".csv"]), index_col="date", parse_dates=True).reindex(dates)
    index = get("quote")[["open", "close"]]
    valid = get("quality_mask")
    assert "eligible" in valid
    index = index.where(valid["eligible"].eq(True), axis=0)
    return close, op, index


def clock(event, rec, dates):
    f = event["filing"]
    a = rec.get(f["accessionNumber"], {})
    keys = ["accessionNumber", "form", "reportDate", "filingDate", "acceptanceDateTime", "primaryDocument", "items"]
    if not all(a.get(k) == f.get(k) for k in keys) or f["form"] != "8-K" or "2.02" not in f["items"].split(","):
        return None
    accepted = datetime.fromisoformat(f["acceptanceDateTime"])
    if accepted.tzinfo is None:
        return None
    local = accepted.astimezone(NY)
    if local.date().isoformat() != f["reportDate"]:
        return None
    day = pd.Timestamp(local.date())
    if day < dates[0]:
        return None
    decision = dates.searchsorted(day, side="right")
    entry, target = decision + 1, decision + 21
    if target >= len(dates) or dates[target] > END or dates[decision] < SPLIT <= dates[target]:
        return None
    cutoff = datetime.combine(dates[decision].date() + timedelta(days=1), datetime.min.time(), NY)
    # Fail closed on amendments dated through the decision session, including after-close updates before the order.
    for other in rec.values():
        if other.get("form") != "8-K/A" or other.get("reportDate") != f["reportDate"]:
            continue
        if not other.get("acceptanceDateTime"):
            return None
        amended = datetime.fromisoformat(other["acceptanceDateTime"])
        if amended.tzinfo is None or accepted < amended < cutoff:
            return None
    return f, accepted, day, decision, entry, target


def event_features(stock, idx, dates, day, decision):
    pre = dates.searchsorted(day, side="left") - 1
    if decision < 63 or pre < 0:
        return None
    a, b = stock.iloc[decision-63:decision+1], idx.iloc[decision-63:decision+1]
    if not (np.isfinite(a).all() and np.isfinite(b).all() and a.gt(0).all() and b.gt(0).all()):
        return None
    ret = lambda window, n: window.iloc[-1] / window.iloc[-1-n] - 1
    v = dict(MOM20=ret(a, 20), MOM63=ret(a, 63), RS63=ret(a, 63)-ret(b, 63),
             REV5=-ret(a, 5), VOL20=a.pct_change(fill_method=None).iloc[-20:].std(),
             REACTION=stock.iloc[decision] / stock.iloc[pre] - idx.iloc[decision] / idx.iloc[pre])
    return {key: float(f) for key, f in v.items()} if np.isfinite(list(v.values())).all() else None


def preflight():
    companies, archive, hashes = archived()
    close, op, index = price_frames(archive)
    dates = close.index
    exclusions, raw_ok = Counter(), Counter()
    result, raw_rows, price_quality = [], [], []
    for symbol, company in sorted(companies.items()):
        rec = submission_records(company, archive)
        last_issuer_end = -1
        seen_periods = set()
        for event in company["targets"]:
            if event["source"]["status"] != "SAVED":
                exclusions["original_document_missing"] += 1
                continue
            raw = exhibit(event, archive)
            if raw is None:
                exclusions["verified_exhibit_missing"] += 1
                continue
            f = event["filing"]
            candidates = eps_pairs(raw, pd.Timestamp(f["reportDate"]).date())
            if len(candidates) != 1:
                exclusions["missing_or_ambiguous_quarter_eps"] += 1
                continue
            (period, prior, reported, comparison), proof = next(iter(candidates.items()))
            a, b = float(reported), float(comparison)
            if period in seen_periods:
                exclusions["prior_same_issuer_quarter_seen"] += 1
                continue
            seen_periods.add(period)
            raw_ok[symbol] += 1
            evidence = dict(symbol=symbol, CIK=company["cik"], accession=f["accessionNumber"],
                            filing_date=f["filingDate"], report_date=f["reportDate"],
                            current_period_end=period, prior_period_end=prior, EPS=a, prior_EPS=b,
                            EPS_YOY=(a-b)/(abs(a)+abs(b)), proof=proof, source_url=event["source"]["url"],
                            source_sha256=event["source"]["source_hash"])
            raw_rows.append(evidence)
            timeline = clock(event, rec, dates)
            if timeline is None:
                exclusions["clock_or_window"] += 1
                continue
            if symbol not in close:
                exclusions["price_identity"] += 1
                continue
            _, accepted, day, decision, first, last = timeline
            features = event_features(close[symbol], index.close, dates, day, decision)
            if features is None:
                exclusions["price_feature_path"] += 1
                continue
            price_quality.append(dict(symbol=symbol, accession=f["accessionNumber"], decision=str(dates[decision].date())))
            valid = pd.concat([op[symbol].iloc[first:last+1], index.open.iloc[first:last+1]], axis=1)
            if len(valid)!=21 or not (np.isfinite(valid).all().all() and valid.gt(0).all().all()):
                exclusions["price_h20_path"] += 1
                continue
            if first <= last_issuer_end:
                exclusions["overlap_with_same_issuer"] += 1
                continue
            last_issuer_end = last
            result.append(dict(**evidence, **features, acceptance_utc=accepted.isoformat(),
                               decision=str(dates[decision].date()), entry=str(dates[first].date()),
                               exit=str(dates[last].date()), split="fit" if dates[decision] < SPLIT else "eval"))
    metrics = {}
    for group in ("fit", "eval"):
        subset = [r for r in result if r["split"] == group]
        metrics[group] = dict(rows=len(subset), issuers=len({r["CIK"] for r in subset}),
                              positive=sum(r["EPS_YOY"] > 0 for r in subset),
                              negative=sum(r["EPS_YOY"] < 0 for r in subset),
                              clusters=sorted({f"{r['decision'][:4]}-{(int(r['decision'][5:7])-1)//2+1}" for r in subset}))
    ready = (all(r["rows"] >= 30 and r["issuers"] >= 12 and min(r["positive"], r["negative"]) >= 8
                 for r in metrics.values()) and len(metrics["eval"]["clusters"]) >= 5)
    kr = archive[DART[0]]
    metrics.update(eligible=ready, archive_targets=sum(len(c["targets"]) for c in companies.values()),
                   saved_eps=len(raw_rows), eps_issuers=len(raw_ok), by_issuer=raw_ok,
                   exclusions=exclusions, prices_with_features=len(price_quality), labels_computed=False)
    inputs = {p.relative_to(ROOT).as_posix(): sha(p) for p in [ARCHIVE, PLAN, Path(__file__).resolve(),
              HERE/"source.py", H1/"US_panel.npz", H1/"input_receipt.json", H1/"feature_gate.json",
              ROOT/"experiments/task14/stats_eval.py"]}
    return archive, close, op, index, result, raw_rows, {
        "US": metrics, "KR": {"eligible": False, "status": "DATA_BLOCKED",
                               "B0_KR_reported_numeric_events": sum(str(r.get("symbol", "")).split(".")[0].isdigit() and
                               r.get("revenue_YoY") is not None for r in archive[DART[1]]["earnings"]),
                               "B0_combined_US_KR_reported_numeric_events": kr["numeric_earnings_events"],
                               "B1_DART_collections": len(archive[DART[2]]),
                               "reason": "B0 four audited date-level Korean financial releases from two issuers without a comparable timed EPS panel. No qualified consensus snapshots."},
        "manifest": hashes, "input_sha256": inputs,
    }


def percentiles(series):
    """Fixed-fit percentile transform for concentration diagnostics."""
    ref = np.sort(series)
    return lambda vals: (np.searchsorted(ref, vals, side="left") + np.searchsorted(ref, vals, side="right")) / (2*len(ref))


def inference(data):
    rng = np.random.default_rng(132041)
    group = pd.factorize(data["block"], sort=True)[0]
    names = pd.factorize(data["CIK"], sort=True)[0]
    n, t = max(names)+1, max(group)+1
    vals = data[["price_only", "additive", "y"]].to_numpy()
    draws = []
    for _ in range(5000):
        a = np.bincount(rng.integers(n, size=n), minlength=n)
        b = np.bincount(rng.integers(t, size=t), minlength=t)
        sample = np.repeat(vals, a[names]*b[group], axis=0)
        if len(sample) >= 15:
            pr, add, target = sample.T
            draws.append(corr(add, target, rank=True) - corr(pr, target, rank=True))
    valid = np.asarray(draws)
    valid = valid[np.isfinite(valid)]
    return dict(CI95=np.quantile(valid, [.025, .975]).tolist(), valid_draws=len(valid),
                issuer_clusters=int(n), bimonthly_clusters=int(t))


def evaluate(rows, op, index):
    data = pd.DataFrame([{k:v for k,v in row.items() if k not in ("proof",)} for row in rows])
    data["y"] = [
        op.at[r.exit, r.symbol]/op.at[r.entry, r.symbol]
        - index.at[r.exit, "open"]/index.at[r.entry, "open"]
        for r in data.itertuples()
    ]
    fit, test = (data.loc[data.split.eq(k)].copy() for k in ("fit", "eval"))
    models = {"price_only": CONTROLS, "additive": CONTROLS+["EPS_YOY"]}
    mse_lift = {}
    coefficients = {}
    for name, values in models.items():
        mean, std = fit[values].mean(), fit[values].std(ddof=0)
        assert std.gt(0).all()
        prepare = lambda df: np.column_stack([np.ones(len(df)), (df[values]-mean)/std])
        beta, _, rank, _ = np.linalg.lstsq(prepare(fit), fit.y, rcond=None)
        assert rank == len(beta)
        coefficients[name] = dict(zip(["intercept", *values], beta))
        fit[name], test[name] = prepare(fit)@beta, prepare(test)@beta
        score = percentiles(fit[name])(test[name])
        truth = percentiles(fit.y)(test.y)
        mse_lift[name] = pd.Series((score-truth)**2, index=test.index)
    metrics = {}
    for name in ("MOM20", "MOM63", "RS63", "EPS_YOY", "REACTION", *models):
        count = len(test)//5
        upper = test[name].rank(ascending=False).le(count)
        lower = test[name].rank().le(count)
        metrics[name] = dict(Spearman=corr(test[name], test.y, rank=True), top_H20=float(test.y[upper].mean()),
                             top_n=int(upper.sum()), bottom_H20=float(test.y[lower].mean()))
    delta = lambda d: corr(d.additive, d.y, rank=True)-corr(d.price_only, d.y, rank=True)
    test["block"] = test.decision.map(lambda x: f"{x[:4]}-{(int(x[5:7])-1)//2+1}")
    halves = {h: float(delta(part)) for h, part in test.groupby(test.decision.str[5:7].astype(int).gt(6).map({True:"H2",False:"H1"}))}
    fit_half_diag = {h: float(delta(part)) for h, part in fit.groupby(fit.decision.str[:4]) if len(part)>=15}
    contrib = (mse_lift["price_only"]-mse_lift["additive"]).groupby(test.symbol).sum()/len(test)
    order = contrib.abs().sort_values(ascending=False).index
    test["rank_loss_improvement"] = mse_lift["price_only"]-mse_lift["additive"]
    top_lift = metrics["additive"]["top_H20"]-metrics["price_only"]["top_H20"]
    eps_overlap = {k: corr(test.EPS_YOY, test[k], rank=True) for k in ("MOM20","MOM63","RS63","REACTION")}
    test.to_csv(OUT/"US_eval_events.csv", index=False)
    fit.to_csv(OUT/"US_fit_events.csv", index=False)
    contrib.loc[order].rename("rank_loss_gain").to_csv(OUT/"US_issuer_contribution.csv")
    stats = inference(test)
    gain = float(delta(test))
    candidate = (coefficients["additive"]["EPS_YOY"] > 0 and stats["CI95"][0] > 0 and len(halves)==2
                 and min(halves.values())>0 and top_lift>0 and contrib.loc[order[5:]].sum()>0)
    decision = ("INCREMENTAL_SIGNAL_CANDIDATE" if candidate else "NO_INCREMENTAL_SIGNAL"
                if gain<=0 and top_lift<=0 else "INCONCLUSIVE")
    return dict(decision=decision, delta_spearman=gain, primary=stats, per_signal=metrics,
                half_year_delta=halves, fit_descriptive_only=fit_half_diag, top_quintile_lift=top_lift, EPS_overlap=eps_overlap,
                coefficients=coefficients, total_rank_loss_gain=float(contrib.sum()),
                rank_loss_gain_excluding_largest_five=float(contrib.loc[order[5:]].sum()),
                largest_five_issuer_rank_loss_gain=contrib.loc[order[:5]].to_dict())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["seal","evaluate"])
    argv = parser.parse_args()
    if argv.phase == "evaluate" and (OUT/"reservation.json").exists():
        raise SystemExit("Already reserved")
    _, _, op, index, rows, raw, manifest = preflight()
    if argv.phase == "seal":
        write_json(OUT/"eps_source_audit.json", raw)
        write_json(OUT/"events.json", rows)
        write_json(OUT/"seal.json", {"utc":datetime.now(timezone.utc).isoformat(), **manifest,
                   "events_sha256":sha(OUT/"events.json"), "source_audit_sha256":sha(OUT/"eps_source_audit.json")})
        print({m: manifest[m] for m in ["US","KR"]})
        return
    seal = json.loads((OUT/"seal.json").read_bytes())
    assert all(seal[k]==v for k,v in manifest.items())
    assert sha(OUT/"events.json")==seal["events_sha256"] and json.loads((OUT/"events.json").read_bytes())==rows
    assert sha(OUT/"eps_source_audit.json")==seal["source_audit_sha256"]
    if not seal["US"]["eligible"]:
        raise SystemExit("DATA_BLOCKED: US and KR sample gates")
    write_json(OUT/"reservation.json", dict(utc=datetime.now(timezone.utc).isoformat(), seal_sha256=sha(OUT/"seal.json")))
    us = evaluate(rows, op, index)
    write_json(OUT/"result.json", dict(alpha="ALPHA_NOT_VALIDATED", US=us,
               KR={"decision":"DATA_BLOCKED"}, portfolio_runs=0, task15="GATED"))
    print(us)


if __name__ == "__main__":
    main()
