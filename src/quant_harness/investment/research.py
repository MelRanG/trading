"""Preregistered, common-execution historical screening. No parameter search."""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd
from quant_harness.v104_end_to_end_causal_challenger_audit import adapter


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str, allow_nan=False).encode()).hexdigest()


def contract(root):
    return json.loads((Path(root) / 'config/task3_research_contract.json').read_text())


def bounded(weights, cfg):
    if any(not np.isfinite(v) or v < 0 for v in weights.values()):
        raise ValueError('invalid target')
    gross = sum(weights.values())
    factor = min(1, cfg['gross_cap'] / gross) if gross else 1
    return {k: min(v * factor, cfg['single_name_cap']) for k, v in weights.items() if v > 0}


def candidate_ledgers(built, cfg):
    """Features are D-1. Future prices cannot affect a prior decision."""
    close = built['market']['close']
    gate = built['f69']['universe_gate']['gate']
    symbols = sorted(gate.columns)
    score = close[symbols].pct_change(cfg['momentum_sessions'], fill_method=None).shift(1)
    core = built['cfg77'].core_ticker
    trend = (close[core] > close[core].rolling(cfg['trend_sessions'], min_periods=cfg['trend_sessions']).mean()).shift(1, fill_value=False)
    momentum, defensive = [], []
    for day in close.index:
        eligible = score.loc[day].where(gate.loc[day] & score.loc[day].gt(0)).dropna()
        # Sorted symbols make ties deterministic; no ranking optimization.
        chosen = eligible.idxmax() if not eligible.empty else None
        momentum.append({'date': day, 'target_weights_json': json.dumps({chosen: cfg['gross_cap']} if chosen else {})})
        defensive.append({'date': day, 'target_weights_json': json.dumps({core: cfg['gross_cap']} if trend.loc[day] else {})})
    return {'MOM63_ROTATION': pd.DataFrame(momentum), 'DEFENSIVE_TREND120': pd.DataFrame(defensive)}


def metrics(account, orders, initial):
    nav = account.set_index('date').nav_krw
    path = pd.concat([pd.Series([initial], index=[nav.index[0] - pd.Timedelta(days=1)]), nav])
    ret = path.pct_change().dropna()
    costs = sum(float(orders[c].sum()) for c in ('fee_krw', 'half_spread_cost_krw', 'impact_cost_krw') if c in orders)
    turnover = float((orders.quantity * orders.reference_open_krw).sum()) if len(orders) else 0
    return {'return_pct': float((nav.iloc[-1] / initial - 1) * 100),
            'sharpe': float(ret.mean() / ret.std(ddof=0) * np.sqrt(252)) if ret.std(ddof=0) else 0,
            'mdd_pct': float((path / path.cummax() - 1).min() * 100),
            'turnover_multiple_initial': turnover / initial, 'cost_krw': costs, 'fills': len(orders)}


def run_comparison(root, directory):
    root, directory = Path(root), Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    cfg = contract(root)
    fingerprint = digest(cfg)
    prereg = directory / 'preregistration.json'
    if prereg.exists() and json.loads(prereg.read_text()) != cfg:
        raise ValueError('preregistration changed; use a new experiment')
    prereg.write_text(json.dumps(cfg, indent=2))
    specs = adapter.load_candidate_specs(root)
    built = adapter.build_candidate_ledgers(root, specs['V69_PARENT'])
    ledgers = candidate_ledgers(built, cfg)
    ledgers.update({k: adapter.build_candidate_ledgers(root, specs[k])['ledger'] for k in ('V69_PARENT', 'V79_PARENT')})
    market = built['market']
    dates = market['close'].index
    dates = dates[(dates >= cfg['period'][0]) & (dates <= cfg['period'][1])]
    if not len(dates):
        raise ValueError('no common dates')
    core = built['cfg77'].core_ticker
    for name, weight in [('ETF_BUY_HOLD', 1.0), ('ETF_RISK_MATCHED', cfg['gross_cap'])]:
        # One initial purchase, no daily rebalance for buy-hold below.
        ledgers[name] = pd.DataFrame({'date': dates, 'target_weights_json': [json.dumps({core: weight})] * len(dates)})
    common = {k: market[k].reindex(dates) for k in ('close', 'open', 'adv20_d1')}
    input_hash = digest({k: v.to_json(orient='split', date_format='iso') for k, v in market.items() if isinstance(v, pd.DataFrame)})
    results = {}
    paths = {}
    for name, ledger in ledgers.items():
        ledger = ledger.set_index('date').reindex(dates).reset_index()
        if ledger.target_weights_json.isna().any():
            raise ValueError('missing target sessions')
        if name not in ('ETF_BUY_HOLD', 'ETF_RISK_MATCHED'):
            ledger['target_weights_json'] = ledger.target_weights_json.map(lambda x: json.dumps(bounded(json.loads(x), cfg), sort_keys=True))
        for day, raw in zip(dates, ledger.target_weights_json):
            for symbol in json.loads(raw):
                if any(not np.isfinite(common[k].loc[day, symbol]) or common[k].loc[day, symbol] <= 0 for k in common):
                    raise ValueError(f'missing executable data: {day} {symbol}')
        account, orders, intents = replay_targets(market, dates, ledger, cfg['initial_capital'], built['cfg77'].base_execution,
                                                  buy_hold=name in ('ETF_BUY_HOLD', 'ETF_RISK_MATCHED'))
        account.to_csv(directory / f'{name}_nav.csv', index=False)
        orders.to_csv(directory / f'{name}_fills.csv', index=False)
        ledger.to_csv(directory / f'{name}_targets.csv', index=False)
        paths[name] = account.set_index('date').nav_krw
        result = metrics(account, orders, cfg['initial_capital'])
        stress_account, stress_orders, _ = replay_targets(market,dates,ledger,cfg['initial_capital'],built['cfg77'].stress_execution,buy_hold=name in ('ETF_BUY_HOLD','ETF_RISK_MATCHED'))
        result['stress'] = metrics(stress_account,stress_orders,cfg['initial_capital'])
        stress_account.to_csv(directory / f'{name}_stress_nav.csv',index=False)
        result['year_returns_pct'] = {}
        for year, group in account.groupby(account.date.dt.year):
            prior=account[account.date<group.date.iloc[0]]
            opening=float(prior.nav_krw.iloc[-1]) if len(prior) else cfg['initial_capital']
            result['year_returns_pct'][str(year)] = float((group.nav_krw.iloc[-1]/opening-1)*100)
        result['splits'] = {}
        for split, (start, end) in cfg['splits'].items():
            subset = account[(account.date >= start) & (account.date <= end)]
            prior = account[account.date < start]
            if len(subset):
                opening = float(prior.nav_krw.iloc[-1]) if len(prior) else cfg['initial_capital']
                result['splits'][split] = metrics(subset, orders[(orders.date >= start) & (orders.date <= end)] if len(orders) else orders, opening)
        regime = built['regime']['risk_on'].reindex(dates)
        returns = account.set_index('date').nav_krw.pct_change().fillna(account.nav_krw.iloc[0]/cfg['initial_capital']-1)
        result['regime_daily_mean_bps'] = {str(k): float(returns[regime.eq(k)].mean() * 10000) for k in (True, False)}
        result.update(input_hash=input_hash, candidate_fingerprint=digest({'contract': fingerprint, 'candidate': name}), status='HISTORICAL_SCREEN_ONLY')
        results[name] = result
    index = market['close'][built['cfg77'].benchmark_ticker]
    prior = index[index.index < dates[0]].dropna()
    benchmark = float((index.loc[dates[-1]] / prior.iloc[-1] - 1) * 100) if len(prior) else None
    for result in results.values():
        result['excess_kospi_pp'] = result['return_pct'] - benchmark if benchmark is not None else None
        result['excess_etf_pp'] = result['return_pct'] - results['ETF_BUY_HOLD']['return_pct']
    paired = {}
    bench_returns=paths['ETF_RISK_MATCHED'].pct_change().dropna()
    for name,path in paths.items():
        difference=path.pct_change().dropna()-bench_returns
        monthly=difference.groupby(difference.index.to_period('M')).sum().to_numpy()
        rng=np.random.default_rng(3013)
        samples=rng.choice(monthly,size=(1000,len(monthly)),replace=True).mean(axis=1)*12*100
        paired[name]={'annualized_mean_daily_excess_pp':float(difference.mean()*252*100),'monthly_block_bootstrap_95pct':np.quantile(samples,[0.025,0.975]).tolist(),'independent_oos':False}
    code_hash=digest({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__), root/'src/quant_harness/v77_corrected_price_allocation/engine.py',root/'src/quant_harness/v104_end_to_end_causal_challenger_audit/adapter.py']})
    report = {'code_hash':code_hash,'paired_vs_risk_matched_etf':paired,'contract_hash': fingerprint, 'input_hash': input_hash, 'start': str(dates[0].date()), 'end': str(dates[-1].date()),
              'sessions': len(dates), 'results': results, 'kospi_price_return_pct': benchmark,
              'limitations': [cfg['bias'], 'Adjusted ETF prices, dividend treatment follows source and is not independently verified; KOSPI price index excludes reinvested dividends.',
                 '80% cap is a target exposure, not a continuous intraday guarantee. Baseline signals are risk-normalized and differ from original strategy performance. Shared D-1 sizing changes the execution contract relative to legacy V101.',
                 'Long-only shared execution, D-1 features; ETF buy-hold full exposure differs from 80% risk-matched benchmark.',
                 'FinRL-inspired rules are not upstream engine replication. ai-hedge-fund/TradingAgents require PIT company inputs; Qlib model training deferred without untouched holdout. No efficacy claim or automatic exclusion.'],
              'selection': cfg['selection']}
    (directory / 'comparison.json').write_text(json.dumps(report, indent=2, allow_nan=False))
    return report


def replay_targets(market, dates, ledger, initial, spec, buy_hold=False, *, rebalance_dates=None, allow_unpriced_hold=False):
    """Shared D-1 sizing, next-open execution; supports uninvested cash.

    Reuses V77 fee/spread/impact and cash-cap arithmetic. V101 requires fully
    invested targets, so it cannot represent this registered cash strategy.
    """
    from quant_harness.v77_corrected_price_allocation import engine as v77
    cash, held, account, fills, intents = float(initial), {}, [], [], []
    previous = market['close'].shift(1)
    for i, day in enumerate(dates):
        targets = json.loads(ledger.iloc[i].target_weights_json)
        symbols = set(held) | set(targets)
        rebalance = (not buy_hold or i == 0) and (rebalance_dates is None or day in rebalance_dates)
        missing_previous = any(not np.isfinite(previous.loc[day,s]) or previous.loc[day,s] <= 0 for s in symbols)
        if missing_previous and (rebalance or rebalance_dates is None):
            if not allow_unpriced_hold:
                raise ValueError('missing D-1 sizing price')
            rebalance = False
            intents.append({'date':day,'symbol':'PORTFOLIO','reason':'HOLD_ONLY_MISSING_D1_MARK'})
        nav_d1 = cash + sum(q * previous.loc[day,s] for s,q in held.items() if q)
        desired = {s: int(nav_d1*w/previous.loc[day,s]) for s,w in targets.items()} if rebalance else {}
        for s in held:
            desired.setdefault(s,0)
        if rebalance:
            ordered = sorted(symbols, key=lambda s: (desired.get(s,0) >= held.get(s,0), s))
            for s in ordered:
                delta = desired.get(s,0)-held.get(s,0)
                if not delta:
                    continue
                raw, adv = float(market['open'].loc[day,s]), float(market['adv20_d1'].loc[day,s])
                if not np.isfinite(raw) or raw <= 0 or not np.isfinite(adv) or adv <= 0:
                    if allow_unpriced_hold:
                        intents.append({'date':day,'symbol':s,'reason':'HOLD_ONLY_MISSING_OPEN_OR_ADV','requested':abs(delta)})
                        continue
                    raise ValueError('missing executable open or D-1 ADV')
                side = 'BUY' if delta > 0 else 'SELL'
                qty = min(abs(delta), int(adv*spec.max_participation_of_d1_adv/raw))
                if qty*raw < spec.minimum_order_notional_krw:
                    intents.append({'date':day,'symbol':s,'reason':'MINIMUM_OR_PARTICIPATION','requested':abs(delta)})
                    continue
                impact = v77._impact_bps(qty*raw,adv,spec)
                if side == 'BUY':
                    qty,impact,px,fee,_ = v77._buy_fill_terms(cash=cash,max_quantity=qty,raw_open=raw,adv=adv,spec=spec)
                else:
                    px=raw*(1-(spec.half_spread_bps+impact)/10000)
                    fee=qty*px*spec.sell_fee_bps/10000
                if qty*raw < spec.minimum_order_notional_krw:
                    continue
                cash += -(qty*px+fee) if side=='BUY' else qty*px-fee
                held[s]=held.get(s,0)+(qty if side=='BUY' else -qty)
                fills.append({'date':day,'ticker':s,'side':side,'quantity':qty,'reference_open_krw':raw,'fill_price_krw':px,
                    'fee_krw':fee,'half_spread_cost_krw':qty*raw*spec.half_spread_bps/10000,'impact_cost_krw':qty*raw*impact/10000})
        if cash < -0.000001 or any(q < 0 for q in held.values()):
            raise ValueError('negative balance')
        missing_mark = any(not np.isfinite(market['close'].loc[day,s]) for s,q in held.items() if q)
        if missing_mark and not allow_unpriced_hold:
            raise ValueError('missing NAV mark')
        nav = float('nan') if missing_mark else cash+sum(q*market['close'].loc[day,s] for s,q in held.items() if q)
        record={'date':day,'nav_krw':nav,'cash_krw':cash,'holdings_json':json.dumps(held)}
        if allow_unpriced_hold:
            record['mark_status']='MISSING_MARK_HOLD_ONLY' if missing_mark else 'OBSERVED'
        account.append(record)
    return pd.DataFrame(account),pd.DataFrame(fills),pd.DataFrame(intents)
