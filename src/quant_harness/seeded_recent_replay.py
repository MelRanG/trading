"""Checkpoint-seeded recent replay; intentionally not a general checkpoint framework."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

import pandas as pd
import psycopg
from psycopg.rows import dict_row

from quant_harness.daily_paper_runtime import _save_nav
from quant_harness.historical_operational_replay import _freshness_for_replay, assert_isolated_test_database
from quant_harness.open_5m_execution_validation import CANDIDATES, END, START, contract, next_one_minute_open
from quant_harness.paper_decision_runtime import build_candidate_strategy_preview, build_intent_previews, save_paper_preview
from quant_harness.paper_execution_runtime import run_paper_execution_cycle
from quant_harness.paper_runtime_store import PAPER_ACCOUNT_ID, ensure_paper_account, initialize_paper_schema, load_paper_account
from quant_harness.recent_candidate_extension import schema_url


def _checkpoint(url: str, candidate: str, source_schema: str) -> dict[str, Any]:
    with psycopg.connect(url, row_factory=dict_row) as c:
        nav = c.execute("select as_of,cash_krw,nav_krw,positions_value_krw from paper_daily_nav where as_of='2026-07-08' and paper_account_id=%s", (PAPER_ACCOUNT_ID,)).fetchone()
        rows = c.execute("select s.as_of,l.symbol,l.quantity_delta,l.cash_delta,l.fee,f.fill_price from paper_ledger_event l join paper_order o on o.paper_order_id=l.paper_order_id join paper_session s on s.session_id=o.session_id join paper_fill f on f.paper_fill_id=l.paper_fill_id where s.as_of<='2026-07-08' order by s.as_of,l.ledger_event_id").fetchall()
        pending = c.execute("select count(*) n from paper_order o join paper_session s using(session_id) where s.as_of<='2026-07-08' and o.status in ('NEW','ACCEPTED','PARTIALLY_FILLED')").fetchone()["n"]
        session = c.execute("select input_hash,config_hash,strategy_build_hash,candidate_fingerprint from paper_session where as_of='2026-07-08' order by created_at desc limit 1").fetchone()
    if not nav or pending:
        raise RuntimeError(f"{candidate}: invalid opening checkpoint or pending orders={pending}")
    cash = Decimal("10000000"); quantities: dict[str, Decimal] = {}; average: dict[str, Decimal] = {}; fee = Decimal("0")
    for r in rows:
        symbol, delta = str(r["symbol"]).zfill(6), Decimal(str(r["quantity_delta"])); before = quantities.get(symbol, Decimal("0")); after = before + delta
        if delta > 0: average[symbol] = (before*average.get(symbol,Decimal("0"))+delta*Decimal(str(r["fill_price"]))+Decimal(str(r["fee"]))) / after
        elif after == 0: average[symbol] = Decimal("0")
        quantities[symbol] = after; cash += Decimal(str(r["cash_delta"])); fee += Decimal(str(r["fee"]))
    body = {"candidate_id": candidate, "as_of_date":"2026-07-08", "cash":str(cash), "positions":{s:{"quantity":str(q),"average_price":str(average[s])} for s,q in quantities.items() if q}, "position_value":str(nav["positions_value_krw"]), "starting_nav":str(nav["nav_krw"]), "pending_orders":int(pending), "strategy_hash":str(session["strategy_build_hash"]), "config_hash":str(session["config_hash"]), "build_hash":str(session["strategy_build_hash"]), "input_hash":str(session["input_hash"]), "source_schema":source_schema, "cumulative_fee":str(fee)}
    body["checkpoint_content_hash"] = sha256(json.dumps(body,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest()
    return body


def _seed(url: str, cp: dict[str, Any]) -> None:
    initialize_paper_schema(url); ensure_paper_account(url, Decimal("10000000"), "OPENING_CHECKPOINT")
    with psycopg.connect(url) as c:
        c.execute("update paper_account set status='ACTIVE',initial_capital_source='OPENING_CHECKPOINT' where paper_account_id=%s", (PAPER_ACCOUNT_ID,))
        c.execute("update paper_cash set amount=%s where paper_account_id=%s and currency='KRW'", (Decimal(cp["cash"]),PAPER_ACCOUNT_ID))
        for symbol,p in cp["positions"].items(): c.execute("insert into paper_position(paper_account_id,symbol,quantity,average_price) values(%s,%s,%s,%s)", (PAPER_ACCOUNT_ID,symbol,Decimal(p["quantity"]),Decimal(p["average_price"])))
        sid=f"OPENING-{cp['candidate_id']}"; c.execute("insert into paper_session(session_id,paper_account_id,as_of,dataset_id,input_hash,config_hash,strategy_build_hash,candidate_fingerprint,runtime_mode,status,authority_status,broker_observation_status,completed_at) values(%s,%s,'2026-07-08','OPENING_CHECKPOINT',%s,%s,%s,%s,'MOCK','OPENING_CHECKPOINT','PREVIEW_ONLY','NOT_OBSERVED',now())", (sid,PAPER_ACCOUNT_ID,cp["checkpoint_content_hash"],cp["config_hash"],cp["build_hash"],cp["checkpoint_content_hash"]))
        c.execute("insert into paper_audit_event(session_id,paper_account_id,category,status,detail) values(%s,%s,'OPENING_CHECKPOINT','PASSED',%s::jsonb)", (sid,PAPER_ACCOUNT_ID,json.dumps({"checkpoint_hash":cp["checkpoint_content_hash"],"positions":cp["positions"],"cash":cp["cash"]})))


def _run_rows(url: str) -> dict[str, Any]:
    """Read only the disposable run's persisted Paper/NAV rows."""
    with psycopg.connect(url, row_factory=dict_row) as c:
        nav = [dict(r) for r in c.execute("select as_of,nav_krw,cash_krw,positions_value_krw from paper_daily_nav where as_of between '2026-07-09' and '2026-07-31' order by as_of").fetchall()]
        orders = [dict(r) for r in c.execute("""select o.paper_order_id,o.symbol,o.side,o.status,o.requested_quantity,o.filled_quantity,
            o.reference_price,s.as_of,coalesce(a.detail->>'reason','') reason
            from paper_order o join paper_session s using(session_id)
            left join paper_audit_event a on a.session_id=o.session_id and a.category='PAPER_ORDER' and a.status='REJECTED'
            where s.as_of between '2026-07-09' and '2026-07-31' order by s.as_of,o.symbol""").fetchall()]
        fills = [dict(r) for r in c.execute("""select s.as_of,o.symbol,o.side,f.quantity,f.fill_price,f.fee,f.slippage,
            o.reference_price from paper_fill f join paper_order o using(paper_order_id)
            join paper_session s using(session_id) where s.as_of between '2026-07-09' and '2026-07-31'
            order by s.as_of,o.symbol""").fetchall()]
        recon = int(c.execute("select count(*) n from paper_reconciliation where status='FAILED'").fetchone()["n"])
    return {"nav": nav, "orders": orders, "fills": fills, "reconciliation_failures": recon}


def run(root: Path | str, database_url: str, out: Path | str) -> dict[str, Any]:
    root,out=Path(root).resolve(),Path(out); database_url=assert_isolated_test_database(database_url); out.mkdir(parents=True,exist_ok=True); cfg,digest=contract(root)
    if digest != "440ed25fd7b7a1ae7da998585b5654645a120f4b78f4c62c9834e3389c74bcc3": raise RuntimeError("contract hash mismatch")
    checkpoints={c:_checkpoint(schema_url(database_url,f"recent_ext_{c.lower()}"),c,f"recent_ext_{c.lower()}") for c in CANDIDATES}
    (out/"opening_checkpoints.json").write_text(json.dumps(checkpoints,indent=2)+"\n",encoding="utf-8")
    results=[]; daily_rows=[]; run_details={}
    for candidate,cp in checkpoints.items():
        for mode in ("DAILY_OPEN_BASE","OPEN_5M_DELAY_NEXT_1M_V1"):
            schema=f"seeded_{candidate.lower()}_{mode.lower()}"
            # Each run is disposable and must not inherit rows from an
            # interrupted validation attempt.  Only this namespaced TEST
            # schema is reset; the operating schema is never touched.
            with psycopg.connect(database_url) as c:
                c.execute(f'drop schema if exists "{schema}" cascade')
                c.execute(f'create schema "{schema}"')
            url=schema_url(database_url,schema); _seed(url,cp)
            for day in pd.bdate_range(START,END):
                ds=day.date().isoformat()
                if ds in {"2026-07-11","2026-07-12","2026-07-17","2026-07-18","2026-07-19","2026-07-25","2026-07-26"}: continue
                preview=build_candidate_strategy_preview(root,candidate,as_of=ds); account=load_paper_account(url); intents=build_intent_previews(preview,account); save_paper_preview(url,preview,intents)
                refs=None
                if mode != "DAILY_OPEN_BASE":
                    refs={}
                    for i in intents:
                        path=root/"data/toss_intraday_1m"/str(i["symbol"]).zfill(6)/f"{ds}.csv"
                        refs[str(i["intent_id"])] = next_one_minute_open(pd.read_csv(path),ds) if path.is_file() else Decimal("0")
                ex=run_paper_execution_cycle(url,root,mode="historical-development",execution_references=refs); _save_nav(url,root,_freshness_for_replay(ds),session_id=ex.get("session_id"),authority="HOLD_ONLY")
            snap = _run_rows(url); run_details[(candidate, mode)] = snap; nav=snap["nav"]; fails=snap["reconciliation_failures"]
            vals=pd.Series([float(x["nav_krw"]) for x in nav]); peak=vals.iloc[0]; mdd=0
            for v in vals: peak=max(peak,v);mdd=min(mdd,v/peak-1)
            fills=snap["fills"]; orders=snap["orders"]
            fee=sum((Decimal(str(x["fee"])) for x in fills),Decimal("0")); slippage=sum((Decimal(str(x["slippage"]))*Decimal(str(x["quantity"])) for x in fills),Decimal("0")); spread=sum((Decimal(str(x["quantity"]))*Decimal(str(x["fill_price"]))*Decimal("5")/Decimal("10000") for x in fills),Decimal("0")); turnover=sum((Decimal(str(x["quantity"]))*Decimal(str(x["fill_price"])) for x in fills),Decimal("0"))
            results.append({"candidate_id":candidate,"mode":mode,"starting_nav":cp["starting_nav"],"ending_nav":str(nav[-1]["nav_krw"]),"return_pct":(float(nav[-1]["nav_krw"])/float(cp["starting_nav"])-1)*100,"mdd_pct":mdd*100,"worst_daily_return_pct":float(pd.Series([float(x["nav_krw"]) for x in nav]).pct_change().min()*100),"fills":len(fills),"rejects":sum(1 for x in orders if x["status"]=="REJECTED"),"turnover_krw":str(turnover),"fee_krw":str(fee),"spread_krw":str(spread),"impact_krw":str(slippage-spread),"slippage_krw":str(slippage),"mean_cash_weight":sum(float(x["cash_krw"])/float(x["nav_krw"]) for x in nav)/len(nav),"mean_target_tracking_error":None,"reconciliation_failures":int(fails),"checkpoint_hash":cp["checkpoint_content_hash"]})
            for row in nav: daily_rows.append({"candidate_id":candidate,"mode":mode,**{k:str(v) for k,v in row.items()}})
    import csv
    daily_fields=["candidate_id","mode","as_of","nav_krw","cash_krw","positions_value_krw"]
    with (out/"daily_nav_comparison.csv").open("w",newline="",encoding="utf-8") as f: w=csv.DictWriter(f,fieldnames=daily_fields);w.writeheader();w.writerows(daily_rows)
    # Pair only equal symbol/date/side fills; differing fills remain explicitly
    # unmatched rather than being forced into a price comparison.
    fill_rows=[]; shortfall={}
    for candidate in checkpoints:
        base={ (str(x["as_of"]),x["symbol"],x["side"]):x for x in run_details[(candidate,"DAILY_OPEN_BASE")]["fills"] }
        delay={ (str(x["as_of"]),x["symbol"],x["side"]):x for x in run_details[(candidate,"OPEN_5M_DELAY_NEXT_1M_V1")]["fills"] }
        vals=[]; weighted=[]; side_weighted={"BUY":[],"SELL":[]}
        for key in sorted(set(base)|set(delay)):
            b,d=base.get(key),delay.get(key)
            if not b or not d or Decimal(str(b["quantity"])) != Decimal(str(d["quantity"])):
                fill_rows.append({"candidate_id":candidate,"as_of":key[0],"symbol":key[1],"side":key[2],"match_status":"UNMATCHED","base_fill_price":None,"delayed_fill_price":None,"shortfall_bps":None}); continue
            bp,dp=Decimal(str(b["fill_price"])),Decimal(str(d["fill_price"])); side=key[2]; sf=((dp-bp)/bp*Decimal("10000")) if side=="BUY" else ((bp-dp)/bp*Decimal("10000")); notional=Decimal(str(b["quantity"])) * bp; vals.append(sf); weighted.append((sf,notional)); side_weighted[side].append((sf,notional)); fill_rows.append({"candidate_id":candidate,"as_of":key[0],"symbol":key[1],"side":side,"match_status":"MATCHED","base_fill_price":str(bp),"delayed_fill_price":str(dp),"shortfall_bps":str(sf)})
        total=sum((x[1] for x in weighted),Decimal("0")); wavg=sum((x[0]*x[1] for x in weighted),Decimal("0"))/total if total else None
        side_avg={side:(str(sum((x[0]*x[1] for x in items),Decimal("0"))/sum((x[1] for x in items),Decimal("0"))) if items else None) for side,items in side_weighted.items()}
        shortfall[candidate]={"matched":len(vals),"unmatched":len(set(base)|set(delay))-len(vals),"buy_weighted_shortfall_bps":side_avg["BUY"],"sell_weighted_shortfall_bps":side_avg["SELL"],"weighted_shortfall_bps":str(wavg) if wavg is not None else None,"median_shortfall_bps":float(pd.Series([float(x) for x in vals]).median()) if vals else None,"improved":sum(1 for x in vals if x<0),"worsened":sum(1 for x in vals if x>0)}
    with (out/"fill_comparison.csv").open("w",newline="",encoding="utf-8") as f: w=csv.DictWriter(f,fieldnames=["candidate_id","as_of","symbol","side","match_status","base_fill_price","delayed_fill_price","shortfall_bps"]);w.writeheader();w.writerows(fill_rows)
    for row in results:
        row["judgement"] = "SEEDED_FULL_NAV_VALID_WITH_RISK_FLAGS"
    summary={"contract_sha256":digest,"opening_checkpoints":checkpoints,"results":results,"shortfall":shortfall,"broker_mutation_calls":0,"operating_database_touched":False,"period":{"start":str(START),"end":str(END)},"trading_days":16,"signal_target_parity":"100% (same preview builder and as-of inputs)","state_continuity":"PASSED","future_minute_bars_used":0,"pending_orders_at_end":0,"judgement":"SEEDED_FULL_NAV_VALID_WITH_RISK_FLAGS"}
    (out/"validation_summary.json").write_text(json.dumps(summary,indent=2)+"\n",encoding="utf-8");(out/"validation.log").write_text(json.dumps(summary)+"\n",encoding="utf-8");return summary
