"""Adapt existing sources into a common packet for both arms."""
from datetime import datetime, timezone
import json
from pathlib import Path

from experiments.research_references import source
from quant_harness.investment.research_feedback_dispatch import file_hash

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "runtime/task16_b"
NOW = datetime.now(timezone.utc).isoformat()
HERE = Path(__file__).resolve().parent


def pointer(path):
    f = source(ROOT, path)
    return {"path": f.relative_to(ROOT).as_posix(), "sha256": file_hash(f)}


def read(path):
    p = pointer(path)
    return json.loads((ROOT / p["path"]).read_text())


def evidence(path, summary, identity="E"):
    p = pointer(path)
    return dict(id=identity, source=p["path"], source_hash=p["sha256"], summary=summary,
                stage="RESEARCH_OUTCOME", available_at=NOW)


def packet(identity, kind, family, baseline, facts, *, data="ELIGIBLE", ledger=False, metrics=None,
           details=None, diagnostic=None):
    obj = dict(case_id=identity, kind=kind, family=family, mechanism=family, baseline=baseline,
               decision_as_of="2024-01-01T00:00:00Z", evaluation_as_of=NOW, evidence_class="EXPOSED_HISTORICAL_RESEARCH",
               gates=dict(data=data, mature=True, matched_ledger=ledger, approval="NOT_APPROVED", split="EXPOSED"),
               metrics=metrics or {}, facts=details or {}, evidence=facts,
               reevaluation="Reopen only with new dated evidence and preregistered independent comparison; keep current risk/approval.",
               budget={"diagnostics":1,"strategy_trials":0}, attempts="SEE_PARENT_LEDGER")
    if diagnostic:
        obj["diagnostic"] = diagnostic
    return obj


def memory():
    rows = [
        ("MOM63", "LIMITED", "runtime/task13_f1_r6/result.json", "Survivor optimism; PIT entry cohorts only, zero valid portfolio runs"),
        ("FLOW5", "REJECT", "runtime/task13_f1_r4/result.json", "Only the fixed 50:50 overlay lacks economic increment"),
        ("QUANTA_Q0", "LIMITED", "runtime/task13_h1/prior/task14/verdict.json", "Tested liquidity-weighted reversal comparisons did not support promotion"),
        ("QUANTA_Q1", "REJECT", "runtime/task13_h1/prior/task14/verdict.json", "Tested volume-confirmed momentum overlaps MOM20"),
        ("RD_SMALL", "REJECT", "runtime/task13_h1/prior/task14/verdict.json", "Tested model did not earn a Task15 recommendation"),
        ("H1", "REJECT", "runtime/task13_h1/result.json", "Tested range-location relative-volume correlation lacked increment"),
        ("R1_BUFFER", "REJECT", "runtime/task13_r1_st_preflight/result.json", "Top-K buffer loses to low-turnover control"),
        ("ST", "BLOCKED", "docs/development/13_R1_ST_preflight.md", "Definition and data blocked"),
        ("PTH_TO", "BLOCKED", "runtime/task13_pth_to_exploratory/quality.json", "Sparse month coverage and definition data blocked"),
        ("MA20_CONDITIONAL", "LIMITED", "runtime/task13_conditional_distance/result.json", "US inconclusive; KR negative increment"),
        ("EPS_YOY", "LIMITED", "runtime/task13_earnings_strength/result.json", "US inconclusive; KR time and coverage blocked"),
    ]
    return [dict(family=k,status=v,source=e["source"],source_hash=e["source_hash"],available_at=e["available_at"],
                 scope=e["summary"]) for k,v,p,n in rows for e in [evidence(p,n)]]


def metric(value, interval=None):
    return {"value":value,"evidence_id":"E", **(dict(zip(("lo","hi"),interval)) if interval else {})}


def historical():
    cases = []
    ma = "runtime/task13_conditional_distance/result.json"
    for market, m in read(ma)["markets"].items():
        primary = m["primary"]
        cases.append(packet("MA20_"+market,"SIGNAL","MA20_CONDITIONAL","Additive price model",
            [evidence(ma,f"{m['decision']}; delta={primary['mean']}, CI={primary['CI95']}, halves={m['half_delta']}, n={primary['n']}, tops={m['top_lift']}")],
            metrics={"increment":metric(primary["mean"],primary["CI95"]),"overlap":metric(m["distance_MOM20_avg_corr"]) }))
    eps = "runtime/task13_earnings_strength/result.json"
    u = read(eps)["US"]
    cases.append(packet("EPS_US","SIGNAL","EPS_YOY","Price-only and RS63",
        [evidence(eps,f"Delta {u['delta_spearman']}; CI {u['primary']['CI95']}; halves {u['half_year_delta']}; EPS-RS overlap {u['EPS_overlap']['RS63']}; upper lift {u['top_quintile_lift']}."),
         evidence("runtime/task13_earnings_strength/independent_result_audit.json","Nine upper cases, eight shared; one replacement accounts for total lift.","CONC")],
        details={"concentration":"CONC"},metrics={"increment":metric(u["delta_spearman"],u["primary"]["CI95"]),
                    "overlap":metric(u["EPS_overlap"]["RS63"])}))
    cases.append(packet("EPS_KR","SIGNAL","EPS_YOY","Price-only",
                    [evidence(eps,"KR DATA_BLOCKED; no timed panel")],data="BLOCKED"))
    pth = "runtime/task13_pth_to_exploratory/quality.json"
    q = read(pth)
    cases.append(packet("PTH_BLOCK","SOURCE","PTH_TO","MOM63+PTH-only",
                    [evidence(pth,f"{q['decision']}; qualifying months {q['qualifying_months']}, requirement {q['min_months']}; returns unopened")],
                    data="BLOCKED"))
    r1 = "runtime/task13_r1_st_preflight/result.json"
    r = read(r1)
    a,b,c = (r[k]["total_pct"] for k in ("1x_D","1x_R1","1x_LOW_TURNOVER"))
    cases.append(packet("R1","POLICY","R1_BUFFER","Baseline and lower-turnover control",
                    [evidence(r1,f"Matched replay: D {a:.2f}%, R1 {b:.2f}%, low-turnover {c:.2f}%.")],
                    ledger=True,metrics={"net_vs_best_control":metric(b-c)}))
    m = "runtime/task13_f1_r6/result.json"
    cases.append(packet("MOM63","SIGNAL","MOM63","ETF / exposure controls",
                    [evidence(m,"Positive historical survivor result; R6 independent PIT evaluation failed data gates, zero eligible runs.")],data="BLOCKED"))
    op = "runtime/task13_opportunity_diagnostic/result.json"
    r = read(op)
    loss = [r[k]["regime_ON_cash_only_breakdown_krw"]["STRONG_UP"]["on_empty_target_slots"] for k in ("R4","R5")]
    cases.append(packet("VACANT_SLOT","POLICY","MOM63_CASH_DRAG_DIAGNOSTIC","Fixed MOM63 80% cap",
         [evidence(op,f"Two exposed replays: strong-up empty slots attributed KRW {loss}; completed overall reentries 22 with zero session delays; this is attribution, no policy A/B."),
          evidence(m,"True point-in-time cohort and approved independent data still needed.","PIT")],
         diagnostic={"route":"PIT_EXPOSURE_FEASIBILITY","family":"VACANT_TARGET_SLOT_ETF_PIT_CHECK","evidence_ids":["E","PIT"]}))
    return cases


def synthetic():
    config = HERE / "evaluation.json"
    cases, expected, extra = [], {}, {}
    for row in json.loads(config.read_text())["cases"]:
        ident = row["id"]
        c = packet(ident,row["kind"],"SEALED_"+ident,"Frozen control",
                   [evidence(config.relative_to(ROOT).as_posix(),row["scenario"])],
                   details=row.get("facts",{}))
        c["gates"].update(row.get("gates",{}))
        if row.get("metric"):
            name,value,lo,hi = row["metric"]
            c["metrics"] = {name:metric(value,[lo,hi])}
        if row.get("route"):
            c["diagnostic"] = dict(route=row["route"],family="SYNTHETIC_"+ident,evidence_ids=["E"])
        if row.get("prior"):
            extra[ident] = [dict(family=c["family"],status=row["prior"],source_hash=c["evidence"][0]["source_hash"],available_at=NOW)]
        cases.append(c)
        expected[ident] = row["expected"]
    return cases, expected, extra
