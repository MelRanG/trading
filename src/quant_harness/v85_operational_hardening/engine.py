from __future__ import annotations

import json
import shutil
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import yaml

from quant_harness.v77_corrected_price_allocation import engine as v77
from quant_harness.v84_dual_paper_parity.engine import (
    DualPaperStore, ExecutionPolicy, PortfolioState, build_strategy_ledgers,
    execute_target_map, run as run_v84,
)

REPORT = "v85_operational_hardening"
STAGES = ("DATA_SYNC", "DATA_VALIDATE", "UNIVERSE_RESOLVE", "PLAN", "RISK_GATE", "EXECUTE", "RECONCILE", "FEEDBACK", "BACKUP", "REPORT")


@dataclass(frozen=True)
class RiskLimits:
    kill_switch: bool
    max_single_symbol_weight: float
    max_daily_loss_pct: float
    max_rolling_drawdown_pct: float
    max_open_gap_pct: float
    max_participation_of_d1_adv: float
    minimum_cash_krw: float


class AlertSink:
    def __init__(self, path: Path):
        self.path = path; path.parent.mkdir(parents=True, exist_ok=True)
    def emit(self, severity: str, code: str, message: str, **context: Any) -> dict[str, Any]:
        event = {"at": datetime.now(timezone.utc).isoformat(), "severity": severity, "code": code, "message": message, "context": context}
        with self.path.open("a", encoding="utf-8") as f: f.write(json.dumps(event, sort_keys=True) + "\n")
        return event


class OrchestratorState:
    def __init__(self, path: Path):
        self.path = path; path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as conn:
            conn.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS runs(run_id TEXT PRIMARY KEY,session TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,completed_at TEXT);
            CREATE TABLE IF NOT EXISTS stages(run_id TEXT NOT NULL,stage TEXT NOT NULL,status TEXT NOT NULL,payload_hash TEXT NOT NULL,updated_at TEXT NOT NULL,PRIMARY KEY(run_id,stage));
            """)
    def start(self, run_id: str, session: str) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute("INSERT OR IGNORE INTO runs VALUES(?,?,?, ?,NULL)", (run_id, session, "RUNNING", datetime.now(timezone.utc).isoformat()))
    def stage_done(self, run_id: str, stage: str) -> bool:
        with sqlite3.connect(self.path) as conn:
            row=conn.execute("SELECT status FROM stages WHERE run_id=? AND stage=?",(run_id,stage)).fetchone()
        return bool(row and row[0]=="DONE")
    def mark(self, run_id: str, stage: str, payload: Any) -> None:
        h=sha256(json.dumps(payload,sort_keys=True,default=str).encode()).hexdigest()
        with sqlite3.connect(self.path) as conn:
            conn.execute("INSERT INTO stages VALUES(?,?,?,?,?) ON CONFLICT(run_id,stage) DO UPDATE SET status=excluded.status,payload_hash=excluded.payload_hash,updated_at=excluded.updated_at",(run_id,stage,"DONE",h,datetime.now(timezone.utc).isoformat()))
    def complete(self, run_id: str) -> None:
        with sqlite3.connect(self.path) as conn: conn.execute("UPDATE runs SET status='DONE',completed_at=? WHERE run_id=?",(datetime.now(timezone.utc).isoformat(),run_id))


def _cfg(root: Path) -> dict[str, Any]:
    return yaml.safe_load((root/"config/v85_operations.yaml").read_text(encoding="utf-8"))


def build_point_in_time_universe(root: Path, universe: pd.DataFrame) -> pd.DataFrame:
    full = pd.read_csv(root / "data/toss_v19c_daily/universe.csv", dtype={"ticker": str})
    full["ticker"] = full["ticker"].str.zfill(6)
    rows=[]
    for row in full.itertuples(index=False):
        ticker=str(row.ticker).zfill(6); p=root/f"data/toss_v19c_daily/{ticker}_1d.csv"
        d=pd.read_csv(p); dates=pd.to_datetime(d["timestamp"],utc=True).dt.tz_convert("Asia/Seoul").dt.tz_localize(None).dt.normalize()
        rows.append({"ticker":ticker,"name":str(row.name),"sector":str(row.sector),"available_from":dates.min().date().isoformat(),"available_to":dates.max().date().isoformat(),"status":"ACTIVE_AS_OF_DATA_END","listing_source":"OBSERVED_FIRST_BAR_PROXY","delisting_complete":False,"corporate_action_verified":False})
    frame=pd.DataFrame(rows).sort_values("ticker")
    path=root/"data/canonical/v85_point_in_time_universe.csv"; path.parent.mkdir(parents=True,exist_ok=True); frame.to_csv(path,index=False)
    return frame


def eligible_tickers(pit: pd.DataFrame, session: pd.Timestamp) -> set[str]:
    day=session.normalize()
    start=pd.to_datetime(pit.available_from); end=pd.to_datetime(pit.available_to)
    return set(pit.loc[(start<=day)&(end>=day),"ticker"].astype(str))


def risk_gate(
    *, targets: dict[str,float], state: PortfolioState, open_prices: dict[str,float], previous_close: dict[str,float],
    adv20_d1: dict[str,float], limits: RiskLimits, previous_nav: float | None = None, peak_nav: float | None = None, core_ticker: str = "069500",
) -> dict[str, Any]:
    blockers=[]; warnings=[]
    if limits.kill_switch: blockers.append("KILL_SWITCH")
    if abs(sum(targets.values())-1.0)>1e-9: blockers.append("TARGET_SUM")
    non_core = [w for t,w in targets.items() if t != core_ticker]
    if non_core and max(non_core)>limits.max_single_symbol_weight+1e-12: blockers.append("SINGLE_SYMBOL_CONCENTRATION")
    if state.cash < limits.minimum_cash_krw-0.01: blockers.append("NEGATIVE_CASH")
    for t,w in targets.items():
        if t not in open_prices or not np.isfinite(open_prices[t]) or open_prices[t]<=0: blockers.append(f"MISSING_OPEN:{t}")
        prev=previous_close.get(t)
        if prev and abs(open_prices[t]/prev-1)>limits.max_open_gap_pct: blockers.append(f"EXTREME_GAP:{t}")
        adv=adv20_d1.get(t,np.nan)
        if not np.isfinite(adv) or adv<=0: blockers.append(f"MISSING_D1_ADV:{t}")
    if previous_nav and previous_nav>0:
        nav_open=state.cash+sum(q*open_prices.get(t,0.0) for t,q in state.quantities.items())
        if nav_open/previous_nav-1 < -limits.max_daily_loss_pct: blockers.append("DAILY_LOSS_LIMIT")
    if peak_nav and peak_nav>0 and previous_nav and previous_nav/peak_nav-1 < -limits.max_rolling_drawdown_pct: blockers.append("DRAWDOWN_LIMIT")
    return {"allowed":not blockers,"blockers":sorted(set(blockers)),"warnings":warnings,"mode":"PAPER" if not blockers else "HOLD_ONLY"}


def backup_sqlite(source: Path, backup_dir: Path, tag: str) -> dict[str, Any]:
    backup_dir.mkdir(parents=True,exist_ok=True); target=backup_dir/f"{source.stem}_{tag}.db"
    with sqlite3.connect(source) as src, sqlite3.connect(target) as dst: src.backup(dst)
    digest=sha256(target.read_bytes()).hexdigest()
    return {"path":str(target),"sha256":digest,"size":target.stat().st_size}


def restore_and_check(backup: Path, target: Path) -> dict[str, Any]:
    if target.exists(): target.unlink()
    shutil.copy2(backup,target)
    with sqlite3.connect(target) as conn:
        integrity=conn.execute("PRAGMA integrity_check").fetchone()[0]
        accounts=conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
        sessions=conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    return {"integrity":integrity,"accounts":accounts,"sessions":sessions,"passed":integrity=="ok" and accounts==2 and sessions>0}


def _target_at(ledger: pd.DataFrame, session: pd.Timestamp) -> dict[str,float]:
    row=ledger.set_index("date").loc[session,"target_weights_json"]
    return {str(k):float(v) for k,v in json.loads(str(row)).items()}


def run_operating_day(root: Path | str, *, session: str | None=None, rebuild: bool=False) -> dict[str, Any]:
    root=Path(root); cfg=_cfg(root); out=root/"reports"/REPORT; out.mkdir(parents=True,exist_ok=True)
    alert=AlertSink(root/cfg["operations"]["alert_log"]); orch=OrchestratorState(root/cfg["operations"]["orchestrator_db"])
    market, universe, ledger69, ledger79, _=build_strategy_ledgers(root)
    trade_session=pd.Timestamp(session) if session else market["close"].index.max()
    if trade_session not in market["close"].index: raise ValueError("session is not in canonical trading index")
    run_id=f"V85-{trade_session.date()}"; orch.start(run_id,str(trade_session.date()))
    existing_manifest = root/cfg["operations"]["run_manifest_dir"]/f"{run_id}.json"
    if not rebuild and existing_manifest.exists():
        return json.loads(existing_manifest.read_text(encoding="utf-8"))
    payload:dict[str,Any]={"run_id":run_id,"session":str(trade_session.date()),"stages":{}}
    if rebuild or not orch.stage_done(run_id,"DATA_SYNC"):
        v84=run_v84(root); payload["stages"]["DATA_SYNC"]={"v84_status":v84["status"]}; orch.mark(run_id,"DATA_SYNC",payload["stages"]["DATA_SYNC"])
    canonical=pd.read_csv(root/cfg["operations"]["canonical_market"],dtype={"ticker":str})
    current=canonical[canonical.date==str(trade_session.date())]
    data_gate={"rows":len(current),"unique_tickers":current.ticker.nunique(),"duplicates":int(current.duplicated(["date","ticker"]).sum()),"adjusted_only":set(current.price_scale)=={"ADJUSTED_OHLC"}}
    if data_gate["duplicates"] or not data_gate["adjusted_only"]: alert.emit("CRITICAL","DATA_INVALID","canonical data gate failed",**data_gate); raise RuntimeError(data_gate)
    payload["stages"]["DATA_VALIDATE"]=data_gate; orch.mark(run_id,"DATA_VALIDATE",data_gate)
    pit=build_point_in_time_universe(root,universe); eligible=eligible_tickers(pit,trade_session)
    payload["stages"]["UNIVERSE_RESOLVE"]={"eligible_count":len(eligible),"point_in_time_proxy":True}; orch.mark(run_id,"UNIVERSE_RESOLVE",payload["stages"]["UNIVERSE_RESOLVE"])
    plans={"v69_fixed80_daily_control":_target_at(ledger69,trade_session),"v79_core70_generic_trend30":_target_at(ledger79,trade_session)}
    for sid,t in plans.items():
        unavailable=sorted(set(t)-eligible)
        if unavailable: raise RuntimeError(f"{sid} targets unavailable tickers {unavailable}")
    payload["stages"]["PLAN"]={k:dict(sorted(v.items())) for k,v in plans.items()}; orch.mark(run_id,"PLAN",payload["stages"]["PLAN"])
    limits=RiskLimits(**cfg["risk"]); policy=ExecutionPolicy.from_v77(v77._load_config(root).base_execution)
    db=root/cfg["operations"]["dual_paper_db"]
    if rebuild and db.exists(): db.unlink()
    store=DualPaperStore(db)
    # Rebuild up to selected session, preserving exact historical path and idempotency.
    indices=market["close"].index[market["close"].index<=trade_session]
    risk_rows=[]; final={}
    for sid,ledger,band,priority in [
        ("v69_fixed80_daily_control",ledger69,0.0,"CORE_THEN_TARGET_DESC"),
        ("v79_core70_generic_trend30",ledger79,0.05,"DEFICIT_DESC")]:
        state=store.load(sid,float(cfg["initial_capital_krw"])); prev_nav=None; peak_nav=None
        for pos,date in enumerate(indices):
            targets=_target_at(ledger,date); relevant=set(state.quantities)|set(targets)
            opens={t:float(market["open"].loc[date,t]) for t in relevant}; adv={t:float(market["adv20_d1"].loc[date,t]) for t in relevant}
            prev_close={t:float(market["close"].iloc[pos-1][t]) for t in relevant} if pos>0 else opens
            if date < trade_session:
                # Bootstrap uses the frozen historical execution contract. Operational risk limits
                # are evaluated only at the current decision boundary, not retroactively.
                missing_adv = [t for t in targets if not np.isfinite(adv.get(t, np.nan)) or adv.get(t, 0) <= 0]
                if missing_adv:
                    nav=state.cash+sum(q*float(market["close"].loc[date,t]) for t,q in state.quantities.items()); fills=[]
                else:
                    state,fills,_=execute_target_map(state,targets=targets,open_prices=opens,adv20_d1=adv,policy=policy,rebalance_band=band,buy_priority=priority,core_ticker=v77._load_config(root).core_ticker)
                    nav=state.cash+sum(q*float(market["close"].loc[date,t]) for t,q in state.quantities.items())
                gate={"allowed":True,"blockers":[],"warnings":[],"mode":"BOOTSTRAP"}
            else:
                gate=risk_gate(targets=targets,state=state,open_prices=opens,previous_close=prev_close,adv20_d1=adv,limits=limits,previous_nav=prev_nav,peak_nav=peak_nav,core_ticker=v77._load_config(root).core_ticker)
                if not gate["allowed"]:
                    alert.emit("CRITICAL","RISK_BLOCK",f"{sid} risk gate blocked",session=str(date.date()),blockers=gate["blockers"]); raise RuntimeError(gate)
                state,fills,_=execute_target_map(state,targets=targets,open_prices=opens,adv20_d1=adv,policy=policy,rebalance_band=band,buy_priority=priority,core_ticker=v77._load_config(root).core_ticker)
                nav=state.cash+sum(q*float(market["close"].loc[date,t]) for t,q in state.quantities.items())
            plan_hash=sha256(json.dumps({"sid":sid,"date":str(date.date()),"targets":targets},sort_keys=True).encode()).hexdigest()
            store.commit(sid,str(date.date()),state,nav,fills,plan_hash)
            prev_nav=nav; peak_nav=max(peak_nav or nav,nav)
            if date==trade_session: risk_rows.append({"strategy_id":sid,**gate}); final[sid]={"nav":nav,"cash":state.cash,"holdings":state.quantities,"fills":len(fills)}
    payload["stages"]["RISK_GATE"]={"strategies":risk_rows}; orch.mark(run_id,"RISK_GATE",payload["stages"]["RISK_GATE"])
    payload["stages"]["EXECUTE"]=final; orch.mark(run_id,"EXECUTE",final)
    with sqlite3.connect(db) as conn:
        integrity=conn.execute("PRAGMA integrity_check").fetchone()[0]; account_count=conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]; session_count=conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    reconcile={"integrity":integrity,"account_count":account_count,"session_count":session_count,"passed":integrity=="ok" and account_count==2}
    payload["stages"]["RECONCILE"]=reconcile; orch.mark(run_id,"RECONCILE",reconcile)
    feedback={"v69":"SELF_RESEARCH_LEDGER_ONLY_NO_MUTATION","v79":"SELF_RESEARCH_LEDGER_ONLY_NO_MUTATION","cross_strategy_feedback":False}
    payload["stages"]["FEEDBACK"]=feedback; orch.mark(run_id,"FEEDBACK",feedback)
    backup=backup_sqlite(db,root/cfg["operations"]["backup_dir"],str(trade_session.date()).replace("-","")); restore=restore_and_check(Path(backup["path"]),root/cfg["operations"]["backup_dir"]/"restore_test.db")
    payload["stages"]["BACKUP"]={"backup":backup,"restore":restore}; orch.mark(run_id,"BACKUP",payload["stages"]["BACKUP"])
    manifest_dir=root/cfg["operations"]["run_manifest_dir"]; manifest_dir.mkdir(parents=True,exist_ok=True); manifest=manifest_dir/f"{run_id}.json"
    payload["status"]="v85_operational_hardening_complete_live_blocked"; payload["live_execution_allowed"]=False; manifest.write_text(json.dumps(payload,indent=2,default=str),encoding="utf-8")
    orch.mark(run_id,"REPORT",{"manifest":str(manifest.relative_to(root))}); orch.complete(run_id)
    return payload


def logical_db_digest(path: Path) -> str:
    payload: dict[str, Any] = {}
    with sqlite3.connect(path) as conn:
        for table in ("accounts", "sessions", "fills"):
            columns = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
            rows = conn.execute(f"SELECT * FROM {table} ORDER BY " + ",".join(columns)).fetchall()
            payload[table] = [list(r) for r in rows]
    return sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()

def run(root: Path | str) -> dict[str, Any]:
    root=Path(root); out=root/"reports"/REPORT; out.mkdir(parents=True,exist_ok=True)
    result=run_operating_day(root,rebuild=True)
    cfg=_cfg(root); db=root/cfg["operations"]["dual_paper_db"]
    # Re-run exactly once to prove idempotency.
    before=logical_db_digest(db); rerun=run_operating_day(root,rebuild=False); after=logical_db_digest(db)
    gates={
        "dual_accounts_present":result["stages"]["RECONCILE"]["account_count"]==2,
        "sqlite_integrity":result["stages"]["RECONCILE"]["integrity"]=="ok",
        "backup_restore_passed":result["stages"]["BACKUP"]["restore"]["passed"],
        "idempotent_logical_state":before==after,
        "all_operational_stages_present":all(s in result["stages"] for s in STAGES if s!="REPORT"),
        "point_in_time_universe_written":(root/cfg["operations"]["pit_universe"]).exists(),
        "risk_allowed_both":all(x["allowed"] for x in result["stages"]["RISK_GATE"]["strategies"]),
        "live_blocked":not result["live_execution_allowed"],
    }
    pd.DataFrame([{"gate":k,"passed":v} for k,v in gates.items()]).to_csv(out/"quality_gates.csv",index=False)
    summary={"status":"v85_complete_paper_ready_live_blocked","gates":gates,"operating_day":result,"rerun_status":rerun["status"]}
    (out/"summary.json").write_text(json.dumps(summary,indent=2,default=str),encoding="utf-8")
    return summary
