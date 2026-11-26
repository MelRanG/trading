"""One reserved 2026 account continuation and two predeclared stress-cost paths."""
import json
from collections import Counter, defaultdict
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from experiments.research_references import sealed
from experiments.task13_f1_r4.execution import Account, trade_open
from experiments.task13_f1_r4.replay import ROOT, load, save, sha
from experiments.task13_f1_r5.preflight import OUT, ANCHOR, session_flags
from quant_harness.v77_corrected_price_allocation.engine import ExecutionSpec, _buy_fill_terms


def spec():
    costs = load(ROOT / 'config/task3_equity_contract.json')['execution_assumptions']
    minimum = 10_000_000 * costs.pop('minimum_order_nav_fraction')
    return ExecutionSpec(**costs,minimum_order_notional_krw=minimum)


def market_data(inputs):
    idx = inputs['index']
    opening_gaps, halt_proxies = {}, {}
    for board, frame in idx.items():
        opening_gaps[board], halt_proxies[board] = session_flags(frame)
    stress = pd.DataFrame(opening_gaps).le(-.03).any(axis=1)
    return pd.DataFrame(halt_proxies), stress


def run(inputs, costs, shock, name):
    nominal = {s:f for s,f in inputs['nominal'].items() if s in inputs['assets']}
    adv = {s:(f.close*f.volume).rolling(20,min_periods=20).mean().shift() for s,f in nominal.items()}
    targets = inputs['targets']
    carry = inputs['carry']
    halt, stress = market_data(inputs)
    account = Account(carry['cash'], carry['positions'].copy(),carry['pending'].copy())
    mark = {s:float(nominal[s].loc[ANCHOR,'close']) for s in account.positions}
    prior_date = ANCHOR
    fills, events, ledger = [], [], []
    gain = defaultdict(float)
    for d, row in targets.iterrows():
        start, pending_before, cash_start = account.positions.copy(), account.pending_sells.copy(), account.cash
        previous = {s:f.loc[prior_date,'close'] for s,f in nominal.items()}
        opens, ends, blockers, close_references = {}, {}, {}, []
        for s, f in nominal.items():
            bar = f.loc[d]
            since = inputs['actions'][s].get(d)
            if since and s in start:
                save(OUT/f'{name}_corporate_block.json',dict(date=str(d.date()),symbol=s,
                     flag=since,holdings=start,pending=pending_before))
                raise ValueError(f'Unsettled noncash corporate action: {d.date()} {s} {since}')
            board = inputs['assets'][s]['board']
            ends[s] = float(bar.close)
            if bar.volume == 0:
                close_references.append(s)
            if since:
                blockers[s] = 'NONCASH_ACTION_UNRESOLVED'
            elif not np.isfinite(bar.open) or not bar.volume > 0:
                blockers[s] = 'NO_TRADABLE_NOMINAL_OPEN'
            elif halt.loc[d,board]:
                blockers[s] = 'FILL_UNCERTAIN_BOARD_LOW_POSSIBLE_HALT'
            elif previous[s] > 0 and abs(bar.open / previous[s] - 1) >= .29:
                blockers[s] = 'FILL_UNCERTAIN_EXTREME_OPEN'
            opens[s] = None if s in blockers else float(bar.open)
        risk = bool(row.risk_on)
        # Marks at the sourced opening are indicative on sessions where the actual fill was withheld.
        if all(nominal[s].loc[d,'volume'] > 0 and nominal[s].loc[d,'open'] > 0 for s in start):
            opening = cash_start + sum(q*nominal[s].loc[d,'open'] for s,q in start.items())
        else:
            opening = None
        day_costs = replace(costs,half_spread_bps=costs.half_spread_bps+shock) if shock and stress.loc[d] else costs
        tx, es, pretrade_exposure = trade_open(account,row.targets,previous,opens,
                  {s:float(v.loc[d]) for s,v in adv.items()},day_costs,
                  rebalance=bool(row.decision),risk_on=risk)
        independent_cash, independent_lots = cash_start, start.copy()
        for t in tx:
            s = t['symbol']
            qty = int(t['quantity'])
            direction = 1 if t['side']=='BUY' else -1
            independent_cash -= direction*qty*t['fill_price'] + t['fee']
            independent_lots[s] = independent_lots.get(s,0) + direction*qty
            if independent_lots[s] == 0:
                del independent_lots[s]
            if direction > 0:
                stock = sum(q*opens[k] for k,q in independent_lots.items())
                assert risk and stock <= .8*(stock+independent_cash)+1e-6
                assert independent_lots[s]*opens[s] <= .2*(stock+independent_cash)+1e-6
            fills.append(dict(date=d,**t))
        assert abs(independent_cash-account.cash)<1e-6 and independent_lots==account.positions
        assert len(account.positions)<=4 and account.cash>=-1e-6
        for s in set(start)|set(account.positions):
            if not np.isfinite(ends[s]) or ends[s] <= 0:
                raise ValueError(f'missing held nominal close {s} {d.date()}')
        for s,q in start.items():
            gain[s] += q*(ends[s]-mark[s])
        for t in tx:
            s = t['symbol']
            direction = 1 if t['side']=='BUY' else -1
            gain[s] += direction*t['quantity']*(ends[s]-t['fill_price'])-t['fee']
        mark = {s:ends[s] for s in account.positions}
        stock = sum(q*mark[s] for s,q in account.positions.items())
        nav = account.cash+stock
        assert np.isfinite(nav) and nav>0 and abs(nav-(carry['nav']+sum(gain.values()))) < 1e-4
        ledger.append(dict(date=d, nav=nav, cash=account.cash,equity=stock/nav, names=len(account.positions),
                           opening_nav=opening, pretrade_exposure=pretrade_exposure,
                           risk_on=risk, decision=bool(row.decision), candidates=int(row.candidates),
                           targets=json.dumps(row.targets), positions=json.dumps(account.positions),
                           start_positions=json.dumps(start), start_cash=cash_start,
                           pending_before=json.dumps(pending_before), pending_after=json.dumps(account.pending_sells),
                           zero_volume_marks=json.dumps(sorted(set(close_references)&set(account.positions))),
                           blocked_boards=json.dumps(halt.columns[halt.loc[d]].tolist()),
                           stress_open=bool(stress.loc[d]), shock_bps=shock if stress.loc[d] else 0))
        for event in es:
            symbol = event.get('symbol')
            events.append(dict(date=d,**event,detail=blockers.get(symbol,'R4_LIQUIDITY_OR_RISK_CONSTRAINT')))
        prior_date = d
    return pd.DataFrame(ledger).set_index('date'),pd.DataFrame(fills),pd.DataFrame(events),dict(gain)


def metrics(series, equity=None):
    daily = series.pct_change(fill_method=None).dropna()
    total = series.iloc[-1]/series.iloc[0]-1
    years = (series.index[-1]-series.index[0]).days/365.2425
    vol = daily.std(ddof=1)
    return dict(total_pct=100*total,cagr_pct=100*((1+total)**(1/years)-1),
                mdd_pct=100*(series/series.cummax()-1).min(),
                annual_vol_pct=100*np.sqrt(252)*vol,
                sharpe_rf0=np.sqrt(252)*daily.mean()/vol if vol>0 else None,
                avg_equity_pct=100*equity.mean() if equity is not None else None)


def benchmarks(inputs, nav, costs):
    idx = inputs['index']
    out = pd.DataFrame({k:f.close/f.close.loc[ANCHOR] for k,f in idx.items()})
    out['MIX_35_25'] = (out.KOSPI*35+out.KOSDAQ*25)/60
    stock_exp = pd.concat([pd.Series([1-inputs['carry']['cash']/inputs['carry']['nav']],index=[ANCHOR]),nav.equity])
    out['MIX_LAGGED_EXPOSURE'] = (1+out.MIX_35_25.pct_change().fillna(0)*stock_exp.shift().fillna(0)).cumprod()
    out['CASH'] = 1.
    etf = inputs['nominal']['069500.KS']
    capital = inputs['carry']['nav']
    start = nav.index[0]
    p = float(etf.loc[start,'open'])
    adv = (etf.close*etf.volume).rolling(20).mean().shift().loc[start]
    adv = float(adv)
    limit = min(int(capital/p),int(adv*costs.max_participation_of_d1_adv/p))
    quantity, _, price, fee, _ = _buy_fill_terms(cash=capital,max_quantity=limit,raw_open=p,adv=adv,spec=costs)
    assert quantity>0 and price is not None
    cash = capital-quantity*price-fee
    assert cash>=-1e-6
    etf_nav = quantity*etf.loc[nav.index,'close']+cash
    out['KODEX200'] = pd.concat([pd.Series([capital],index=[ANCHOR]),etf_nav])/capital
    out['MOM63'] = pd.concat([pd.Series([capital],index=[ANCHOR]),nav.nav])/capital
    weights = {'MOM63':nav.equity,'MIX_LAGGED_EXPOSURE':stock_exp.shift().loc[nav.index],
               'KODEX200':1-cash/etf_nav,'CASH':pd.Series(0.,index=nav.index)}
    stats = {k:metrics(out[k],weights.get(k,pd.Series(1.,index=nav.index))) for k in out}
    return out,stats,dict(quantity=quantity,cash=cash,entry_price=price,fee=fee,date=str(start.date()))


def periods(drawdown, threshold):
    result=[]
    episode=None
    peak=drawdown.index[0]
    for day,val in drawdown.items():
        if val>=0:
            if episode is not None:
                result.append({**episode,'recovered':str(day.date())})
                episode=None
            peak=day
        elif val <= threshold and episode is None:
            episode=dict(peak=str(peak.date()),crossing=str(day.date()),trough=str(day.date()),pct=100*val)
        elif episode is not None and 100*val<episode['pct']:
            episode.update(trough=str(day.date()),pct=100*val)
    if episode is not None:
        result.append({**episode,'recovered':None})
    return result


def stress_analysis(inputs, nav, events, marks):
    kospi=marks.KOSPI
    ret=kospi.pct_change()
    gate=nav.risk_on
    date_list=nav.index
    events=events.copy()
    diag=[]
    for d in ret.index[ret.le(-.05)]:
        i=date_list.get_loc(d)
        day=nav.loc[d]
        before=date_list[i-1] if i else ANCHOR
        prior_decision=nav.loc[:before].query('decision').tail(1)
        off=nav.loc[d:].index[~gate.loc[d:]]
        off0=off[0] if len(off) else None
        exit_date=None
        if off0 is not None:
            next_on=nav.loc[off0:].index[gate.loc[off0:]]
            liquidation_window=nav.loc[off0:next_on[0]] if len(next_on) else nav.loc[off0:]
            flat=liquidation_window.index[liquidation_window.names.eq(0)]
            exit_date=flat[0] if len(flat) else None
        expiry=nav.loc[d:].index[nav.loc[d:].names.gt(0)] if exit_date is None else nav.loc[exit_date:].index[nav.loc[exit_date:].names.gt(0)]
        recovered=marks.loc[d:].index[marks.MOM63.loc[d:].ge(marks.MOM63.loc[before])]
        residual=events.loc[(events.date==d)&(events.reason=='SELL_REMAINDER')].to_dict('records')
        for er in residual:
            er['date']=str(er['date'].date())
        diag.append(dict(date=str(d.date()),kospi_pct=100*ret[d],
                         account_pct=100*(marks.MOM63[d]/marks.MOM63[before]-1),
                         prior_equity_pct=100*(1-day.start_cash/(marks.MOM63[before]*inputs['carry']['nav'])),
                         prior_decision=str(prior_decision.index[0].date()) if len(prior_decision) else None,
                         previous_selected=json.loads(prior_decision.targets.iloc[0]) if len(prior_decision) else inputs['carry']['targets'],
                         previous_cash=day.start_cash, previous_positions=json.loads(day.start_positions),
                         opening_gap_pct=100*(day.opening_nav/(marks.MOM63[before]*inputs['carry']['nav'])-1)
                         if pd.notna(day.opening_nav) else None,
                         risk_on_open=bool(gate[d]), risk_off_next_open=bool(not gate.iloc[i+1]) if i+1<len(gate) else None,
                         pending_exit_targets_at_close=json.loads(day.pending_after),
                         unfilled_requested_shares=residual, potential_halt_boards=json.loads(day.blocked_boards),
                         next_off=str(off0.date()) if off0 is not None else None,
                         first_risk_off_flat=str(exit_date.date()) if exit_date is not None else None,
                         sessions_off_to_flat=date_list.get_loc(exit_date)-date_list.get_loc(off0) if exit_date is not None else None,
                         first_reentry=str(expiry[0].date()) if len(expiry) and exit_date is not None else None,
                         recovers_pre_event_nav=str(recovered[0].date()) if len(recovered) else None))
    windows={}
    for name,(a,b) in load(OUT/'contract.json')['stress_windows'].items():
        window=marks.loc[a:b]
        anchor=marks.index[marks.index<window.index[0]][-1]
        linked=marks.loc[anchor:window.index[-1]]
        before=marks.loc[anchor]
        account=linked.MOM63
        index=linked.KOSPI
        trough=index.idxmin()
        peak=index.loc[:trough].idxmax()
        account_trough=account.idxmin()
        ref_high=marks.MOM63.loc[:anchor].max()
        peak_date=marks.MOM63.loc[:anchor].idxmax()
        recovery=marks.loc[account_trough:].index[marks.MOM63.loc[account_trough:].ge(ref_high)]
        real=nav.loc[window.index]
        off=real.index[~real.risk_on]
        switches=real.index[real.risk_on.ne(nav.risk_on.shift().reindex(real.index))]
        out=100*(window.iloc[-1]/before-1)
        crash=next((row for row in diag if a<=row['date']<=b),None)
        first=pd.Timestamp(crash['date']) if crash else None
        extra=(100*(account.loc[first:].min()/account.loc[first]-1)) if first is not None else None
        exits=[str(d.date()) for d in real.index[real.names.eq(0)&nav.names.shift(fill_value=0).reindex(real.index).gt(0)]]
        entries=[str(d.date()) for d in real.index[real.names.gt(0)&nav.names.shift(fill_value=0).reindex(real.index).eq(0)]]
        windows[name]=dict(start=str(window.index[0].date()),end=str(window.index[-1].date()),
                           return_pct=out.to_dict(), account_mdd_pct=metrics(account)['mdd_pct'],
                           index_mdd_pct=metrics(index)['mdd_pct'],
                           kospi_peak=str(peak.date()),kospi_trough=str(trough.date()),
                           account_low_date=str(account_trough.date()),account_low_from_anchor_pct=100*(account.min()/before.MOM63-1),
                           additional_loss_from_first_crash_close_pct=extra,
                           first_crash=crash['date'] if crash else None,
                           average_cash_pct=100*(1-real.equity.mean()), off_sessions=len(off),
                           risk_switches=[dict(date=str(d.date()),on=bool(real.risk_on[d])) for d in switches],
                           full_cash_dates=exits,reentry_dates=entries, prior_high_date=str(peak_date.date()),
                           recovered_prior_high=str(recovery[0].date()) if len(recovery) else None,
                           prior_high_recovery_sessions=(date_list.get_loc(recovery[0])-date_list.get_loc(peak_date))
                           if len(recovery) and peak_date in date_list and recovery[0] in date_list else None)
    dd=kospi/kospi.cummax()-1
    under=marks.MOM63/marks.MOM63.cummax()-1
    minimum=under.idxmin()
    account_peak=marks.MOM63.loc[:minimum].idxmax()
    account_recovery=marks.loc[minimum:].index[marks.MOM63.loc[minimum:].ge(marks.MOM63.loc[account_peak])]
    return dict(windows=windows, crash_days=diag,kospi_minus10=periods(dd,-.1),kospi_minus20=periods(dd,-.2),
                account_mdd_dates={'peak':str(account_peak.date()),'trough':str(minimum.date()),
                                   'recovery':str(account_recovery[0].date()) if len(account_recovery) else None})


def pit_summary(inputs, contribution):
    snapshot=pd.read_csv(OUT/'roster_snapshots.csv',dtype={'date':str,'code':str})
    result={}
    current={s[:6]:s for s in inputs['assets']}
    for d,g in snapshot.groupby('date'):
        if not g.code.is_unique:
            raise ValueError('overlapping exchange rosters')
        m=g.set_index('code')
        retained=m.loc[m.index.intersection(current)]
        eligible=m[m.cap.ge(500_000_000_000)&m.volume.gt(0)]
        result[d]=dict(roster=len(m),present=len(retained),
                       missing=sorted(set(current)-set(retained.index)),
                       present_below_500bn=sorted(retained.index[retained.cap.lt(500_000_000_000)]),
                       present_zero_volume=sorted(retained.index[retained.volume.eq(0)]),
                       board_change=sorted(c for c,r in retained.iterrows() if r.board!=inputs['assets'][current[c]]['board']),
                       cap_volume_pool=len(eligible),noncohort_cap_volume_pool=len(set(eligible.index)-set(current)),
                       name_difference=[dict(code=c, historical=r['name'], current=inputs['assets'][current[c]]['name'])
                                        for c,r in retained.iterrows() if r['name'].strip()!=inputs['assets'][current[c]]['name'].strip()])
    cohorts={d:set(g.code) for d,g in snapshot.groupby('date')}
    prior=set(contribution)
    result['2025_to_2026_absent_codes'] = len(cohorts['20251230']-cohorts['20261118'])
    result['2025_to_2026_new_codes'] = len(cohorts['20261118']-cohorts['20251230'])
    result['non_prior_holdings_universe'] = len(set(inputs['assets'])-prior)
    return result


def main():
    if (OUT/'reservation.json').exists():
        raise FileExistsError('Existing R5 evaluation reservation')
    gate=load(OUT/'preflight.json')
    for p,h in gate['hashes'].items():
        sealed(ROOT,p,h)
    for p,h in gate['outputs'].items():
        assert sha(OUT/p)==h, p
    inputs=pd.read_pickle(OUT/'sealed_inputs.pkl')
    save(OUT/'reservation.json',dict(time=datetime.now(timezone.utc).isoformat(),
                                     preflight_sha256=sha(OUT/'preflight.json'), code_sha256=sha(Path(__file__)),
                                     primary=1,predeclared_cost_sensitivities=2))
    costs=spec()
    nav,fills,ev,gain=run(inputs,costs,0,'primary')
    nav.to_csv(OUT/'nav.csv')
    fills.to_csv(OUT/'fills.csv',index=False)
    ev.to_csv(OUT/'events.csv',index=False)
    data,stats,etf=benchmarks(inputs,nav,costs)
    data.to_csv(OUT/'benchmarks.csv')
    sensitivity={}
    for shock in [15,35]:
        account,tx,exc,_=run(inputs,costs,shock,f'cost_{shock}bp')
        path=pd.concat([pd.Series([inputs['carry']['nav']],index=[ANCHOR]),account.nav])
        sensitivity[shock]=dict(**metrics(path,account.equity),fill_count=len(tx),residual_events=int(exc.reason.eq('SELL_REMAINDER').sum()))
    charges=float((fills.quantity*(fills.fill_price-fills.reference_open).abs()+fills.fee).sum())
    days=fills.groupby('date').open_notional.sum().reindex(nav.index,fill_value=0)
    day_turnover=days/nav.nav.shift(fill_value=inputs['carry']['nav'])
    ordered=sorted(gain.items(),key=lambda item:-item[1])
    positive=sum(pnl for _,pnl in ordered if pnl>0)
    summary=dict(execution='EXECUTION_UNCERTAIN',history='EXPOSED_HISTORICAL_STRESS',
                 universe='SURVIVOR_BIASED',metrics=stats,
                 cost_sensitivity=sensitivity, net_alpha_gap_pp={k:stats['MOM63']['total_pct']-v['total_pct']
                 for k,v in stats.items() if k!='MOM63'},etf=etf,
                 stress=stress_analysis(inputs,nav,ev,data),universe_evidence=pit_summary(inputs,gain),
                 trade_stats={'max_positions':int(nav.names.max()),'fill_count':len(fills),'total_cost_krw':charges,
                              'total_turnover_multiple':day_turnover.sum(),'days_with_trade':int(day_turnover.gt(0).sum()),
                              'off_days':int((~nav.risk_on).sum()),'off_days_still_exposed':int((~nav.risk_on&nav.equity.gt(0)).sum()),
                              'residual_events':int(ev.reason.eq('SELL_REMAINDER').sum()),
                              'residual_reasons':dict(Counter(ev.loc[ev.reason.eq('SELL_REMAINDER'),'detail'])),
                              'residual_days':int(nav.pending_after.ne('{}').sum()),
                              'sell_fills':int(fills.side.eq('SELL').sum()),
                              'holding_name_count':len(gain)},
                 contribution={'top10':ordered[:10],'bottom10':ordered[-10:][::-1],
                 'positive_total_krw':positive,'positive_share_top':{n:sum(x[1] for x in ordered[:n] if x[1]>0)/positive
                 if positive>0 else None for n in [1,3,5]},
                 'monthly_pct':(100*data.MOM63.resample('ME').last().pct_change().dropna()).rename(index=lambda d:str(d.date())).to_dict()})
    save(OUT/'result.json',summary)


if __name__=='__main__':
    main()
