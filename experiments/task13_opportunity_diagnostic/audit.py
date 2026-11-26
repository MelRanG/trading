"""Attribute fixed R4/R5 ledger returns. Never generate orders or strategy variants."""
from collections import Counter
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
from unittest.mock import patch

import numpy as np
import pandas as pd

from experiments.task13_f1_r4 import replay as r4
from experiments.task13_r1_st_preflight.replay import stage
from experiments.task13_r1_st_preflight.audit import ROOT, RUNTIME, R4, R5, R2, checked, read
from experiments.task12.readiness import regimes

OUT = RUNTIME / "task13_opportunity_diagnostic"


def check(value, detail):
    if not value:
        raise ValueError(detail)


def csv(raw):
    frame = pd.read_csv(io.BytesIO(raw), parse_dates=[0])
    return frame.set_index(frame.columns[0]).sort_index().rename_axis("date")


def archived(tasks):
    refs = read(RUNTIME/"research_reference/index.json")
    inventory = json.loads(checked(Path(refs["archive_inventory"]), refs["archive_inventory_sha256"]))
    found = {}
    with tarfile.open(refs["archive"], "r|gz") as pack:
        for item in pack:
            if item.name not in tasks:
                continue
            raw = pack.extractfile(item).read()
            check(hashlib.sha256(raw).hexdigest()==inventory[item.name]["sha256"], item.name)
            found[item.name] = raw
            if len(found)==len(tasks):
                return found
    raise ValueError(f"Missing archive objects: {tasks - found.keys()}")


def inputs():
    prices = {}
    manifest = read(R4/"artifact_manifest.json")
    key = "runtime/task13_f1_r4/T1_A_fills.csv"
    kospi = "runtime/task13_r0/accepted/KR/^KS11/quote.csv"
    raw = archived({key,kospi})
    b0 = csv(raw[kospi]).close
    with tempfile.TemporaryDirectory(prefix="opportunity_readonly_") as temp:
        root = Path(temp)
        stage(root)
        with patch.multiple(r4, ROOT=root, R0=root/"runtime/task13_r0", R2=root/"runtime/task13_f1_r2",
                            R3=root/"runtime/task13_f1_r3", OUT=root/"runtime/task13_f1_r4",
                            RAW=root/"runtime/task13_f1_r4/raw",
                            __file__=str(root/"experiments/task13_f1_r4/replay.py")):
            dates, prices, raw_actions, _ = r4.inputs()
            bm = r4.dates_csv(r4.R3/"benchmark_nav.csv").loc[dates]
            scheduled = set(r4.indices(r4.R3/"decision_dates.csv"))
    nav4 = csv(checked(R4/"T1_A_nav.csv",manifest["runtime/task13_f1_r4/T1_A_nav.csv"]))
    nav4["positions"] = nav4.positions_json
    nav4["decision"] = nav4.index.isin(scheduled)
    nav4["names"] = nav4.number_held
    targets4 = csv(checked(R2/"T1_A_targets.csv", read(R2/"artifact_manifest.json")["runtime/task13_f1_r2/T1_A_targets.csv"]))
    nav4["targets"] = targets4.target_weights_json
    f4 = csv(raw[key])
    check(bm.index.equals(nav4.index), "R4 benchmark calendar")
    bm4 = pd.DataFrame(dict(ETF=bm.KODEX200_NOMINAL_COST/1e7,KOSPI=bm.KOSPI/1e7,MIX=bm.MIX_35_25/1e7))
    actions4 = {s:{d:spec["ratio"] for d,spec in ds.items()} for s,ds in raw_actions.items()}
    x4 = pd.read_pickle(io.BytesIO(checked(R2/"inputs.pkl", read(R2/"artifact_manifest.json")["runtime/task13_f1_r2/inputs.pkl"])))

    m5 = read(R5/"artifact_manifest.json")
    def file5(name):
        return checked(R5/name,m5[f"runtime/task13_f1_r5/{name}"])
    bundle = pd.read_pickle(io.BytesIO(file5("sealed_inputs.pkl")))
    nav5 = csv(file5("nav.csv"))
    f5 = csv(file5("fills.csv"))
    bench5 = csv(file5("benchmarks.csv")).loc[nav5.index]
    bm5 = bench5.rename(columns={"KODEX200":"ETF","MIX_35_25":"MIX"})[["ETF","KOSPI","MIX"]]
    actions5={s:dict.fromkeys(events) for s,events in bundle["actions"].items()}
    return {
        "R4":(nav4,f4,prices,actions4,bm4,1e7,b0,x4),
        "R5":(nav5,f5,{s:t for s,t in bundle["nominal"].items() if s in bundle["assets"]},
              actions5,bm5,bundle["carry"]["nav"],b0,None),
    }


def adjust(qty, actions, day):
    holdings = qty.copy()
    for symbol, shares in holdings.items():
        action = actions.get(symbol,{})
        if day in action:
            ratio = action[day]
            check(ratio is not None and (shares*ratio).is_integer(), f"Unsettled holding {symbol} {day}")
            holdings[symbol] = int(shares*ratio)
    return holdings


def mark(positions, price, day):
    value = 0.
    for asset, shares in positions.items():
        px = price.at[day,asset]
        check(np.isfinite(px) and px>0,f"Missing mark {asset} {day}")
        value += shares*px
    return value


def market_attribution(nav,fills,close,actions,bm,capital):
    """Telescoping difference against ETF, state frozen before each day's returns."""
    actual=nav.nav.div(nav.nav.shift(fill_value=capital))-1
    index=bm.div(bm.shift(fill_value=1))-1
    previous=nav.nav.shift(fill_value=capital)
    prev_weight=nav.equity.shift(fill_value=0)
    prior_gate=nav.risk_on.shift(fill_value=True)
    prior_target=nav.targets.map(lambda payload:sum(json.loads(payload).values())).shift(fill_value=0.)
    dayfills={d:g for d,g in fills.groupby(level=0)}
    book, records = {}, []
    old_cash=capital
    for day,i in zip(nav.index,range(len(nav))):
        holdings=adjust(book,actions,day)
        pnl_hold=(mark(holdings,close,day)-mark(book,close,nav.index[i-1])) if book else 0.
        pnl_trade=cost=0.
        cash=old_cash
        for order in dayfills.get(day,fills.iloc[:0]).itertuples():
            direction=1 if order.side=="BUY" else -1
            pnl_trade += direction*order.quantity*(close.at[day,order.symbol]-order.reference_open)
            cost += order.fee + direction*order.quantity*(order.fill_price-order.reference_open)
            cash -= direction*order.quantity*order.fill_price+order.fee
            holdings[order.symbol]=holdings.get(order.symbol,0)+int(direction*order.quantity)
        holdings={s:q for s,q in holdings.items() if q}
        check(holdings==json.loads(nav.at[day,"positions"]),f"Position mismatch {day}")
        check(abs(cash-nav.at[day,"cash"])<.0001,f"Cash mismatch {day}")
        check(abs(previous[day]*actual[day] - pnl_hold - pnl_trade + cost)<.0001,f"PnL mismatch {day}")
        drift=-(1-prev_weight[day])*index.at[day,"ETF"]
        average_index=prev_weight[day]*index.at[day,"ETF"]
        records.append(dict(date=day, net=actual[day], etf=index.at[day,"ETF"], matched_etf=average_index,
                            match_mix=prev_weight[day]*index.at[day,"MIX"], prior_exposure=prev_weight[day],
                            gate_off_cash=drift if not prior_gate[day] else 0.,
                            gate_on_cash=drift if prior_gate[day] else 0.,
                            on_reserve=-(1-.8)*index.at[day,"ETF"] if prior_gate[day] else 0.,
                            on_empty_target_slots=-(.8-prior_target[day])*index.at[day,"ETF"] if prior_gate[day] else 0.,
                            on_net_target_gap=-(prior_target[day]-prev_weight[day])*index.at[day,"ETF"] if prior_gate[day] else 0.,
                            prior_holdings_relative=pnl_hold/previous[day]-average_index,
                            fills_timing=pnl_trade/previous[day], friction=-cost/previous[day]))
        old_cash=cash
        book=holdings
    by_day=pd.DataFrame(records).set_index("date")
    weights=previous*(bm.ETF.iloc[-1]/bm.ETF)
    columns=["gate_off_cash","gate_on_cash","prior_holdings_relative","fills_timing","friction"]
    cash_columns=["on_reserve","on_empty_target_slots","on_net_target_gap"]
    check(np.allclose(by_day[cash_columns].sum(axis=1),by_day.gate_on_cash,atol=1e-12),
          "Gate-on cash subledger")
    linked=by_day[columns].multiply(weights,axis=0)
    error=float(nav.nav.iloc[-1]-capital*bm.ETF.iloc[-1]-linked.to_numpy().sum())
    check(abs(error)<.001,"Terminal benchmark attribution residual")
    return by_day,linked,error


def simple_hold(nav,fills,close,actions,capital):
    """Fixed shares from the first actually filled basket over observable holding life."""
    start=fills.index[0]
    first=fills.loc[[start]]
    check(first.side.eq("BUY").all(),"Unexpected first transaction")
    positions=first.groupby("symbol").quantity.sum().astype(int).to_dict()
    cash=capital-float((first.quantity*first.fill_price+first.fee).sum())
    levels=pd.Series(capital,index=nav.index,dtype=float)
    unresolved=None
    for d in nav.loc[start:].index:
        try:
            positions=adjust(positions,actions,d)
            levels[d]=cash+mark(positions,close,d)
        except ValueError as error:
            levels.loc[d:]=np.nan
            unresolved=str(error)
            break
    return levels, unresolved


def regime_tables(nav,bm,market,book,hold,capital):
    series=pd.DataFrame({"policy":nav.nav/capital,"ETF":bm.ETF,"same_mean_exposure":
                        (1+book.etf*nav.equity.mean()).cumprod(),"same_initial_names":hold/capital})
    daily=series.div(series.shift(fill_value=1))-1
    old=regimes(market).AS_OF_REGIME.shift(1).reindex(nav.index)
    # Fixed calendar buckets and Task12 thresholds. Retrospective labels are used only for attribution.
    groups={}
    for month,g in book.groupby(book.index.to_period("M")):
        returns=g.etf
        total=(1+returns).prod()-1
        crash=(1+returns).rolling(5).apply(np.prod,raw=True).min()-1
        compounded=(1+returns).cumprod()
        dips=(1+returns).rolling(5).apply(np.prod,raw=True)-1
        breach=dips.index[dips.le(-.10)]
        aftermath=compounded.loc[breach[0]:] if len(breach) else compounded.iloc[0:0]
        rebound=(aftermath/aftermath.cummin()-1).max()
        if crash<=-.10:
            category="CRASH_OR_REBOUND" if rebound>=.08 else "CRASH"
        elif total>=.10:
            category="STRONG_UP"
        elif total>=.05:
            category="GRADUAL_UP"
        elif total>-.05:
            category="SIDEWAYS"
        else:
            category="DOWN"
        groups.update(dict.fromkeys(g.index,category))
    classification=pd.Series(groups).reindex(nav.index)
    output={}
    for k, dates in classification.groupby(classification).groups.items():
        d=daily.loc[dates]
        a=book.loc[dates]
        selected=dates[a.etf.gt(0)]
        ret={name:float((1+d[name]).prod()-1)*100 if d[name].notna().all() else None for name in d}
        positive_base=float(a.loc[selected,"etf"].sum())
        output[k]=dict(days=len(dates),months=len(dates.to_period("M").unique()),returns_pct=ret,
                     mean_exposure_pct=100*nav.loc[dates,"equity"].mean(),
                     prior_risk_off_days=int((~nav.risk_on.shift(fill_value=True).loc[dates]).sum()),
                     capture_on_ETF_positive_days=float(a.loc[selected,"net"].sum()/positive_base) if positive_base>0 else None)
    return output,dict(Counter(old.fillna("WARMUP"))),classification,series


def exit_and_reentry(nav,fills,close,actions,bm):
    """Sell marks fixed to at most five sessions. Account cash gaps shown separately."""
    indices=nav.index
    positions=nav.positions.map(json.loads)
    exits=[]
    for j,day in enumerate(indices):
        older=positions.iloc[j-1] if j else {}
        for s in older.keys()-positions.at[day].keys():
            sell=fills.loc[(fills.index==day)&fills.symbol.eq(s)&fills.side.eq("SELL")]
            if sell.empty:
                continue
            cap=indices[j:min(j+5,len(indices))]
            future=next((k for k in cap[1:] if s in positions.at[k]),None)
            end=cap[-1] if future is None else cap[cap<future][-1]
            # An event whose incomplete window hits the sample edge is right-censored.
            if len(cap)<5 and future is None:
                continue
            try:
                q=int(sell.quantity.sum())
                book={s:q}
                for d in indices[(indices>day)&(indices<=end)]:
                    book=adjust(book,actions,d)
                compare=mark(book,close,end)
            except ValueError:
                continue
            reference=float((sell.quantity*sell.reference_open).sum())
            exits.append(dict(date=str(day.date()),end=str(end.date()),symbol=s,risk_off=not bool(nav.at[day,"risk_on"]),
                              shares=q,hold_minus_sell_open_krw=compare-reference,
                              hold_minus_net_sale_krw=compare-float((sell.quantity*sell.fill_price-sell.fee).sum())))
    episodes=[]
    for j,day in enumerate(indices[1:],start=1):
        if not (nav.names.iloc[j-1]>0 and nav.names.iloc[j]==0 and not nav.risk_on.iloc[j]):
            continue
        finish=next((i for i in range(j+1,len(indices)) if nav.names.iloc[i]>0),len(indices))
        on=next((i for i in range(j+1,finish+1) if i<len(indices) and nav.risk_on.iloc[i]),None)
        ready=next((i for i in range(on,finish+1) if i<len(indices) and nav.risk_on.iloc[i] and
                    nav.decision.iloc[i] and json.loads(nav.targets.iloc[i])),None) if on is not None else None
        off_frame=nav.iloc[j+1:(on if on is not None else finish)]
        dormant=nav.iloc[on:finish] if on is not None else nav.iloc[0:0]
        reentry=indices[finish] if finish<len(indices) else None
        def gap(frame):
            h=bm.ETF.div(bm.ETF.shift(fill_value=1)).loc[frame.index]
            return float((h.prod()-1)*100)
        episodes.append(dict(exit=str(day.date()),gate_on=str(indices[on].date()) if on is not None else None,
                             first_nonempty_target=str(indices[ready].date()) if ready is not None else None,
                             first_rebuy=str(reentry.date()) if reentry is not None else None,
                             sessions_gate_off_flat=len(off_frame),sessions_open_gate_flat=len(dormant),
                             gate_to_target_sessions=ready-on if ready is not None else None,
                             target_to_fill_sessions=finish-ready if ready is not None and reentry is not None else None,
                             gate_off_etf_pct=gap(off_frame),gate_on_flat_etf_pct=gap(dormant),
                             gate_off_etf_gap_krw=nav.at[day,"nav"]*gap(off_frame)/100,
                             gate_on_flat_etf_gap_krw=nav.at[day,"nav"]*gap(dormant)/100))
    return exits,episodes


def missed_leaders(nav,close,opening,actions,prices,ranks):
    """Ex-post top realised issue per non-overlapping scheduled decision interval."""
    dates=list(nav.index[nav.decision&nav.risk_on])
    positions=nav.positions.map(json.loads)
    rows=[]
    scheduled = list(nav.index[nav.decision])
    for day in dates:
        j=nav.index.get_loc(day)
        if j+5>=len(nav) or not nav.risk_on.iloc[j:j+5].all():
            continue
        end=nav.index[j+4]
        if any(day<other<=end for other in scheduled):
            continue
        available=[]
        for s in close:
            if any(day<=ek<=end for ek in actions.get(s,{})):
                continue
            series=prices[s].loc[day:end]
            if ("listing_eligible" in series and not series.listing_eligible.all()) or not (series.volume.gt(0).all() and series.close.gt(0).all()):
                continue
            if opening.at[day,s]>0:
                available.append((close.at[end,s]/opening.at[day,s]-1,s))
        if not available:
            continue
        value,s=max(available)
        picks=json.loads(nav.at[day,"targets"])
        reason="held" if s in positions.at[day] else ("selected_no_position" if s in picks else "not_selected_rank_unknown")
        if ranks is not None and reason.endswith("rank_unknown"):
            mom=ranks["prior"]["MOM63"].at[day,s]
            valid=pd.notna(ranks["flow"][1].at[day,s])
            if pd.isna(mom):
                reason="signal_missing"
            elif mom<=0:
                reason="momentum_nonpositive"
            elif not valid:
                reason="flow_availability_mask"
            else:
                reason="eligible_below_cutoff"
        rows.append(dict(date=str(day.date()),end=str(end.date()),symbol=s,
                         hindsight_open_close_pct=value*100,reason=reason))
    return rows


def overall(series):
    result={}
    for name, v in series.items():
        use=v.dropna()
        values=np.r_[1.,use.to_numpy()]
        result[name]=dict(final_pct=100*(values[-1]-1),days=len(use),
                          mdd_pct=100*float(np.min(values/np.maximum.accumulate(values)-1)))
    return result


def main():
    results={"audit_code_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    for name,(nav,fills,prices,actions,bm,capital,market,ranks) in inputs().items():
        close=pd.DataFrame({s:p.close for s,p in prices.items()})
        opening=pd.DataFrame({s:p.open for s,p in prices.items()})
        b,l,err=market_attribution(nav,fills,close,actions,bm,capital)
        hold,censor=simple_hold(nav,fills,close,actions,capital)
        by_regime,asof,classification,series=regime_tables(nav,bm,market,b,hold,capital)
        ex,ri=exit_and_reentry(nav,fills,close,actions,bm)
        leaders=missed_leaders(nav,close,opening,actions,prices,ranks)
        # Totals are strictly additive only within the ETF attribution bridge.
        attributed={k:float(v) for k,v in l.sum().items()}
        link_weights=nav.nav.shift(fill_value=capital)*(bm.ETF.iloc[-1]/bm.ETF)
        cash_split=b[["on_reserve","on_empty_target_slots","on_net_target_gap"]].multiply(link_weights,axis=0)
        results[name]=dict(capital=capital,regimes=by_regime,asof_counts=asof,
          comparators=overall(series), static_hold_censor=censor,
          arithmetic_cash_drag_up_krw=float((-b.loc[b.etf.gt(0),["gate_off_cash","gate_on_cash"]].sum(axis=1)*
                                            nav.nav.shift(fill_value=capital)).sum()),
          exposure_matched_mixed_pct=float(100*((1+b.match_mix).prod()-1)),
          exposure_matched_etf_pct=float(100*((1+b.matched_etf).prod()-1)),
          linked_ETF_gap_krw=attributed, linked_residual_krw=err,
          linked_ON_cash_only_breakdown_krw=cash_split.sum().to_dict(),
          regime_ON_cash_only_breakdown_krw=cash_split.groupby(classification).sum().to_dict("index"),
          regime_linked_gap_krw=l.groupby(classification).sum().to_dict("index"),
          exit_summary=pd.DataFrame(ex).groupby("risk_off").hold_minus_sell_open_krw.agg(
              ["count","sum",lambda s:s[s.gt(0)].sum(),lambda s:-s[s.lt(0)].sum()]).to_dict("index"),
          leaders_count=dict(Counter(r["reason"] for r in leaders)),
          reentry=ri)
        b.assign(ex_post_regime=classification).join(l.add_prefix("linked_")).to_csv(OUT/f"{name}_daily.csv")
        pd.DataFrame(ex).to_csv(OUT/f"{name}_exits.csv",index=False)
        pd.DataFrame(ri).to_csv(OUT/f"{name}_reentries.csv",index=False)
        pd.DataFrame(leaders).to_csv(OUT/f"{name}_leaders.csv",index=False)
    print(json.dumps(results,indent=2,allow_nan=False,default=lambda x:x.item()))


if __name__ == "__main__":
    main()
