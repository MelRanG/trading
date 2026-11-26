"""Read frozen evidence and check comparison coverage. No evaluator or network calls."""
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
from statistics import mean
import time

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "runtime/task13_e2"
SOURCES = {}


def load(path, *, table=False):
    raw = (ROOT/path).read_bytes()
    SOURCES[path] = hashlib.sha256(raw).hexdigest()
    if table:
        return list(csv.DictReader(raw.decode("utf-8-sig").splitlines()))
    return json.loads(raw)


def selection_history():
    endpoint = load("runtime/task9_1/evaluation_endpoint/portfolios.json")
    marks = load("runtime/task9_1/evaluation_endpoint/price_events.json")
    result = []
    subjects = []
    for date in ("2024-11-29","2025-06-30"):
        arms = load(f"runtime/task9_1/evaluation_v3/{date}.json")
        stock = load(f"runtime/task9_1/evaluation_v3/{date}_stock.json")
        model = load(f"runtime/task9_1/decisions/{date}_market.json")["decision"]
        for market in ("US","KR"):
            screen = load(f"runtime/task9_1/screens/{date}/{market}.json")["deep"]
            ranked = sorted(screen,key=lambda x:(-x["momentum63"],x["symbol"]))
            portfolio = next(p for p in model["portfolios"] if p["market"]==market)
            selected = set(portfolio["ranked_top3"])
            names = {x["symbol"] for x in screen}
            assert selected <= names
            available = endpoint if market=="KR" else arms
            for horizon in [3,6,12]:
                cells = {x["arm"]:x for x in available if x["date"]==date and x["market"]==market and x["months"]==horizon}
                q, fused = [cells[k] for k in ("SELECT_QUANT_RANK100","SELECT_INTEGRATED_RANK_FUSION")]
                assert set(q["positions"]) == {x["symbol"] for x in ranked[:3]}
                assert q["entry"]==fused["entry"] and q["exit"]==fused["exit"]
                assert abs(sum(q["positions"].values())-1)<1e-10 and abs(sum(fused["positions"].values())-1)<1e-10
                returns = {r["symbol"]:r["price_return"] for r in stock if r["market"]==market and r["months"]==horizon}
                if market=="KR":
                    # Existing corroborated endpoint facts, no outcome fetch or replay.
                    returns = {r["symbol"]:r["exit_open"]/r["entry_open"]-1 for r in marks
                               if r["date"]==date and r["months"]==horizon and r["entry"]==q["entry"]
                               and r["exit"]==q["exit"] and r["no_split_declared"]}
                for place,row in enumerate(ranked,1):
                    symbol=row["symbol"]
                    subjects.append({"date":date,"market":market,"months":horizon,"symbol":symbol,
                        "research_group":"TEAM2_TOP3" if symbol in selected else "OUTSIDE_TOP3_NO_VETO_INFERRED",
                        "MOM63_rank_in_deep":place,"MOM63":row["momentum63"],"vol63":row.get("vol63"),
                        "sector_from_screen":row.get("sector"),"price_at_screen":row.get("last_close"),
                        "gross_price_return":returns.get(symbol),
                        "fusion_selected":symbol in fused["positions"]})
                groups = {}
                for key,group in [("top3",selected),("other_deep",names-selected)]:
                    out=[returns[s] for s in sorted(group) if s in returns]
                    groups[key]={"n":len(group),"mature_observed":len(out),
                                 "gross_mean":mean(out) if len(out)==len(group) and out else None}
                result.append({"date":date,"market":market,"months":horizon,"entry":q["entry"],"exit":q["exit"],
                    "rank_only_net":q.get("net_price_return"),"fusion_net":fused.get("net_price_return"),
                    "changed_selection":set(q["positions"])!=set(fused["positions"]),
                    "team2_rank_comparison":groups,"quality":fused["quality"]})
    return result,subjects


def coverage():
    comparisons={}
    outcomes=load("runtime/task9_4/evaluation_v2/asset_returns.json")
    for market in ("US","KR"):
        screen=load(f"runtime/task9_3/screens/{market}.json")
        study=load(f"runtime/task9_3/decisions/{market}/2026-05-15.json")
        seal=load(f"runtime/task9_3/seals/{market}/2026-05-15.json")
        assert study["input_hash"]==seal["packet_hash"]
        discovery=load(f"runtime/task9_4/research/{market}.json")
        selected={x["symbol"] for x in discovery["selected"]}
        outside={x["symbol"] for x in discovery["not_selected"]}
        valid={x["symbol"] for x in outcomes if x["market_context"]==market and x["horizon"]=="6m" and x.get("price_return") is not None}
        comparisons[market]={"task93_screen":len(screen),"task93_deep":len(study["cases"]),
            "task94_recommend":len(selected),"task94_other":len(outside),
            "deep_intersection":sorted({x["symbol"] for x in study["cases"]}&(selected|outside)),
            "mature_recommend":sorted(selected&valid),"mature_other":sorted(outside&valid),
            "other_status_counts":dict(Counter(x["status"] for x in discovery["not_selected"])),
            "task93_cash_weight_at_initial":study["cash_weight"]}
    return comparisons


def information():
    flow=load("data/historical_investor_flow/market_investor_flow_daily.csv",table=True)
    dart=load("data/opendart_quarterly_pit.csv",table=True)
    macro=load("runtime/task13_b1/macro_normalized.json")
    macro93={}
    for market in ("US","KR"):
        rows=[load(str(p.relative_to(ROOT))) for p in sorted((ROOT/f"runtime/task9_3/macro/{market}").glob("*.json"))]
        macro93[market]=sorted({r["published"] for r in rows if r.get("status")=="SAVED" and r.get("published")})
    return {"flow":{"rows":len(flow),"market_counts":dict(Counter(r["market"] for r in flow)),
            "date_span":[min(r["as_of_date"] for r in flow),max(r["as_of_date"] for r in flow)],
            "status":dict(Counter(r["data_status"] for r in flow)),
            "historical_publication_field_present":any(k in flow[0] for k in ["received_at","published_at","available_at"]),
            "canonical_krx_present":(ROOT/"data/krx_market_flow_pack_v1/canonical/krx_market_flow_pack_v1.csv").exists()},
            "DART":{"rows":len(dart),"tickers":len({r["ticker"] for r in dart}),
                    "date_span":[min(r["received_at"] for r in dart),max(r["received_at"] for r in dart)]},
            "macro_B1":[{k:r[k] for k in ("kind","PIT","public_date","finite") if k in r} for r in macro],
            "macro_task93_dates_deduped":macro93,"prior_V102":load("reports/v102_market_evidence_agent/v102_candidate_promotion.csv",table=True)}


def main():
    start=time.process_time()
    selection,subjects=selection_history()
    paired=coverage()
    info=information()
    task10=load("runtime/task10/evaluation/summary.json")
    regime=load("runtime/task10/evaluation/regimes.json")
    for path in ["runtime/task9_3/evaluation/US/results.json","runtime/task9_3/evaluation/KR/results.json",
                 "runtime/task9_4/research_seal.json","runtime/task9_4/evaluation_v2/task93_descriptive_comparison.json",
                 "runtime/task9_3/valuation_arithmetic_audit.json","runtime/task9_2/limited_historical_audit/result.json",
                 "runtime/task10_1/forward/registration.json","runtime/task13_d1/execution.json",
                 "runtime/task13_b3_repair/result_summary.json","runtime/task13_c4_repair/r2_verification.json",
                 "runtime/task14/verdict.json"]:
        load(path)
    output={"Q1":"TEAM2_COMPARISON_INCONCLUSIVE","paired_policy":"PAIRED_COMPARISON_NOT_AVAILABLE",
            "historical_selection":"EXPLORATORY_ONLY","Q2":"NOT_EVALUABLE",
            "selection_arms":selection,"individual_coverage":subjects,"task93_94_coverage":paired,
            "information_readiness":info,"team3_task10":task10,"observed_regime_diagnostic":regime,
            "E1_named_artifacts":[str(p.relative_to(ROOT)) for area in ("docs/development","runtime","experiments")
                                   for p in sorted((ROOT/area).glob("*")) if "13_e1" in p.name.lower()],
            "sources":SOURCES,"audit_cpu_seconds":time.process_time()-start,
            "new_return_labels":0,"new_information_evaluations":0,"new_replays":0,"HTTP":0,"research_LLM_calls":0}
    target=OUT/"audit.json"
    with target.open("x") as handle:
        json.dump(output,handle,indent=2,allow_nan=False)
    print(len(selection),"stored arm pairs,",len(subjects),"existing candidate-window rows,",len(SOURCES),"source hashes")


if __name__=="__main__":
    main()
