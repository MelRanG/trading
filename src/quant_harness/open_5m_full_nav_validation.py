"""Run the frozen 5m delay through the established Paper ledger path only."""
from __future__ import annotations

import csv
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd
import psycopg
from psycopg.rows import dict_row

from quant_harness.historical_operational_replay import assert_isolated_test_database, run_historical_operational_replay
from quant_harness.open_5m_execution_validation import CANDIDATES, END, START, contract, next_one_minute_open
from quant_harness.recent_candidate_extension import schema_url
from quant_harness.v77_corrected_price_allocation import engine as v77


def _resolver(root: Path):
    cfg = v77._load_config(root, use_common_cutoff=True)
    adjusted_open = v77.load_adjusted_market(root, cfg)["open"]
    warmup_open = {
        pd.Timestamp(day).date().isoformat(): {
            str(symbol).zfill(6): Decimal(str(price))
            for symbol, price in row.items() if pd.notna(price) and float(price) > 0
        }
        for day, row in adjusted_open.iterrows()
    }

    def resolve(preview: dict[str, Any], intents: list[dict[str, Any]]) -> dict[str, Decimal]:
        session = str(preview["as_of"].date())
        if session < START:
            prices: dict[str, Decimal] = {}
            for intent in intents:
                symbol = str(intent["symbol"]).zfill(6)
                if session not in warmup_open or symbol not in warmup_open[session]:
                    raise RuntimeError(f"missing warm-up daily open for {symbol} on {session}")
                prices[str(intent["intent_id"])] = warmup_open[session][symbol]
            return prices
        out: dict[str, Decimal] = {}
        for intent in intents:
            path = root / "data/toss_intraday_1m" / str(intent["symbol"]).zfill(6) / f"{session}.csv"
            if not path.is_file():
                raise RuntimeError(f"missing full-session intraday cache for {intent['symbol']} on {session}")
            out[str(intent["intent_id"])] = next_one_minute_open(pd.read_csv(path), session)
        return out
    return resolve


def _metrics(url: str) -> dict[str, Any]:
    with psycopg.connect(url, row_factory=dict_row) as conn:
        nav = [dict(r) for r in conn.execute("select as_of,nav_krw,cash_krw,positions_value_krw from paper_daily_nav where as_of between %s and %s order by as_of", (START, END)).fetchall()]
        prior = conn.execute("select nav_krw from paper_daily_nav where as_of<'2026-07-09' order by as_of desc limit 1").fetchone()
        fills = [dict(r) for r in conn.execute("select s.as_of,o.symbol,o.side,f.quantity,f.fill_price,f.fee,f.slippage,o.reference_price from paper_fill f join paper_order o on o.paper_order_id=f.paper_order_id join paper_session s on s.session_id=o.session_id where s.as_of between %s and %s order by s.as_of,o.side,o.symbol", (START, END)).fetchall()]
        rejects = conn.execute("select count(*) n from paper_order o join paper_session s using(session_id) where s.as_of between %s and %s and o.status='REJECTED'", (START, END)).fetchone()["n"]
        recon = conn.execute("select count(*) n from paper_reconciliation where status='FAILED'").fetchone()["n"]
    opening = Decimal(str(prior["nav_krw"])); ending = Decimal(str(nav[-1]["nav_krw"])); values = [float(opening)] + [float(x["nav_krw"]) for x in nav]
    peak = values[0]; mdd = 0.0
    for value in values: peak=max(peak,value); mdd=min(mdd,value/peak-1)
    daily = pd.Series(values).pct_change().dropna()
    fee=sum(Decimal(str(x["fee"])) for x in fills); slip=sum(Decimal(str(x["slippage"]))*Decimal(str(x["quantity"])) for x in fills)
    turnover=sum(abs(Decimal(str(x["fill_price"]))*Decimal(str(x["quantity"]))) for x in fills)
    return {"final_nav_krw":str(ending),"return_pct":float((ending/opening-1)*100),"mdd_pct":mdd*100,"worst_daily_return_pct":float(daily.min()*100),"fills":len(fills),"rejects":int(rejects),"turnover_krw":str(turnover),"fee_krw":str(fee),"slippage_krw":str(slip),"mean_cash_weight":sum(float(x["cash_krw"])/float(x["nav_krw"]) for x in nav)/len(nav),"reconciliation_failures":int(recon),"nav_days":len(nav),"fills_detail":fills}


def run(root: Path | str, database_url: str, output_dir: Path | str) -> dict[str, Any]:
    root, out = Path(root).resolve(), Path(output_dir); out.mkdir(parents=True, exist_ok=True)
    database_url = assert_isolated_test_database(database_url)
    cfg, digest = contract(root)
    if digest != "440ed25fd7b7a1ae7da998585b5654645a120f4b78f4c62c9834e3389c74bcc3": raise RuntimeError("frozen contract hash mismatch")
    rows=[]; fills=[]
    for candidate in CANDIDATES:
        for mode, resolver in (("DAILY_OPEN_BASE",None),("OPEN_5M_DELAY_NEXT_1M_V1",_resolver(root))):
            schema=f"open5m_{mode.lower()}_{candidate.lower()}"
            with psycopg.connect(database_url) as conn: conn.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
            url=schema_url(database_url, schema)
            run_historical_operational_replay(
                root,
                url,
                reset=True,
                candidate_id=candidate,
                start_date="2021-10-13",
                end_date=END,
                execution_reference_resolver=resolver,
                execution_contract_name="OPEN_5M_DELAY_NEXT_1M_V1" if resolver else "D_MINUS_1_CLOSE_SIZE_D_OPEN_EXECUTION_V1",
                execution_contract_hash=digest if resolver else None,
                execution_price_contract="first permitted next 1-minute open after the frozen opening 5-minute delay" if resolver else "D adjusted open",
                output_dir=out / candidate / mode,
            )
            metric=_metrics(url); detail=metric.pop("fills_detail"); rows.append({"candidate_id":candidate,"mode":mode,**metric})
            for x in detail: fills.append({"candidate_id":candidate,"mode":mode,**x})
    with (out/"daily_nav_comparison.csv").open("w",newline="",encoding="utf-8") as f: w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    with (out/"fill_comparison.csv").open("w",newline="",encoding="utf-8") as f: w=csv.DictWriter(f,fieldnames=list(fills[0]));w.writeheader();w.writerows(fills)
    summary={"contract":cfg,"contract_sha256":digest,"results":rows,"broker_mutation_calls":0,"operating_database_touched":False,"reports_touched":False}
    (out/"validation_summary.json").write_text(json.dumps(summary,indent=2,default=str)+"\n",encoding="utf-8")
    (out/"validation.log").write_text(json.dumps({"contract_sha256":digest,"broker_mutation_calls":0,"live_execution_allowed":False})+"\n",encoding="utf-8")
    return summary
